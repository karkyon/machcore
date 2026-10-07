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

利用元: mc_full_import.py PHASE1/PHASE6、nc_full_import_v2.py PHASE3
"""
import re
import unicodedata

_SEP = re.compile(r"[&＆、,，・/／+＋]")
_WS = re.compile(r"[\s　]+")


def person_key(raw):
    """担当者名の正規化キー。空なら None"""
    if raw is None:
        return None
    s = unicodedata.normalize("NFKC", str(raw))
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
