#!/usr/bin/env python3
"""
fix_v47.py
1. api.ts axiosインターセプター: 全リクエスト・レスポンス・エラーをconsole.log
2. NestJS LoggerMiddleware追加（全APIリクエスト/レスポンスをサーバーログ出力）
3. mc/edit page.tsx: 全UIイベント + handleSave/handleKanryoOkにconsole.log
4. mc/record page.tsx: 全主要イベントにconsole.log
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

# ============================================================
# 1. api.ts — axiosインターセプターに完全ログ追加
# ============================================================
API_TS = os.path.join(ROOT, "apps/web/lib/api.ts")

patch(API_TS,
    """const api = axios.create({ baseURL: "/api" });

// リクエストインターセプター: work_tokenを自動付与
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("work_token");
    if (token && !config.headers["Authorization"]) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return config;
});""",
    """const api = axios.create({ baseURL: "/api" });

// ── APIリクエスト/レスポンス完全ログ ─────────────────────────
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("work_token");
    if (token && !config.headers["Authorization"]) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  const body = config.data;
  console.log(
    `%c[API REQ] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`,
    "color:#2563eb;font-weight:bold",
    { params: config.params, body: body ? (typeof body === "string" ? JSON.parse(body) : body) : undefined,
      auth: config.headers["Authorization"] ? "Bearer ***" : "none" }
  );
  return config;
}, (error) => {
  console.error("[API REQ ERROR]", error);
  return Promise.reject(error);
});

api.interceptors.response.use(
  (response) => {
    console.log(
      `%c[API RES] ${response.status} ${response.config.method?.toUpperCase()} ${response.config.url}`,
      "color:#059669;font-weight:bold",
      { data: response.data }
    );
    return response;
  },
  (error) => {
    const status = error?.response?.status;
    const data   = error?.response?.data;
    const url    = error?.config?.url;
    const method = error?.config?.method?.toUpperCase();
    const body   = error?.config?.data;
    console.error(
      `%c[API ERR] ${status} ${method} ${url}`,
      "color:#dc2626;font-weight:bold",
      { requestBody: body ? (typeof body === "string" ? JSON.parse(body) : body) : undefined,
        responseData: data, message: Array.isArray(data?.message) ? data.message.join(", ") : data?.message }
    );
    return Promise.reject(error);
  }
);""",
    "api.ts 全APIリクエスト/レスポンスconsole.log追加"
)

# ============================================================
# 2. NestJS LoggerMiddleware — 全APIリクエストをPM2ログへ
# ============================================================
MIDDLEWARE_PATH = os.path.join(ROOT, "apps/api/src/common/logger.middleware.ts")
os.makedirs(os.path.dirname(MIDDLEWARE_PATH), exist_ok=True)
write(MIDDLEWARE_PATH, """\
import { Injectable, NestMiddleware, Logger } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';

@Injectable()
export class LoggerMiddleware implements NestMiddleware {
  private readonly logger = new Logger('HTTP');

