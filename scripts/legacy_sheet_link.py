#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_sheet_link.py — 旧システムの作業記録と段取シート(印刷)を結び付ける共通ロジック(再利用モジュール)

作業記録画面の「過去記録」は、その作業記録の段取シートの印刷日時を表示する
(work_records.nc_setup_sheet_log_id / mc_setup_sheet_log_id)。
旧データには結び付けの列が無いため、コンバート時に次の規則で結び付ける。

  NC: 旧ACC_Historyは1行=1枚の段取シート(Out=印刷 → In=戻り・作業実績)。
      同じ行から作られた印刷履歴と作業記録を結び付ける(確定的)。
  MC: 旧ACC_変更履歴は「段取シート印刷」(内容区分ID=1/3/7)と「作業記録」(17)が別の行。
      印刷行の R_IN_DATE(戻り日付=段取シートバック日)が作業記録行の入力日と同じ日で、
      作業記録より前に印刷された、まだ結び付いていない印刷のうち最も新しいものと結び付ける。
      同じ行に印刷と作業実績がある場合はその印刷と結び付ける。参考資料の印刷は対象外。

利用元: mc_full_import.py PHASE6 / nc_full_import_v2.py PHASE3 / link_legacy_work_records_to_sheets.py
"""
import re
from datetime import datetime, date, timedelta


def to_date(v):
    """datetime/date/文字列('YYYY/MM/DD','YYYY-MM-DD' 始まり) → date。解釈できなければ None"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def round_sec(dt):
    """秒単位に丸める(SQL Serverのdatetime(1/300秒)とPostgreSQLのtimestamp(3)の差を吸収して突き合わせるため)"""
    if dt is None:
        return None
    return (dt + timedelta(microseconds=500000)).replace(microsecond=0)


def new_mc_candidate(log_id, input_raw, r_in_date, is_reference):
    """MCの印刷1件(旧ACC_変更履歴の印刷行)を結び付け候補として表す"""
    return {"id": log_id, "in": input_raw if isinstance(input_raw, datetime) else None,
            "r_in": to_date(r_in_date), "ref": bool(is_reference), "used": False}


def pick_mc_sheet(cands, work_input_raw):
    """MCの作業記録行(入力日=work_input_raw, JSTのnaive datetime)に対応する印刷候補のidを返す(無ければNone)"""
    if not isinstance(work_input_raw, datetime):
        return None
    wday = work_input_raw.date()
    pool = [c for c in cands
            if not c["used"] and not c["ref"] and c["r_in"] == wday
            and (c["in"] is None or c["in"] <= work_input_raw)]
    if not pool:
        return None
    c = max(pool, key=lambda x: x["in"] or datetime.min)
    c["used"] = True
    return c["id"]


def parse_hms_min(s):
    """旧MCの '3H 30M' 形式 → 分(mc_full_import.py PHASE6 と同じ規則)"""
    if not s:
        return None
    s = str(s).strip()
    mh = re.search(r"(\d+)H", s); mm = re.search(r"H\s*(\d+)M", s)
    if mh:
        h = int(mh.group(1)); m = int(mm.group(1)) if mm else 0
        return h * 60 + m if (h > 0 or m > 0) else None
    return None
