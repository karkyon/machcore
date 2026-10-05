#!/usr/bin/env python3
# coding: utf-8
"""
旧SQL Server(imotomc/imotodb/NC)からの取得文字列の文字化け補正ヘルパー。

旧DBの一部列(例: v_旧部品マスタ.主機種型式)はLatin系照合順序の非Unicode列に
Shift_JIS(CP932)のバイト列がそのまま格納されており、pymssql(FreeTDS)経由で
取得するとLatin-1/CP1252として解釈され「\x83J\x83C...」のような化けた文字列になる
(画面上は「□i□J□C□^□b□N□j」等)。
取得後の文字列をバイト列へ戻してCP932で再デコードすることで復元する。

誤補正防止のため、以下のいずれかを満たす場合のみ補正する:
  - C1制御文字(U+0080-U+009F)またはCP1252固有記号を含む(SJIS全角の先行バイト由来)
  - U+00A1-U+00DFの文字が2文字以上連続(SJIS半角カナ由来)
かつ、全文字が1バイトに戻せてCP932として正しくデコードできること。
正常な日本語(漢字・かな等U+0100以上を含む)やASCIIのみの文字列は一切変更しない。
"""
import re

_CP1252_REV = {}
for _b in range(0x80, 0xA0):
    try:
        _CP1252_REV[bytes([_b]).decode("cp1252")] = _b
    except UnicodeDecodeError:
        pass

_KANA_RUN = re.compile(r"[\u00A1-\u00DF]{2,}")


def _to_bytes(s):
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if o < 0x100:
            out.append(o)
        elif ch in _CP1252_REV:
            out.append(_CP1252_REV[ch])
        else:
            return None
    return bytes(out)


def fix_mojibake(s):
    if not isinstance(s, str) or not s:
        return s
    if all(ord(c) < 0x80 for c in s):
        return s
    has_c1 = any(0x80 <= ord(c) <= 0x9F or c in _CP1252_REV for c in s)
    if not (has_c1 or _KANA_RUN.search(s)):
        return s
    b = _to_bytes(s)
    if b is None:
        return s
    try:
        return b.decode("cp932")
    except UnicodeDecodeError:
        return s


def fix_row(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return {k: fix_mojibake(v) for k, v in row.items()}
    return tuple(fix_mojibake(v) for v in row)


class _FixCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return fix_row(self._cur.fetchone())

    def fetchall(self):
        return [fix_row(r) for r in self._cur.fetchall()]

    def fetchmany(self, *a, **kw):
        return [fix_row(r) for r in self._cur.fetchmany(*a, **kw)]

    def __iter__(self):
        for r in self._cur:
            yield fix_row(r)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _FixConn:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *a, **kw):
        return _FixCursor(self._conn.cursor(*a, **kw))

    def __getattr__(self, name):
        return getattr(self._conn, name)


def wrap_connection(conn):
    """pymssql接続をラップし、全取得行の文字列に fix_mojibake を適用する"""
    return _FixConn(conn)


if __name__ == "__main__":
    _sample = "\x81i\x83J\x83C\x83^\x83b\x83N\x81j"
    print(repr(_sample), "->", fix_mojibake(_sample))
