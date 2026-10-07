#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deploy_14.py — 192.168.1.14 の internal / group 両インスタンスへ、最新コードの展開と
                旧システムからのデータコンバートを行う再利用スクリプト

  .11(UAT)で直したプログラム・コンバートを、.14 の 2 インスタンスへ同じように当てる。
  2 インスタンスはコード・コンバート規則は同じで、次は別々に持つ(混ざると事故になるもの)。

    項目                 internal                              group
    -------------------  ------------------------------------  ------------------------------------
    リポジトリ           ~/projects/machcore-internal          ~/projects/machcore-group
    pm2 設定 / 名前      ecosystem.internal.config.js          ecosystem.group.config.js
                         machcore-api / machcore-web           machcore-group-api / machcore-group-web
    DB                   machcore_internal (5440)              machcore_group (5441)
    API / Web / https    3011 / 3010 / 8443                    3021 / 3020 / 8543
    ファイル格納先       ~/machcore-storage/internal           ~/machcore-storage/group
    Web の API 転送先    apps/web/.env.production API_PORT     (ビルド時に焼き込まれる。group は 3021 必須)

モード(--mode):
  check    読むだけ。両インスタンスの設定・DB・マスタ・旧DB/旧ファイル・cron・nginx・pm2 を点検し、
           コンバートで消えるデータの件数も出す(既定)
  deploy   DBバックアップ → 最新コード(origin/main) → DBスキーマ同期(削除を伴う差分なら止める)
           → 型チェック(エラー0件のときだけ) → ビルド → pm2 再起動 → 動作確認 → 部品同期cron
  convert  DBバックアップ → (group)マスタ補完 → [--with-test]コンバート試験 → pm2停止
           → MC/NC フルコンバート+.WPD統一+新旧検証 → 作業記録の全件検証 → pm2 再開 → 動作確認
  all      check → deploy → convert

実行例(どちらのリポジトリから実行してもよい。先にそのリポジトリを最新にしてから):
  cd ~/projects/machcore-internal && git fetch origin && git reset --hard origin/main \\
    && python3 scripts/deploy_14.py --env both --mode check
  cd ~/projects/machcore-internal && python3 scripts/deploy_14.py --env both --mode all

オプション:
  --env internal|group|both   対象(既定 both。both は internal → group の順に実行)
  --with-test                 本番コンバートの前に run_conversion_test.py(試験用DBでの試験)を行い、NGなら止める
  --no-copy-masters           group の機械・担当者マスタを internal から補完しない
  --internal-masters-from DSN internal に無い機械・担当者を別DB(例 .11 の machcore_dev)から補完する
  --accept-data-loss          スキーマ同期で列やテーブルの削除を伴う差分があっても進める(通常は使わない)
  --skip-backup               DBバックアップを取らない(通常は使わない)

出力:
  画面と ~/machcore-deploy-logs/deploy14_日時.log、各リポジトリの scripts/verify_reports/deploy14_<env>_日時.md
  DBバックアップ: ~/machcore-backups/<env>/<db>_日時.dump
    戻し方: docker exec -i <コンテナ> pg_restore -U <user> -d <db> --clean --if-exists < <dump>
