#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
name_match.py — 旧システムの担当者名(文字列) → 新システム users.id の照合(再利用モジュール)

旧データの担当者名は手入力で、全角/半角(ｱｲﾝ/アイン、ＡＢ/AB)・空白(全角/半角/連続/有無)の
表記ゆれがあり、さらに1欄に複数名が書かれている(「井本　アイン」「徳富 中川」「ソン＋フォン」)。
users.name との完全一致だけでは担当者欄が空になるため、次の規則で照合する。

  正規化キー: NFKC(全角英数・半角カナ → 標準形) → 空白をすべて除去 → 大文字化
  1名の照合: ①完全一致 → ②正規化キー一致 → ③姓だけの記載で、その姓の利用者が1人だけの場合
  複数名の照合: 区切り文字(& ＆ 、 , ， ・ / ／ + ＋)で分割し、各部分を
                さらに空白区切りの語の並びとして、先頭から「最も長く一致する連続した語」を順に当てはめる
                (例: 「井本　昌成 アイン」→ 井本 昌成 / アイン)
  同じ正規化キーや同じ姓の利用者が複数いる場合は、系統(MC/NC)で1人に決まるときだけ結び付け、
  決まらなければ誤った人に結び付けないよう照合しない。
  旧の通称(LEGACY_ALIASES)は社員コードで結び付ける。

利用元: mc_full_import.py PHASE1/PHASE6、nc_full_import_v2.py PHASE1/PHASE3/PHASE4、
        verify_work_records.py、verify_user_fields_old_new.py
