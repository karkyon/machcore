#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parity_check.py — .11(UAT で確かめてきた環境)と .14(internal / group)の動作環境を突き合わせる(再利用スクリプト・何も変更しない)

UAT を .11 から .14 に移すにあたり「環境が変わったことによる問題」を事前に洗い出す。
両方で env_fingerprint.py の指紋を取り、項目ごとに 一致 / 想定内の違い / 要対応 を判定する。

  ・ホスト: 時刻帯・言語・Python/Node 等の版・帳票フォント(ipag.ttf と日本語フォント)・プリンタ・
            旧ファイル共有のマウント・cron・pm2(TZ)・nginx(アップロード上限・タイムアウト)
  ・設定  : .env のキーと安全な値(RIDOC_API_URL・TZ 等)・pm2 設定の env・Web の API 転送先・
            帳票テンプレート PDF(管理画面で差し替えた版)・ロゴ
  ・実行部品: sharp・puppeteer(Chromium で日本語 PDF)・帳票フォント
  ・DB    : 版・時刻帯・文字コード・照合順序・スキーマ(列定義)・索引・外部キー
  ・マスタ: 利用者(パスワードの指紋含む)・機械・帳票テンプレート/印字位置・営業日カレンダー・
            クランプ/加工リスト候補・特殊シート・会社設定・システム設定(言語の辞書等)
  ・格納先: upload_base_path の各フォルダ・mc/nc_storage_path が共有先を指していないか
  ・動作確認: 両方で API・画面・プレビュー PDF・図面(Ridoc)・画像・https を実際に呼ぶ(書き込みなし)

実行(.14 で。.11 の指紋は ssh で .11 上で取る。パスワードを聞かれたら .11 の karkyon のパスワード):
  cd ~/projects/machcore-internal && git fetch origin && git reset --hard origin/main \\
    && python3 scripts/parity_check.py --ref-ssh karkyon@192.168.1.11
  .11 の指紋を先に取ってある場合: --ref ~/fp_11.json
  ssh が使えない場合: --ref-db(.11 の DB 192.168.1.11:5440 を直接読む。DB・マスタ・格納先設定だけを比べる。
                     ホスト・実行部品・動作確認は .14 側の単独の点検(deploy_14 の動作確認)で確かめる)
  対象を絞る: --targets internal   (既定 internal,group)

