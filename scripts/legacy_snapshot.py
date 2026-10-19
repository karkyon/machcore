#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_snapshot.py — コンバートが旧DBを読んだ時点(スナップショット)の判定(再利用モジュール)

旧システムは UAT 中も並行して使われており、コンバートが旧DBを読んだ後に旧へ入力・回収された行は
新DBに入っていないのが正しい。新旧の検証ではそれらを「コンバート後に旧で入力(比較対象外)」として、
コンバート時点の旧データで期待値を作る。

基準時刻 = コンバートで作った作業記録の作成時刻の最小(work_records.created_at。履歴を読んだ直後に作られる)を
JST(旧DBの日時と同じ)にしたもの。MC と NC はコンバートの時刻が違うので別々に求める。

利用元: verify_user_fields_old_new.py / verify_old_new_db.py / verify_nc_old_new_db.py /
        verify_work_records.py / run_conversion_test.py
"""
from datetime import datetime, date, time


def conversion_read_jst(pgc, system):
    """system: "MC" / "NC"。コンバートが旧の履歴を読んだ時刻(JST・naive)。分からなければ None"""
    col = "mc_program_id" if system == "MC" else "nc_program_id"
    try:
        pgc.execute(f"""SELECT (MIN(created_at) AT TIME ZONE current_setting('TimeZone')) AT TIME ZONE 'Asia/Tokyo'
                        FROM work_records WHERE {col} IS NOT NULL""")
        r = pgc.fetchone()
        return r[0] if r and r[0] is not None else None
    except Exception:
        try:
            pgc.connection.rollback()
        except Exception:
            pass
        return None


def after(dt, cutoff):
    """旧の日時 dt がコンバートの基準時刻より後(=コンバート時点には無かった入力)なら True"""
    if cutoff is None or dt is None:
        return False
    if isinstance(dt, datetime):
        return dt > cutoff
    if isinstance(dt, date):
        return datetime.combine(dt, time.min) > cutoff
    return False
