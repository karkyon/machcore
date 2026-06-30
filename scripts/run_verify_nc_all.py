#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_verify_nc_all.py
=======================
verify_nc_old_new_db.py (NC側DB比較) → generate_verify_report_nc.py (HTMLレポート生成)
を1コマンドで実行するラッパー。run_verify_all.py(MC用)のNC版。

実行方法:
  python3 run_verify_nc_all.py
  python3 run_verify_nc_all.py --limit 500   # テスト用に先頭500件だけ検証

出力:
  /home/karkyon/projects/machcore/verify_reports/verify_nc_result_YYYYMMDD_HHMMSS.json
  /home/karkyon/projects/machcore/verify_reports/verify_nc_report_YYYYMMDD_HHMMSS.html
"""
import sys, os, subprocess, argparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "verify_reports")


def run(cmd):
    print(f"[RUN] {' '.join(cmd)}")
    p = subprocess.run(cmd, capture_output=True, text=True)
    print(p.stdout)
    if p.stderr:
        print(p.stderr, file=sys.stderr)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(OUT_DIR, f"verify_nc_result_{ts}.json")
    html_path = os.path.join(OUT_DIR, f"verify_nc_report_{ts}.html")

    cmd1 = [sys.executable, os.path.join(HERE, "verify_nc_old_new_db.py"), "--out", json_path]
    if args.limit:
        cmd1 += ["--limit", str(args.limit)]
    rc1 = run(cmd1)
    if rc1 != 0:
        print("[ABORT] verify_nc_old_new_db.py が異常終了しました。")
        sys.exit(1)

    cmd2 = [sys.executable, os.path.join(HERE, "generate_verify_report_nc.py"),
            "--in", json_path, "--out", html_path]
    rc2 = run(cmd2)
    if rc2 != 0:
        print("[ABORT] generate_verify_report_nc.py が異常終了しました。")
        sys.exit(1)

    print("")
    print("=" * 60)
    print(f"[DONE] NC側検証レポート生成完了: {html_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
