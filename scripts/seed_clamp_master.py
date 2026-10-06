#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_clamp_master.py — クランプ マスタ(アイテム選択の候補)の初期投入(再利用スクリプト)

MC「変更・登録」画面の「クランプ アイテム選択」は、バイス/敷板/チャック/爪/インデックスの候補を
clamp_vise / clamp_shiki / clamp_chuck / clamp_tsume / clamp_index から表示する(GET /mc/clamp-master)。
これらのテーブルが空だと、リストが「— なし —」だけになりクランプを選べない。

このスクリプトは、旧ACCESSのアイテムフォームの候補(画面 apps/web/app/mc/[mc_id]/edit/page.tsx の
フォールバック一覧と同一の内容)を、空のテーブルにだけ投入する。
既に1件でも登録があるテーブルには何もしない(管理画面 /admin/clamp-master での追加・修正を上書きしない)。

実行方法:
  python3 scripts/seed_clamp_master.py            # 空のテーブルに投入
  python3 scripts/seed_clamp_master.py --dry-run  # 件数確認のみ
接続先: apps/api/.env の DATABASE_URL(環境変数 MACHCORE_PG_DSN があればそちらを優先)
"""
import os
import re
import sys
import argparse
from pathlib import Path

VISE = [  # (名称, 型式, メーカー)
    ("バイス 150×45", "VG-150", "津田駒工業株式会社"),
    ("バイス 200×55", "VG-200", "津田駒工業株式会社"),
    ("高バイス 175×100", "VT-175", "津田駒工業株式会社"),
    ("大バイス 300×100", "VB-300", "津田駒工業株式会社"),
    ("油圧バイス 175×60", "VH-175", "津田駒工業株式会社"),
    ("4連バイス 100×75", "VM-100-4", "津田駒工業株式会社"),
    ("バイス 125×40", "VG-125", "津田駒工業株式会社"),
    ("バイス 100×35", "VG-100", "津田駒工業株式会社"),
    ("VOX160 159.5×45", "VQX160", "北川鉄工所株式会社"),
    ("ロックタイト精密マシンバイス 15", "LTFV-150H", "ナベヤ"),
    ("ロックタイト5軸マシンバイス 102", "LT5AU100M", "ナベヤ"),
    ("ロックタイト精密マシンバイス 16", "LTCV160H", "ナベヤ"),
]
SHIKI = ["50×60", "50×70", "50×80", "50×90", "50×100", "100×50", "100×60", "100×80"]
CHUCK = [  # (名称, サイズ, メーカー)
    ("2連チャック#12", "12インチ", "SOUL"),
    ("2連チャック#6", "6インチ", "SOUL"),
    ("2連チャック#7", "7インチ", "SOUL"),
    ("2連チャックAタイプ", "7インチ", None),
    ("2連チャックBタイプ", "7インチ", None),
    ("2連チャックCタイプ", "7インチ", None),
    ("2連チャックDタイプ", "7インチ", None),
    ("2連チャック生爪2", "7インチ", None),
    ("4連チャック#5", "5インチ", "KITAGAWA"),
    ("4連チャック#6", "6インチ", "SOUL"),
    ("4連チャックAタイプ", "5インチ", "SOUL"),
    ("4連チャックBタイプ", "4インチ", "C"),
    ("チャック 10インチ", "10インチ", "SOUL"),
    ("チャック 12インチ", "12インチ", "SOUL"),
    ("チャック 12インチ", "12インチ", "KITAGAWA"),
    ("チャック 18インチ", "18インチ", None),
    ("チャック 8インチ", "8インチ", None),
    ("チャック 4インチ", "4インチ", "SOUL"),
    ("チャック 5インチ", "5インチ", "SOUL"),
    ("チャック 6インチ", "6インチ", "SOUL"),
    ("チャック 7インチ", "7インチ", "SOUL"),
    ("チャック 9インチ", "9インチ", "SOUL"),
    ("チャック K-1", "4インチ", "KITAGAWA"),
    ("チャック K-2", "4インチ", "KITAGAWA"),
    ("チャック SC-8A", "8インチ", "大和工機株式会社"),
    ("チャック マルチ S-1", "4インチ", "SOUL"),
    ("チャック マルチ S-2", "4インチ", "SOUL"),
    ("チャック マルチ S-3", "4インチ", "SOUL"),
]
TSUME = ["標準爪", "生爪", "逆爪", "ソフトジョー", "特殊爪"]
INDEX = [  # (名称, 搭載機, 型式)
    ("5AX-200Ⅱ", "MC10(常時)", "5AX-200Ⅱ Wc≦21"),
    ("5AX-220Ⅱ", "MC10(常時)", "5AX-220Ⅱ Wc≦21"),
    ("CNC-200F MC1", "MC1", "CNC-200F"),
    ("CNC-230-DC OKK2", "不動", "CNC-230-DC"),
    ("インデックス MC12", "MC12(専用)", "RNCV-201R"),
    ("インデックス MC13", "MC13(専用)", "RB-250"),
    ("インデックス MC16", "MC16(専用)", "RB-250R"),
    ("インデックス MC3", "MC3(常時)", "RNCV-201R"),
    ("インデックス MC4", "MC4(常時)", "RNCV-201R"),
    ("インデックス MC5", "MC5(常時)", "CNC-200F"),
    ("インデックス MC6", "MC6(常時)", "MD 300"),
    ("インデックス MC7", "MC7(専用)", "CNC-200FA"),
    ("インデックス OKK1", "OKK1(常時)", "CNC-150α"),
    ("インデックス PS1", "PS-1(常時)", "RZ-150R"),
    ("インデックス RN-200R", "MC9", "RN-200R"),
    ("インデックス RNCV-201R", "MC7(一時)", "RNCV-201R"),
    ("マルチ1", "OFF", "5AX-4MT-120"),
    ("マルチ2 → マルチ4", "MC11(常時)", "5AX-4MT-120"),
    ("マルチ3", "OFF", "5AX-4MT-120"),
    ("マルチ4", "MC11(常時)", "5AX-4MT-120"),
]

# テーブル → (列, 行データ)
PLAN = [
    ("clamp_vise",  ("name", "model", "maker"),   VISE),
    ("clamp_shiki", ("name",),                    [(v,) for v in SHIKI]),
    ("clamp_chuck", ("name", "size", "maker"),    CHUCK),
    ("clamp_tsume", ("name",),                    [(v,) for v in TSUME]),
    ("clamp_index", ("name", "machine", "model"), INDEX),
]


def load_pg_dsn():
    ov = os.environ.get("MACHCORE_PG_DSN")
    if ov:
        return ov.split("?", 1)[0]
    env = Path(__file__).resolve().parent.parent / "apps" / "api" / ".env"
    with open(env, encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^DATABASE_URL="?([^"\n]*)"?$', line.strip())
            if m:
                return m.group(1).split("?", 1)[0]
    raise RuntimeError(f"DATABASE_URL not found in {env}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import psycopg2
    pg = psycopg2.connect(load_pg_dsn())
    cur = pg.cursor()
    total = 0
    for table, cols, rows in PLAN:
        cur.execute(f"SELECT COUNT(*), COUNT(*) FILTER (WHERE is_active) FROM {table}")
        cnt, active = cur.fetchone()
        if cnt > 0:
            print(f"[クランプマスタ] {table}: 登録済み {cnt}件(有効 {active}件) → 投入しない")
            continue
        if args.dry_run:
            print(f"[クランプマスタ] {table}: 0件 → {len(rows)}件 投入予定(dry-run)")
            continue
        col_sql = ", ".join(cols)
        ph = ", ".join(["%s"] * len(cols))
        for i, r in enumerate(rows, start=1):
            cur.execute(
                f"INSERT INTO {table} ({col_sql}, sort_order, is_active, created_at, updated_at) "
                f"VALUES ({ph}, %s, TRUE, NOW(), NOW())",
                tuple(r) + (i,))
        total += len(rows)
        print(f"[クランプマスタ] {table}: 0件 → {len(rows)}件 投入")
    if not args.dry_run:
        pg.commit()
    pg.close()
    print(f"[クランプマスタ] 投入合計: {total}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
