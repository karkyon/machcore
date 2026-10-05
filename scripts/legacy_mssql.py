#!/usr/bin/env python3
# coding: utf-8
"""
legacy_mssql.py — 旧SQL Server(192.168.1.9: imotomc / imotodb)読み出し共通層

【文字化けの根本原因(2026-10-05 旧DB実データで確定)】
旧DBの非Unicode列(char/varchar/text)は日本語照合(コードページ932)で正しく定義され、
Shift_JISバイト列が格納されている。しかし pymssql(FreeTDS)がこのサーバ上で
コードページ932の変換を行えず、1バイト=1文字(Latin-1)として返していた。
その結果「（カイタック）」(81 69 83 4A ...)が「\x81i\x83J...」となり
画面上「□i□J□C□^□b□N□j」と化けていた。

【本モジュールの対処(型情報に基づく確定処理・推測なし)】
1. 実行するSELECTごとに sp_describe_first_result_set で結果列の
   型・照合順序をSQL Server自身に問い合わせる。
2. 非Unicode型の列は照合順序に関係なく常に CAST(... AS VARBINARY(MAX)) で
   生バイトのまま取得し、その列の照合順序のコードページ(932→cp932等)で
   Python側がデコードする。FreeTDSの文字コード変換は一切経由させない。
   Unicode型・数値・日付列は従来どおりそのまま取得。
3. Unicode型(nchar/nvarchar/ntext)列に、正規の文字列では絶対に出現しない
   C1制御文字(U+0080-U+009F)が含まれる場合は、旧Access側でSJISバイトが
   1バイト=1文字として保存されてしまったデータであるため、バイト列に戻して
   CP932で復元する。
4. 旧データの改行コード CR+LF(\\r\\n) および単独CR を、新システム標準の LF(\\n) に統一する
   (Web画面入力はLF。CRが残ると帳票PDFの行分割等で改行位置が崩れるため)。
処理内容は列単位で標準出力に記録する。
"""
import re

_CODEPAGE_CACHE = {}
_UNICODE_TYPES = ("nchar", "nvarchar", "ntext")
_NONUNI_TYPES = ("char", "varchar", "text")
_C1 = re.compile("[\u0080-\u009f]")

_CP1252_REV = {}
for _b in range(0x80, 0xA0):
    try:
        _CP1252_REV[bytes([_b]).decode("cp1252")] = _b
    except UnicodeDecodeError:
        pass

STATS = {"binary_columns": {}, "decode_errors": 0, "unicode_repaired": 0, "unicode_unrepairable": 0,
         "newline_normalized": 0}


def _normalize_newlines(s):
    """CR+LF / 単独CR → LF(新システム標準の改行)"""
    if "\r" not in s:
        return s
    STATS["newline_normalized"] += 1
    return s.replace("\r\n", "\n").replace("\r", "\n")


class LegacyCharsetError(RuntimeError):
    pass


def _base_type(system_type_name):
    return (system_type_name or "").split("(")[0].strip().lower()


def _codec_for_codepage(cp):
    """SQL Serverの照合順序コードページ → Pythonコーデック名"""
    if cp in (None, 0, 932):
        return "cp932"
    try:
        import codecs
        codecs.lookup(f"cp{cp}")
        return f"cp{cp}"
    except LookupError:
        return "cp932"


def _decode_bytes(b, codec):
    try:
        return bytes(b).decode(codec)
    except UnicodeDecodeError:
        STATS["decode_errors"] += 1
        return bytes(b).decode(codec, errors="replace")


def _repair_stored_unicode(s):
    """Unicode列に1バイト=1文字で保存されたSJISを復元(C1制御文字を含む場合のみ)"""
    if not isinstance(s, str) or not _C1.search(s):
        return s
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if o < 0x100:
            out.append(o)
        elif ch in _CP1252_REV:
            out.append(_CP1252_REV[ch])
        else:
            STATS["unicode_unrepairable"] += 1
            return s
    try:
        r = bytes(out).decode("cp932")
    except UnicodeDecodeError:
        STATS["unicode_unrepairable"] += 1
        return s
    STATS["unicode_repaired"] += 1
    return r


def _find_top_level_order_by(sql):
    """括弧・[]・''の外側にある最後の ORDER BY の開始位置を返す(無ければ-1)"""
    depth = 0
    i = 0
    n = len(sql)
    last = -1
    in_br = in_q = False
    while i < n:
        c = sql[i]
        if in_br:
            if c == "]":
                in_br = False
        elif in_q:
            if c == "'":
                in_q = False
        elif c == "[":
            in_br = True
        elif c == "'":
            in_q = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and c in "oO":
            m = re.match(r"ORDER\s+BY\b", sql[i:], re.I)
            if m and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_")):
                last = i
        i += 1
    return last


_SELECT_HEAD = re.compile(
    r"^\s*SELECT\s+(?P<distinct>DISTINCT\s+)?(?P<top>TOP\s*(?:\(\s*\d+\s*\)|\d+)(?:\s+PERCENT)?\s+)?",
    re.I,
)


