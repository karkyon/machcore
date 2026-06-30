#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_nightly_full_reimport_and_verify.py
==========================================
UAT再実施に向けた、MC・NC両系統の「全データ再投入 → 検証 → レポート生成」を
1コマンドで一括実行する夜間バッチ用ラッパー。

実行順序:
  1. mc_full_import.py   --phase 0   (MC: 全フェーズ本番実行)
  2. nc_full_import_v2.py --phase 0  (NC: 全フェーズ本番実行)
  3. run_verify_all.py               (MC: DB比較 + HTMLレポート生成)
  4. run_verify_nc_all.py            (NC: DB比較 + HTMLレポート生成)

各ステップは前段が異常終了(returncode!=0)した場合、後続をスキップして停止する
(中途半端な状態のままインポート・検証が進行することを防ぐため)。

DB更新を伴うため、--dry-run無しでの実行は必ず夜間・業務影響のない時間帯に行うこと。
mc_full_import.py / nc_full_import_v2.py は自身のログを
logs/mc_full_import.log / logs/nc_full_import.log に追記する(このラッパー自体は
標準出力をそのまま流すのみで、別ログファイルへの二重記録は行わない)。

実行方法:
  本番一括実行(夜間):
    python3 run_nightly_full_reimport_and_verify.py

  事前ドライラン(DB更新なし、所要時間とエラー有無の確認用):
    python3 run_nightly_full_reimport_and_verify.py --dry-run

  検証のみ再実行(インポートはスキップ):
    python3 run_nightly_full_reimport_and_verify.py --verify-only

  MC側のみ / NC側のみ:
    python3 run_nightly_full_reimport_and_verify.py --target mc
    python3 run_nightly_full_reimport_and_verify.py --target nc

出力:
  scripts/verify_reports/verify_result_YYYYMMDD_HHMMSS.json / .html        (MC)
  scripts/verify_reports/verify_nc_result_YYYYMMDD_HHMMSS.json / .html     (NC)
  scripts/verify_reports/nightly_run_summary_YYYYMMDD_HHMMSS.md            (本ラッパーの実行サマリ)
