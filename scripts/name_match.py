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
  同じ正規化キーや同じ姓の利用者が複数いる場合は、誤った人に結び付けないよう照合しない。

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


class PersonResolver:
    """users から作る 旧担当者名 → users.id の照合器"""

    def __init__(self, rows):
        """rows: [(id, name), ...]"""
        self.exact = {}
        self.key = {}
        self.surname = {}
        dup_key, dup_sur = set(), set()
        for uid, name in rows:
            if not name:
                continue
            self.exact.setdefault(str(name).strip(), uid)
            k = person_key(name)
            if k:
                if k in self.key and self.key[k] != uid:
                    dup_key.add(k)
                self.key[k] = uid
            tokens = _WS.split(unicodedata.normalize("NFKC", str(name)).strip())
            if len(tokens) >= 2:
                sk = person_key(tokens[0])
                if sk and sk != k:
                    if sk in self.surname and self.surname[sk] != uid:
                        dup_sur.add(sk)
                    self.surname[sk] = uid
        for k in dup_key:
            self.key.pop(k, None)
        for k in dup_sur:
            self.surname.pop(k, None)
        # 姓が誰かの氏名全体と同じ場合は氏名全体を優先(姓での救済はしない)
        for k in list(self.surname):
            if k in self.key:
                self.surname.pop(k, None)

    @classmethod
    def from_db(cls, pgc):
        pgc.execute("SELECT id, name FROM users")
        return cls(pgc.fetchall())

    def resolve(self, raw):
        """1名として照合。見つからなければ None"""
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        if s in self.exact:
            return self.exact[s]
        k = person_key(s)
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
