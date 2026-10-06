#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_nc_tool_master.py — NC 加工リスト マスタ(加/工/形状(チップ)/ホルダー の候補)の投入(再利用スクリプト)

NC「変更・登録」画面の加工リストは、加(Sv1)/工(Sv2)/形状(チップ)/ホルダーの候補を
nc_tool_shave1_master / nc_tool_shave2_master / nc_tool_chip_master / nc_tool_holder_master
から表示する(GET /admin/nc-tool-master/:category)。空だと候補が出ない。

候補の取得元(旧システム):
  ① 旧サーバ(SQL Server)上に旧Accessの候補テーブル t_d_Shave1 / t_d_Shave2 / t_d_Chip / t_d_Holder が
     あれば、その内容(表の先頭列の順)をそのまま使う。全データベースを探す。
  ② 無ければ、旧加工リスト ACC_Tool の Shave1 / Shave2 / Chip / Holder 列に実際に入っている値を
     使用件数の多い順に使う(旧システムで実際に選ばれていた値)。
     全角/半角が違うだけの値('40H'/'40Ｈ'、'ｽﾃｯｷ'/'ステッキ')は1つにまとめ、使用件数が多い方の表記を残す。
空のテーブルにだけ投入する(管理画面 /admin/nc-tool-master での追加・修正は上書きしない)。
フルコンバート(nc_full_import_v2.py --phase 0)の PHASE6 でも自動実行される。

実行方法:
  python3 scripts/seed_nc_tool_master.py            # 空のテーブルに投入
  python3 scripts/seed_nc_tool_master.py --dry-run  # 取得元と件数の確認のみ