  use(req: Request, res: Response, next: NextFunction) {
    const { method, originalUrl } = req;
    const start = Date.now();
    const body = req.body;

    res.on('finish', () => {
      const { statusCode } = res;
      const ms = Date.now() - start;
      const bodyStr = body && Object.keys(body).length > 0
        ? JSON.stringify(body).slice(0, 500)
        : '';
      const level = statusCode >= 400 ? 'error' : 'log';
      this.logger[level](
        `${method} ${originalUrl} ${statusCode} ${ms}ms ${bodyStr}`
      );
    });
    next();
  }
}
""")
print("OK: LoggerMiddleware作成")

# app.module.tsにLoggerMiddleware登録
APP_MODULE = os.path.join(ROOT, "apps/api/src/app.module.ts")
content = read(APP_MODULE)
if "LoggerMiddleware" not in content:
    # importsの先頭にMiddlewareConsumer追加
    content = content.replace(
        "import { Module } from '@nestjs/common';",
        "import { Module, NestModule, MiddlewareConsumer } from '@nestjs/common';\nimport { LoggerMiddleware } from './common/logger.middleware';"
    )
    # AppModule classにimplements NestModule追加とconfigure追加
    content = content.replace(
        "export class AppModule {}",
        "export class AppModule implements NestModule {\n  configure(consumer: MiddlewareConsumer) {\n    consumer.apply(LoggerMiddleware).forRoutes('*');\n  }\n}"
    )
    write(APP_MODULE, content)
    print("OK: app.module.ts LoggerMiddleware登録")
else:
    print("INFO: LoggerMiddleware既登録")

# ============================================================
# 3. mc/edit page.tsx — 全UIイベント + APIコールにconsole.log
# ============================================================
EDIT = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/edit/page.tsx")

# handleSave先頭にログ追加
patch(EDIT,
    "  const handleSave = async () => {\n    if (!token) { setSaveError(\"認証が必要です\"); return; }",
    """  const handleSave = async () => {
    console.log("[EDIT] handleSave開始", { sbMode, sbRepeatMode, token: token ? "あり" : "なし", mcId,
      data: { machineId, oNumber, clampNote, cycleH, cycleM, cycleS, machiningQty, note, creatorId, sheetCreatedAt,
              toolingRows: toolingRows.length, offsetRows: offsetRows.length, indexRows: indexRows.length } });
    if (!token) { setSaveError("認証が必要です"); return; }""",
    "edit/page.tsx handleSave先頭ログ"
)

# handleKanryoOk先頭にログ追加
patch(EDIT,
    "  const handleKanryoOk = async () => {\n    if (!token || !pendingBody) return;",
    """  const handleKanryoOk = async () => {
    console.log("[EDIT] handleKanryoOk", { kanryoType, kanryoDetail, pendingBody, token: token ? "あり" : "なし" });
    if (!token || !pendingBody) return;""",
    "edit/page.tsx handleKanryoOk先頭ログ"
)

# setDetail後にログ
patch(EDIT,
    "    mcApi.findOne(mcId).then(r => {\n      const d = (r as any).data ?? r;\n      setDetail(d);",
    """    mcApi.findOne(mcId).then(r => {
      const d = (r as any).data ?? r;
      console.log("[EDIT] detail取得", { id: d.id, version: d.version, status: d.status, machine: d.machine });
      setDetail(d);""",
    "edit/page.tsx findOne後ログ"
)

# machineId変更ログ
patch(EDIT,
    '                    <select value={machineId} onChange={e => setMachineId(e.target.value)}',
    """                    <select value={machineId} onChange={e => { console.log("[EDIT] 機械変更", e.target.value); setMachineId(e.target.value); }}""",
    "edit/page.tsx 機械selectログ"
)

# oNumber変更ログ
patch(EDIT,
    '                    <input value={oNumber} onChange={e => setONumber(e.target.value)}',
    """                    <input value={oNumber} onChange={e => { console.log("[EDIT] 主Oナンバ変更", e.target.value); setONumber(e.target.value); }}""",
    "edit/page.tsx 主Oナンバログ"
)

# セクションタブクリックログ
patch(EDIT,
    "              <button key={k} onClick={() => setActiveSection(k as any)}",
    "              <button key={k} onClick={() => { console.log('[EDIT] セクション切替', k); setActiveSection(k as any); }}",
    "edit/page.tsx セクションタブログ"
)

# ============================================================
# 4. mc/record page.tsx — 主要イベントにconsole.log
# ============================================================
RECORD = os.path.join(ROOT, "apps/web/app/mc/[mc_id]/record/page.tsx")

# handleSubmit先頭（既存ログがある場合はスキップ）
content_rec = read(RECORD)
if "[STEP2] handleSubmit" not in content_rec:
    patch(RECORD,
        "  const handleSubmit = async () => {",
        """  const handleSubmit = async () => {
    console.log("[STEP2] handleSubmit", { sbMode, token: token ? "あり" : "なし", isAuthenticated,
      machineId, cycleH, cycleM, cycleS, cyclePcs, setupOps, prodOps, checkMan, prgMan,
      startedAt, checkedAt, finishedAt, quantity, setupQty, dStopH, dStopM, yStopH, yStopM,
      times: calcTimes() });""",
        "record/page.tsx handleSubmit先頭ログ"
    )

# タイムモード切替ログ
if "timeMode切替" not in content_rec:
    patch(RECORD,
        'setTimeMode(m => m === "hm" ? "datetime" : "hm")',
        'setTimeMode(m => { const next = m === "hm" ? "datetime" : "hm"; console.log("[STEP2] timeMode切替", next); return next; })',
        "record/page.tsx timeMode切替ログ"
    )

# ============================================================
# BUILD & PUSH
# ============================================================
print("\n--- API npx tsc --noEmit ---")
r2 = subprocess.run("cd ~/projects/machcore/apps/api && npx tsc --noEmit", shell=True, capture_output=True, text=True)
if r2.returncode != 0:
    print(r2.stdout); print("STDERR:", r2.stderr)
    print("API TSC FAILED — abort"); sys.exit(1)
else:
    print("(no output)")

print("\n--- npm run build ---")
r = subprocess.run("cd ~/projects/machcore/apps/web && npm run build", shell=True, capture_output=True, text=True)
print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
stderr_clean = "\n".join(l for l in r.stderr.split("\n") if "react-pdf" not in l)
if stderr_clean.strip():
    print("STDERR:", stderr_clean[-800:])

if r.returncode != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run("pm2 restart machcore-api machcore-web --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "feat: 全API/UI完全ログ実装 LoggerMiddleware v47" && git push',
    shell=True
)
print("DONE")
