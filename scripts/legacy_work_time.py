#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_work_time.py
===================
旧 ACC_変更履歴(MC作業記録)の時間・サイクルの値を新 work_records の列へ変換する共通規則。
取込(mc_full_import.py PHASE6)・検証(verify_work_records.py)・既存データ補正で同じ規則を使う。

旧の時間は文字列: '1H 15M' / '14H15M' / '45M'(Hなし) / '0H 44M 24S' / '0H -35M'(負=入力ミス)
  - 負の値を含むものは値なしとして扱う
旧のサイクル:
  TH/TM/TS     = 1サイクルの時間(生の値)          → work_records.cycle_time_sec
  1S_個数      = 1サイクルで加工する個数          → work_records.cycle_pcs
  ｻｲｸﾙﾀｲﾑ/1P  = TH/TM/TS ÷ 1S_個数(旧画面の表示値) → 保存しない(画面で計算)
"""
import re
import unicodedata


def parse_hms_sec(v):
    """旧の時間文字列 → 秒。空・負・解釈不可は None。0 は 0"""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).strip().upper()
    if not s or "-" in s:
        return None
    # 旧には '0H 2.1M' '1H 29.3M' のような小数の分もある
    mh = re.search(r"(\d+(?:\.\d+)?)\s*H", s)
    mm = re.search(r"(\d+(?:\.\d+)?)\s*M", s)
    ms = re.search(r"(\d+(?:\.\d+)?)\s*S", s)
    if not (mh or mm or ms):
        return None
    return int(round((float(mh.group(1)) if mh else 0) * 3600
                     + (float(mm.group(1)) if mm else 0) * 60
                     + (float(ms.group(1)) if ms else 0)))


def parse_hms_min(v):
    """旧の時間文字列 → 分(秒は切捨て)。空・負・0・解釈不可は None"""
    sec = parse_hms_sec(v)
    if not sec:
        return None
    return sec // 60 or None


def _int0(v):
    if v is None:
        return 0
    try:
        return int(float(str(v).strip() or 0))
    except (TypeError, ValueError):
        return 0


def _raw_cycle(row):
    return _int0(row.get("TH")) * 3600 + _int0(row.get("TM")) * 60 + _int0(row.get("TS"))


def cycle_pcs(row):
    """1S_個数 → 個/1サイクル。
    1S_個数 が空(古い記録に多い)でも旧画面は ｻｲｸﾙﾀｲﾑ/1P を出しているため、
    TH/TM/TS ÷ ｻｲｸﾙﾀｲﾑ/1P から個数を求める(ふつうは1)。求められなければ None"""
    n = _int0(row.get("1S_個数"))
    if n > 0:
        return n
    raw = _raw_cycle(row)
    per1 = parse_hms_sec(row.get("ｻｲｸﾙﾀｲﾑ/1P"))
    if raw > 0 and per1:
        return max(1, int(round(raw / per1)))
    return None


def cycle_sec(row):
    """1サイクルの時間(秒)。TH/TM/TS を正とし、空のときだけ ｻｲｸﾙﾀｲﾑ/1P × 個数 で補う"""
    raw = _int0(row.get("TH")) * 3600 + _int0(row.get("TM")) * 60 + _int0(row.get("TS"))
    if raw > 0:
        return raw
    per1 = parse_hms_sec(row.get("ｻｲｸﾙﾀｲﾑ/1P"))
    if per1:
        return per1 * (cycle_pcs(row) or 1)
    return None


def _old_import_parse_sec(v):
    """補正前の取込(mc_full_import.py 5abf136 より前)の _parse_hms_sec をそのまま再現(小数の分は読めず0になる)"""
    if not v:
        return None
    s = str(v).strip()
    mh = re.search(r"(\d+)H", s)
    mm = re.search(r"H\s*(\d+)M", s)
    ms = re.search(r"M\s*(\d+)S", s)
    h = int(mh.group(1)) if mh else 0
    m = int(mm.group(1)) if mm else 0
    sc = int(ms.group(1)) if ms else 0
    return h * 3600 + m * 60 + sc if (h or m or sc) else None


def converted_cycle_sec_before_fix(row):
    """補正前の取込が入れていた値: ｻｲｸﾙﾀｲﾑ/1P を優先、無ければ TH/TM/TS"""
    per1 = _old_import_parse_sec(row.get("ｻｲｸﾙﾀｲﾑ/1P"))
    if per1 is not None:
        return per1
    th, tm, ts = _int0(row.get("TH")), _int0(row.get("TM")), _int0(row.get("TS"))
    return th * 3600 + tm * 60 + ts if (th or tm or ts) else None
