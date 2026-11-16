#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
master_guard.py — コンバート(mc_full_import.py / nc_full_import_v2.py)が
「整備済みのマスタ(利用者 users / 機械 machines)」を消したり書き換えたりしないための安全装置。

  ① 接続ガード : guarded_connect() が返す接続は、users / machines への
                 DELETE / TRUNCATE / INSERT / UPDATE / ALTER / DROP を実行前に拒否する(SQLを流す前に例外)。
                 ※ 他の表の DELETE が外部キーの CASCADE で users/machines に波及する事故も、
                    下の②で検出する。
  ② 実行前後の照合 : snapshot() で users / machines の全行の指紋(件数+内容のMD5)を取り、
                 verify_unchanged() で実行後に同じか確認する。違えば例外(コンバート失敗として扱う)。
                 ※ 書き込み中にトランザクションがコミットされた後の検出になるため、
                    コンバート前に pg_dump / sync_masters_from_11.py のバックアップを推奨。

利用者・機械を意図して変える場合は、管理画面か scripts/sync_masters_from_11.py を使う(コンバートでは変更しない)。
"""
import re
import hashlib

PROTECTED_TABLES = ("users", "machines")

# users / machines に対する書き込み系SQL(スキーマ修飾・引用符・ONLY・IF EXISTS を許容)
_T = r'(?:public\.)?"?(?:' + "|".join(PROTECTED_TABLES) + r')"?'
_WRITE_RE = re.compile(
    r'^\s*(?:'
    r'DELETE\s+FROM\s+(?:ONLY\s+)?' + _T +
    r'|TRUNCATE\s+(?:TABLE\s+)?(?:ONLY\s+)?(?:[\w."]+\s*,\s*)*' + _T +
    r'|INSERT\s+INTO\s+' + _T +
    r'|UPDATE\s+(?:ONLY\s+)?' + _T +
    r'|ALTER\s+TABLE\s+(?:ONLY\s+|IF\s+EXISTS\s+)*' + _T +
    r'|DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:[\w."]+\s*,\s*)*' + _T +
    r')(?![\w"])',
    re.IGNORECASE)
_TRUNC_CASCADE_RE = re.compile(r'^\s*TRUNCATE\b.*\bCASCADE\b', re.IGNORECASE | re.DOTALL)


class MasterProtectedError(RuntimeError):
    pass


def check_sql(sql):
    s = sql.decode("utf-8", "replace") if isinstance(sql, (bytes, bytearray)) else str(sql)
    if _WRITE_RE.match(s) or _TRUNC_CASCADE_RE.match(s):
        raise MasterProtectedError(
            "[master_guard] 利用者(users)・機械(machines)マスタへの書き込み/削除はコンバートでは禁止です: "
            + " ".join(s.split())[:120])


def guarded_connect(dsn):
    """users / machines への書き込みSQLを拒否する psycopg2 接続を返す"""
    import psycopg2
    from psycopg2.extensions import cursor as _Cursor

    class _GuardedCursor(_Cursor):
        def execute(self, query, vars=None):
            check_sql(query if isinstance(query, (str, bytes, bytearray)) else self.mogrify(query, vars))
            return super().execute(query, vars)

        def executemany(self, query, vars_list):
            check_sql(query)
            return super().executemany(query, vars_list)

    return psycopg2.connect(dsn, cursor_factory=_GuardedCursor)


def snapshot(pg):
    """users / machines の件数と全行の指紋(MD5)。読み取りのみ。"""
    cur = pg.cursor()
    snap = {}
    for t in PROTECTED_TABLES:
        cur.execute(f"SELECT COUNT(*), COALESCE(MD5(string_agg(j::text, E'\\n' ORDER BY j::text)), '') FROM (SELECT to_jsonb(x) - 'updated_at' AS j FROM {t} x) q")
        n, h = cur.fetchone()
        snap[t] = (int(n), h)
    pg.rollback()  # 読み取りだけなので開いたトランザクションを閉じる
    return snap


def log_snapshot(log, snap, label):
    for t, (n, h) in snap.items():
        log(f"[master_guard] {label}: {t} {n}件 指紋={h[:12]}")


def verify_unchanged(pg, before, log=print):
    after = snapshot(pg)
    bad = [t for t in PROTECTED_TABLES if after[t] != before[t]]
    for t in PROTECTED_TABLES:
        log(f"[master_guard] 実行後: {t} {after[t][0]}件 指紋={after[t][1][:12]} "
            f"({'変更なし' if t not in bad else '★変更あり★'})")
    if bad:
        raise MasterProtectedError(
            f"[master_guard] コンバート中に {', '.join(bad)} が変化しました。"
            "外部キーのCASCADE等による削除の可能性があります。直ちにバックアップから復元してください。")
    return after
