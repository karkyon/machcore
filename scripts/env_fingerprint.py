#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env_fingerprint.py — MachCore の 1 インスタンスの「動作環境の指紋」を取る(再利用スクリプト・何も変更しない)

.11(UAT)で動いていた状態と .14(internal / group)の状態を、同じ物差しで比べるための材料を集める。
比較は parity_check.py が行う。このスクリプト単体でも動作確認(スモークテスト)の結果を出す。

集めるもの
  [ホスト]   OS・時刻帯(TZ)・言語・Python/Node/pnpm/pm2/docker の版・日本語フォント(帳票 ipag.ttf /
             fc-list の日本語フォント)・CUPS のプリンタ・旧ファイル共有などのマウント・cron・pm2・nginx
  [実行部品] apps/api で sharp / puppeteer(Chromium で日本語 PDF を実際に作る)/ 帳票フォントの読み込み
  [設定]     apps/api/.env のキー(値は安全なものだけ)・pm2 設定の env・Web の API 転送先・帳票テンプレートPDFの中身(ハッシュ)
  [DB]       版・時刻帯・文字コード・照合順序・拡張・スキーマ(列の定義のハッシュ)・全表の件数
  [マスタ]   利用者・機械・帳票テンプレート/印字位置・営業日カレンダー・候補マスタ・特殊シート・会社設定・システム設定
             (パスワードは値でなくハッシュの指紋だけ)
  [格納先]   upload_base_path / 各サブフォルダの有無・書き込み可否・ロゴ・UploadAgent 配布物
  [動作確認] API に管理者トークンで GET(と副作用の無いプレビュー PDF 生成)を多数送り、
             HTTP 状態・中身の種類(PDF/画像/JSON)を確かめる。Web 画面・https(nginx)経由も確かめる。
             データを書き込む操作は一切しない(段取シートは is_preview のプレビューだけ。履歴に残らない)

実行例
  .11:  cd ~/projects/machcore && python3 scripts/env_fingerprint.py --out ~/fp_11.json
  .14:  cd ~/projects/machcore-internal && python3 scripts/env_fingerprint.py --out ~/fp_internal.json
  別のリポジトリを指定: --repo ~/projects/machcore-group
  標準出力に JSON: --stdout(parity_check.py が ssh 越しに .11 で実行するときに使う)