def build_binary_rewrite(sql, names, binary_idx):
    """元SQLを派生表で包み、binary_idx列だけVARBINARY(MAX)で取り出すSQLを返す。
    元の並び順(ORDER BY)はROW_NUMBER()で厳密に保持する。"""
    if any(not nm for nm in names):
        raise LegacyCharsetError("列名の無い結果列があるため変換できません(SELECT句に別名を付けてください)")
    if len(set(names)) != len(names):
        raise LegacyCharsetError(f"結果列名が重複しているため変換できません: {names}")
    s = sql.strip().rstrip(";").strip()
    head = _SELECT_HEAD.match(s)
    if not head:
        raise LegacyCharsetError("SELECT文として解析できません")
    pos = _find_top_level_order_by(s)
    order_by = ""
    core = s
    if pos >= 0:
        order_by = re.sub(r"^ORDER\s+BY\s+", "", s[pos:], flags=re.I).strip()
        if head.group("distinct"):
            raise LegacyCharsetError("DISTINCTとORDER BYの併用は変換できません")
        if not head.group("top"):
            core = s[:pos].rstrip()
        rest = core[head.end():]
        core = core[:head.end()] + f"ROW_NUMBER() OVER (ORDER BY {order_by}) AS [__lc_rn], " + rest
    cols = []
    for i, nm in enumerate(names):
        q = "[" + nm.replace("]", "]]") + "]"
        cols.append(f"CAST(__lc.{q} AS VARBINARY(MAX)) AS {q}" if i in binary_idx else f"__lc.{q}")
    out = f"SELECT {', '.join(cols)} FROM ({core}) AS __lc"
    if order_by:
        out += " ORDER BY __lc.[__lc_rn]"
    return out


class _LegacyCursor:
    def __init__(self, owner, cur):
        self._owner = owner
        self._cur = cur
        self._bin = set()
        self._uni = set()
        self._codec = {}

    def execute(self, sql, params=None):
        self._bin, self._uni, self._codec = set(), set(), {}
        if params is not None:
            return self._cur.execute(sql, params)
        meta = self._owner.describe(sql)
        if meta is None:
            return self._cur.execute(sql)
        names = [m["name"] for m in meta]
        need = set()
        for i, m in enumerate(meta):
            bt = _base_type(m["type"])
            if bt in _UNICODE_TYPES:
                self._uni.add(i)
            elif bt in _NONUNI_TYPES:
                # FreeTDSにコードページ変換をさせず、常に生バイト取得→列のコードページでデコード
                need.add(i)
                self._codec[i] = _codec_for_codepage(self._owner.codepage(m["collation"]))
        if not need:
            return self._cur.execute(sql)
        rewritten = build_binary_rewrite(sql, names, need)
        key = re.sub(r"\s+", " ", sql.strip())[:80]
        cols = [f"{names[i]}({self._codec[i]})" for i in sorted(need)]
        if STATS["binary_columns"].get(key) != cols:
            STATS["binary_columns"][key] = cols
            print(f"[legacy_mssql] 非Unicode列を生バイト取得→コードページでデコード: {key} → {', '.join(cols)}")
        self._bin = need
        return self._cur.execute(rewritten)

    def _fix(self, row):
        if row is None:
            return row
        out = list(row)
        for i in self._bin:
            if isinstance(out[i], (bytes, bytearray)):
                out[i] = _decode_bytes(out[i], self._codec.get(i, "cp932"))
        for i in self._uni:
            if isinstance(out[i], str):
                out[i] = _repair_stored_unicode(out[i])
        # 旧データの改行(CR+LF/CR)を全文字列列でLFに統一
        for i, v in enumerate(out):
            if isinstance(v, str):
                out[i] = _normalize_newlines(v)
        return tuple(out)

    def fetchone(self):
        return self._fix(self._cur.fetchone())

    def fetchall(self):
        return [self._fix(r) for r in self._cur.fetchall()]

    def fetchmany(self, *a, **kw):
        return [self._fix(r) for r in self._cur.fetchmany(*a, **kw)]

    def __iter__(self):
        for r in self._cur:
            yield self._fix(r)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class LegacyConnection:
    def __init__(self, raw):
        self._raw = raw

    def codepage(self, collation):
        if not collation:
            return None
        if collation not in _CODEPAGE_CACHE:
            c = self._raw.cursor()
            c.execute("SELECT CONVERT(int, COLLATIONPROPERTY(N'" + collation.replace("'", "''") + "', 'CodePage'))")
            r = c.fetchone()
            _CODEPAGE_CACHE[collation] = r[0] if r else None
        return _CODEPAGE_CACHE[collation]

    def describe(self, sql):
        c = self._raw.cursor()
        try:
            c.execute("EXEC sp_describe_first_result_set @tsql = N'" + sql.replace("'", "''") + "'")
            idx = {d[0]: k for k, d in enumerate(c.description)}
            rows = c.fetchall()
        except Exception as e:
            print(f"[legacy_mssql] WARN 結果列メタデータ取得失敗のため通常取得します: {e}")
            return None
        meta = []
        for r in sorted(rows, key=lambda r: r[idx["column_ordinal"]]):
            if r[idx["is_hidden"]]:
                continue
            meta.append({"name": r[idx["name"]], "type": r[idx["system_type_name"]],
                         "collation": r[idx["collation_name"]]})
        return meta

    def cursor(self, *a, **kw):
        return _LegacyCursor(self, self._raw.cursor(*a, **kw))

    def __getattr__(self, name):
        return getattr(self._raw, name)


def wrap(raw_connection):
    return LegacyConnection(raw_connection)


def connect(server, user, password, database):
    import pymssql
    return wrap(pymssql.connect(server=server, user=user, password=password,
                                database=database, tds_version="7.4"))


def report_lines():
    lines = [f"非Unicode列を生バイト取得→コードページデコードしたクエリ数: {len(STATS['binary_columns'])}"]
    for k, v in STATS["binary_columns"].items():
        lines.append(f"  {k} → {', '.join(v)}")
    lines.append(f"デコード不能バイト列(置換文字で取得): {STATS['decode_errors']}件")
    lines.append(f"Unicode列の破損データ復元: {STATS['unicode_repaired']}件 / 復元不能: {STATS['unicode_unrepairable']}件")
    lines.append(f"改行コード CR+LF/CR → LF 統一: {STATS['newline_normalized']}件")
    return lines