"""
import sys
import os
import subprocess
import argparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "verify_reports")


def run(cmd, label):
    print("=" * 70)
    print(f"[STEP] {label}")
    print(f"[CMD]  {' '.join(cmd)}")
    print("=" * 70)
    start = datetime.now()
    p = subprocess.run(cmd, cwd=HERE)
    elapsed = (datetime.now() - start).total_seconds()
    status = "OK" if p.returncode == 0 else f"FAILED(rc={p.returncode})"
    print(f"[RESULT] {label}: {status} ({elapsed:.1f}s)\n")
    return p.returncode, elapsed, status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                     help="インポートスクリプトを--dry-runで実行(DB更新なし、所要時間・エラー確認用)")
    ap.add_argument("--verify-only", action="store_true",
                     help="インポートをスキップし、検証(verify+report)のみ実行")
    ap.add_argument("--target", choices=["both", "mc", "nc"], default="both",
                     help="対象システム(既定: both)")
    ap.add_argument("--limit", type=int, default=None,
                     help="検証件数を先頭N件に制限(テスト用、本番では指定しない)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    py = sys.executable

    steps = []  # (label, returncode, elapsed, status)

    do_mc = args.target in ("both", "mc")
    do_nc = args.target in ("both", "nc")

    # ── 1. インポート ──────────────────────────────────────
    if not args.verify_only:
        if do_mc:
            cmd = [py, os.path.join(HERE, "mc_full_import.py"), "--phase", "0"]
            if args.dry_run:
                cmd.append("--dry-run")
            rc, el, st = run(cmd, "MC全データ再投入 (mc_full_import.py --phase 0)")
            steps.append(("MC再投入", rc, el, st))
            if rc != 0:
                print("[ABORT] MC再投入が失敗したため、後続処理を中止します。")
                write_summary(ts, steps, aborted=True)
                sys.exit(1)

        if do_nc:
            cmd = [py, os.path.join(HERE, "nc_full_import_v2.py"), "--phase", "0"]
            if args.dry_run:
                cmd.append("--dry-run")
            rc, el, st = run(cmd, "NC全データ再投入 (nc_full_import_v2.py --phase 0)")
            steps.append(("NC再投入", rc, el, st))
            if rc != 0:
                print("[ABORT] NC再投入が失敗したため、後続処理を中止します。")
                write_summary(ts, steps, aborted=True)
                sys.exit(1)
    else:
        print("[INFO] --verify-only 指定のため、インポートをスキップします。")

    if args.dry_run:
        print("[INFO] --dry-run指定のため、検証(verify)はスキップします"
              "(dry-run時はDBが更新されないため、検証しても意味のある結果になりません)。")
        write_summary(ts, steps, aborted=False, verify_skipped=True)
        return

    # ── 2. 検証 + レポート生成 ──────────────────────────────
    mc_html = nc_html = None
    if do_mc:
        json_path = os.path.join(OUT_DIR, f"verify_result_{ts}.json")
        html_path = os.path.join(OUT_DIR, f"verify_report_{ts}.html")
        cmd1 = [py, os.path.join(HERE, "verify_old_new_db.py"), "--out", json_path]
        if args.limit:
            cmd1 += ["--limit", str(args.limit)]
        rc, el, st = run(cmd1, "MC検証 (verify_old_new_db.py)")
        steps.append(("MC検証", rc, el, st))
        if rc == 0:
            cmd2 = [py, os.path.join(HERE, "generate_verify_report.py"),
                    "--in", json_path, "--out", html_path]
            rc2, el2, st2 = run(cmd2, "MCレポート生成 (generate_verify_report.py)")
            steps.append(("MCレポート生成", rc2, el2, st2))
            if rc2 == 0:
                mc_html = html_path

    if do_nc:
        json_path = os.path.join(OUT_DIR, f"verify_nc_result_{ts}.json")
        html_path = os.path.join(OUT_DIR, f"verify_nc_report_{ts}.html")
        cmd1 = [py, os.path.join(HERE, "verify_nc_old_new_db.py"), "--out", json_path]
        if args.limit:
            cmd1 += ["--limit", str(args.limit)]
        rc, el, st = run(cmd1, "NC検証 (verify_nc_old_new_db.py)")
        steps.append(("NC検証", rc, el, st))
        if rc == 0:
            cmd2 = [py, os.path.join(HERE, "generate_verify_report_nc.py"),
                    "--in", json_path, "--out", html_path]
            rc2, el2, st2 = run(cmd2, "NCレポート生成 (generate_verify_report_nc.py)")
            steps.append(("NCレポート生成", rc2, el2, st2))
            if rc2 == 0:
                nc_html = html_path

    write_summary(ts, steps, aborted=False, mc_html=mc_html, nc_html=nc_html)

    print("=" * 70)
    print("[DONE] 夜間一括再投入+検証 完了")
    if mc_html:
        print(f"  MCレポート: {mc_html}")
    if nc_html:
        print(f"  NCレポート: {nc_html}")
    print("=" * 70)


def write_summary(ts, steps, aborted=False, verify_skipped=False, mc_html=None, nc_html=None):
    path = os.path.join(OUT_DIR, f"nightly_run_summary_{ts}.md")
    lines = [
        f"# 夜間一括再投入+検証 実行サマリ ({ts})",
        "",
        f"- 実行終了状態: {'中断(ABORT)' if aborted else ('検証スキップ(dry-run)' if verify_skipped else '完了')}",
        "",
        "| ステップ | 結果 | 所要時間(秒) |",
        "|---|---|---|",
    ]
    for label, rc, el, st in steps:
        lines.append(f"| {label} | {st} | {el:.1f} |")
    lines.append("")
    if mc_html:
        lines.append(f"- MCレポート: `{mc_html}`")
    if nc_html:
        lines.append(f"- NCレポート: `{nc_html}`")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[INFO] 実行サマリを保存しました: {path}")


if __name__ == "__main__":
    main()