このファイルは他のスクリプトを import しない(ssh 越しに標準入力から実行できるようにするため)。
"""
import os
import re
import sys
import ssl
import glob
import json
import time
import hmac
import base64
import shutil
import socket
import hashlib
import argparse
import platform
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
SECRET_KEYS = re.compile(r"PASS|SECRET|TOKEN|KEY|DATABASE_URL|REDIS_URL", re.I)


def sh(cmd, cwd=None, timeout=60, env=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                           shell=isinstance(cmd, str))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return -1, str(e)


def sha(x):
    if isinstance(x, (bytes, bytearray)):
        return hashlib.sha256(x).hexdigest()[:16]
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"[:400]}


def read_env(path):
    vals = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            m = re.match(r'^\s*([A-Za-z0-9_]+)\s*=\s*"?([^"\n]*)"?\s*$', line)
            if m:
                vals[m.group(1)] = m.group(2)
    except Exception:
        pass
    return vals


def node_env():
    env = dict(os.environ)
    for k in ("DATABASE_URL", "API_PORT", "PORT", "CORS_ORIGINS", "UPLOAD_AGENT_DIR", "MACHCORE_PG_DSN"):
        env.pop(k, None)
    pref = HOME / ".nvm" / "versions" / "node" / "v20.20.0" / "bin"
    v20 = sorted(glob.glob(str(HOME / ".nvm" / "versions" / "node" / "v20.*" / "bin")), reverse=True)
    b = str(pref) if pref.is_dir() else (v20[0] if v20 else None)
    if b:
        env["PATH"] = b + os.pathsep + env.get("PATH", "")
    return env


NENV = node_env()


# ──────────────────────────── ホスト ────────────────────────────
def host_info():
    h = {"hostname": socket.gethostname()}
    try:
        osr = dict(re.findall(r'^(\w+)="?([^"\n]*)"?', Path("/etc/os-release").read_text(), re.M))
        h["os"] = osr.get("PRETTY_NAME")
    except Exception:
        h["os"] = platform.platform()
    h["kernel"] = platform.release()
    rc, o = sh(["timedatectl", "show", "-p", "Timezone", "--value"])
    tz = o.strip() if rc == 0 and o.strip() else None
    if not tz:
        try:
            tz = os.path.realpath("/etc/localtime").split("zoneinfo/")[-1]
        except Exception:
            tz = None
    h["timezone"] = tz
    h["utc_offset"] = time.strftime("%z")
    h["lang"] = os.environ.get("LANG")
    h["python"] = sys.version.split()[0]
    h["python_path"] = sys.executable
    for mod in ("pymssql", "psycopg2"):
        try:
            m = __import__(mod)
            h[f"py_{mod}"] = getattr(m, "__version__", "ok").split()[0]
        except Exception as e:
            h[f"py_{mod}"] = f"なし({e.__class__.__name__})"
    for name, cmd in (("node", ["node", "-v"]), ("pnpm", ["pnpm", "-v"]), ("pm2", ["pm2", "-v"]),
                      ("docker", ["docker", "version", "--format", "{{.Server.Version}}"]),
                      ("nginx", ["nginx", "-v"]), ("lp", ["which", "lp"]), ("lpstat", ["which", "lpstat"]),
                      ("fc-list", ["which", "fc-list"]), ("smbclient", ["which", "smbclient"]),
                      ("mount.cifs", ["which", "mount.cifs"])):
        rc, o = sh(cmd, env=NENV)
        h[f"cmd_{name}"] = (o.strip().splitlines() or [""])[-1][:120] if rc == 0 else None
    # 帳票のフォント(MC 段取シートは pdf-lib + この TTF。NC 段取シートは Chromium で描くため OS の日本語フォント)
    h["font_ipag_ttf"] = os.path.exists("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf")
    rc, o = sh(["fc-list", ":lang=ja", "family"])
    h["fonts_ja"] = sorted(set(x.split(",")[0].strip() for x in o.splitlines() if x.strip())) if rc == 0 else None
    rc, o = sh(["fc-match", "sans-serif:lang=ja"])
    h["font_default_ja_sans"] = o.strip() if rc == 0 else None
    # CUPS
    rc, o = sh(["lpstat", "-p"])
    h["printers"] = sorted(re.findall(r"^printer\s+(\S+)", o, re.M)) if rc == 0 else []
    rc, o = sh(["lpstat", "-d"])
    h["printer_default"] = o.strip() if rc == 0 else None
    rc, o = sh(["lpstat", "-v"])
    h["printer_devices"] = sorted(l.strip() for l in o.splitlines() if l.strip()) if rc == 0 else []
    # マウント(cifs / nfs と /mnt 配下)
    mounts = []
    try:
        for l in Path("/proc/mounts").read_text().splitlines():
            f = l.split()
            if len(f) >= 4 and (f[2] in ("cifs", "nfs", "nfs4", "smb3") or f[1].startswith("/mnt")):
                o = f[3].split(",")
                mounts.append({"src": f[0], "dst": f[1], "type": f[2], "mode": "ro" if "ro" in o else "rw"})
    except Exception:
        pass
    h["mounts"] = mounts
    # cron(リポジトリのパスは {REPO} に置き換えて比べやすくする)
    rc, o = sh(["crontab", "-l"])
    h["crontab"] = [l.strip() for l in o.splitlines() if l.strip() and not l.lstrip().startswith("#")] if rc == 0 else []
    # pm2
    rc, o = sh(["pm2", "jlist"], env=NENV)
    procs = []
    try:
        for p in json.loads(o[o.find("["):]) if "[" in o else []:
            e = p.get("pm2_env", {})
            procs.append({"name": p.get("name"), "status": e.get("status"), "cwd": e.get("pm_cwd"),
                          "exec": e.get("pm_exec_path"), "node": e.get("node_version"),
                          "restarts": e.get("restart_time"), "TZ": (e.get("env") or {}).get("TZ") or e.get("TZ"),
                          "uptime_h": round((time.time() * 1000 - (e.get("pm_uptime") or 0)) / 3600000, 1)})
    except Exception:
        pass
    h["pm2"] = procs
    rc, o = sh(["systemctl", "is-enabled", "pm2-" + os.environ.get("USER", "karkyon")])
    h["pm2_autostart"] = o.strip() or None
    # nginx(listen と proxy_pass)
    ng = []
    for f in sorted(glob.glob("/etc/nginx/sites-enabled/*")) + sorted(glob.glob("/etc/nginx/conf.d/*.conf")):
        try:
            txt = re.sub(r"#[^\n]*", "", Path(f).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for m in re.finditer(r"\bserver\s*\{", txt):
            depth, i = 1, m.end()
            while i < len(txt) and depth:
                depth += {"{": 1, "}": -1}.get(txt[i], 0)
                i += 1
            body = txt[m.end():i]
            ng.append({"file": Path(f).name,
                       "listen": sorted(set(int(x) for x in re.findall(r"\blisten\s+(?:[\d.]+:)?(\d+)", body))),
                       "proxy": re.findall(r"proxy_pass\s+([^;]+);", body),
                       "root": re.findall(r"\b(?:root|alias)\s+([^;]+);", body),
                       "client_max_body_size": re.findall(r"client_max_body_size\s+([^;]+);", body),
                       "proxy_read_timeout": re.findall(r"proxy_read_timeout\s+([^;]+);", body)})
    h["nginx"] = ng
    return h


# ──────────────────────────── インスタンス ────────────────────────────
def find_ecosystem(repo):
    for f in sorted(repo.glob("ecosystem*.config.js")):
        rc, o = sh(["node", "-e", f"console.log(JSON.stringify(require({json.dumps(str(f))})))"], env=NENV)
        try:
            apps = json.loads(o.strip().splitlines()[-1]).get("apps", [])
        except Exception:
            continue
        if any(str(repo) in (a.get("cwd", "") + a.get("script", "")) for a in apps):
            return f, apps
    return None, []


def instance_config(repo):
    c = {"repo": str(repo)}
    rc, o = sh(["git", "rev-parse", "--short", "HEAD"], cwd=repo)
    c["git_head"] = o.strip()
    rc, o = sh(["git", "log", "-1", "--format=%s"], cwd=repo)
    c["git_subject"] = o.strip()[:120]
    rc, o = sh(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo)
    c["git_dirty"] = [l[3:] for l in o.splitlines() if l.strip()][:30]
    ev = read_env(repo / "apps" / "api" / ".env")
    c["env_keys"] = sorted(ev)
    c["env"] = {k: v for k, v in ev.items() if not SECRET_KEYS.search(k)}
    c["env_jwt_secret_fp"] = sha(ev.get("JWT_SECRET", "")) if ev.get("JWT_SECRET") else None
    url = ev.get("DATABASE_URL", "")
    m = re.match(r"postgres(?:ql)?://([^:@/]+)(?::[^@]*)?@([^:/]+):?(\d*)/([^?]+)", url)
    c["db"] = {"user": m.group(1), "host": m.group(2), "port": int(m.group(3) or 5432), "name": m.group(4)} if m else None
    eco, apps = find_ecosystem(repo)
    c["ecosystem"] = eco.name if eco else None
    c["pm2_apps"] = [{"name": a.get("name"), "cwd": a.get("cwd"), "script": a.get("script"), "env": a.get("env", {})}
                     for a in apps]
    api_env = next((a.get("env", {}) for a in apps if "apps/api" in (a.get("cwd") or "")), {})
    web_env = next((a.get("env", {}) for a in apps if "apps/api" not in (a.get("cwd") or "")), {})
    c["api_port"] = int(api_env.get("API_PORT") or ev.get("API_PORT") or 3011)
    web_port = web_env.get("PORT")
    if not web_port:
        for a in apps:
            s = a.get("script") or ""
            if s.endswith(".sh") and os.path.exists(s):
                m2 = re.search(r"-p\s+(\d+)", Path(s).read_text())
                if m2:
                    web_port = m2.group(1)
    c["web_port"] = int(web_port or 3010)
    c["web_env_production"] = read_env(repo / "apps" / "web" / ".env.production")
    man = repo / "apps" / "web" / ".next" / "routes-manifest.json"
    c["web_baked_api_ports"] = sorted(set(re.findall(r"localhost:(\d+)/api", man.read_text(errors="replace")))) if man.exists() else None
    # 帳票テンプレートPDF(管理画面から差し替えると Git の版と変わる)
    assets = repo / "apps" / "api" / "assets"
    c["assets"] = {p.name: sha(p.read_bytes()) for p in sorted(assets.glob("*")) if p.is_file()} if assets.is_dir() else {}
    rc, o = sh(["git", "status", "--porcelain", "--", "apps/api/assets"], cwd=repo)
    c["assets_changed_from_git"] = [l[3:] for l in o.splitlines() if l.strip()]
    pub = repo / "apps" / "web" / "public"
    c["web_public_branding"] = {str(p.relative_to(pub)): sha(p.read_bytes()) for p in pub.rglob("*")
                                if p.is_file() and ("branding" in str(p) or p.name.startswith("logo"))} if pub.is_dir() else {}
    return c


def runtime_checks(repo):
    """apps/api の Node 実行部品: sharp・puppeteer(実際に Chromium で日本語PDFを作る)・帳票フォント"""
    api = repo / "apps" / "api"
    js = r"""