"""
import os
import re
import sys
import argparse
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# (新テーブル, 旧Access候補テーブル, 旧ACC_Toolの列)
PLAN = [
    ("nc_tool_shave1_master", "t_d_Shave1", "Shave1"),
    ("nc_tool_shave2_master", "t_d_Shave2", "Shave2"),
    ("nc_tool_chip_master",   "t_d_Chip",   "Chip"),
    ("nc_tool_holder_master", "t_d_Holder", "Holder"),
]
NAME_MAX = 50
_WIDTH_CHARS = re.compile(r"[\uFF01-\uFF5E\uFF61-\uFF9F\u3000]+")


def width_key(raw):
    """全角/半角の違いだけを無視した比較キー(全角英数記号→半角、半角カナ→全角、全角空白→半角)。
    ①・Ⅱ・㎜ などは変換しない(全角/半角の違いではないため)"""
    s = _WIDTH_CHARS.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), str(raw or ""))
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def merge_width_variants(values):
    """使用件数の多い順に並んだ値から、全角/半角が違うだけの重複を除く(先に出た=多い方の表記を残す)。
    (残す値の配列, [(残した表記, [まとめた表記...]), ...]) を返す"""
    kept, by_key = [], {}
    for v in values:
        k = width_key(v)
        if not k:
            continue
        if k in by_key:
            if v != by_key[k][0] and v not in by_key[k][1]:
                by_key[k][1].append(v)
            continue
        by_key[k] = (v, [])
        kept.append(v)
    return kept, [(v, m) for v, m in by_key.values() if m]
_TEXT_TYPES = ("char", "varchar", "nchar", "nvarchar", "text", "ntext")


def _find_legacy_tables(ssc, log):
    """旧サーバの全DBから t_d_* 候補テーブルを探す。{旧テーブル名(小文字): (db, schema, table)}"""
    found = {}
    names = [p[1].lower() for p in PLAN]
    try:
        ssc.execute("SELECT name FROM sys.databases WHERE state_desc = 'ONLINE'")
        dbs = [r[0] for r in ssc.fetchall()]
    except Exception as e:
        log(f"[加工リストマスタ] 旧サーバのDB一覧を取得できない: {e}", "WARN")
        return found
    for db in dbs:
        if db in ("master", "tempdb", "model", "msdb"):
            continue
        try:
            ssc.execute(f"SELECT TABLE_SCHEMA, TABLE_NAME FROM [{db}].INFORMATION_SCHEMA.TABLES")
            for sch, tbl in ssc.fetchall():
                if str(tbl).lower() in names and str(tbl).lower() not in found:
                    found[str(tbl).lower()] = (db, sch, tbl)
        except Exception:
            continue
    return found


def _values_from_legacy_table(ssc, db, sch, tbl):
    ssc.execute(f"""
        SELECT COLUMN_NAME, DATA_TYPE FROM [{db}].INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION
    """, (sch, tbl))
    cols = ssc.fetchall()
    if not cols:
        return None, []
    first_col = cols[0][0]
    text_cols = [c for c, t in cols if str(t).lower() in _TEXT_TYPES]
    if not text_cols:
        return None, []
    name_col = text_cols[0]
    # 旧DBの文字コード変換(legacy_mssql)を効かせるため、加工せずに列を取得して並べ替えはPython側で行う
    ssc.execute(f"SELECT [{first_col}], [{name_col}] FROM [{db}].[{sch}].[{tbl}]")
    rows = ssc.fetchall()
    try:
        rows.sort(key=lambda r: (r[0] is None, r[0]))
    except TypeError:
        pass
    return name_col, [r[1] for r in rows]


def _values_from_acc_tool(ssc, col):
    from collections import Counter
    ssc.execute(f"SELECT [{col}] FROM ACC_Tool")
    cnt = Counter()
    for (v,) in ssc.fetchall():
        sv = str(v).strip() if v is not None else ""
        if sv:
            cnt[sv] += 1
    return [v for v, _ in sorted(cnt.items(), key=lambda x: (-x[1], x[0]))]


def seed(pg, ss, log=print, dry_run=False):
    """空の加工リストマスタ表にだけ候補を投入する。pg=新DB接続, ss=旧imotomc接続(legacy_mssql.wrap済み)"""
    cur = pg.cursor()
    ssc = ss.cursor()
    legacy_tables = None
    total = 0
    for table, legacy_name, acc_col in PLAN:
        cur.execute(f"SELECT COUNT(*), COUNT(*) FILTER (WHERE is_active) FROM {table}")
        cnt, active = cur.fetchone()
        if cnt > 0:
            log(f"[加工リストマスタ] {table}: 登録済み {cnt}件(有効 {active}件) → 投入しない")
            continue
        if legacy_tables is None:
            legacy_tables = _find_legacy_tables(ssc, log)
        src = legacy_tables.get(legacy_name.lower())
        values = []
        if src:
            name_col, values = _values_from_legacy_table(ssc, *src)
            src_desc = f"旧候補テーブル {src[0]}.{src[1]}.{src[2]}.{name_col}"
        if not values:
            values = _values_from_acc_tool(ssc, acc_col)
            src_desc = f"旧ACC_Tool.{acc_col} の使用値(使用件数順)"
        rows, skipped = [], []
        for v in values:
            s = str(v or "").strip()
            if not s:
                continue
            if len(s) > NAME_MAX:
                skipped.append(s)
                continue
            rows.append(s)
        rows, merged = merge_width_variants(rows)
        if merged:
            log(f"[加工リストマスタ]   全角/半角違いをまとめた: {sum(len(m) for _, m in merged)}件 "
                f"(例: {', '.join(f'{k}←{"/".join(m)}' for k, m in merged[:5])})")
        if dry_run:
            log(f"[加工リストマスタ] {table}: 0件 → {len(rows)}件 投入予定(取得元: {src_desc}, dry-run)")
            continue
        for i, name in enumerate(rows, start=1):
            cur.execute(
                f"INSERT INTO {table} (name, sort_order, is_active, created_at, updated_at) "
                f"VALUES (%s, %s, TRUE, NOW(), NOW())", (name, min(i, 32767)))
        total += len(rows)
        log(f"[加工リストマスタ] {table}: 0件 → {len(rows)}件 投入(取得元: {src_desc})")
        if skipped:
            log(f"[加工リストマスタ]   {NAME_MAX}文字を超えるため除外: {len(skipped)}件 {skipped[:5]}", "WARN")
    if not dry_run:
        pg.commit()
    log(f"[加工リストマスタ] 投入合計: {total}件")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import nc_full_import_v2 as NC
    pg = NC.pg_connect()
    ss = NC.ss_connect()
    try:
        seed(pg, ss, log=lambda m, lv="INFO": print(m), dry_run=args.dry_run)
    finally:
        pg.close()
        ss.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
