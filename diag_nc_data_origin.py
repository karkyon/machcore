#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_nc_data_origin.py
現在DB内のNCデータ(7,839件)がどういう経路で投入されたかを正確に特定するための診断。
コード変更は一切行わない。

確認内容:
  1. nc_programs の legacyKid / legacyVer の充足率（移行スクリプト経由なら高いはず）
  2. registeredBy が全件 ADMIN(22) など特定の1人に偏っていないか（簡易インポートの特徴）
  3. createdAt の分布（一括INSERTなら同一タイムスタンプに集中するはず）
  4. work_records / change_history / setup_sheet_logs の件数（HANDOFFにある旧t_k_History
     12,046件からの3分割が行われていればこれらも数千件あるはず。0件ならNC側は
     「メインレコードだけ入れてある」中途半端な状態と確定できる）
  5. nc_tools の件数（旧t3_Toolからの移行有無）
"""
import psycopg2
from datetime import datetime

def main():
    conn = psycopg2.connect(
        host="localhost", port=5440, dbname="machcore_dev",
        user="machcore", password="machcore_pass_change_me"
    )
    cur = conn.cursor()

    print("=" * 70)
    print("【診断】NC側現行データの投入経路調査")
    print("=" * 70)

    print("\n=== [1] nc_programs 総件数と legacyKid/legacyVer 充足率 ===")
    cur.execute("SELECT COUNT(*) FROM nc_programs")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM nc_programs WHERE legacy_kid IS NOT NULL")
    has_legacy_kid = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM nc_programs WHERE legacy_ver IS NOT NULL")
    has_legacy_ver = cur.fetchone()[0]
    print(f"  総件数: {total}")
    print(f"  legacy_kid 充足: {has_legacy_kid} ({has_legacy_kid/total*100:.1f}%)" if total else "  データなし")
    print(f"  legacy_ver 充足: {has_legacy_ver} ({has_legacy_ver/total*100:.1f}%)" if total else "")

    print("\n=== [2] registered_by の分布(上位5名) ===")
    cur.execute("""
        SELECT u.name, COUNT(*) AS cnt
        FROM nc_programs np JOIN users u ON np.registered_by = u.id
        GROUP BY u.name ORDER BY cnt DESC LIMIT 5
    """)
    for name, cnt in cur.fetchall():
        print(f"  {name}: {cnt}件 ({cnt/total*100:.1f}%)" if total else "")

    print("\n=== [3] created_at の分布(同一タイムスタンプへの集中具合) ===")
    cur.execute("""
        SELECT DATE_TRUNC('minute', created_at) AS minute_bucket, COUNT(*) AS cnt
        FROM nc_programs GROUP BY minute_bucket ORDER BY cnt DESC LIMIT 5
    """)
    for bucket, cnt in cur.fetchall():
        print(f"  {bucket}: {cnt}件")

    print("\n=== [4] 関連テーブルの件数(0件なら未移行と確定) ===")
    for tbl in ["nc_tools", "work_records", "change_history", "setup_sheet_logs", "nc_files"]:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = cur.fetchone()[0]
        print(f"  {tbl}: {cnt}件")

    print("\n=== [5] work_records の work_collected フラグ分布(回収済み/未回収) ===")
    cur.execute("SELECT COUNT(*) FROM work_records")
    wr_total = cur.fetchone()[0]
    if wr_total > 0:
        cur.execute("SELECT work_collected, COUNT(*) FROM work_records GROUP BY work_collected")
        for flag, cnt in cur.fetchall():
            print(f"  work_collected={flag}: {cnt}件")
    else:
        print("  work_records が0件のため対象外")

    print("\n=== [6] setup_sheet_logs の work_collected フラグ分布(段取シート回収判定) ===")
    cur.execute("SELECT COUNT(*) FROM setup_sheet_logs")
    sl_total = cur.fetchone()[0]
    if sl_total > 0:
        cur.execute("SELECT work_collected, COUNT(*) FROM setup_sheet_logs GROUP BY work_collected")
        for flag, cnt in cur.fetchall():
            print(f"  work_collected={flag}: {cnt}件")
    else:
        print("  setup_sheet_logs が0件のため対象外（Image1のNC側「未回収32,649件」の出所を別途特定する必要あり）")

    print("\n=== [7] NcProgramStatus(承認状況)の分布 ===")
    cur.execute("SELECT status, COUNT(*) FROM nc_programs GROUP BY status")
    for status, cnt in cur.fetchall():
        print(f"  {status}: {cnt}件")

    print("\n" + "=" * 70)
    print("【完了】上記出力結果を貼ってください。")
    print("=" * 70)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