"""
import os
import re
import sys
import glob
import json
import shutil
import secrets
import argparse
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

HOME = Path.home()
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

ENVS = {
    "internal": {
        "label": "自社(internal)",
        "repo": HOME / "projects" / "machcore-internal",
        "eco": "ecosystem.internal.config.js",
        "pm2": ["machcore-api", "machcore-web"],
        "db": "machcore_internal",
        "db_port": 5440,
        "api_port": 3011,
        "web_port": 3010,
        "https_port": 8443,
        "cert_port": 9100,
        "storage": HOME / "machcore-storage" / "internal",
        "ua_dir": "/var/www/machcore-cert",
    },
    "group": {
        "label": "グループ会社(group)",
        "repo": HOME / "projects" / "machcore-group",
        "eco": "ecosystem.group.config.js",
        "pm2": ["machcore-group-api", "machcore-group-web"],
        "db": "machcore_group",
        "db_port": 5441,
        "api_port": 3021,
        "web_port": 3020,
        "https_port": 8543,
        "cert_port": 9200,
        "storage": HOME / "machcore-storage" / "group",
        "ua_dir": "/var/www/machcore-cert-group",
    },
}

# 子プロセスへ渡さない環境変数(他インスタンスのDB・ログ先を誤って使わないため)
POLLUTING_ENV = ("MACHCORE_PG_DSN", "MACHCORE_IMPORT_LOG_DIR", "DATABASE_URL", "SHADOW_DATABASE_URL",
                 "API_PORT", "PORT", "CORS_ORIGINS", "UPLOAD_AGENT_DIR")

LOG_DIR = HOME / "machcore-deploy-logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / f"deploy14_{TS}.log"
_logf = open(LOG_PATH, "a", encoding="utf-8")


class Abort(Exception):
    pass


def log(msg=""):
    print(msg, flush=True)
    _logf.write(msg + "\n")
    _logf.flush()


# ──────────────────────────────────────────────────────────────
# 実行環境(Python / Node)
# ──────────────────────────────────────────────────────────────
def _py_has_modules(py):
    try:
        r = subprocess.run([py, "-c", "import pymssql, psycopg2"], capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def ensure_python():
    """旧DB(pymssql)と新DB(psycopg2)の両方を読める Python で動かす。無ければ見つけて実行し直す"""
    try:
        import pymssql  # noqa: F401
        import psycopg2  # noqa: F401
        return
    except ImportError:
        pass
    cands = sorted(glob.glob(str(HOME / ".pyenv" / "versions" / "*" / "bin" / "python3")), reverse=True)
    cands += ["/usr/local/bin/python3", "/usr/bin/python3"]
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout if shutil.which("crontab") else ""
        cands += re.findall(r"(\S*python3?(?:\.\d+)?)\s+\S*sync_parts\.py", cron)
    except Exception:
        pass
    for py in cands:
        py = os.path.expandvars(py)
        if os.path.exists(py) and os.path.realpath(py) != os.path.realpath(sys.executable) and _py_has_modules(py):
            print(f"[INFO] pymssql/psycopg2 のある Python で実行し直します: {py}", flush=True)
            os.execv(py, [py] + sys.argv)
    print("[FAIL] pymssql と psycopg2 の両方を import できる Python が見つかりません。"
          "pip install pymssql psycopg2-binary を行ってから実行してください。", flush=True)
    sys.exit(1)


ensure_python()
import psycopg2  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from name_match import person_key, LEGACY_ALIASES  # noqa: E402
from machine_name_match import normalize_machine  # noqa: E402


def node_env():
    """Node v20 系(nvm)を PATH の先頭に置き、他インスタンス向けの環境変数を外した環境"""
    env = dict(os.environ)
    for k in POLLUTING_ENV:
        env.pop(k, None)
    v20 = sorted(glob.glob(str(HOME / ".nvm" / "versions" / "node" / "v20.*" / "bin")), reverse=True)
    pref = str(HOME / ".nvm" / "versions" / "node" / "v20.20.0" / "bin")
    path_bin = pref if os.path.isdir(pref) else (v20[0] if v20 else None)
    if path_bin:
        env["PATH"] = path_bin + os.pathsep + env.get("PATH", "")
    return env


ENV0 = node_env()


def sh_out(cmd):
    """外部コマンドの標準出力(コマンドが無ければ空)"""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _expand(x):
    return os.path.expandvars(os.path.expanduser(x.replace("$HOME", str(HOME))))


def sync_cron_entries():
    """crontab の部品同期行 → [(行, 対象リポジトリ, スクリプトの実パス or None, python)]"""
    res = []
    for l in sh_out(["crontab", "-l"]).splitlines():
        if "sync_parts" not in l or l.lstrip().startswith("#"):
            continue
        cd = re.search(r"\bcd\s+(\S+)", l)
        base = _expand(cd.group(1)) if cd else None
        sp = re.search(r"(\S*sync_parts\.py)", l)
        script = None
        if sp:
            t = _expand(sp.group(1))
            script = t if os.path.isabs(t) else (os.path.join(base, t) if base else None)
        repo = str(Path(script).resolve().parent.parent) if script else base
        m = re.search(r"(\S*python3?(?:\.\d+)?)\s", l)
        res.append((l, repo, script if script and os.path.exists(script) else None, _expand(m.group(1)) if m else None))
    return res


def sudo(cmd, label):
    """sudo で実行(パスワードを聞かれたら端末で入力)"""
    log(f"$ sudo {' '.join(cmd)}   ({label})")
    r = subprocess.run(["sudo"] + cmd)
    log(f"  → rc={r.returncode}")
    return r.returncode == 0


def which(cmd):
    return shutil.which(cmd, path=ENV0["PATH"])


def run(cmd, cwd=None, env=None, label=None, check=True, capture=True, timeout=None, stdout_file=None):
    shown = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
    if label:
        log(f"\n----- {label}")
    log(f"$ {shown}" + (f"   (cwd={cwd})" if cwd else ""))
    t0 = datetime.now()
    try:
        if stdout_file is not None:
            r = subprocess.run(cmd, cwd=cwd, env=env or ENV0, shell=isinstance(cmd, str), stdout=stdout_file,
                               stderr=subprocess.PIPE, text=True, timeout=timeout)
            out = r.stderr or ""
        elif capture:
            r = subprocess.run(cmd, cwd=cwd, env=env or ENV0, shell=isinstance(cmd, str), capture_output=True,
                               text=True, timeout=timeout)
            out = (r.stdout or "") + (r.stderr or "")
        else:
            p = subprocess.Popen(cmd, cwd=cwd, env=env or ENV0, shell=isinstance(cmd, str), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
            lines = []
            for line in p.stdout:
                line = line.rstrip("\n")
                log("  " + line)
                lines.append(line)
            p.wait(timeout=timeout)
            r = subprocess.CompletedProcess(cmd, p.returncode)
            out = "\n".join(lines)
    except subprocess.TimeoutExpired:
        raise Abort(f"{label or shown} が時間内に終わりませんでした")
    el = (datetime.now() - t0).total_seconds()
    if capture and out.strip() and stdout_file is None:
        tail = out.strip().splitlines()
        for line in tail[-40:]:
            log("  " + line)
    log(f"  → rc={r.returncode} ({el:.0f}秒)")
    if check and r.returncode != 0:
        raise Abort(f"{label or shown} が失敗しました(rc={r.returncode})")
    return r.returncode, out


# ──────────────────────────────────────────────────────────────
# 結果の記録
# ──────────────────────────────────────────────────────────────
class Report:
    def __init__(self, name):
        self.name = name
        self.items = []   # (level, title, detail)
        self.deploy_block = []   # deploy も止める NG(設定の取り違えなど)

    def add(self, level, title, detail="", stage="convert"):
        """level=NG の stage: "deploy"=展開もコンバートも止める / "convert"=コンバートだけ止める"""
        self.items.append((level, title, detail))
        if level == "NG" and stage == "deploy":
            self.deploy_block.append(title)
        mark = {"OK": "✓", "WARN": "△", "NG": "✗", "INFO": "・"}[level]
        log(f"  [{mark} {level}] {title}" + (f" — {detail}" if detail else ""))

    def ng(self):
        return [i for i in self.items if i[0] == "NG"]

    def warn(self):
        return [i for i in self.items if i[0] == "WARN"]

    def write(self, path, extra=""):
        lines = [f"# .14 {self.name} 展開・コンバート結果 ({TS})", "",
                 f"- NG: {len(self.ng())}件 / 注意: {len(self.warn())}件", "", "| 判定 | 項目 | 内容 |", "|---|---|---|"]
        for lv, t, d in self.items:
            lines.append(f"| {lv} | {t} | {str(d).replace('|', '/')} |")
        if extra:
            lines += ["", extra]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"\n[INFO] 結果を保存しました: {path}")


# ──────────────────────────────────────────────────────────────
# 設定ファイル
# ──────────────────────────────────────────────────────────────
def read_env_file(path):
    vals = {}
    if not path.exists():
        return vals
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^\s*([A-Z0-9_]+)\s*=\s*"?([^"\n]*)"?\s*$', line)
        if m:
            vals[m.group(1)] = m.group(2)
    return vals


def set_env_value(path, key, value):
    """KEY=value を書き換える(無ければ末尾に追記)。シンボリックリンクなら実体を書き換える"""
    real = Path(os.path.realpath(path))
    text = real.read_text(encoding="utf-8") if real.exists() else ""
    line = f'{key}="{value}"'
    if re.search(rf"^\s*{key}\s*=", text, re.M):
        text = re.sub(rf"^\s*{key}\s*=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    real.write_text(text, encoding="utf-8")


def dsn_of(cfg):
    url = read_env_file(cfg["repo"] / "apps" / "api" / ".env").get("DATABASE_URL")
    if not url:
        raise Abort(f"{cfg['repo']}/apps/api/.env に DATABASE_URL がありません")
    return url.split("?", 1)[0]


def connect(dsn):
    return psycopg2.connect(dsn)


def q1(c, sql, args=None):
    c.execute(sql, args)
    r = c.fetchone()
    return r[0] if r else None


def table_exists(c, name):
    return bool(q1(c, "SELECT to_regclass(%s) IS NOT NULL", (f"public.{name}",)))


def find_container(port):
    try:
        o = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return None
    for line in o.splitlines():
        name, _, ports = line.partition("\t")
        if f":{port}->" in ports:
            return name
    return None


# ──────────────────────────────────────────────────────────────
# nginx(読むだけ)
# ──────────────────────────────────────────────────────────────
def nginx_servers():
    """sites-enabled の server ブロックから listen / proxy_pass / root を取り出す"""
    res = []
    for f in sorted(glob.glob("/etc/nginx/sites-enabled/*")) + sorted(glob.glob("/etc/nginx/conf.d/*.conf")):
        try:
            txt = Path(f).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        txt = re.sub(r"#[^\n]*", "", txt)
        for m in re.finditer(r"\bserver\s*\{", txt):
            depth, i = 1, m.end()
            while i < len(txt) and depth:
                depth += {"{": 1, "}": -1}.get(txt[i], 0)
                i += 1
            body = txt[m.end():i]
            res.append({
                "file": f,
                "listen": [int(x) for x in re.findall(r"\blisten\s+(?:[\d.]+:)?(\d+)", body)],
                "proxy": re.findall(r"proxy_pass\s+([^;]+);", body),
                "root": re.findall(r"\b(?:root|alias)\s+([^;]+);", body),
            })
    return res


# ──────────────────────────────────────────────────────────────
# CHECK(読むだけ)
# ──────────────────────────────────────────────────────────────
def check(env, cfg, rep, other_cfg=None):
    log(f"\n{'=' * 70}\n[CHECK] {cfg['label']}  {cfg['repo']}\n{'=' * 70}")
    repo = cfg["repo"]
    if not (repo / ".git").is_dir():
        rep.add("NG", "リポジトリ", f"{repo} がありません", stage="deploy")
        return
    # ── git ──
    run(["git", "fetch", "origin", "main"], cwd=repo, check=False)
    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=False)[1].strip()
    orig = run(["git", "rev-parse", "--short", "origin/main"], cwd=repo, check=False)[1].strip()
    rep.add("OK" if head == orig else "INFO", "コードの版", f"HEAD={head} / origin/main={orig}"
            + ("" if head == orig else "(deploy で origin/main に揃えます)"))
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo, check=False)[1].strip()
    if dirty:
        rep.add("WARN", "未コミットの変更", "deploy で破棄されます: " + ", ".join(l[3:] for l in dirty.splitlines()[:10]))
    left = [p.name for pat in ("apply_*.py", "fix_*.py", "patch_*.py", "investigate_*.py", "check_*.py", "diag_*.py")
            for p in repo.glob(pat)]
    if left:
        rep.add("WARN", "ルート直下の実行済みパッチの残り", ", ".join(sorted(left)))

    # ── apps/api/.env ──
    envf = repo / "apps" / "api" / ".env"
    ev = read_env_file(envf)
    url = ev.get("DATABASE_URL", "")
    p = urlparse(url.split("?", 1)[0]) if url else None
    if not p:
        rep.add("NG", "apps/api/.env の DATABASE_URL", "ありません", stage="deploy")
        return
    ok_db = p.path.lstrip("/") == cfg["db"] and (p.port or 5432) == cfg["db_port"]
    rep.add("OK" if ok_db else "NG", "接続先DB", f"{p.path.lstrip('/')}:{p.port}(想定 {cfg['db']}:{cfg['db_port']})", stage="deploy")
    if not ok_db:
        return
    jwt = ev.get("JWT_SECRET", "")
    if not jwt or "change-me" in jwt or "change_me" in jwt:
        rep.add("WARN", "JWT_SECRET", "未設定またはテンプレートのまま(deploy で乱数に置き換えます)")
    elif other_cfg:
        ojwt = read_env_file(other_cfg["repo"] / "apps" / "api" / ".env").get("JWT_SECRET", "")
        if ojwt and ojwt == jwt:
            rep.add("WARN", "JWT_SECRET", "internal と group が同じ値(片方のログイン情報がもう片方の API で通る)。"
                    "group 側を deploy で乱数に置き換えます" if env == "group" else
                    "internal と group が同じ値(group 側を deploy で置き換えます)")
        else:
            rep.add("OK", "JWT_SECRET", "インスタンスごとに別の値")
    ua = ev.get("UPLOAD_AGENT_DIR") or "/var/www/machcore-cert(既定)"
    rep.add("INFO", "UploadAgent 配布先", ua)

    # ── Web の API 転送先(ビルド時に焼き込まれる) ──
    wenv = read_env_file(repo / "apps" / "web" / ".env.production")
    wport = wenv.get("API_PORT")
    if str(wport or "3011") == str(cfg["api_port"]):
        rep.add("OK", "Web→API 転送先", f"API_PORT={wport or '3011(既定)'}")
    else:
        rep.add("WARN", "Web→API 転送先",
                f"apps/web/.env.production API_PORT={wport}(想定 {cfg['api_port']})。deploy で直します")
    man = repo / "apps" / "web" / ".next" / "routes-manifest.json"
    if man.exists():
        txt = man.read_text(encoding="utf-8", errors="replace")
        baked = sorted(set(re.findall(r"localhost:(\d+)/api", txt)))
        rep.add("OK" if baked == [str(cfg["api_port"])] else "WARN", "ビルド済み Web の API 転送先",
                f"localhost:{','.join(baked) or '?'}(想定 {cfg['api_port']})"
                + ("" if baked == [str(cfg["api_port"])] else " — 別インスタンスの API に繋がっています。deploy で作り直します"))

    # ── pm2 設定 ──
    eco = repo / cfg["eco"]
    if not eco.exists():
        rep.add("NG", "pm2 設定", f"{eco} がありません", stage="deploy")
    else:
        etxt = eco.read_text(encoding="utf-8")
        bad = [x for x in re.findall(r"/home/karkyon/projects/([\w-]+)/", etxt) if x != repo.name]
        rep.add("NG" if bad else "OK", "pm2 設定のパス", f"他のリポジトリを指している: {sorted(set(bad))}" if bad else cfg["eco"],
                stage="deploy")

    # ── ツール ──
    for t in ("node", "pnpm", "pm2", "docker"):
        rep.add("OK" if which(t) else "NG", f"コマンド {t}", which(t) or "見つかりません", stage="deploy")
    nv = run(["node", "-v"], check=False)[1].strip() if which("node") else ""
    rep.add("OK" if nv.startswith("v20.") else "WARN", "Node のバージョン", f"{nv}(v20 系で動かしています)")
    rep.add("OK", "Python", f"{sys.executable}(pymssql/psycopg2 あり)")

    # ── DB ──
    dsn = url.split("?", 1)[0]
    try:
        pg = connect(dsn)
    except Exception as e:
        rep.add("NG", "DB 接続", str(e).strip(), stage="deploy")
        return
    c = pg.cursor()
    rep.add("OK", "DB 接続", f"{cfg['db']}  {q1(c, 'SELECT pg_size_pretty(pg_database_size(current_database()))')}")
    cont = find_container(cfg["db_port"])
    rep.add("OK" if cont else "WARN", "DB コンテナ", cont or f"ポート {cfg['db_port']} のコンテナが見つかりません(バックアップはホストの pg_dump を使います)")

    cs = None
    if table_exists(c, "company_settings"):
        c.execute("SELECT company_name, upload_base_path, mc_printer, nc_printer FROM company_settings ORDER BY id LIMIT 1")
        cs = c.fetchone()
    if not cs:
        rep.add("NG", "会社設定(company_settings)", "行がありません")
    else:
        rep.add("INFO", "会社名", cs[0])
        ub = (cs[1] or "").rstrip("/")
        exp = str(cfg["storage"])
        if not ub:
            rep.add("NG", "ファイル格納先(upload_base_path)", f"未設定(コンバートが共有SMB /mnt/mc_files に書き込むため不可)。{exp} を設定してください")
        elif os.path.realpath(ub) != os.path.realpath(exp):
            rep.add("NG", "ファイル格納先(upload_base_path)", f"{ub}(想定 {exp})")
        else:
            w = os.access(ub, os.W_OK) if os.path.isdir(ub) else False
            rep.add("OK" if w else "NG", "ファイル格納先(upload_base_path)", f"{ub}" + ("" if w else " — 無いか書き込めません"))
        if other_cfg and ub and os.path.realpath(ub) == os.path.realpath(str(other_cfg["storage"])):
            rep.add("NG", "ファイル格納先の分離", "もう片方のインスタンスと同じ場所です")
        for i, label in ((2, "MCプリンタ"), (3, "NCプリンタ")):
            if cs[i]:
                ok = run(["lpstat", "-p", cs[i]], check=False)[0] == 0 if which("lpstat") else False
                rep.add("OK" if ok else "WARN", label, cs[i] + ("" if ok else "(CUPS に未登録)"))
            else:
                rep.add("INFO", label, "未設定")
        try:
            du = shutil.disk_usage(ub or "/")
            rep.add("OK" if du.free > 20 * 1024 ** 3 else "WARN", "空き容量(格納先)", f"{du.free / 1024 ** 3:.0f} GB")
        except Exception:
            pass

    # ── マスタ(コンバートは users / machines を作らず、照合だけする) ──
    if table_exists(c, "users"):
        nu = q1(c, "SELECT COUNT(*) FROM users")
        na = q1(c, "SELECT COUNT(*) FROM users WHERE is_active")
        adm = q1(c, "SELECT id FROM users WHERE employee_code='ADMIN001'")
        rep.add("OK" if adm else "NG", "ADMIN001", f"users.id={adm}" if adm else "ありません(コンバートの代替入力者が決まりません)")
        rep.add("INFO", "担当者マスタ(users)", f"{nu}人(有効 {na})")
        c.execute("SELECT employee_code, name FROM users WHERE upper(employee_code) = ANY(%s)",
                  ([v.upper() for v in LEGACY_ALIASES.values()],))
        have = {r[0].upper(): r[1] for r in c.fetchall()}
        for alias, code in LEGACY_ALIASES.items():
            if code.upper() in have:
                rep.add("OK", f"旧の通称「{alias}」", f"{code} {have[code.upper()]}")
            else:
                rep.add("WARN", f"旧の通称「{alias}」", f"社員コード {code} が users に無い" + (
                    "(group はコンバート時に internal から補完します)" if env == "group"
                    else "ため、この名前の記録は担当者が空欄になります"))
    if table_exists(c, "machines"):
        c.execute("SELECT system_type::text, is_active, COUNT(*) FROM machines GROUP BY 1,2 ORDER BY 1,2")
        rows = c.fetchall()
        nmc = sum(r[2] for r in rows if r[0] in ("MC", "BOTH"))
        nnc = sum(r[2] for r in rows if r[0] in ("NC", "BOTH"))
        txt = " / ".join(f"{r[0]}{'' if r[1] else '(無効)'}={r[2]}" for r in rows) or "0件"
        if not (nmc and nnc):
            txt += (" — MC/NC どちらかが空。group はコンバート時に internal から補完します" if env == "group"
                    else " — 空の系統があるとコンバートで機械が全件空欄になります")
        rep.add("OK" if nmc and nnc else ("WARN" if env == "group" else "NG"), "機械マスタ(machines)", txt)
    for t, label in (("pdf_templates", "帳票テンプレート"), ("pdf_field_definitions", "帳票の印字位置")):
        if table_exists(c, t):
            n = q1(c, f"SELECT COUNT(*) FROM {t}")
            rep.add("OK" if n else ("WARN" if env == "group" else "NG"), label, f"{n}件" + (
                "" if n else ("(group はコンバート時に internal から投入します)" if env == "group" else "(段取シートの見出しが空になります)")))
    for t in ("clamp_vise", "clamp_chuck", "clamp_tsume", "clamp_shiki", "clamp_index",
              "nc_tool_shave1_master", "nc_tool_shave2_master", "nc_tool_chip_master", "nc_tool_holder_master"):
        if table_exists(c, t):
            n = q1(c, f"SELECT COUNT(*) FROM {t}")
            rep.add("INFO", f"候補マスタ {t}", f"{n}件" + ("(空ならコンバートで投入)" if not n else ""))
    if table_exists(c, "business_calendars"):
        rep.add("INFO", "営業日カレンダー", f"{q1(c, 'SELECT COUNT(*) FROM business_calendars')}件(コンバート対象外)")

    # ── コンバートで消えるデータ ──
    lost = []
    for sql, label in (
        ("SELECT COUNT(*) FROM mc_programs", "MC 加工データ"),
        ("SELECT COUNT(*) FROM mc_programs WHERE legacy_mcid IS NULL", "  うち新システムで登録"),
        ("SELECT COUNT(*) FROM nc_programs", "NC 加工データ"),
        ("SELECT COUNT(*) FROM nc_programs WHERE legacy_nc_id IS NULL", "  うち新システムで登録"),
        ("SELECT COUNT(*) FROM work_records", "作業記録"),
        ("SELECT COUNT(*) FROM mc_setup_sheet_logs", "MC 段取シート印刷履歴"),
        ("SELECT COUNT(*) FROM setup_sheet_logs", "NC 段取シート印刷履歴"),
        ("SELECT COUNT(*) FROM operation_logs", "操作ログ"),
    ):
        try:
            lost.append(f"{label}={q1(c, sql)}")
        except Exception:
            pg.rollback()
    rep.add("INFO", "コンバートで作り直すデータ(今の件数)", " / ".join(lost))
    try:
        c.execute("""SELECT (created_at + interval '9 hour')::date, COUNT(*) FROM work_records
                     GROUP BY 1 ORDER BY 1 DESC LIMIT 8""")
        rep.add("INFO", "作業記録の登録日(created_at)別件数 新しい順",
                " / ".join(f"{d}={n}" for d, n in c.fetchall()))
    except Exception:
        pg.rollback()
    pg.close()

    # ── 旧DB / 旧ファイル ──
    src = (SCRIPTS_DIR / "mc_full_import.py").read_text(encoding="utf-8")
    srv = re.search(r'SS_MC_SERVER\s*=\s*"([^"]+)"', src).group(1)
    usr = re.search(r'SS_MC_USER\s*=\s*"([^"]+)"', src).group(1)
    pw = re.search(r'SS_MC_PASS\s*=\s*"([^"]+)"', src).group(1)
    try:
        import pymssql
        for db in ("imotomc", "imotodb"):
            cn = pymssql.connect(server=srv, user=usr, password=pw, database=db, tds_version="7.4", login_timeout=15)
            cn.close()
        rep.add("OK", "旧DB(SQL Server)", f"{srv} imotomc / imotodb に接続できます")
    except Exception as e:
        rep.add("NG", "旧DB(SQL Server)", f"{srv} に接続できません: {e}")
    roots = re.findall(r'(?:SMB_MC_ROOT|SRC_NC_ROOT)\s*=\s*Path\("([^"]+)"\)',
                       src + (SCRIPTS_DIR / "nc_full_import_v2.py").read_text(encoding="utf-8"))
    for l in Path("/proc/mounts").read_text().splitlines():
        f = l.split()
        if len(f) >= 4 and f[1] == "/mnt/mcfiles":
            rep.add("OK" if "ro" in f[3].split(",") else "WARN", "旧ファイル共有のマウント",
                    f"{f[0]} {f[2]} " + ("読み取り専用" if "ro" in f[3].split(",") else "読み書き可(ro を推奨)"))
    for r in roots:
        try:
            ents = sorted(os.listdir(r))
            rep.add("OK" if ents else "NG", f"旧ファイル {r}", f"{len(ents)}項目({', '.join(ents[:4])})" if ents
                    else "空です(マウントが外れている可能性。コンバートで図・写真・プログラムの登録が空になります)")
        except Exception as e:
            rep.add("NG", f"旧ファイル {r}", f"読めません({e})。コンバートで図・写真・プログラムの登録が空になります")

    # ── 部品マスタ同期 cron(このリポジトリの行だけを見る) ──
    mine = [e for e in sync_cron_entries() if e[1] and os.path.realpath(e[1]) == os.path.realpath(repo)]
    if not mine:
        rep.add("WARN", "部品マスタ同期 cron", "このリポジトリの sync_parts.py の行がありません(deploy で追加します)")
    for l, _, script, py in mine:
        okpy = bool(py) and _py_has_modules(py)
        rep.add("OK" if script and okpy else "WARN", "部品マスタ同期 cron", l.strip() + (
            "" if script else "  ← スクリプトがありません") + ("" if okpy else "  ← この Python では pymssql/psycopg2 が使えません"))

    # ── pm2 ──
    try:
        jl = json.loads(sh_out(["pm2", "jlist"]) or "[]")
    except Exception:
        jl = []
    for name in cfg["pm2"]:
        pr = [x for x in jl if x.get("name") == name]
        if not pr:
            rep.add("WARN", f"pm2 {name}", "登録されていません(deploy で起動します)")
            continue
        e = pr[0].get("pm2_env", {})
        cwd = e.get("pm_cwd", "")
        st = e.get("status")
        okc = str(repo) in (cwd + e.get("pm_exec_path", ""))
        rep.add("OK" if st == "online" and okc else ("NG" if not okc else "WARN"),
                f"pm2 {name}", f"{st}  cwd={cwd}" + ("" if okc else " — 別のリポジトリで動いています"), stage="deploy")
    en = sh_out(["systemctl", "is-enabled", "pm2-karkyon"]).strip()
    rep.add("OK" if en == "enabled" else "WARN", "pm2 の自動起動(pm2-karkyon)", en or "不明")

    # ── nginx ──
    srvs = nginx_servers()
    if not srvs:
        rep.add("WARN", "nginx", "/etc/nginx/sites-enabled を読めませんでした")
    else:
        for s in srvs:
            if cfg["https_port"] in s["listen"]:
                okp = any(f":{cfg['web_port']}" in x for x in s["proxy"])
                rep.add("OK" if okp else "NG", f"nginx {cfg['https_port']}", f"proxy_pass {s['proxy']}({Path(s['file']).name})")
            if cfg["cert_port"] in s["listen"]:
                rep.add("INFO", f"nginx {cfg['cert_port']}(証明書配布)", f"root {s['root']}({Path(s['file']).name})")


# ──────────────────────────────────────────────────────────────
# バックアップ
# ──────────────────────────────────────────────────────────────
_backed = {}


def backup(env, cfg, rep, skip=False):
    if skip:
        rep.add("WARN", "DBバックアップ", "--skip-backup のため取っていません")
        return
    if env in _backed:
        return
    dsn = dsn_of(cfg)
    p = urlparse(dsn)
    d = HOME / "machcore-backups" / env
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{cfg['db']}_{TS}.dump"
    cont = find_container(cfg["db_port"])
    if cont:
        cmd = ["docker", "exec", "-e", f"PGPASSWORD={p.password or ''}", cont,
               "pg_dump", "-Fc", "-U", p.username, "-d", p.path.lstrip("/")]
    else:
        cmd = ["pg_dump", "-Fc", "-h", p.hostname, "-p", str(p.port), "-U", p.username, "-d", p.path.lstrip("/")]
    env2 = dict(ENV0, PGPASSWORD=p.password or "")
    with open(out, "wb") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env2)
    if r.returncode != 0 or out.stat().st_size < 1024:
        raise Abort(f"DBバックアップに失敗しました: {r.stderr.decode(errors='replace')[-500:]}")
    _backed[env] = out
    rep.add("OK", "DBバックアップ", f"{out}({out.stat().st_size / 1024 ** 2:.1f} MB)"
            + (f"  戻し方: docker exec -i {cont} pg_restore -U {p.username} -d {p.path.lstrip('/')} --clean --if-exists < {out}" if cont else ""))


# ──────────────────────────────────────────────────────────────
# DEPLOY
# ──────────────────────────────────────────────────────────────
def http_get(url, timeout=15):
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        code = getattr(e, "code", None)
        return code, str(e)


def health(env, cfg, rep):
    import time
    pg = connect(dsn_of(cfg))
    c = pg.cursor()
    cname = q1(c, "SELECT company_name FROM company_settings ORDER BY id LIMIT 1")
    pg.close()
    for i in range(30):
        st, _ = http_get(f"http://127.0.0.1:{cfg['api_port']}/api/admin/company")
        if st == 200:
            break
        time.sleep(3)
    for label, urls in (("API 直接", [f"http://127.0.0.1:{cfg['api_port']}/api/admin/company"]),
                        ("Web 経由(Web→API 転送先の確認)", [f"http://127.0.0.1:{cfg['web_port']}/api/admin/company"]),
                        ("https(nginx)経由", [f"https://127.0.0.1:{cfg['https_port']}/api/admin/company",
                                              f"https://192.168.1.14:{cfg['https_port']}/api/admin/company"])):
        for url in urls:
            st, body = http_get(url)
            if st == 200:
                break
        try:
            got = json.loads(body).get("companyName") if st == 200 else None
        except Exception:
            got = None
        if st == 200 and (got is None or got == cname):
            rep.add("OK", f"動作確認 {label}", f"HTTP 200 会社名={got}")
        elif st == 200:
            rep.add("NG", f"動作確認 {label}", f"別インスタンスの API に繋がっています(会社名={got} / このDB={cname})")
        else:
            rep.add("NG", f"動作確認 {label}", f"HTTP {st} {body[:200]}")
    st, _ = http_get(f"http://127.0.0.1:{cfg['web_port']}/")
    rep.add("OK" if st in (200, 307, 308) else "NG", "動作確認 Web 画面", f"HTTP {st}")


def ensure_cron(env, cfg, rep):
    """このリポジトリの部品同期行が動く状態ならそのまま(間隔も変えない)。無い・動かない場合だけ直す。
       もう片方のインスタンスの行には触らない"""
    repo = cfg["repo"]
    if not which("crontab"):
        rep.add("WARN", "部品マスタ同期 cron", "crontab コマンドがありません")
        return
    mine = [e for e in sync_cron_entries() if e[1] and os.path.realpath(e[1]) == os.path.realpath(repo)]
    good = [e for e in mine if e[2] and e[3] and _py_has_modules(e[3])]
    (repo / "logs").mkdir(exist_ok=True)
    if good:
        rep.add("OK", "部品マスタ同期 cron(変更なし)", good[0][0].strip())
    else:
        bad = {e[0] for e in mine}
        cron = sh_out(["crontab", "-l"])
        keep = [l for l in cron.splitlines() if l not in bad]
        line = f"* * * * * cd {repo} && {sys.executable} scripts/sync_parts.py >> {repo}/logs/sync_parts.log 2>&1"
        r = subprocess.run(["crontab", "-"], input="\n".join(keep + [line]) + "\n", text=True, capture_output=True)
        if r.returncode != 0:
            rep.add("WARN", "部品マスタ同期 cron", f"書き込めませんでした: {r.stderr}")
            return
        for l in bad:
            log(f"  [cron] 置き換え前: {l}")
        rep.add("OK", "部品マスタ同期 cron を設定(1分ごと)", line)
    run([sys.executable, "scripts/sync_parts.py"], cwd=repo, label=f"{env}: 部品マスタ同期を1回実行", check=False,
        env=dict(ENV0), timeout=1800)


def ensure_instance_settings(env, cfg, rep, other_cfg):
    repo = cfg["repo"]
    envf = repo / "apps" / "api" / ".env"
    ev = read_env_file(envf)
    # JWT_SECRET: テンプレートのまま / もう片方と同じ → 乱数に置き換え(このインスタンスは再ログインが必要)
    jwt = ev.get("JWT_SECRET", "")
    ojwt = read_env_file(other_cfg["repo"] / "apps" / "api" / ".env").get("JWT_SECRET", "") if other_cfg else ""
    if (not jwt or "change-me" in jwt or "change_me" in jwt) or (env == "group" and ojwt and jwt == ojwt):
        set_env_value(envf, "JWT_SECRET", secrets.token_hex(32))
        rep.add("OK", "JWT_SECRET を乱数に変更", "このインスタンスの利用者は再ログインが必要です")
    # UploadAgent 配布先: group は internal と別の場所
    if env == "group" and not ev.get("UPLOAD_AGENT_DIR"):
        d = Path(cfg["ua_dir"])
        try:
            user = os.environ.get("USER", "karkyon")
            if not d.exists() or not os.access(d, os.W_OK):
                sudo(["install", "-d", "-o", user, "-g", user, str(d)], "UploadAgent 配布先(group)を作成")
                sudo(["chown", f"{user}:{user}", str(d)], "UploadAgent 配布先(group)を書き込み可に")
            if not os.access(d, os.W_OK):
                raise PermissionError("書き込み不可")
            src = Path("/var/www/machcore-cert/UploadAgent_Setup_latest.exe")
            if src.exists() and not (d / src.name).exists():
                shutil.copy2(src, d / src.name)
            set_env_value(envf, "UPLOAD_AGENT_DIR", str(d))
            rep.add("OK", "UploadAgent 配布先を分離", f"UPLOAD_AGENT_DIR={d}(今の配布物をコピー済み)")
        except Exception as e:
            rep.add("WARN", "UploadAgent 配布先を分離できませんでした",
                    f"{d}: {e}。sudo install -d -o karkyon -g karkyon {d} を実行後、再度 deploy してください")
    # Web の API 転送先(ビルド時に焼き込み)
    wf = repo / "apps" / "web" / ".env.production"
    if read_env_file(wf).get("API_PORT") != str(cfg["api_port"]):
        if not wf.exists():
            wf.write_text("", encoding="utf-8")
        set_env_value(wf, "API_PORT", str(cfg["api_port"]))
        rep.add("OK", "Web→API 転送先を設定", f"apps/web/.env.production API_PORT={cfg['api_port']}")


LEGACY_SHARE = "//192.168.1.9/d1"
LEGACY_MOUNT = "/mnt/mcfiles"
LEGACY_CRED = "/etc/cifs-credentials-mcfiles-d1"
_mount_done = False


def ensure_legacy_mount(rep):
    """旧システムのファイル共有(図・写真・プログラムのコピー元)を .11 と同じ /mnt/mcfiles にマウントする。
       コンバートは読むだけなので読み取り専用(ro)。internal/group の格納先(~/machcore-storage/*)とは別物"""
    global _mount_done

    def ok():
        try:
            return bool(os.listdir(f"{LEGACY_MOUNT}/MC")) and bool(os.listdir(f"{LEGACY_MOUNT}/NC"))
        except Exception:
            return False

    def clear_ng():
        rep.items = [i for i in rep.items if not (i[0] == "NG" and i[1].startswith(f"旧ファイル {LEGACY_MOUNT}"))]
    def opts():
        for l in Path("/proc/mounts").read_text().splitlines():
            f = l.split()
            if len(f) >= 4 and f[1] == LEGACY_MOUNT and f[2] == "cifs":
                return f[0], f[3].split(",")
        return None, []

    def report(title):
        dev, o = opts()
        ro = "ro" in o
        rep.add("OK" if ro else "WARN", title, f"{dev} → {LEGACY_MOUNT} " + ("読み取り専用(ro)" if ro else
                f"読み書き可({','.join(x for x in o if x in ('rw', 'ro'))})。コンバートは読むだけだが、"
                f"/etc/fstab の {LEGACY_SHARE} 行の rw を ro に変えておくと安全"))
    if ok():
        clear_ng()
        report("旧ファイル共有")
        return
    if _mount_done:
        rep.add("NG", "旧ファイル共有をマウントできません", f"{LEGACY_SHARE} → {LEGACY_MOUNT}")
        return
    _mount_done = True
    fstab = Path("/etc/fstab").read_text(encoding="utf-8", errors="replace")
    line = (f"{LEGACY_SHARE} {LEGACY_MOUNT} cifs credentials={LEGACY_CRED},vers=2.0,ro,uid=karkyon,gid=karkyon,"
            f"file_mode=0444,dir_mode=0555,_netdev,soft,serverino,x-systemd.automount 0 0")
    steps = []
    if not os.path.exists(LEGACY_CRED):
        steps.append((["sh", "-c", f"umask 077 && printf 'username=machcore\\npassword=RTW65b\\n' > {LEGACY_CRED}"], "認証ファイル作成(root のみ読める)"))
    if not re.search(rf"^\s*{re.escape(LEGACY_SHARE)}\s+{re.escape(LEGACY_MOUNT)}\s", fstab, re.M):
        steps.append((["sh", "-c", f"cp -p /etc/fstab /etc/fstab.bak_{TS} && echo '{line}' >> /etc/fstab"], "fstab に追記(元は /etc/fstab.bak_日時)"))
    steps += [(["mkdir", "-p", LEGACY_MOUNT], "マウント先作成"),
              (["systemctl", "daemon-reload"], "fstab の読み直し"),
              (["mount", LEGACY_MOUNT], "マウント")]
    log("\n----- 旧ファイル共有のマウント(sudo のパスワードを聞かれたら入力)")
    for cmd, label in steps:
        sudo(cmd, label)
    if ok():
        clear_ng()
        report("旧ファイル共有をマウント")
    else:
        rep.add("NG", "旧ファイル共有をマウントできません",
                f"{LEGACY_SHARE} → {LEGACY_MOUNT}。mount の表示を確認してください(cifs-utils が無ければ sudo apt install cifs-utils)")


def cleanup_leftovers(cfg, rep):
    """ルート直下に残った実行済みの一度きりパッチ(Git 管理外)を消す"""
    repo = cfg["repo"]
    gone = []
    for pat in ("apply_*.py", "fix_*.py", "patch_*.py", "investigate_*.py", "check_*.py", "diag_*.py"):
        for f in repo.glob(pat):
            if subprocess.run(["git", "ls-files", "--error-unmatch", f.name], cwd=repo, capture_output=True).returncode != 0:
                f.unlink()
                gone.append(f.name)
    if gone:
        rep.add("OK", "実行済みパッチの残りを削除", ", ".join(sorted(gone)))
        rep.items = [i for i in rep.items if i[1] != "ルート直下の実行済みパッチの残り"]


def deploy(env, cfg, rep, args, other_cfg):
    repo = cfg["repo"]
    api = repo / "apps" / "api"
    web = repo / "apps" / "web"
    log(f"\n{'=' * 70}\n[DEPLOY] {cfg['label']}\n{'=' * 70}")
    if rep.deploy_block:
        raise Abort("点検で設定の取り違えがあるため deploy しません: " + " / ".join(rep.deploy_block))
    backup(env, cfg, rep, args.skip_backup)

    run(["git", "fetch", "origin", "main"], cwd=repo, label="最新コードの取得")
    run(["git", "reset", "--hard", "origin/main"], cwd=repo)
    head = run(["git", "log", "--oneline", "-1"], cwd=repo)[1].strip()
    rep.add("OK", "コードを origin/main に揃えた", head)
    cleanup_leftovers(cfg, rep)
    ensure_legacy_mount(rep)

    ensure_instance_settings(env, cfg, rep, other_cfg)

    run(["pnpm", "install", "--frozen-lockfile"], cwd=repo, label="依存パッケージ", timeout=1800)
    run(["git", "checkout", "--", "pnpm-workspace.yaml", "pnpm-lock.yaml"], cwd=repo, check=False)

    # ── DBスキーマ同期(削除を伴う差分は止める) ──
    rc, diff = run(["pnpm", "exec", "prisma", "migrate", "diff", "--from-config-datasource",
                    "--to-schema", "prisma/schema.prisma", "--script"], cwd=api, label="DBスキーマ差分(読むだけ)", check=False)
    sql = "\n".join(l for l in diff.splitlines()
                    if not l.strip().startswith(("Loaded Prisma", "[dotenv", "$", "--")))
    if rc != 0:
        rep.add("WARN", "DBスキーマ差分", "差分の取得に失敗(db push の判定に任せます)")
    else:
        stmts = [s.strip() for s in re.split(r";\s*(?:\n|$)", sql) if s.strip()]
        risky = [s for s in stmts if re.search(r"\bDROP\s+(TABLE|COLUMN|TYPE|INDEX)|\bALTER\s+COLUMN\b.*\bTYPE\b|SET NOT NULL", s, re.I | re.S)]
        for st in stmts:
            log("  [差分] " + re.sub(r"\s+", " ", st)[:300])
        rep.add("OK" if not stmts else "INFO", "DBスキーマ差分", f"{len(stmts)}文" + (": " + " / ".join(
            re.sub(r"\s+", " ", s)[:90] for s in stmts[:12]) if stmts else "(同期済み)")
                + (f"(うちデータが消える可能性のある変更 {len(risky)}文)" if risky else ""))
        if risky and not args.accept_data_loss:
            for s in risky:
                log("  [削除・型変更を伴う差分] " + re.sub(r"\s+", " ", s)[:300])
            raise Abort(f"スキーマ同期にデータが消える可能性のある変更が {len(risky)} 件あります。"
                        "内容を確認し、問題なければ --accept-data-loss を付けて再実行してください")
    cmd = ["pnpm", "exec", "prisma", "db", "push"] + (["--accept-data-loss"] if args.accept_data_loss else [])
    run(cmd, cwd=api, label="DBスキーマ同期(prisma db push)", timeout=900)
    run(["pnpm", "exec", "prisma", "generate"], cwd=api, label="prisma generate", timeout=900)

    # ── 型チェック: API / Web ともエラー0件のときだけビルド ──
    for name, d in (("API", api), ("Web", web)):
        rc, out = run([str(d / "node_modules" / ".bin" / "tsc"), "--noEmit", "-p", "tsconfig.json"], cwd=d,
                      label=f"型チェック {name}", check=False, timeout=1800)
        n = len(re.findall(r"error TS\d+", out))
        if rc != 0 or n:
            raise Abort(f"型チェック {name} でエラー {n} 件。ビルド・再起動はしていません")
        rep.add("OK", f"型チェック {name}", "エラー0件")
    benv = dict(ENV0, API_PORT=str(cfg["api_port"]), NODE_ENV="production")
    run([str(api / "node_modules" / ".bin" / "nest"), "build"], cwd=api, label="API ビルド", env=benv, timeout=1800)
    run(["pnpm", "--filter", "web", "build"], cwd=repo, label="Web ビルド", env=benv, timeout=3600)
    run(["git", "checkout", "--", "pnpm-workspace.yaml", "pnpm-lock.yaml"], cwd=repo, check=False)
    man = web / ".next" / "routes-manifest.json"
    baked = sorted(set(re.findall(r"localhost:(\d+)/api", man.read_text(encoding="utf-8", errors="replace")))) if man.exists() else []
    if baked != [str(cfg["api_port"])]:
        raise Abort(f"ビルドした Web の API 転送先が localhost:{baked}(想定 {cfg['api_port']})。再起動していません")
    rep.add("OK", "ビルド", f"API / Web(API 転送先 localhost:{cfg['api_port']})")

    pm2_restart(cfg, rep)
    health(env, cfg, rep)
    ensure_cron(env, cfg, rep)


def pm2_restart(cfg, rep):
    eco = str(cfg["repo"] / cfg["eco"])
    # 登録の有無に関わらず起動できるよう、まず start(既にあれば何もしない)→ restart で設定を読み直す
    run(["pm2", "start", eco], cwd=cfg["repo"], check=False, label="pm2 起動/再起動")
    run(["pm2", "restart", eco, "--update-env"], cwd=cfg["repo"])
    run(["pm2", "save"], check=False)
    rep.add("OK", "pm2 再起動", ", ".join(cfg["pm2"]))


# ──────────────────────────────────────────────────────────────
# マスタ補完(コンバートは users / machines を照合するだけなので、事前に揃える)
# ──────────────────────────────────────────────────────────────
def copy_masters(src_dsn, dst_dsn, rep, inactive, label):
    """src にあって dst に無い機械(machine_code)・担当者(employee_code)を dst に追加する。
       同じ機械名・同じ氏名(表記ゆれを正規化して)が dst に既にあるものは追加しない(同姓同名を作ると照合できなくなる)。
       inactive=True: 無効・ログイン不可(閲覧者・承認権限なし)として追加する(group 用。過去記録の表示と照合にだけ使う)"""
    s = connect(src_dsn)
    d = connect(dst_dsn)
    sc, dc = s.cursor(), d.cursor()
    try:
        dc.execute("SELECT machine_code FROM machines")
        dcodes = {r[0] for r in dc.fetchall()}
        dkeys = {normalize_machine(x) for x in dcodes}
        sc.execute("""SELECT machine_code, machine_name, machine_type, maker, sort_order, is_active, system_type::text,
                             mc_specs::text, pg_is_folder FROM machines ORDER BY id""")
        add_m = []
        for r in sc.fetchall():
            if r[0] in dcodes or normalize_machine(r[0]) in dkeys:
                continue
            dc.execute("""INSERT INTO machines (machine_code, machine_name, machine_type, maker, sort_order, is_active,
                                                system_type, mc_specs, pg_is_folder, created_at, updated_at)
                          VALUES (%s,%s,%s,%s,%s,%s,%s::system_type,%s::jsonb,%s,NOW(),NOW())""",
                       (r[0], r[1], r[2], r[3], r[4], False if inactive else r[5], r[6], r[7], r[8]))
            add_m.append(r[0])
        dc.execute("SELECT employee_code, name FROM users")
        rows = dc.fetchall()
        ucodes = {r[0].upper() for r in rows}
        ukeys = {person_key(r[1]) for r in rows if r[1]}
        sc.execute("""SELECT employee_code, name, name_kana, password_hash, role::text, is_active, can_approve,
                             system_type::text FROM users ORDER BY id""")
        add_u, skip_u = [], []
        for r in sc.fetchall():
            if r[0].upper() in ucodes:
                continue
            alias_code = r[0].upper() in {v.upper() for v in LEGACY_ALIASES.values()}
            if r[1] and person_key(r[1]) in ukeys and not alias_code:
                skip_u.append(f"{r[0]} {r[1]}")
                continue
            if inactive:
                vals = (r[0], r[1], r[2], "!disabled:copied-from-internal", "VIEWER", False, False, r[7])
            else:
                vals = (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7])
            dc.execute("""INSERT INTO users (employee_code, name, name_kana, password_hash, role, is_active, can_approve,
                                             system_type, created_at, updated_at)
                          VALUES (%s,%s,%s,%s,%s::user_role,%s,%s,%s::system_type,NOW(),NOW())""", vals)
            ukeys.add(person_key(r[1]))
            add_u.append(f"{r[0]} {r[1]}")
        d.commit()
    except Exception:
        d.rollback()
        raise
    finally:
        s.close()
        d.close()
    rep.add("OK", f"機械マスタ補完({label})", f"{len(add_m)}台追加" + ("(無効として)" if inactive else "")
            + (": " + ", ".join(add_m[:30]) if add_m else ""))
    rep.add("OK", f"担当者マスタ補完({label})", f"{len(add_u)}人追加" + ("(無効・ログイン不可として)" if inactive else "")
            + (": " + ", ".join(add_u[:30]) + (" ほか" if len(add_u) > 30 else "") if add_u else ""))
    if skip_u:
        rep.add("WARN", f"担当者マスタ補完({label}) 同じ氏名の別コードのため追加しなかった人", ", ".join(skip_u[:30]))


def copy_pdf_templates_if_empty(src_dsn, dst_dsn, rep):
    s = connect(src_dsn)
    d = connect(dst_dsn)
    sc, dc = s.cursor(), d.cursor()
    try:
        nt = q1(dc, "SELECT COUNT(*) FROM pdf_templates")
        nf = q1(dc, "SELECT COUNT(*) FROM pdf_field_definitions")
        if nt and nf:
            st = q1(sc, "SELECT COUNT(*) FROM pdf_templates")
            sf = q1(sc, "SELECT COUNT(*) FROM pdf_field_definitions")
            rep.add("OK" if (st, sf) == (nt, nf) else "WARN", "帳票テンプレート",
                    f"このDB {nt}/{nf}件、internal {st}/{sf}件" + ("" if (st, sf) == (nt, nf) else "(件数が違います。必要なら管理画面で揃えてください)"))
            return
        if nf:
            raise Abort("pdf_templates が空なのに pdf_field_definitions に行があります。手で確認してください")
        for t in ("pdf_templates", "pdf_field_definitions"):
            sc.execute(f"SELECT * FROM {t} ORDER BY id")
            cols = [x.name for x in sc.description]
            rows = sc.fetchall()
            for r in rows:
                dc.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})", r)
            dc.execute(f"SELECT setval(pg_get_serial_sequence('{t}','id'), COALESCE((SELECT MAX(id) FROM {t}),1))")
            rep.add("OK", f"{t} を internal から投入(空だったため)", f"{len(rows)}件")
        d.commit()
    except Exception:
        d.rollback()
        raise
    finally:
        s.close()
        d.close()


# ──────────────────────────────────────────────────────────────
# CONVERT
# ──────────────────────────────────────────────────────────────
def convert(env, cfg, rep, args):
    repo = cfg["repo"]
    log(f"\n{'=' * 70}\n[CONVERT] {cfg['label']}\n{'=' * 70}")
    if rep.ng():
        raise Abort("NG があるためコンバートしません: " + " / ".join(t for _, t, _ in rep.ng()))
    head = run(["git", "rev-parse", "HEAD"], cwd=repo)[1].strip()
    orig = run(["git", "rev-parse", "origin/main"], cwd=repo)[1].strip()
    if head != orig:
        raise Abort("コードが origin/main ではありません。先に --mode deploy を実行してください")
    # この版のスクリプトが使う列(作業記録の個/1サイクル等)が DB にあるか
    pg = connect(dsn_of(cfg))
    c = pg.cursor()
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='work_records'")
    have = {r[0] for r in c.fetchall()}
    ub = (q1(c, "SELECT upload_base_path FROM company_settings ORDER BY id LIMIT 1") or "").rstrip("/")
    pg.close()
    schema = (repo / "apps" / "api" / "prisma" / "schema.prisma").read_text(encoding="utf-8")
    wr = re.search(r"model WorkRecord \{(.*?)\n\}", schema, re.S).group(1)
    need = set(re.findall(r'(?<!@)@map\("([a-z0-9_]+)"\)', wr))   # @@map("work_records") は表名なので除く
    miss = sorted(need - have)
    if miss:
        raise Abort(f"work_records に列がありません({miss})。先に --mode deploy を実行してください")
    if os.path.realpath(ub or "/mnt/mc_files") != os.path.realpath(str(cfg["storage"])):
        raise Abort(f"upload_base_path={ub or '未設定'}(想定 {cfg['storage']})。共有先へ書き込むためコンバートしません")
    backup(env, cfg, rep, args.skip_backup)

    if env == "group" and not args.no_copy_masters:
        idsn = dsn_of(ENVS["internal"])
        copy_masters(idsn, dsn_of(cfg), rep, inactive=True, label="internal → group")
        copy_pdf_templates_if_empty(idsn, dsn_of(cfg), rep)
    if env == "internal" and args.internal_masters_from:
        copy_masters(args.internal_masters_from, dsn_of(cfg), rep, inactive=False, label="指定DB → internal")
    pg = connect(dsn_of(cfg))
    c = pg.cursor()
    nmc = q1(c, "SELECT COUNT(*) FROM machines WHERE system_type::text IN ('MC','BOTH')")
    nnc = q1(c, "SELECT COUNT(*) FROM machines WHERE system_type::text IN ('NC','BOTH')")
    ntp = q1(c, "SELECT COUNT(*) FROM pdf_field_definitions")
    pg.close()
    if not (nmc and nnc and ntp):
        raise Abort(f"機械マスタ(MC {nmc} / NC {nnc})か帳票の印字位置({ntp})が空のためコンバートしません")

    py = sys.executable
    cenv = dict(ENV0)
    if args.with_test:
        rc, out = run([py, "scripts/run_conversion_test.py"], cwd=repo, env=cenv, capture=False,
                      label=f"{env}: コンバート試験(試験用DB・本番DBは変更しない)", check=False, timeout=4 * 3600)
        m = re.search(r"まとめ:.*?NG (\d+)件", out)
        if rc != 0 or not m or int(m.group(1)) > 0:
            raise Abort(f"コンバート試験が NG です(rc={rc}, NG={m.group(1) if m else '不明'})。"
                        "scripts/verify_reports/conversion_test_*.md を確認してください。本番コンバートはしていません")
        rep.add("OK", "コンバート試験", "NG なし")

    names = cfg["pm2"]
    run(["pm2", "stop"] + names, check=False, label=f"{env}: 利用を止める(pm2 stop)")
    try:
        rc, out = run([py, "scripts/run_nightly_full_reimport_and_verify.py"], cwd=repo, env=cenv, capture=False,
                      label=f"{env}: MC/NC フルコンバート+.WPD統一+新旧検証", check=False, timeout=6 * 3600)
        if rc != 0:
            raise Abort("フルコンバートが失敗しました。logs/mc_full_import.log / logs/nc_full_import.log を確認し、"
                        f"必要ならバックアップ {_backed.get(env)} から戻してください")
        rep.add("OK", "フルコンバート", "MC/NC 全フェーズ・.WPD統一・新旧検証")
        rc, out2 = run([py, "scripts/verify_work_records.py", "--target", "all"], cwd=repo, env=cenv, capture=False,
                       label=f"{env}: 作業記録の新旧全件・全項目検証", check=False, timeout=3 * 3600)
        rep.add("OK" if rc == 0 else "WARN", "作業記録の全件検証", "scripts/verify_reports/verify_work_records_*.md")
        check_file_links(cfg, rep)
    finally:
        pm2_restart(cfg, rep)
    health(env, cfg, rep)
    summarize_conversion(env, cfg, rep, out)


def check_file_links(cfg, rep):
    """コンバート後の図・写真・プログラムの登録が、このインスタンスの格納先を指し、実ファイルがあるか"""
    import random
    base = str(cfg["storage"]).rstrip("/") + "/"
    pg = connect(dsn_of(cfg))
    c = pg.cursor()
    for t, label in (("mc_files", "MC 図・写真・プログラム"), ("nc_files", "NC プログラム")):
        c.execute(f"SELECT file_type::text, COUNT(*), COUNT(*) FILTER (WHERE file_path NOT LIKE %s) FROM {t} GROUP BY 1 ORDER BY 1",
                  (base + "%",))
        rows = c.fetchall()
        total = sum(r[1] for r in rows)
        outside = sum(r[2] for r in rows)
        c.execute(f"SELECT file_path FROM {t}")
        paths = [r[0] for r in c.fetchall()]
        sample = random.sample(paths, min(300, len(paths)))
        missing = [x for x in sample if not os.path.exists(x)]
        detail = " / ".join(f"{r[0]}={r[1]}" for r in rows) or "0件"
        bad = total == 0 or outside or missing
        rep.add("NG" if bad else "OK", f"{label}の登録", detail + (
            f"  格納先外を指す行={outside}" if outside else "") + (
            f"  実ファイルが無い={len(missing)}/{len(sample)}件(抜き取り) 例: {missing[0]}" if missing else "") + (
            "  登録が0件" if total == 0 else ""))
    pg.close()


def summarize_conversion(env, cfg, rep, out):
    repo = cfg["repo"]
    for f in ("mc_full_import.log", "nc_full_import.log"):
        p = repo / "logs" / f
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        last = txt[txt.rfind("開始:"):] if "開始:" in txt else txt
        for l in last.splitlines():
            if "[WARN]" in l and ("users" in l or "machines" in l or "管理者で代替" in l):
                rep.add("WARN", f"{f} マスタに無い名前", re.sub(r"^\S+\s+\S+\s+", "", l.strip())[:400])
            if "ERROR" in l:
                rep.add("NG", f"{f} エラー", l.strip()[:300])
    reps = sorted((repo / "scripts" / "verify_reports").glob("nightly_run_summary_*.md"))
    if reps:
        rep.add("INFO", "コンバート実行サマリ", str(reps[-1]))
    for pat in ("verify_report_*.html", "verify_nc_report_*.html", "verify_work_records_*.md"):
        fs = sorted((repo / "scripts" / "verify_reports").glob(pat))
        if fs:
            rep.add("INFO", "検証レポート", str(fs[-1]))


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=".14 internal / group への展開とデータコンバート")
    ap.add_argument("--env", choices=["internal", "group", "both"], default="both")
    ap.add_argument("--mode", choices=["check", "deploy", "convert", "all"], default="check")
    ap.add_argument("--with-test", action="store_true")
    ap.add_argument("--no-copy-masters", action="store_true")
    ap.add_argument("--internal-masters-from", default=None)
    ap.add_argument("--accept-data-loss", action="store_true")
    ap.add_argument("--skip-backup", action="store_true")
    args = ap.parse_args()

    host = sh_out(["hostname"]).strip()
    log(f"deploy_14.py  {TS}  host={host}  env={args.env}  mode={args.mode}  python={sys.executable}")
    log(f"ログ: {LOG_PATH}")
    if not any((cfg["repo"] / ".git").is_dir() for cfg in ENVS.values()):
        log("[FAIL] ~/projects/machcore-internal も machcore-group もありません。.14(machcore-server)で実行してください")
        sys.exit(1)

    targets = ["internal", "group"] if args.env == "both" else [args.env]
    results = {}
    failed = False
    for env in targets:
        cfg = ENVS[env]
        other = ENVS["group" if env == "internal" else "internal"]
        other = other if (other["repo"] / ".git").is_dir() else None
        rep = Report(cfg["label"])
        results[env] = rep
        try:
            check(env, cfg, rep, other)
            if args.mode in ("deploy", "all"):
                deploy(env, cfg, rep, args, other)
            if args.mode in ("convert", "all"):
                if env == "group" and not args.no_copy_masters and not (ENVS["internal"]["repo"] / ".git").is_dir():
                    raise Abort("group のマスタ補完元の internal が見つかりません(--no-copy-masters で補完なし)")
                convert(env, cfg, rep, args)
        except Abort as e:
            rep.add("NG", "中止", str(e))
            failed = True
        except Exception as e:
            import traceback
            log(traceback.format_exc())
            rep.add("NG", "想定外のエラーで中止", repr(e))
            failed = True
        out = cfg["repo"] / "scripts" / "verify_reports" / f"deploy14_{env}_{TS}.md"
        if (cfg["repo"] / ".git").is_dir():
            rep.write(out)
        if failed and args.mode != "check":
            log(f"\n[STOP] {cfg['label']} で中止したため、残りのインスタンスは実行しません")
            break

    log("\n" + "=" * 70 + "\n結果一覧\n" + "=" * 70)
    for env, rep in results.items():
        log(f"■ {rep.name}: NG {len(rep.ng())}件 / 注意 {len(rep.warn())}件")
        for lv, t, d in rep.ng() + rep.warn():
            log(f"   [{lv}] {t} — {d}")
    log(f"\nログ: {LOG_PATH}")
    sys.exit(1 if failed or any(r.ng() for r in results.values()) else 0)


if __name__ == "__main__":
    main()
