#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
link_legacy_work_records_to_sheets.py — コンバート済みの作業記録を段取シート(印刷履歴)に結び付ける(再利用スクリプト)

コンバート(mc_full_import.py PHASE6 / nc_full_import_v2.py PHASE3)は取り込み時に結び付けるが、
それ以前に取り込んだデータは結び付いていない(作業記録画面の過去記録に印刷日時が出ない)。
再コンバートせずに、既存データへ同じ規則(legacy_sheet_link.py)で結び付けを補う。

  ・旧DBの行から作った値(印刷日時・作業日・段取/加工時間・個数)で新DBの行を特定する。
  ・結び付いていない作業記録(nc/mc_setup_sheet_log_id が NULL)だけを更新する。
    MachCoreで入力した作業記録や、既に結び付いているものは変更しない。

実行:
  python3 scripts/link_legacy_work_records_to_sheets.py            # 本番実行
  python3 scripts/link_legacy_work_records_to_sheets.py --dry-run  # 件数の確認のみ
"""
import os, sys, argparse
from collections import defaultdict, deque
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from legacy_sheet_link import round_sec, new_mc_candidate, pick_mc_sheet, parse_hms_min  # noqa: E402
import verify_nc_old_new_db as V  # noqa: E402  (旧DB/新DBの接続設定を共用)


def log(m):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}", flush=True)


def _pop(dq_map, key):
    q = dq_map.get(key)
    return q.popleft() if q else None


def link_nc(ss, pg, dry):
    pc = pg.cursor(); sc = ss.cursor()
    pc.execute("SELECT id, machining_id FROM nc_programs")
    kid_progs = defaultdict(list)
    for pid, kid in pc.fetchall():
        kid_progs[kid].append(pid)
    pc.execute("SELECT nc_setup_sheet_log_id FROM work_records WHERE nc_setup_sheet_log_id IS NOT NULL")
    used = {r[0] for r in pc.fetchall()}
    pc.execute("SELECT id, nc_program_id, printed_at FROM setup_sheet_logs ORDER BY id")
    logs = defaultdict(deque)
    for lid, pid, pa in pc.fetchall():
        if lid not in used:
            logs[(pid, round_sec(pa))].append(lid)
    pc.execute("""SELECT id, nc_program_id, work_date, setup_time_min, machining_time_min, quantity
                  FROM work_records WHERE nc_program_id IS NOT NULL AND nc_setup_sheet_log_id IS NULL ORDER BY id""")
    wrs = defaultdict(deque)
    for wid, pid, wd, st, mt, q in pc.fetchall():
        wrs[(pid, wd, st, mt, q)].append(wid)

    sc.execute("""SELECT K_id, Out_Cont, Out_Date, In_Date, Dan_Op, Dan_H, Dan_M, La_H, La_M, P, La_Op
                  FROM ACC_History ORDER BY K_id, In_Date""")
    upd = []; no_log = no_wr = 0
    for kid, out_cont, out_date, in_date, dan_op, dan_h, dan_m, la_h, la_m, p, la_op in sc.fetchall():
        if kid is None or "印刷" not in str(out_cont or "") or not out_date:
            continue
        dh = int(dan_h or 0); dm = int(dan_m or 0); lh = int(la_h or 0); lm = int(la_m or 0); pi = int(p or 0)
        if not (str(dan_op or "").strip() or dh or dm or lh or lm or pi):
            continue
        setup_min = (dh * 60 + dm) or None
        mach_min = (lh * 60 + lm) or None
        wd_raw = in_date or out_date
        work_date = wd_raw.date() if hasattr(wd_raw, "year") else datetime(2005, 1, 1).date()
        printed = round_sec(out_date - timedelta(hours=9))
        for pid in kid_progs.get(int(kid), []):
            lid = _pop(logs, (pid, printed))
            if lid is None:
                no_log += 1; continue
            wid = _pop(wrs, (pid, work_date, setup_min, mach_min, pi if pi > 0 else None))
            if wid is None:
                no_wr += 1; continue
            upd.append((lid, wid))
    log(f"[NC] 結び付け {len(upd)}件 / 印刷履歴が見つからない {no_log}件 / 作業記録が見つからない {no_wr}件")
    if upd and not dry:
        pc.executemany("UPDATE work_records SET nc_setup_sheet_log_id=%s WHERE id=%s", upd)
    return len(upd)


def link_mc(ss, pg, dry):
    pc = pg.cursor(); sc = ss.cursor()
    pc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_progs = defaultdict(list)
    for pid, mcid in pc.fetchall():
        mcid_progs[mcid].append(pid)
    pc.execute("SELECT mc_setup_sheet_log_id FROM work_records WHERE mc_setup_sheet_log_id IS NOT NULL")
    used = {r[0] for r in pc.fetchall()}
    pc.execute("SELECT id, mc_program_id, printed_at FROM mc_setup_sheet_logs ORDER BY id")
    logs = defaultdict(deque)
    for lid, pid, pa in pc.fetchall():
        logs[(pid, round_sec(pa))].append(lid)
    pc.execute("""SELECT id, mc_program_id, work_date, setup_time_min, machining_time_min, quantity
                  FROM work_records WHERE mc_program_id IS NOT NULL AND mc_setup_sheet_log_id IS NULL ORDER BY id""")
    wrs = defaultdict(deque)
    for wid, pid, wd, st, mt, q in pc.fetchall():
        wrs[(pid, wd, st, mt, q)].append(wid)

    sc.execute("""SELECT MCID, 内容, 内容区分ID, 入力日, R_IN_DATE, 段取時間, 加工時間, 総時間, [ﾜｰｸ数]
                  FROM ACC_変更履歴 ORDER BY MCID, 入力日""")
    cands = defaultdict(list)
    upd = []; no_wr = no_link = 0
    for mcid, content, nk, in_raw, r_in, st_s, mt_s, total, qty_val in sc.fetchall():
        try: nk = int(nk or 0)
        except (TypeError, ValueError): nk = 0
        content = str(content or "").strip()
        has_work = (nk == 17) or (total is not None and str(total).strip() != "")
        for pid in mcid_progs.get(mcid, []):
            row_c = None
            if nk in (1, 3, 7) and isinstance(in_raw, datetime):
                lid = _pop(logs, (pid, round_sec(in_raw - timedelta(hours=9))))
                if lid is not None:
                    row_c = new_mc_candidate(lid, in_raw, r_in, nk == 1 and "参考" in content)
                    if lid in used:
                        row_c["used"] = True
                    cands[pid].append(row_c)
            if not has_work or not isinstance(in_raw, datetime):
                continue
            try:
                qty = int(float(str(qty_val))) if qty_val else None
            except (TypeError, ValueError):
                qty = None
            wid = _pop(wrs, (pid, in_raw.date(), parse_hms_min(st_s), parse_hms_min(mt_s), qty))
            if wid is None:
                no_wr += 1; continue
            if row_c is not None and not row_c["used"] and not row_c["ref"]:
                row_c["used"] = True; lid = row_c["id"]
            else:
                lid = pick_mc_sheet(cands[pid], in_raw)
            if lid is None:
                no_link += 1; continue
            upd.append((lid, wid))
    log(f"[MC] 結び付け {len(upd)}件 / 対応する印刷が無い作業記録 {no_link}件 / 新DBで作業記録が見つからない {no_wr}件")
    if upd and not dry:
        pc.executemany("UPDATE work_records SET mc_setup_sheet_log_id=%s WHERE id=%s", upd)
    return len(upd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ss = V.ss_connect(); pg = V.pg_connect()
    try:
        link_nc(ss, pg, a.dry_run)
        link_mc(ss, pg, a.dry_run)
        if a.dry_run:
            pg.rollback(); log("dry-run: 変更していません")
        else:
            pg.commit(); log("commit 完了")
    except Exception:
        pg.rollback(); raise
    finally:
        ss.close(); pg.close()


if __name__ == "__main__":
    main()
