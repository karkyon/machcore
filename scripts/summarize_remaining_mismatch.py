#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_remaining_mismatch.py
================================
verify_old_new_db.py が出力した最新のJSON結果を読み込み、
②ツーリングの残存mismatchedの内訳をフィールド別・パターン別に集計して表示する。

[前回の不具合修正]
  前回はカレントディレクトリ依存の相対パス(scripts/verify_reports/...)で
  globしていたため、実行時のCWDによって見つからない場合があった。
  今回は固定の絶対パス(/home/karkyon/projects/machcore/scripts/verify_reports/)
  を最優先候補にし、スクリプト自身の場所基準・相対パスもフォールバックとして
  残すことで確実に見つける。

実行方法:
  python3 scripts/summarize_remaining_mismatch.py
  (verify_reports/ 配下の最新JSONを自動で探す)

  または明示的に指定:
  python3 scripts/summarize_remaining_mismatch.py /path/to/verify_result_XXXX.json
"""
import sys, os, json, glob
from collections import Counter, defaultdict

# 候補ディレクトリ(優先順): ①固定絶対パス ②スクリプト自身基準 ③カレントディレクトリ基準
CANDIDATE_DIRS = [
    "/home/karkyon/projects/machcore/scripts/verify_reports",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_reports"),
    os.path.join(os.getcwd(), "scripts", "verify_reports"),
    os.path.join(os.getcwd(), "verify_reports"),
]


def find_latest_json():
    seen = set()
    all_candidates = []
    for d in CANDIDATE_DIRS:
        d = os.path.normpath(d)
        if d in seen:
            continue
        seen.add(d)
        if not os.path.isdir(d):
            continue
        found = glob.glob(os.path.join(d, "verify_result_*.json"))
        all_candidates.extend(found)
    if not all_candidates:
        return None
    return max(all_candidates, key=os.path.getmtime)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else find_latest_json()
    if not path or not os.path.exists(path):
        print("[ABORT] JSON結果ファイルが見つかりません。")
        print("  検索した候補ディレクトリ:")
        for d in CANDIDATE_DIRS:
            print(f"    - {os.path.normpath(d)} (存在: {os.path.isdir(os.path.normpath(d))})")
        print("  対象ファイルのパスを直接指定することもできます:")
        print("    python3 summarize_remaining_mismatch.py /path/to/verify_result_XXXX.json")
        sys.exit(1)

    print(f"=== 読み込み: {path} ===\n")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tooling = data.get("details", {}).get("tooling", [])

    mismatch_recs = [r for r in tooling if r["status"] == "MISMATCH"]
    missing_recs  = [r for r in tooling if r["status"] == "MISSING_IN_NEW"]
    rowcount_recs = [r for r in tooling if r["status"] == "ROW_COUNT_MISMATCH"]

    print(f"MISMATCH件数(加工ID単位): {len(mismatch_recs)}")
    print(f"MISSING_IN_NEW件数: {len(missing_recs)}")
    print(f"ROW_COUNT_MISMATCH件数: {len(rowcount_recs)}\n")

    # フィールド別集計
    field_counter = Counter()
    kakoid_field_samples = defaultdict(list)
    for rec in mismatch_recs:
        kakoid = rec["kakoid"]
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                field_counter[fd["field"]] += 1
                if len(kakoid_field_samples[fd["field"]]) < 8:
                    kakoid_field_samples[fd["field"]].append(
                        f"加工ID:{kakoid} 行{row['row_index']}: '{fd['old']}' -> '{fd['new']}'"
                    )

    print("--- フィールド別 不一致件数 ---")
    for field, cnt in field_counter.most_common():
        print(f"  {field}: {cnt}件")

    print("\n--- 各フィールドのサンプル(最大8件) ---")
    for field, samples in kakoid_field_samples.items():
        print(f"\n[{field}]")
        for s in samples:
            print(f"  {s}")

    # MISSING_IN_NEW の加工IDリスト
    if missing_recs:
        print("\n--- MISSING_IN_NEW 加工ID一覧 ---")
        print([r["kakoid"] for r in missing_recs])

    print("\n=== 集計完了 ===")


if __name__ == "__main__":
    main()
