#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
machine_name_match.py — 旧システムの機械名(文字列) → 新システム machines.id の照合(再利用モジュール)

旧ACC_マシニングraw.機械 / ACC_変更履歴.機械 は手入力の文字列で、全角/半角・大文字/小文字・
ハイフン/空白の表記ゆれがある(例: 'ＭＣ7' / 'A500z' / 'MV-45')。
machines.machine_code と完全一致でしか引かないと、表記ゆれだけで機械が空欄になるため、
新旧両方に同じ正規化をかけて照合する。

  正規化: NFKC(全角→半角) → 大文字化 → 空白・ハイフン・アンダースコア除去
          'ＭＣ7' → 'MC7'、'a500Z'/'A500z' → 'A500Z'、'MV-45' → 'MV45'
  照合順: ①machine_code 完全一致 → ②正規化キー一致 → ③'MC'を付けた正規化キー一致('7' → MC7)
          正規化キーが複数の機械に該当する場合(マスタ側の重複)はどれにも結び付けない(誤結合防止)。

利用元: mc_full_import.py PHASE1/PHASE6、verify_old_new_db.py、apply_* の一度きり補正
"""
import re
import unicodedata


def normalize_machine(raw):
    """機械名の正規化キー。空なら None"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = unicodedata.normalize("NFKC", s).upper()
    s = re.sub(r"[\s\-_]+", "", s)
    return s or None


def machine_names_equal(old_name, new_code):
    """検証用: 旧の機械名と新の machine_code が同じ機械を指すか(取込の照合規則と同じ)"""
    a = normalize_machine(old_name)
    b = normalize_machine(new_code)
    if a == b:
        return True
    return a is not None and b is not None and ("MC" + a) == b


class MachineResolver:
    """machines マスタから作る 旧機械名 → machines.id の照合器"""

    def __init__(self, rows):
        """rows: [(id, machine_code), ...]"""
        self.exact = {}
        self.norm = {}
        ambiguous = set()
        for mid, code in rows:
            if code is None:
                continue
            self.exact[str(code).strip()] = mid
            k = normalize_machine(code)
            if k is None:
                continue
            if k in self.norm and self.norm[k] != mid:
                ambiguous.add(k)
            self.norm[k] = mid
        for k in ambiguous:
            self.norm.pop(k, None)
        self.ambiguous = sorted(ambiguous)
        self.unresolved = {}   # 旧機械名 → 件数(マスタ未登録)

    @classmethod
    def from_db(cls, pgc, system_types=("MC", "BOTH")):
        pgc.execute("SELECT id, machine_code FROM machines WHERE system_type::text = ANY(%s)",
                    (list(system_types),))
        return cls(pgc.fetchall())

    def resolve(self, raw, count_unresolved=True):
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        if s in self.exact:
            return self.exact[s]
        k = normalize_machine(s)
        mid = self.norm.get(k)
        if mid is None and k is not None:
            mid = self.norm.get("MC" + k)
        if mid is None and count_unresolved:
            self.unresolved[s] = self.unresolved.get(s, 0) + 1
        return mid

    def unresolved_summary(self):
        return ", ".join(f"{k}({v})" for k, v in
                         sorted(self.unresolved.items(), key=lambda x: (-x[1], x[0])))
