#!/usr/bin/env python3
"""
imotodb → machcore parts テーブル同期スクリプト
対象: 図面番号, 名称, 主機種型式, 得意先名(client_name)
実行: python3 scripts/sync_parts.py
cron例: 0 2 * * * /home/karkyon/.nvm/versions/node/$(node -v)/bin/python3 /home/karkyon/projects/machcore/scripts/sync_parts.py >> /home/karkyon/projects/machcore/logs/sync_parts.log 2>&1
"""
import pymssql, psycopg2, sys, os, re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from datetime import datetime

print(f"[{datetime.now()}] parts同期開始")

try:
    src = pymssql.connect(server='192.168.1.9', user='sa', password='RTW65b', database='imotodb', tds_version='7.4')
    sc = src.cursor()
    sc.execute("""
        SELECT p.[部品ID], p.[図面番号], p.[名称], p.[主機種型式], t.[会社名]
        FROM [dbo].[v_旧部品マスタ] p
        LEFT JOIN [dbo].[v_旧得意先マスタ] t ON p.[納入先ID] = t.[納入先ID]
    """)
    rows = sc.fetchall()
    src.close()
    print(f"旧DB取得: {len(rows)}件")
except Exception as e:
    print(f"旧DB接続エラー: {e}", file=sys.stderr)
    sys.exit(1)

try:
    # [BUGFIX] 単一インスタンス時代の接続先決め打ちを廃止。
    # DATABASE_URL(環境変数、無ければ apps/api/.env)から自動判定することで、
    # machcore-internal / machcore-group のどちらで実行しても、実行した
    # インスタンス自身の正しいDBに同期されるようにする。
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'apps', 'api', '.env')
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as ef:
                for line in ef:
                    m = re.match(r'^DATABASE_URL=["\']?([^"\'\n]+)', line)
                    if m:
                        database_url = m.group(1)
                        break
    if not database_url:
        print('DATABASE_URL が見つかりません(環境変数 or apps/api/.env)', file=sys.stderr)
        sys.exit(1)
    # [BUGFIX] DATABASE_URLの `?schema=public` はPrisma独自のクエリパラメータで、
    # libpq(psycopg2)は認識できずinvalid dsnエラーになる。libpqが実際に認識する
    # パラメータだけ残し、Prisma独自のものは除去してから接続する。
    _ALLOWED_LIBPQ_PARAMS = {
        'sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'connect_timeout',
        'application_name', 'target_session_attrs',
    }
    _parsed = urlparse(database_url)
    _qs = parse_qs(_parsed.query)
    _kept = {k: v for k, v in _qs.items() if k in _ALLOWED_LIBPQ_PARAMS}
    clean_dsn = urlunparse(_parsed._replace(query=urlencode(_kept, doseq=True)))
    dst = psycopg2.connect(clean_dsn)
    dc = dst.cursor()

    inserted = updated = 0
    for part_id, drawing_no, name, main_model, client_name in rows:
        pid   = str(part_id).strip()
        dno   = (drawing_no  or '').strip()
        nm    = (name        or '').strip()
        mm    = (main_model  or '').strip() or None
        cn    = (client_name or '').strip() or None

        dc.execute("SELECT id FROM parts WHERE part_id=%s", (pid,))
        row = dc.fetchone()
        if row:
            dc.execute("""
                UPDATE parts SET drawing_no=%s, name=%s, main_model=%s, client_name=%s, synced_at=NOW()
                WHERE part_id=%s
            """, (dno, nm, mm, cn, pid))
            updated += 1
        else:
            dc.execute("""
                INSERT INTO parts (part_id, drawing_no, name, main_model, client_name, synced_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (pid, dno, nm, mm, cn))
            inserted += 1

    dst.commit()
    dst.close()
    print(f"新規追加: {inserted}件 / 更新: {updated}件")
    print(f"[{datetime.now()}] 同期完了")
except Exception as e:
    print(f"新DB書き込みエラー: {e}", file=sys.stderr)
    sys.exit(1)