1人だけ入れる欄(オペレーター・承認者・作成者・PG作成者): resolve_first(複数名なら先頭に照合できた人)
users に無い旧担当者名は空欄のまま(管理者で代替しない: 2026-10-07 ユーザー指定)
"""
import re
import unicodedata

_SEP = re.compile(r"[&＆、,，・/／+＋]")
_WS = re.compile(r"[\s　]+")


# カタカナの後のハイフン類は長音「ー」の打ち間違い(例: 旧NCの「チュ-ン」= チューン)
_KANA_DASH = re.compile(r"(?<=[\u30A1-\u30FA\u30FC])[-‐‑‒–—―−－]")


def person_key(raw):
    """担当者名の正規化キー。空なら None"""
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", str(raw))
    s = _KANA_DASH.sub("ー", s)
    s = _WS.sub("", s).upper()
    return s or None


# 旧データの名前 → 社員コード(users.employee_code)。氏名だけでは一人に決まらない人を明示する
#   「チューン」: 通称。日長 陽介 / MC140 (ユーザー指定 2026-10-07)
#   「ティン」  : 同姓同名の別人が2人いる(STAFF030=旧システムからの利用者 / NC003=新システムで追加した利用者)。
#                 旧データに記録されている「ティン」は旧システムの利用者 STAFF030 (旧 ACC_Staff St_id=30)
LEGACY_ALIASES = {
    "チューン": "MC140",
    "ティン": "STAFF030",
}


class PersonResolver:
    """users から作る 旧担当者名 → users.id の照合器

    system: "MC" / "NC" を渡すと、同じ氏名の利用者が複数いる場合にその系統(または共通 BOTH)の
            利用者が1人だけならその人に結び付ける(例: MC と NC に同姓同名の「ティン」が別人でいる)。
            それでも決まらない氏名は誤った人に結び付けないよう照合しない(ambiguous に記録)。
    """

    def __init__(self, rows, system=None):
        """rows: [(id, name), ...] または [(id, name, employee_code, system_type, is_active), ...]"""
        self.system = system
        self.ambiguous = {}          # 一意に決まらなかった名前 → 候補の説明
        exact_c, key_c, sur_c = {}, {}, {}
        self._code = {}
        self._info = {}
        for r in rows:
            uid, name = r[0], r[1]
            code = r[2] if len(r) > 2 else None
            stype = str(r[3]) if len(r) > 3 and r[3] is not None else None
            self._info[uid] = (name, code, stype)
            if code:
                self._code[str(code).strip().upper()] = uid
            if not name:
                continue
            exact_c.setdefault(str(name).strip(), []).append(uid)
            k = person_key(name)
            if k:
                key_c.setdefault(k, []).append(uid)
            tokens = _WS.split(unicodedata.normalize("NFKC", str(name)).strip())
            if len(tokens) >= 2:
                sk = person_key(tokens[0])
                if sk and sk != k:
                    sur_c.setdefault(sk, []).append(uid)
        self.exact = {n: self._choose(n, c) for n, c in exact_c.items()}
        self.key = {k: self._choose(k, c) for k, c in key_c.items()}
        # 姓が誰かの氏名全体と同じ場合は氏名全体を優先(姓での救済はしない)
        self.surname = {k: self._choose(k, c, record=False) for k, c in sur_c.items() if k not in key_c}
        self.alias = {}
        for a, code in LEGACY_ALIASES.items():
            uid = self._code.get(code.upper())
            if uid is not None:
                self.alias[person_key(a)] = uid
        # 通称の表で決まる名前は「決まらない名前」から外す
        self.ambiguous = {n: v for n, v in self.ambiguous.items() if person_key(n) not in self.alias}

    def _choose(self, label, cands, record=True):
        cands = list(dict.fromkeys(cands))
        if len(cands) == 1:
            return cands[0]
        if self.system:
            pref = [u for u in cands if self._info.get(u, (None, None, None))[2] in (self.system, "BOTH")]
            if len(pref) == 1:
                return pref[0]
        if record:
            self.ambiguous[label] = ", ".join(
                f"id={u}({self._info.get(u, ('', '', ''))[1]}/{self._info.get(u, ('', '', ''))[2]})" for u in cands)
        return None

    @classmethod
    def from_db(cls, pgc, system=None):
        pgc.execute("SELECT id, name, employee_code, system_type::text, is_active FROM users ORDER BY id")
        return cls(pgc.fetchall(), system=system)

    def resolve(self, raw):
        """1名として照合。見つからない・同姓同名で決まらなければ None"""
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        k = person_key(s)
        if k and k in self.alias:
            return self.alias[k]
        if s in self.exact:
            return self.exact[s]
        if not k:
            return None
        return self.key.get(k) or self.surname.get(k)

    def resolve_multi(self, raw):
        """複数名の可能性がある欄を照合。(users.idの配列, 照合できなかった部分の配列)"""
        if raw is None:
            return [], []
        s = str(raw).strip()
        if not s:
            return [], []
        one = self.resolve(s)
        if one:
            return [one], []
        ids, unresolved = [], []
        for part in _SEP.split(unicodedata.normalize("NFKC", s)):
            part = part.strip()
            if not part:
                continue
            uid = self.resolve(part)
            if uid:
                if uid not in ids:
                    ids.append(uid)
                continue
            tokens = [t for t in _WS.split(part) if t]
            i = 0
            while i < len(tokens):
                hit = None
                for j in range(len(tokens), i, -1):
                    uid = self.resolve("".join(tokens[i:j]))
                    if uid:
                        hit = (uid, j)
                        break
                if hit:
                    if hit[0] not in ids:
                        ids.append(hit[0])
                    i = hit[1]
                else:
                    unresolved.append(tokens[i])
                    i += 1
        return ids, unresolved

    def resolve_first(self, raw):
        """1人だけを入れる欄(オペレーター・承認者・作成者・PG作成者 等)の照合。
        1名として照合できればその人。「井本　アイン」のように複数名が書かれていれば先頭に照合できた人。
        誰にも照合できなければ None(users に無い旧担当者名は空欄のまま。管理者で代替しない)"""
        uid = self.resolve(raw)
        if uid is not None:
            return uid
        ids, _ = self.resolve_multi(raw)
        return ids[0] if ids else None

    def explain(self, raw):
        """resolve_first と同じ結果と、その理由。(users.id または None, 理由)"""
        if raw is None or not str(raw).strip():
            return None, "空欄"
        s = str(raw).strip()
        k = person_key(s)
        if k and k in self.alias:
            return self.alias[k], "通称"
        if s in self.exact:
            if self.exact[s] is not None:
                return self.exact[s], "完全一致"
            return None, "同姓同名で決まらない"
        if k and self.key.get(k) is not None:
            return self.key[k], "表記ゆれ(全角/半角・空白)"
        if k and self.surname.get(k) is not None:
            return self.surname[k], "姓のみ"
        ids, unres = self.resolve_multi(s)
        if ids:
            return ids[0], ("複数名(先頭)" if len(ids) > 1 else "複数名(一部のみusersに有り)" if unres else "複数名(先頭)")
        if s in self.ambiguous or (k and k in self.ambiguous):
            return None, "同姓同名で決まらない"
        return None, "usersに無い(空欄)"


def staff_id_map_from_rows(pgc, staff_rows, system="NC"):
    """旧NC担当者マスタ ACC_Staff の行 [(St_id, S_name), ...] → {St_id: users.id}
    ① 社員コード STAFF{St_id:03d}(旧システムから移した利用者の規則)
    ② ①が無いときは氏名で照合(同姓同名は通称の表/系統で決める)
    返り値: (staff_id_map, 未対応の (St_id, 氏名) 一覧)。参照側の型の違いに備えて整数キーでも引ける"""
    pgc.execute("SELECT id, employee_code FROM users")
    code_to_userid = {r[1]: r[0] for r in pgc.fetchall()}
    person = PersonResolver.from_db(pgc, system=system)
    staff_id_map, unmatched = {}, []
    for st_id, s_name in staff_rows:
        try:
            code = f"STAFF{int(st_id):03d}"
        except (TypeError, ValueError):
            continue
        uid = code_to_userid.get(code) or person.resolve(s_name)
        if uid is not None:
            staff_id_map[st_id] = uid
            staff_id_map[int(st_id)] = uid
        else:
            unmatched.append((st_id, s_name))
    return staff_id_map, unmatched


def staff_uid(staff_id_map, raw):
    """旧の担当者ID(St_id。数値/文字列どちらでも) → users.id。無ければ None(管理者で代替しない)"""
    if raw is None:
        return None
    uid = staff_id_map.get(raw)
    if uid is None:
        try:
            uid = staff_id_map.get(int(str(raw).strip()))
        except (TypeError, ValueError):
            uid = None
    return uid