出力: scripts/verify_reports/parity_<日時>.md / .json(指紋も保存)。要対応(NG)があれば終了コード 1
"""
import os
import re
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REF_DB_DEFAULT = "postgresql://machcore:machcore_pass_change_me@192.168.1.11:5440/machcore_dev"
REPOS = {"internal": HOME / "projects" / "machcore-internal", "group": HOME / "projects" / "machcore-group",
         "11": HOME / "projects" / "machcore"}

ROWS = []


def row(level, target, area, item, ref, tgt, note=""):
    ROWS.append({"level": level, "target": target, "area": area, "item": item,
                 "ref": _s(ref), "tgt": _s(tgt), "note": note})


def _s(v):
    if v is None:
        return "—"
    if isinstance(v, (list, dict)):
        t = json.dumps(v, ensure_ascii=False, default=str)
    else:
        t = str(v)
    return t if len(t) <= 400 else t[:400] + "…"


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d is not None else default


def take_local(repo):
    py = sys.executable
    r = subprocess.run([py, str(HERE / "env_fingerprint.py"), "--repo", str(repo), "--stdout"],
                       capture_output=True, text=True, timeout=1800)
    sys.stderr.write(r.stderr)
    return json.loads(r.stdout)


def take_ssh(target):
    host, _, repo = target.partition(":")
    repo = repo or "~/projects/machcore"
    cmd = (f"cd {repo} && git fetch -q origin main && git show origin/main:scripts/env_fingerprint.py "
           f"| python3 - --repo {repo} --stdout")
    print(f"[.11] ssh {host} で指紋を取ります(パスワードを聞かれたら入力)", flush=True)
    r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=accept-new", host, cmd], stdout=subprocess.PIPE,
                       stderr=None, text=True, timeout=1800)
    if r.returncode != 0 or not r.stdout.strip().startswith("{"):
        raise SystemExit(f"[FAIL] .11 の指紋を取れませんでした(rc={r.returncode})。.11 で "
                         f"python3 scripts/env_fingerprint.py --out ~/fp_11.json を実行し、そのファイルを .14 にコピーして "
                         f"--ref で指定してください")
    return json.loads(r.stdout)


# ──────────────────────────── 比較 ────────────────────────────
def norm_cron(lines, repo):
    out = set()
    for l in lines or []:
        l = l.replace(str(repo), "{REPO}")
        l = re.sub(r"/home/\w+/projects/machcore(-internal|-group)?", "{REPO}", l)
        l = re.sub(r"\S*/python3(\.\d+)?", "{PY}", l)
        out.add(l)
    return out


def ver_major(v):
    m = re.search(r"(\d+)", str(v or ""))
    return m.group(1) if m else None


def compare_host(R, T, t):
    rh, th = R.get("host", {}), T.get("host", {})
    for k, lv in (("timezone", "NG"), ("utc_offset", "NG"), ("lang", "WARN")):
        a, b = rh.get(k), th.get(k)
        row("OK" if a == b else lv, t, "ホスト", k, a, b, "" if a == b else "時刻の扱い(作業日・タイムカード・帳票の日付)が変わる恐れ" if k != "lang" else "")
    for k in ("py_pymssql", "py_psycopg2"):
        b = th.get(k)
        row("NG" if not b or "なし" in str(b) else "OK", t, "ホスト", k, rh.get(k), b)
    a, b = rh.get("cmd_node"), th.get("cmd_node")
    row("OK" if ver_major(a) == ver_major(b) else "NG", t, "ホスト", "node", a, b)
    for k in ("cmd_pnpm", "cmd_pm2", "python"):
        a, b = rh.get(k), th.get(k)
        row("OK" if ver_major(a) == ver_major(b) else "WARN", t, "ホスト", k.replace("cmd_", ""), a, b)
    for k in ("cmd_lp", "cmd_lpstat", "cmd_fc-list", "cmd_mount.cifs"):
        a, b = rh.get(k), th.get(k)
        row("OK" if b or not a else "NG", t, "ホスト", k.replace("cmd_", "コマンド "), a, b)
    a, b = rh.get("font_ipag_ttf"), th.get("font_ipag_ttf")
    row("OK" if b else "NG", t, "帳票フォント", "ipag.ttf(MC 段取シート)", a, b, "" if b else "sudo apt install fonts-ipafont-gothic")
    fa, fb = set(rh.get("fonts_ja") or []), set(th.get("fonts_ja") or [])
    if not fb:
        row("NG", t, "帳票フォント", "日本語フォント(NC 段取シート・Chromium)", sorted(fa), [], "日本語が描けません")
    else:
        miss = sorted(fa - fb)
        row("OK" if not miss else "WARN", t, "帳票フォント", "日本語フォント(NC 段取シート・Chromium)",
            f"{len(fa)}種", f"{len(fb)}種", ("無いフォント: " + ", ".join(miss)) if miss else "")
    a, b = rh.get("font_default_ja_sans"), th.get("font_default_ja_sans")
    row("OK" if a == b else "WARN", t, "帳票フォント", "既定の日本語ゴシック(fc-match)", a, b,
        "" if a == b else "NC 段取シートの文字の幅・改行位置が .11 と変わる恐れ")
    # プリンタ
    cs = (g(T, "db", "masters", "company_settings") or [{}])[0]
    for k in ("mc_printer", "nc_printer", "printer_name"):
        p = cs.get(k)
        if p:
            row("OK" if p in (th.get("printers") or []) else "NG", t, "プリンタ", f"会社設定 {k}", None, p,
                "" if p in (th.get("printers") or []) else "CUPS に登録がありません")
    miss = sorted(set(rh.get("printers") or []) - set(th.get("printers") or []))
    row("OK" if not miss else "INFO", t, "プリンタ", "CUPS 登録", rh.get("printers"), th.get("printers"),
        ("(.11 にだけある: " + ", ".join(miss) + ")") if miss else "")
    # マウント
    tm = {m["dst"]: m for m in th.get("mounts") or []}
    leg = tm.get("/mnt/mcfiles")
    row("OK" if leg else "NG", t, "旧ファイル共有", "/mnt/mcfiles(コンバートのコピー元)", g({m["dst"]: m for m in rh.get("mounts") or []}, "/mnt/mcfiles"), leg,
        "" if leg else "コンバートで図・写真・プログラムが登録されません")
    if leg and leg.get("mode") == "rw":
        row("WARN", t, "旧ファイル共有", "/mnt/mcfiles の書き込み", None, "rw", "読むだけなので ro 推奨")
    # cron
    rrepo = g(R, "instance", "repo") or ""
    trepo = g(T, "instance", "repo") or ""
    rc = norm_cron(rh.get("crontab"), rrepo)
    tc = norm_cron([l for l in th.get("crontab") or [] if trepo in l or "machcore" not in l], trepo)
    miss = sorted(rc - tc)
    row("OK" if not miss else "WARN", t, "cron", ".11 にあって .14 に無い定期実行", len(rc), len(tc), " / ".join(miss)[:600])
    # pm2
    names = [a.get("name") for a in g(T, "instance", "pm2_apps", default=[])]
    procs = {p["name"]: p for p in th.get("pm2") or []}
    for n in names:
        p = procs.get(n)
        st = p.get("status") if p else None
        row("OK" if st == "online" else "NG", t, "pm2", n, None, f"{st} 再起動{p.get('restarts') if p else '-'}回" if p else "未登録")
        if p and p.get("restarts") and p.get("uptime_h", 99) < 0.2 and (p.get("restarts") or 0) > 3:
            row("WARN", t, "pm2", f"{n} 再起動の繰り返し", None, f"{p.get('restarts')}回", "落ちて再起動している可能性")
    for a in g(T, "instance", "pm2_apps", default=[]):
        tz = (a.get("env") or {}).get("TZ")
        row("OK" if tz == "Asia/Tokyo" else "NG", t, "pm2 設定", f"{a.get('name')} TZ", None, tz, "" if tz == "Asia/Tokyo" else "Node の時刻帯が JST になりません")
    row("OK" if th.get("pm2_autostart") == "enabled" else "WARN", t, "pm2", "OS 起動時の自動起動", rh.get("pm2_autostart"), th.get("pm2_autostart"))
    # nginx(アップロード上限・タイムアウト)
    rweb, tweb = g(R, "instance", "web_port"), g(T, "instance", "web_port")

    def blk(h, port):
        for s in h.get("nginx") or []:
            if any(f":{port}" in p for p in s.get("proxy", [])) and any(l not in (80,) for l in s.get("listen", [])):
                return s
        return None
    rb, tb = blk(rh, rweb), blk(th, tweb)
    if not tb:
        row("NG", t, "nginx", "https → Web の転送", None, None, "この Web ポートへ転送する server がありません")
    else:
        for k in ("client_max_body_size", "proxy_read_timeout"):
            a, b = (rb or {}).get(k), tb.get(k)
            row("OK" if a == b else "NG" if k == "client_max_body_size" else "WARN", t, "nginx", k, a, b,
                "" if a == b else ("大きい写真・図・プログラムのアップロードが nginx で拒否される恐れ" if k == "client_max_body_size"
                                   else "PDF 生成など時間のかかる処理が途中で切れる恐れ"))


INSTANCE_ENV = {"API_PORT", "PORT", "UPLOAD_AGENT_DIR", "CORS_ORIGINS", "NEXT_PUBLIC_API_URL", "UPLOAD_BASE_PATH",
                "POSTGRES_DB", "POSTGRES_USER"}


def compare_instance(R, T, t):
    ri, ti = R.get("instance", {}), T.get("instance", {})
    row("OK" if ri.get("git_head") == ti.get("git_head") else "INFO", t, "コード", "版", f"{ri.get('git_head')} {ri.get('git_subject')}",
        f"{ti.get('git_head')} {ti.get('git_subject')}")
    if ti.get("git_dirty"):
        row("WARN", t, "コード", "Git と違うファイル", None, ti.get("git_dirty"))
    rk, tk = set(ri.get("env_keys") or []), set(ti.get("env_keys") or [])
    miss = sorted((rk - tk) - INSTANCE_ENV)
    row("OK" if not miss else "WARN", t, ".env", ".11 にあって無いキー", None, miss)
    renv, tenv = ri.get("env") or {}, ti.get("env") or {}
    rapi = next((a.get("env", {}) for a in ri.get("pm2_apps") or [] if "apps/api" in (a.get("cwd") or "")), {})
    tapi = next((a.get("env", {}) for a in ti.get("pm2_apps") or [] if "apps/api" in (a.get("cwd") or "")), {})
    for k in ("RIDOC_API_URL", "TZ", "JWT_EXPIRES_IN", "NODE_ENV"):
        a = tapi.get(k) or tenv.get(k)
        b = rapi.get(k) or renv.get(k)
        row("OK" if a == b else ("NG" if k in ("RIDOC_API_URL", "TZ") else "WARN"), t, "設定", k, b, a)
    cors = tapi.get("CORS_ORIGINS") or tenv.get("CORS_ORIGINS") or "(未設定=.11 用の既定値)"
    hp = T.get("instance", {}).get("https_port")
    own = f"https://192.168.1.14:{hp}" if hp else None
    row("OK" if own and own in cors else "WARN", t, "設定", "CORS_ORIGINS に自分の https", own, cors)
    bk = ti.get("web_baked_api_ports")
    row("OK" if bk == [str(ti.get("api_port"))] else "NG", t, "Web", "ビルドに焼き込んだ API 転送先", None, bk, f"想定 {ti.get('api_port')}")
    # 帳票テンプレート PDF
    ra, ta = ri.get("assets") or {}, ti.get("assets") or {}
    diff = sorted(k for k in set(ra) | set(ta) if ra.get(k) != ta.get(k))
    row("OK" if not diff else "NG", t, "帳票テンプレート", "apps/api/assets の PDF", f"{len(ra)}件", f"{len(ta)}件",
        ("中身が違う: " + ", ".join(diff)) if diff else "")
    if ri.get("assets_changed_from_git"):
        row("WARN", t, "帳票テンプレート", ".11 で管理画面から差し替えて Git に無い PDF", ri.get("assets_changed_from_git"), None,
            "deploy の git reset で .14 には入りません。.11 から持ってくる必要があります")
    rb, tb = ri.get("web_public_branding") or {}, ti.get("web_public_branding") or {}
    if rb != tb:
        row("WARN" if t == "internal" else "INFO", t, "ロゴ", "apps/web/public の branding/logo", rb, tb)


def compare_runtime(R, T, t):
    rr, tr = R.get("runtime", {}), T.get("runtime", {})
    for k, label in (("sharp", "sharp(画像・サムネイル)"), ("ipag_bytes", "帳票フォントの読み込み"), ("pdflib", "pdf-lib"),
                     ("puppeteer_pdf_bytes", "Chromium で日本語 PDF(NC 段取シート)")):
        ok = bool(tr.get(k))
        err = tr.get(k.split("_")[0] + "_err") or tr.get("puppeteer_err") if not ok else ""
        row("OK" if ok else "NG", t, "実行部品", label, "OK" if rr.get(k) else rr.get(k), "OK" if ok else "NG", err or "")
    a, b = rr.get("puppeteer_font"), tr.get("puppeteer_font")
    aw, bw = rr.get("puppeteer_text_width"), tr.get("puppeteer_text_width")
    row("OK" if aw == bw else "WARN", t, "実行部品", "Chromium の日本語の文字幅", f"{a} {aw}px", f"{b} {bw}px",
        "" if aw == bw else "NC 段取シートの文字の幅・改行位置が .11 と変わる恐れ(フォントの違い)")


def compare_db(R, T, t):
    rd, td = R.get("db", {}), T.get("db", {})
    if "_error" in td:
        row("NG", t, "DB", "接続", None, td["_error"])
        return
    for k, lv in (("timezone", "NG"), ("encoding", "NG"), ("collate", "NG"), ("ctype", "NG"), ("version", "WARN")):
        a, b = rd.get(k), td.get(k)
        same = a == b if k != "version" else ver_major(a) == ver_major(b)
        row("OK" if same else lv, t, "DB", k, a, b, "" if same else {"timezone": "NOW() で入る日時(コンバートの作成日時など)がずれる",
                                                                       "collate": "並び順(五十音・英数字)が変わる"}.get(k, ""))
    # 列の定義: 列名・型・NULL 可否が違えば NG。既定値の書き方だけの違い(CURRENT_TIMESTAMP と now() 等)は同じとみなす。
    # _prisma_migrations(prisma migrate の履歴表。アプリは使わない)は比べない
    def norm_cols(cols):
        out = set()
        for c in cols or []:
            p = c.split(":", 3)
            de = (p[3] if len(p) > 3 else "").replace("now()", "CURRENT_TIMESTAMP")
            de = re.sub(r"::[a-z ]+", "", de)
            out.add((p[0], p[1], p[2], de))
        return out
    rc_, tc_ = g(rd, "schema_columns", default={}), g(td, "schema_columns", default={})
    tabs = sorted((set(rc_) | set(tc_)) - {"_prisma_migrations"})
    hard, soft = [], []
    for tb in tabs:
        a, b = norm_cols(rc_.get(tb)), norm_cols(tc_.get(tb))
        a3, b3 = {x[:3] for x in a}, {x[:3] for x in b}
        if a3 != b3:
            hard.append(f"{tb}: .11のみ{sorted(':'.join(x) for x in a3 - b3)} .14のみ{sorted(':'.join(x) for x in b3 - a3)}")
        elif a != b:
            soft.append(f"{tb}: " + ", ".join(f"{x[0]} {x[3] or '-'}→{y[3] or '-'}" for x in sorted(a - b) for y in b if y[:3] == x[:3]))
    row("OK" if not hard else "NG", t, "DB", "スキーマ(列名・型・NULL可否)", f"{len(rc_)}表", f"{len(tc_)}表", " / ".join(hard)[:1500])
    if soft:
        row("INFO", t, "DB", "列の既定値の違い(動作に影響なし)", None, None, " / ".join(soft)[:900])
    # 索引: .11 にあって .14 に無いものは検索の速さ・一意の守りが変わるため注意。
    # .14 にだけあるもの(余分な一意索引等)は .14 でコンバート試験・動作確認を通っているため参考
    ri = {x for x in (rd.get("indexes_list") or []) if not x.startswith("_prisma_migrations")}
    ti = {x for x in (td.get("indexes_list") or []) if not x.startswith("_prisma_migrations")}
    if ri or ti:
        row("OK" if not (ri - ti) else "WARN", t, "DB", "索引(.11 にあるもの)", f"{len(ri)}件", f"{len(ti)}件",
            f".14 に無い: {sorted(ri - ti)[:10]}" if ri - ti else "")
        if ti - ri:
            row("INFO", t, "DB", "索引(.14 にだけあるもの)", None, None,
                f"{sorted(ti - ri)[:10]}(.14 でコンバート試験・動作確認済み。アプリが作る行は該当列が空のため影響なし)")
    for k in ("fks",):
        row("OK" if rd.get(k) == td.get(k) else "WARN", t, "DB", k, rd.get(k), td.get(k))
    re_, te_ = set(rd.get("extensions") or []), set(td.get("extensions") or [])
    row("OK" if re_ == te_ else ("WARN" if re_ - te_ else "INFO"), t, "DB", "拡張", sorted(re_), sorted(te_),
        "" if re_ == te_ else (f".14 に無い: {sorted(re_ - te_)}" if re_ - te_ else ".14 にだけある拡張(アプリは使わない)"))


MASTER_KEYS = {"users": ("employee_code",), "machines": ("machine_code",), "pdf_templates": ("name",),
               "pdf_field_definitions": ("name", "field_key", "page_number", "sort_order"),
               "business_calendars": ("work_date",), "special_sheets": ("sheet_name", "keyword"),
               "system_settings": ("key",),
               "clamp_vise": ("name", "model"), "clamp_chuck": ("name", "size", "maker"), "clamp_tsume": ("name",),
               "clamp_shiki": ("name",), "clamp_index": ("name", "machine", "model"),
               "nc_tool_shave1_master": ("name",), "nc_tool_shave2_master": ("name",),
               "nc_tool_chip_master": ("name",), "nc_tool_holder_master": ("name",)}
MASTER_LABEL = {"users": "利用者", "machines": "機械", "pdf_templates": "帳票テンプレート", "pdf_field_definitions": "帳票の印字位置",
                "business_calendars": "営業日カレンダー", "special_sheets": "特殊シート", "system_settings": "システム設定(言語の辞書等)",
                "clamp_vise": "クランプ候補(バイス)", "clamp_chuck": "クランプ候補(チャック)", "clamp_tsume": "クランプ候補(爪)",
                "clamp_shiki": "クランプ候補(敷)", "clamp_index": "クランプ候補(インデックス)",
                "nc_tool_shave1_master": "NC加工リスト候補(加)", "nc_tool_shave2_master": "NC加工リスト候補(工)",
                "nc_tool_chip_master": "NC加工リスト候補(形状)", "nc_tool_holder_master": "NC加工リスト候補(ホルダー)",
                "company_settings": "会社設定"}
# アプリ(mc.service.ts)が設定なしの時に使う値。.14 にだけあってもこの値なら .11 と同じ動き
SETTING_DEFAULTS = {"cron_timecard_enabled": "true", "cron_timecard_hour": "5", "cron_timecard_minute": "0",
                    "timecard_default_start": "08:00", "timecard_default_end": "17:00"}
SETTING_INSTANCE = {"upload_agent_version": "配布している UploadAgent の版", "custom_dict_vi": "ベトナム語の訳の手直し",
                    "custom_dict_ja": "日本語の訳の手直し"}
GROUP_OWN = {"users": "group 独自の利用者(internal の人は無効・ログイン不可でコンバート時に補完)",
             "machines": "group 独自の機械(internal の機械は無効でコンバート時に補完)",
             "business_calendars": "group の休日は group で登録(.11 の休日はイモト精機のもの)",
             "system_settings": "group 独自の設定(既定の言語等)"}
COMPANY_INSTANCE = {"upload_base_path", "mc_storage_path", "nc_storage_path", "logo_path"}


def keyed(rows, keys):
    out = {}
    for r in rows or []:
        k = tuple(str(r.get(x)) for x in keys) if keys else json.dumps(r, ensure_ascii=False, sort_keys=True, default=str)
        out[k] = r
    return out


def compare_masters(R, T, t):
    rm, tm = g(R, "db", "masters", default={}), g(T, "db", "masters", default={})
    strict = t == "internal"     # internal は .11 と同じ会社(イモト精機)。group は別会社なので違って当然のものは注意
    for tb in MASTER_LABEL:
        a, b = rm.get(tb), tm.get(tb)
        if a is None and b is None:
            continue
        label = MASTER_LABEL[tb]
        if tb == "company_settings":
            ca, cb = (a or [{}])[0], (b or [{}])[0]
            ign = COMPANY_INSTANCE | ({"company_name"} if t == "group" else set())
            d = {k: (ca.get(k), cb.get(k)) for k in set(ca) | set(cb) if k not in ign and ca.get(k) != cb.get(k)}
            pr = {"mc_printer", "nc_printer", "printer_name"}
            dp = {k: v for k, v in d.items() if k in pr}
            do = {k: v for k, v in d.items() if k not in pr}
            row("OK" if not do else "WARN", t, "マスタ", label, None, None, " / ".join(f"{k}: {x}→{y}" for k, (x, y) in do.items()))
            if dp:
                row("INFO", t, "マスタ", label + "(プリンタ)", None, None,
                    "プリンタは .14 の CUPS に登録した名前(環境ごとに違うのが正しい): "
                    + " / ".join(f"{k}: {x}→{y}" for k, (x, y) in dp.items()))
            continue
        keys = MASTER_KEYS.get(tb)
        ka, kb = keyed(a, keys), keyed(b, keys)
        only_r = sorted(set(ka) - set(kb))
        only_t = sorted(set(kb) - set(ka))
        chg = []
        for k in sorted(set(ka) & set(kb)):
            if keys and ka[k] != kb[k]:
                fs = [f for f in set(ka[k]) | set(kb[k]) if ka[k].get(f) != kb[k].get(f)]
                chg.append(f"{'/'.join(k)}[{','.join(sorted(fs))}]")
        if not (only_r or only_t or chg):
            row("OK", t, "マスタ", label, f"{len(ka)}件", f"{len(kb)}件")
            continue
        if not strict and tb in GROUP_OWN:
            # group は別会社(グループ会社)。利用者・機械・カレンダー・言語・プリンタは group 独自が正しい
            row("INFO", t, "マスタ", label, f"{len(ka)}件", f"{len(kb)}件", GROUP_OWN[tb]
                + (f" .11のみ{len(only_r)} / .14のみ{len(only_t)} / 内容違い{len(chg)}"))
            continue
        if tb == "system_settings" and not only_r and not chg:
            # .14 にだけある設定: アプリの既定値と同じなら .11(設定なし=既定値)と同じ動き
            same, diff = [], []
            for k in only_t:
                key, v = k[0], (kb[k].get("value") if isinstance(kb[k], dict) else None)
                if key in SETTING_DEFAULTS and str(v) == SETTING_DEFAULTS[key]:
                    same.append(f"{key}={v}")
                elif key in SETTING_INSTANCE:
                    same.append(f"{key}({SETTING_INSTANCE[key]})")
                else:
                    diff.append(f"{key}={str(v)[:40]}")
            row("WARN" if diff else "INFO", t, "マスタ", label, f"{len(ka)}件", f"{len(kb)}件",
                (f".14 にだけある設定で既定値と違う(.11 と動きが変わる): {', '.join(diff)}" if diff else "")
                + (" / " if diff and same else "") + (f"既定値と同じ・環境固有のため動きは同じ: {', '.join(same)}" if same else ""))
            continue
        if tb == "users":
            lv = "NG" if strict and only_r else "WARN"
            note = "(.11 にいて .14 にいない利用者はログイン・担当者照合ができません)"
        elif tb in ("pdf_templates", "pdf_field_definitions", "special_sheets", "machines"):
            # .14 にだけある行(.14 で登録した実データ)は残すため注意。.11 の行が無い・内容が違うのは NG
            lv = "NG" if strict and (only_r or chg) else "WARN"
            note = {"pdf_templates": "", "pdf_field_definitions": "段取シートの印字位置が .11 と変わります",
                    "special_sheets": "特殊シートの案内が .11 と変わります", "machines": "機械の照合・並び・PG フォルダ判定が変わります"}[tb]
        elif tb == "business_calendars":
            lv = "WARN"
            note = "タイムカードの補完・休日表示が変わります"
        elif tb == "system_settings":
            lv = "WARN"
            note = "言語の既定・辞書の手直しなどが .11 と違います"
        else:
            lv = "WARN"
            note = "コンバートは候補が空の時だけ投入するため、.11 で手直しした候補は入りません"

        def fmt(ks):
            return ", ".join("/".join(k) if isinstance(k, tuple) else k[:60] for k in ks[:15]) + (" ほか" if len(ks) > 15 else "")
        row(lv, t, "マスタ", label, f"{len(ka)}件", f"{len(kb)}件",
            note + (f" .11のみ{len(only_r)}: {fmt(only_r)}" if only_r else "") + (f" / .14のみ{len(only_t)}: {fmt(only_t)}" if only_t else "")
            + (f" / 内容違い{len(chg)}: {', '.join(chg[:15])}" if chg else ""))


def compare_storage(R, T, t, repo):
    s = T.get("storage", {})
    base = s.get("upload_base_path")
    exp = str(HOME / "machcore-storage" / t)
    row("OK" if base and os.path.realpath(base) == os.path.realpath(exp) else "NG", t, "格納先", "upload_base_path", g(R, "storage", "upload_base_path"), base, f"想定 {exp}")
    row("OK" if s.get("dir:/") == "書込可" else "NG", t, "格納先", "書き込み", None, s.get("dir:/"))
    for k in ("mc_storage_path", "nc_storage_path"):
        v = s.get(k)
        if v and not (base and os.path.realpath(v).startswith(os.path.realpath(base))):
            row("NG", t, "格納先", k, g(R, "storage", k), v,
                f"段取シート原本PDF等が {v} に保存されます(このインスタンスの格納先ではない)。管理画面の設定で空にするか {base} 配下に")
        else:
            row("OK", t, "格納先", k, g(R, "storage", k), v or "(未設定=upload_base_path)")
    # 特殊シートの PDF
    sp = [x for x in (g(T, "db", "masters", "special_sheets") or []) if x.get("pdf_path")]
    if sp and base:
        miss = [x["sheet_name"] for x in sp if not os.path.exists(os.path.join(base, x["pdf_path"]))]
        row("OK" if not miss else "NG", t, "格納先", "特殊シートの PDF", None, f"{len(sp) - len(miss)}/{len(sp)}件あり", ", ".join(miss[:10]))


def compare_smoke(R, T, t):
    rs, ts = R.get("smoke") or {}, T.get("smoke") or {}
    if not ts or "_error" in ts:
        row("NG", t, "動作確認", "実行", None, ts.get("_error") if ts else "未実行")
        return
    rbad = {(r["group"].split(" id=")[0], re.sub(r"/\d+", "/N", r["path"])) for r in rs.get("results", []) if not r["ok"]}
    for r in ts.get("results", []):
        if r["ok"]:
            continue
        key = (r["group"].split(" id=")[0], re.sub(r"/\d+", "/N", r["path"]))
        row("WARN" if key in rbad else "NG", t, "動作確認", f"{r['group']} {r['method']} {r['path']}", "(.11 でも NG)" if key in rbad else "OK",
            f"{r['status']} {r['kind']}", r.get("msg", "")[:200])
    slow = [r for r in ts.get("results", []) if r["ok"] and r["sec"] > 20]
    for r in slow:
        row("WARN", t, "動作確認", f"遅い {r['group']} {r['path']}", None, f"{r['sec']}秒")
    row("OK" if ts.get("ng", 1) == 0 else "INFO", t, "動作確認", "集計", f"{rs.get('total', 0) - rs.get('ng', 0)}/{rs.get('total', 0)} OK",
        f"{ts.get('total', 0) - ts.get('ng', 0)}/{ts.get('total', 0)} OK")


def write(out_md, targets):
    order = {"NG": 0, "WARN": 1, "INFO": 2, "OK": 3}
    L = [f"# .11 → .14 動作環境の突き合わせ ({TS})", ""]
    for t in targets:
        rs = [r for r in ROWS if r["target"] == t]
        L.append(f"- {t}: 要対応(NG) {sum(r['level'] == 'NG' for r in rs)}件 / 注意 {sum(r['level'] == 'WARN' for r in rs)}件 / "
                 f"一致 {sum(r['level'] == 'OK' for r in rs)}件")
    for t in targets:
        L += ["", f"## {t}", "", "| 判定 | 区分 | 項目 | .11 | .14 | 内容 |", "|---|---|---|---|---|---|"]
        for r in sorted([r for r in ROWS if r["target"] == t], key=lambda r: order[r["level"]]):
            L.append("| " + " | ".join(str(r[k]).replace("|", "/").replace("\n", " ") for k in ("level", "area", "item", "ref", "tgt", "note")) + " |")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help=".11 の指紋 JSON(env_fingerprint.py --out で作ったもの)")
    ap.add_argument("--ref-ssh", help="ssh 先(例 karkyon@192.168.1.11 または karkyon@192.168.1.11:~/projects/machcore)")
    ap.add_argument("--ref-db", nargs="?", const=REF_DB_DEFAULT, default=None,
                    help=f".11 の DB を直接読む(既定 {REF_DB_DEFAULT.split('@')[-1]})")
    ap.add_argument("--targets", default="internal,group")
    a = ap.parse_args()
    if not (a.ref or a.ref_ssh or a.ref_db):
        raise SystemExit("--ref か --ref-ssh か --ref-db を指定してください")
    out_dir = HERE / "verify_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    partial = False
    if a.ref:
        R = json.loads(Path(a.ref).expanduser().read_text(encoding="utf-8"))
    elif a.ref_ssh:
        R = take_ssh(a.ref_ssh)
    else:
        sys.path.insert(0, str(HERE))
        import env_fingerprint as EF
        print(f"[.11] DB を直接読みます: {a.ref_db.split('@')[-1]}", flush=True)
        try:
            R = {"db": EF.db_info(None, dsn=a.ref_db)}
        except Exception as e:
            raise SystemExit(f"[FAIL] .11 の DB に接続できません: {e}")
        R["storage"] = EF.storage_info(R["db"])
        partial = True
    (out_dir / f"fingerprint_ref_{TS}.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    targets = [x.strip() for x in a.targets.split(",") if x.strip()]
    fps = {}
    for t in targets:
        repo = REPOS.get(t)
        if not repo or not (repo / ".git").is_dir():
            row("NG", t, "対象", "リポジトリ", None, str(repo), "ありません")
            continue
        print(f"[.14 {t}] 指紋を取ります", flush=True)
        T = take_local(repo)
        fps[t] = T
        (out_dir / f"fingerprint_{t}_{TS}.json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        fns = (compare_db, compare_masters) if partial else (compare_host, compare_instance, compare_runtime, compare_db,
                                                              compare_masters, compare_smoke)
        if partial:
            sm = T.get("smoke") or {}
            row("OK" if sm.get("ng") == 0 else "NG", t, "動作確認(.14 単独)", "API・画面・PDF・図面", "(DB 比較のため対象外)",
                f"{sm.get('total', 0) - sm.get('ng', 0)}/{sm.get('total', 0)} OK")
            rt = T.get("runtime") or {}
            row("OK" if rt.get("puppeteer_pdf_bytes") and rt.get("ipag_bytes") and rt.get("sharp") else "NG", t,
                "実行部品(.14 単独)", "sharp・帳票フォント・Chromium で日本語PDF", None, "OK" if rt.get("puppeteer_pdf_bytes") else rt.get("puppeteer_err"))
        for fn in fns:
            try:
                fn(R, T, t)
            except Exception as e:
                row("NG", t, "比較", fn.__name__, None, f"{type(e).__name__}: {e}")
        try:
            compare_storage(R, T, t, repo)
        except Exception as e:
            row("NG", t, "比較", "compare_storage", None, f"{type(e).__name__}: {e}")
    md = out_dir / f"parity_{TS}.md"
    write(md, targets)
    (out_dir / f"parity_{TS}.json").write_text(json.dumps(ROWS, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + "=" * 70)
    for t in targets:
        rs = [r for r in ROWS if r["target"] == t]
        print(f"■ {t}: 要対応(NG) {sum(r['level'] == 'NG' for r in rs)}件 / 注意 {sum(r['level'] == 'WARN' for r in rs)}件")
        for r in rs:
            if r["level"] in ("NG", "WARN"):
                print(f"  [{r['level']}] {r['area']} {r['item']}: .11={r['ref']} / .14={r['tgt']} {r['note']}"[:400])
    print(f"\n結果: {md}")
    sys.exit(1 if any(r["level"] == "NG" for r in ROWS) else 0)


if __name__ == "__main__":
    main()