const r = {};
try { const s = require('sharp'); r.sharp = s.versions; } catch (e) { r.sharp_err = String(e).slice(0, 300); }
try { const f = require('fs'); const b = f.readFileSync('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'); r.ipag_bytes = b.length; } catch (e) { r.ipag_err = String(e).slice(0, 200); }
try { require('pdf-lib'); require('@pdf-lib/fontkit'); r.pdflib = true; } catch (e) { r.pdflib_err = String(e).slice(0, 200); }
(async () => {
  try {
    const p = require('puppeteer');
    r.puppeteer_exec = p.executablePath();
    r.puppeteer_exec_exists = require('fs').existsSync(r.puppeteer_exec);
    const b = await p.launch({ headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'] });
    const pg = await b.newPage();
    await pg.setContent('<html><body style="font-family:sans-serif;font-size:16px"><span id=t>段取シート 日本語 テスト ABC123</span></body></html>');
    r.puppeteer_font = await pg.evaluate(() => getComputedStyle(document.getElementById('t')).fontFamily);
    const w = await pg.evaluate(() => document.getElementById('t').getBoundingClientRect().width);
    r.puppeteer_text_width = Math.round(w);
    const pdf = await pg.pdf({ format: 'A4' });
    r.puppeteer_pdf_bytes = pdf.length;
    r.puppeteer_version = await b.version();
    await b.close();
  } catch (e) { r.puppeteer_err = String(e).slice(0, 400); }
  console.log(JSON.stringify(r));
})();
"""
    rc, o = sh(["node", "-e", js], cwd=api, timeout=180, env=dict(NENV, TZ="Asia/Tokyo"))
    try:
        return json.loads(o.strip().splitlines()[-1])
    except Exception:
        return {"_error": o[-500:]}


# ──────────────────────────── DB ────────────────────────────
MASTERS = {
    # 表名: (並べ替えキー, 除く列)
    "users": ("employee_code", {"id", "created_at", "updated_at", "password_hash"}),
    "machines": ("machine_code", {"id", "created_at", "updated_at"}),
    "pdf_templates": ("name", {"id", "created_at", "updated_at"}),
    "business_calendars": ("work_date", {"id", "created_at", "updated_at"}),
    "clamp_vise": (None, {"id", "created_at", "updated_at"}),
    "clamp_chuck": (None, {"id", "created_at", "updated_at"}),
    "clamp_tsume": (None, {"id", "created_at", "updated_at"}),
    "clamp_shiki": (None, {"id", "created_at", "updated_at"}),
    "clamp_index": (None, {"id", "created_at", "updated_at"}),
    "nc_tool_shave1_master": (None, {"id", "created_at", "updated_at"}),
    "nc_tool_shave2_master": (None, {"id", "created_at", "updated_at"}),
    "nc_tool_chip_master": (None, {"id", "created_at", "updated_at"}),
    "nc_tool_holder_master": (None, {"id", "created_at", "updated_at"}),
    "special_sheets": ("sheet_name", {"id", "created_at", "updated_at"}),
    "company_settings": (None, {"id", "updated_at"}),
    "system_settings": ("key", {"id", "created_at", "updated_at"}),
}


def db_info(cfg):
    import psycopg2
    ev = read_env(Path(cfg["repo"]) / "apps" / "api" / ".env")
    dsn = (ev.get("DATABASE_URL") or "").split("?", 1)[0]
    pg = psycopg2.connect(dsn)
    pg.set_session(readonly=True, autocommit=True)
    c = pg.cursor()

    def q(sql, a=None):
        c.execute(sql, a)
        return c.fetchall()

    d = {"version": q("SHOW server_version")[0][0], "timezone": q("SHOW TimeZone")[0][0],
         "now_local": str(q("SELECT now()::timestamp")[0][0]), "now_utc": str(q("SELECT now() AT TIME ZONE 'UTC'")[0][0]),
         "encoding": q("SHOW server_encoding")[0][0]}
    r = q("SELECT datcollate, datctype FROM pg_database WHERE datname=current_database()")[0]
    d["collate"], d["ctype"] = r
    d["extensions"] = sorted(x[0] for x in q("SELECT extname FROM pg_extension"))
    cols = q("""SELECT table_name, column_name, data_type, is_nullable, column_default FROM information_schema.columns
                WHERE table_schema='public' ORDER BY table_name, ordinal_position""")
    sch = {}
    for t, col, dt, nul, de in cols:
        sch.setdefault(t, []).append(f"{col}:{dt}:{nul}:{re.sub(r'nextval.*', 'serial', str(de))}")
    d["schema"] = {t: sha(v) for t, v in sch.items()}
    d["schema_columns"] = sch
    d["indexes"] = sha(q("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1, 2"))
    d["fks"] = sha(q("""SELECT conrelid::regclass::text, pg_get_constraintdef(oid) FROM pg_constraint
                        WHERE contype='f' AND connamespace='public'::regnamespace ORDER BY 1, 2"""))
    counts = {}
    for t in sorted(sch):
        try:
            counts[t] = q(f'SELECT COUNT(*) FROM "{t}"')[0][0]
        except Exception:
            counts[t] = None
    d["counts"] = counts
    # マスタの中身
    masters = {}
    for t, (key, excl) in MASTERS.items():
        if t not in sch:
            continue
        c.execute(f'SELECT * FROM "{t}"')
        names = [x.name for x in c.description]
        rows = []
        for r in c.fetchall():
            row = {n: (v.isoformat() if hasattr(v, "isoformat") else v) for n, v in zip(names, r) if n not in excl}
            if t == "users":
                ph = r[names.index("password_hash")] if "password_hash" in names else None
                row["password_fp"] = sha(ph or "")
            if t == "system_settings" and isinstance(row.get("value"), str) and len(row["value"]) > 200:
                row["value"] = f"<{len(row['value'])}文字 {sha(row['value'])}>"
            if t == "special_sheets" and isinstance(row.get("content"), str):
                row["content"] = f"<{len(row['content'])}文字 {sha(row['content'])}>"
            rows.append(row)
        rows.sort(key=lambda x: json.dumps(x.get(key) if key else x, ensure_ascii=False, sort_keys=True, default=str))
        masters[t] = rows
    if "pdf_field_definitions" in sch:
        c.execute("""SELECT t.name, f.field_key, f.label, f.x, f.y, f.font_size, f.data_source, f.page_number,
                            f.sort_order, f.is_active, f.note
                     FROM pdf_field_definitions f JOIN pdf_templates t ON t.id=f.template_id ORDER BY 1, 2, 8, 9""")
        names = [x.name for x in c.description]
        masters["pdf_field_definitions"] = [dict(zip(names, r)) for r in c.fetchall()]
    d["masters"] = masters
    d["masters_fp"] = {t: sha(v) for t, v in masters.items()}
    # 変換データの概要(.11 と .14 でコンバート時期が違うので参考値)
    info = {}
    for label, sql in (("mc_programs(旧から)", "SELECT COUNT(*) FROM mc_programs WHERE legacy_mcid IS NOT NULL"),
                       ("mc_programs(新規)", "SELECT COUNT(*) FROM mc_programs WHERE legacy_mcid IS NULL"),
                       ("nc_programs(旧から)", "SELECT COUNT(*) FROM nc_programs WHERE legacy_nc_id IS NOT NULL"),
                       ("nc_programs(新規)", "SELECT COUNT(*) FROM nc_programs WHERE legacy_nc_id IS NULL"),
                       ("コンバート日時(作業記録の作成)", "SELECT MIN(created_at)::text FROM work_records"),
                       ("mc_files格納先の先頭", "SELECT split_part(file_path,'/',2)||'/'||split_part(file_path,'/',3)||'/'||split_part(file_path,'/',4), COUNT(*) FROM mc_files GROUP BY 1 ORDER BY 2 DESC LIMIT 3"),
                       ("nc_files格納先の先頭", "SELECT split_part(file_path,'/',2)||'/'||split_part(file_path,'/',3)||'/'||split_part(file_path,'/',4), COUNT(*) FROM nc_files GROUP BY 1 ORDER BY 2 DESC LIMIT 3")):
        try:
            rr = q(sql)
            info[label] = rr[0][0] if len(rr) == 1 and len(rr[0]) == 1 else [list(x) for x in rr]
        except Exception as e:
            info[label] = f"取得できません({e.__class__.__name__})"
    d["data"] = info
    pg.close()
    return d


def storage_info(db):
    cs = (db.get("masters", {}).get("company_settings") or [{}])[0] if isinstance(db, dict) else {}
    base = (cs.get("upload_base_path") or "").rstrip("/")
    s = {"upload_base_path": base or None, "mc_storage_path": cs.get("mc_storage_path"),
         "nc_storage_path": cs.get("nc_storage_path"), "logo_path": cs.get("logo_path")}
    if base:
        for sub in ("", "MC/files/Drawings", "MC/files/Pictures", "MC/files/Programs", "MC/files/thumbnails",
                    "MC/files/setupsheet", "NC/files/Programs", "special_sheets", "trash"):
            p = os.path.join(base, sub) if sub else base
            s[f"dir:{sub or '/'}"] = ("書込可" if os.access(p, os.W_OK) else "読取のみ") if os.path.isdir(p) else "無し"
        try:
            du = shutil.disk_usage(base)
            s["free_gb"] = round(du.free / 1024 ** 3)
        except Exception:
            pass
    for k in ("mc_storage_path", "nc_storage_path"):
        v = cs.get(k)
        if v:
            s[f"{k}_exists"] = os.path.isdir(v)
            s[f"{k}_writable"] = os.access(v, os.W_OK)
    return s


# ──────────────────────────── 動作確認(API・Web) ────────────────────────────
def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def admin_token(secret, uid):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64u(json.dumps({"sub": uid, "role": "ADMIN", "iat": int(time.time()), "exp": int(time.time()) + 1800}).encode())
    s = b64u(hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{s}"


_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def http(method, url, token=None, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            b = r.read()
            return r.status, r.headers.get("Content-Type", ""), b, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read() or b"", time.time() - t0
    except Exception as e:
        return None, "", str(e).encode(), time.time() - t0


def classify(ct, b):
    if b[:4] == b"%PDF":
        return "pdf"
    if b[:3] == b"\xff\xd8\xff" or b[:8] == b"\x89PNG\r\n\x1a\n" or b[:4] in (b"II*\x00", b"MM\x00*") or b[:4] == b"GIF8":
        return "image"
    if "json" in ct:
        try:
            j = json.loads(b or b"null")
            if isinstance(j, list):
                return f"json[{len(j)}]"
            if isinstance(j, dict):
                return "json{}" if j else "json{空}"
        except Exception:
            return "json(壊れ)"
    if "html" in ct:
        return "html"
    return (ct or "?").split(";")[0]


def smoke(cfg, db_dsn_env, samples=6):
    """副作用の無い API 呼び出しで、画面が使う機能が動くかを確かめる"""
    import psycopg2
    repo = Path(cfg["repo"])
    ev = read_env(repo / "apps" / "api" / ".env")
    secret = ev.get("JWT_SECRET") or "dev_secret_change_me"
    dsn = (ev.get("DATABASE_URL") or "").split("?", 1)[0]
    pg = psycopg2.connect(dsn)
    pg.set_session(readonly=True, autocommit=True)
    c = pg.cursor()

    def q(sql, a=None):
        c.execute(sql, a)
        return c.fetchall()

    adm = q("SELECT id FROM users WHERE employee_code='ADMIN001'")
    uid = adm[0][0] if adm else q("SELECT id FROM users WHERE role='ADMIN' ORDER BY id LIMIT 1")[0][0]
    tok = admin_token(secret, uid)
    api = f"http://127.0.0.1:{cfg['api_port']}/api"
    web = f"http://127.0.0.1:{cfg['web_port']}"

    # 試す加工データ(条件ごとに新しいものを1件ずつ。No.41 の MCID 8507 は必ず)
    def pick(sqls):
        ids = []
        for s in sqls:
            try:
                for r in q(s):
                    if r[0] not in ids:
                        ids.append(r[0])
            except Exception:
                pass
        return ids[:samples + 2]
    mc_ids = pick([
        "SELECT id FROM mc_programs WHERE legacy_mcid=8507",
        "SELECT p.id FROM mc_programs p JOIN mc_files f ON f.mc_program_id=p.id AND f.file_type='PROGRAM' ORDER BY p.legacy_mcid DESC NULLS LAST LIMIT 1",
        "SELECT p.id FROM mc_programs p JOIN mc_files f ON f.mc_program_id=p.id AND f.file_type='DRAWING' ORDER BY p.legacy_mcid DESC NULLS LAST LIMIT 1",
        "SELECT p.id FROM mc_programs p JOIN mc_files f ON f.mc_program_id=p.id AND f.file_type='PHOTO' ORDER BY p.legacy_mcid DESC NULLS LAST LIMIT 1",
        "SELECT p.id FROM mc_programs p JOIN mc_machining_details d ON d.machining_id=p.machining_id WHERE d.pg_is_folder ORDER BY p.legacy_mcid DESC NULLS LAST LIMIT 1",
        "SELECT mc_program_id FROM work_records WHERE mc_program_id IS NOT NULL ORDER BY work_date DESC LIMIT 1",
        "SELECT p.id FROM mc_programs p WHERE p.machining_id IN (SELECT machining_id FROM mc_programs GROUP BY 1 HAVING COUNT(*)>1) ORDER BY p.legacy_mcid DESC NULLS LAST LIMIT 1",
        "SELECT id FROM mc_programs WHERE legacy_mcid IS NULL ORDER BY id DESC LIMIT 1",
    ])
    nc_ids = pick([
        "SELECT p.id FROM nc_programs p JOIN nc_files f ON f.nc_program_id=p.id ORDER BY p.legacy_nc_id DESC NULLS LAST LIMIT 1",
        "SELECT nc_program_id FROM work_records WHERE nc_program_id IS NOT NULL ORDER BY work_date DESC LIMIT 1",
        "SELECT p.id FROM nc_programs p WHERE p.machining_id IN (SELECT machining_id FROM nc_programs GROUP BY 1 HAVING COUNT(*)>1) ORDER BY p.legacy_nc_id DESC NULLS LAST LIMIT 1",
        "SELECT id FROM nc_programs WHERE status='APPROVED' ORDER BY legacy_nc_id DESC NULLS LAST LIMIT 1",
        "SELECT id FROM nc_programs WHERE legacy_nc_id IS NULL ORDER BY id DESC LIMIT 1",
    ])
    mfiles = {}
    for t in ("DRAWING", "PHOTO", "PROGRAM"):
        r = q("SELECT mc_program_id, id FROM mc_files WHERE file_type=%s AND NOT is_deleted ORDER BY id DESC LIMIT 1", (t,))
        if r:
            mfiles[t] = r[0]
    sl_mc = q("SELECT id FROM mc_setup_sheet_logs WHERE pdf_path IS NOT NULL ORDER BY id DESC LIMIT 1")
    sl_nc = q("SELECT id FROM setup_sheet_logs WHERE pdf_path IS NOT NULL ORDER BY id DESC LIMIT 1")
    legacy = dict(q("SELECT id, legacy_mcid FROM mc_programs WHERE id = ANY(%s)", (mc_ids,))) if mc_ids else {}
    nlegacy = dict(q("SELECT id, legacy_nc_id FROM nc_programs WHERE id = ANY(%s)", (nc_ids,))) if nc_ids else {}
    part = q("SELECT p.part_id, p.drawing_no FROM parts p JOIN mc_programs m ON m.part_id=p.id ORDER BY m.id DESC LIMIT 1")
    machine = q("SELECT id FROM machines WHERE is_active AND system_type::text IN ('MC','BOTH') ORDER BY sort_order, id LIMIT 1")
    pg.close()

    today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
    calls = []

    def add(group, method, path, expect="json", body=None, base=None, token=True, ok_codes=(200, 201)):
        calls.append((group, method, path, expect, body, base or api, token, ok_codes))

    for p in ("/admin/company", "/admin/settings/mc-nc", "/admin/printers", "/admin/printer", "/admin/machines",
              "/admin/users", "/admin/pdf-templates", "/admin/pdf-fields", "/admin/system-settings", "/admin/storage",
              "/admin/special-sheets", "/admin/clients", "/admin/clamp-master/vise", "/admin/nc-tool-master/shave1",
              "/admin/calendar", "/admin/upload-agent/version", "/admin/pm2/status", "/admin/system-logs",
              "/language/config", "/machines", "/users", "/dashboard/summary", "/dashboard/uncollected-mc",
              "/dashboard/uncollected-nc", "/mc/recent", "/nc/recent", "/mc/clamp-master", "/nc/client-names",
              f"/mc/timecards/all?work_date={today}",
              f"/mc/timecards/holidays?from={today - timedelta(days=31)}&to={today}",
              f"/admin/timecards?work_date={today}"):
        add("共通", "GET", p)
    if machine:
        add("共通", "GET", f"/mc/timecards?machine_id={machine[0][0]}&work_date={today}")
    if part:
        add("検索", "GET", f"/mc/search?key=part_id&q={urllib.request.quote(str(part[0][0]))}&limit=5")
        add("検索", "GET", f"/mc/search?key=drawing_no&q={urllib.request.quote(str(part[0][1] or ''))}&limit=5")
        add("検索", "GET", f"/nc/search?key=drawing_no&q={urllib.request.quote(str(part[0][1] or ''))}&limit=5")
        add("検索", "GET", f"/mc/parts-search?q={urllib.request.quote(str(part[0][0]))}")
    add("検索", "GET", "/mc/search?limit=5")
    add("検索", "GET", "/nc/search?limit=5")
    for i in mc_ids:
        g = f"MC id={i} MCID={legacy.get(i)}"
        for s in ("", "/tooling", "/work-offsets", "/index-programs", "/work-records", "/change-history",
                  "/setup-sheet-logs", "/files", "/pg-files-list", "/pg-file-info", "/special-sheet-check", "/print-data"):
            add(g, "GET", f"/mc/{i}{s}")
        add(g, "GET", f"/mc/{i}/pg-file", ok_codes=(200, 404))
        add(g, "GET", f"/mc/{i}/drawing-images", ok_codes=(200, 404))
        add(g, "POST", f"/mc/{i}/repeat-print", "pdf", {"include_tooling": True, "include_clamp": True,
                                                         "include_drawings": True, "include_work_offsets": True,
                                                         "include_index_programs": True})
        add(g, "GET", f"/admin/pdf-new-full-preview?mc_id={i}", "pdf")
        add(g, "GET", f"/mc/{i}", "html", base=web, token=False)
        add(g, "GET", f"/mc/{i}/edit", "html", base=web, token=False)
        add(g, "GET", f"/mc/{i}/record", "html", base=web, token=False)
        add(g, "GET", f"/mc/{i}/print", "html", base=web, token=False)
    for t, (pid, fid) in mfiles.items():
        add(f"MCファイル {t}", "GET", f"/mc/{pid}/files/{fid}/serve", "any")
        if t != "PROGRAM":
            add(f"MCファイル {t}", "GET", f"/mc/{pid}/files/{fid}/thumb", "image")
    for i in nc_ids:
        g = f"NC id={i} NC_id={nlegacy.get(i)}"
        for s in ("", "/tooling", "/work-records", "/change-history", "/setup-sheet-logs", "/files", "/pg-files-list",
                  "/print-data", "/operation-logs"):
            add(g, "GET", f"/nc/{i}{s}")
        add(g, "GET", f"/nc/{i}/pg-file", ok_codes=(200, 404))
        add(g, "GET", f"/nc/{i}/drawing-images", ok_codes=(200, 404))
        add(g, "POST", f"/nc/{i}/repeat-print", "pdf", {"include_tools": True, "include_clamp": True, "include_drawings": True})
        add(g, "GET", f"/nc/{i}", "html", base=web, token=False)
        add(g, "GET", f"/nc/{i}/edit", "html", base=web, token=False)
        add(g, "GET", f"/nc/{i}/record", "html", base=web, token=False)
    if sl_mc:
        add("段取シート原本PDF", "GET", f"/mc/setup-sheet-logs/{sl_mc[0][0]}/pdf", "pdf")
    if sl_nc:
        add("段取シート原本PDF", "GET", f"/nc/setup-sheet-logs/{sl_nc[0][0]}/pdf", "pdf")
    for p in ("/", "/mc", "/nc", "/mc/search", "/nc/search", "/mc/new", "/nc/new", "/mc/timecards",
              "/admin/login", "/admin/settings", "/admin/users", "/admin/machines", "/admin/pdf-editor",
              "/admin/calendar", "/admin/clamp-master", "/admin/nc-tool-master", "/admin/special-sheets",
              "/admin/file-browser", "/admin/upload-agent", "/admin/language"):
        add("Web 画面", "GET", p, "html", base=web, token=False)
    add("Web→API 転送", "GET", "/api/admin/company", "json", base=web, token=False)
    https = cfg.get("https_port")
    if https:
        add("https(nginx)", "GET", "/", "html", base=f"https://127.0.0.1:{https}", token=False)
        add("https(nginx)", "GET", "/api/admin/company", "json", base=f"https://127.0.0.1:{https}", token=False)
        add("https(nginx)", "GET", "/mc", "html", base=f"https://127.0.0.1:{https}", token=False)

    res = []
    for group, method, path, expect, body, base, token, ok_codes in calls:
        st, ct, b, el = http(method, base + path, tok if token else None, body)
        kind = classify(ct, b)
        ok = st in ok_codes and (expect == "any" or st == 404 or kind == expect or kind.startswith(expect))
        if expect == "json" and st in ok_codes and kind == "json(壊れ)":
            ok = False
        msg = ""
        if not ok:
            try:
                msg = b[:300].decode("utf-8", errors="replace")
            except Exception:
                msg = ""
        res.append({"group": group, "method": method, "path": path if base == api else base.split("//")[1].split(":")[-1] + "|" + path,
                    "status": st, "kind": kind, "bytes": len(b), "sec": round(el, 2), "ok": ok, "msg": msg})
    return {"samples_mc": {str(k): v for k, v in legacy.items()}, "samples_nc": {str(k): v for k, v in nlegacy.items()},
            "results": res, "ng": sum(1 for r in res if not r["ok"]), "total": len(res)}


def https_port_for(web_port, nginx):
    for s in nginx or []:
        if any(f":{web_port}" in p for p in s.get("proxy", [])):
            for l in s.get("listen", []):
                if l not in (80,):
                    return l
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="対象リポジトリ(既定はこのスクリプトのあるリポジトリ)")
    ap.add_argument("--out", default=None, help="JSON の保存先")
    ap.add_argument("--stdout", action="store_true", help="JSON を標準出力へ(他の表示は標準エラーへ)")
    ap.add_argument("--no-smoke", action="store_true", help="API 動作確認をしない")
    ap.add_argument("--samples", type=int, default=6, help="動作確認で開く加工データの数(MC/NC それぞれ)")
    a = ap.parse_args()
    say = (lambda m: print(m, file=sys.stderr, flush=True)) if a.stdout else (lambda m: print(m, flush=True))
    if a.repo:
        repo = Path(os.path.expanduser(a.repo)).resolve()
    else:
        try:
            repo = Path(__file__).resolve().parent.parent
        except NameError:
            repo = Path.cwd()
        if not (repo / "apps" / "api").is_dir():
            repo = Path.cwd()
    say(f"[指紋] {socket.gethostname()} {repo}")
    fp = {"taken_at": datetime.now().isoformat(timespec="seconds"), "host": safe(host_info)}
    cfg = safe(instance_config, repo)
    if isinstance(cfg, dict) and "_error" not in cfg:
        cfg["https_port"] = https_port_for(cfg.get("web_port"), fp["host"].get("nginx") if isinstance(fp["host"], dict) else [])
    fp["instance"] = cfg
    say("  実行部品(sharp / puppeteer / フォント)...")
    fp["runtime"] = safe(runtime_checks, repo)
    say("  DB ...")
    fp["db"] = safe(db_info, cfg)
    fp["storage"] = safe(storage_info, fp["db"])
    if not a.no_smoke and isinstance(cfg, dict) and "_error" not in cfg:
        say("  API・画面の動作確認 ...")
        fp["smoke"] = safe(smoke, cfg, None, a.samples)
        sm = fp["smoke"]
        if isinstance(sm, dict) and "results" in sm:
            say(f"  動作確認: {sm['total'] - sm['ng']}/{sm['total']} OK")
            for r in sm["results"]:
                if not r["ok"]:
                    say(f"    [NG] {r['group']} {r['method']} {r['path']} → {r['status']} {r['kind']} {r['msg'][:160]}")
    js = json.dumps(fp, ensure_ascii=False, indent=1, default=str)
    if a.stdout:
        sys.stdout.write(js)
    out = a.out or (None if a.stdout else str(repo / "scripts" / "verify_reports" / f"fingerprint_{socket.gethostname()}_{datetime.now():%Y%m%d_%H%M%S}.json"))
    if out:
        Path(out).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(out).expanduser().write_text(js, encoding="utf-8")
        say(f"  保存: {Path(out).expanduser()}")


if __name__ == "__main__":
    main()
