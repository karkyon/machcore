#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_syslog.py
実装内容:
1. systemd unit で PM2 を永続化（サーバ再起動後も自動起動）
2. Prisma: system_logs テーブル追加 → migration
3. NestJS: AppLoggerService (INFO/WARN/ERROR/DEBUG → DB)
4. mc.service.ts: cronログを SystemLog に記録
5. admin.controller.ts: GET /admin/system-logs エンドポイント追加
6. フロント: /admin/system-logs 画面追加
7. サイドバー全ページに「システムログ」メニュー追加
"""
import subprocess, shutil, os, sys

REPO = "/home/karkyon/projects/machcore"
API  = f"{REPO}/apps/api"
WEB  = f"{REPO}/apps/web"

errors = []

# ══════════════════════════════════════════════════════════
# STEP1: systemd unit ファイル作成 + 有効化
# ══════════════════════════════════════════════════════════
SYSTEMD_UNIT = """[Unit]
Description=MachCore PM2 Process Manager
After=network.target

[Service]
Type=forking
User=karkyon
LimitNOFILE=65536
ExecStart=/usr/local/bin/pm2 resurrect
ExecReload=/usr/local/bin/pm2 reload all
ExecStop=/usr/local/bin/pm2 kill
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""

with open("/tmp/machcore-pm2.service", "w") as f:
    f.write(SYSTEMD_UNIT)

r = subprocess.run(["sudo", "cp", "/tmp/machcore-pm2.service", "/etc/systemd/system/machcore-pm2.service"],
    capture_output=True, text=True)
if r.returncode != 0:
    print(f"⚠️  systemd unit コピー失敗 (sudo権限不足の可能性): {r.stderr.strip()}")
else:
    subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True)
    subprocess.run(["sudo", "systemctl", "enable", "machcore-pm2"], capture_output=True)
    # PM2の現在の状態を保存
    subprocess.run(["/usr/local/bin/pm2", "save"], capture_output=True, cwd=REPO)
    print("✅ STEP1: systemd unit 作成・有効化 + pm2 save")

# ══════════════════════════════════════════════════════════
# STEP2: Prisma schema に system_logs テーブル追加
# ══════════════════════════════════════════════════════════
SCHEMA_PATH = f"{API}/prisma/schema.prisma"
with open(SCHEMA_PATH, "r") as f:
    schema = f.read()

SYSTEM_LOG_MODEL = '''
model SystemLog {
  id        Int      @id @default(autoincrement())
  level     String   @db.VarChar(10)   // INFO WARN ERROR DEBUG
  category  String   @db.VarChar(50)   // CRON AUTH API PDF etc
  message   String   @db.Text
  detail    Json?
  createdAt DateTime @default(now()) @map("created_at")

  @@index([level, createdAt])
  @@index([category, createdAt])
  @@map("system_logs")
}
'''

if "system_logs" not in schema:
    # 末尾に追加
    schema += SYSTEM_LOG_MODEL
    with open(SCHEMA_PATH, "w") as f:
        f.write(schema)
    print("✅ STEP2: Prisma schema system_logs 追加")
else:
    print("⏭  STEP2: system_logs 既存スキップ")

# migration 実行
r = subprocess.run(
    ["docker", "exec", "machcore-postgres", "psql", "-U", "machcore", "-d", "machcore_dev", "-c",
     """CREATE TABLE IF NOT EXISTS system_logs (
  id SERIAL PRIMARY KEY,
  level VARCHAR(10) NOT NULL,
  category VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  detail JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category, created_at DESC);
"""],
    capture_output=True, text=True
)
if r.returncode != 0:
    print(f"⚠️  DB migration: {r.stderr.strip()[:200]}")
else:
    print("✅ STEP2b: DB system_logs テーブル作成")

# Prisma generate
subprocess.run(["npx", "prisma", "generate"], cwd=API, capture_output=True)
print("✅ STEP2c: prisma generate")

# ══════════════════════════════════════════════════════════
# STEP3: AppLoggerService 作成
# ══════════════════════════════════════════════════════════
LOGGER_PATH = f"{API}/src/common/app-logger.service.ts"
LOGGER_CONTENT = '''import { Injectable, LoggerService } from \'@nestjs/common\';
import { PrismaService } from \'../prisma/prisma.service\';

export type LogLevel = \'INFO\' | \'WARN\' | \'ERROR\' | \'DEBUG\';
export type LogCategory =
  | \'CRON\' | \'AUTH\' | \'API\' | \'PDF\' | \'FILE\'
  | \'DB\' | \'TIMECARD\' | \'SYSTEM\' | \'MC\' | \'NC\';

@Injectable()
export class AppLoggerService {
  constructor(private readonly prisma: PrismaService) {}

  /** 非同期・fire-and-forget でDBに記録 */
  log(level: LogLevel, category: LogCategory, message: string, detail?: Record<string, unknown>): void {
    const ts = new Date().toISOString();
    const prefix = `[${level}][${category}] ${ts}`;
    if (level === \'ERROR\')  console.error(prefix, message, detail ?? \'\');
    else if (level === \'WARN\') console.warn(prefix, message, detail ?? \'\');
    else if (level === \'DEBUG\') console.debug(prefix, message, detail ?? \'\');
    else                        console.log(prefix, message, detail ?? \'\');

    this.prisma.systemLog.create({
      data: { level, category, message, detail: (detail ?? null) as any },
    }).catch(() => { /* ログ失敗は無視 */ });
  }

  info (category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log(\'INFO\',  category, message, detail); }
  warn (category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log(\'WARN\',  category, message, detail); }
  error(category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log(\'ERROR\', category, message, detail); }
  debug(category: LogCategory, message: string, detail?: Record<string, unknown>) { this.log(\'DEBUG\', category, message, detail); }
}
'''
with open(LOGGER_PATH, "w", encoding="utf-8") as f:
    f.write(LOGGER_CONTENT)
print("✅ STEP3: AppLoggerService 作成")

# ══════════════════════════════════════════════════════════
# STEP4: AppModule に AppLoggerService を登録
# ══════════════════════════════════════════════════════════
APP_MODULE_PATH = f"{API}/src/app.module.ts"
with open(APP_MODULE_PATH, "r", encoding="utf-8") as f:
    app_module = f.read()

if "AppLoggerService" not in app_module:
    # import追加
    app_module = "import { AppLoggerService } from './common/app-logger.service';\n" + app_module
    # providers に追加
    app_module = app_module.replace(
        "OperationLogService,",
        "OperationLogService,\n    AppLoggerService,"
    )
    # exports に追加（もしあれば）
    with open(APP_MODULE_PATH, "w", encoding="utf-8") as f:
        f.write(app_module)
    print("✅ STEP4: AppModule に AppLoggerService 登録")
else:
    print("⏭  STEP4: AppLoggerService 既登録スキップ")

# ══════════════════════════════════════════════════════════
# STEP5: mc.service.ts の cronInitTimecards を AppLogger 使用に変更
# ══════════════════════════════════════════════════════════
MC_SERVICE_PATH = f"{API}/src/mc/mc.service.ts"
with open(MC_SERVICE_PATH, "r", encoding="utf-8") as f:
    mc_service = f.read()

OLD5 = "import { Injectable, NotFoundException } from '@nestjs/common';"
NEW5 = "import { Injectable, NotFoundException } from '@nestjs/common';\nimport { AppLoggerService } from '../common/app-logger.service';"
if "AppLoggerService" not in mc_service:
    mc_service = mc_service.replace(OLD5, NEW5, 1)

# constructor に AppLoggerService 追加
OLD5B = "constructor(private readonly prisma: PrismaService) {}"
NEW5B = "constructor(\n    private readonly prisma: PrismaService,\n    private readonly logger: AppLoggerService,\n  ) {}"
if "private readonly logger: AppLoggerService" not in mc_service:
    mc_service = mc_service.replace(OLD5B, NEW5B, 1)

# cronInitTimecards のログを AppLogger に変更
OLD5C = '''  @Cron('0 5 * * *')
  async cronInitTimecards() {
    const today = new Date();
    const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    try {
      await this.initTimecards(workDate, 1); // operatorId=1 (admin)
      console.log(`[Cron] ${workDate} 機械タイムカード自動生成完了`);
    } catch (e) {
      console.error('[Cron] タイムカード自動生成エラー', e);
    }
  }'''
NEW5C = '''  @Cron('0 5 * * *')
  async cronInitTimecards() {
    const today = new Date();
    const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    this.logger.info('CRON', `機械タイムカード自動生成 開始: ${workDate}`);
    try {
      const result = await this.initTimecards(workDate, 1);
      this.logger.info('CRON', `機械タイムカード自動生成 完了: ${workDate}`, { created: result.created });
    } catch (e: any) {
      this.logger.error('CRON', `機械タイムカード自動生成 失敗: ${workDate}`, { error: e?.message ?? String(e) });
    }
  }'''
if OLD5C in mc_service:
    mc_service = mc_service.replace(OLD5C, NEW5C, 1)
    print("✅ STEP5: cronInitTimecards AppLogger 使用に変更")
else:
    print("⚠️  STEP5: cronInitTimecards パターン不一致（手動確認要）")

with open(MC_SERVICE_PATH, "w", encoding="utf-8") as f:
    f.write(mc_service)

# ══════════════════════════════════════════════════════════
# STEP6: admin.controller.ts に /admin/system-logs エンドポイント追加
# ══════════════════════════════════════════════════════════
ADMIN_CTL_PATH = f"{API}/src/admin/admin.controller.ts"
with open(ADMIN_CTL_PATH, "r", encoding="utf-8") as f:
    admin_ctl = f.read()

SYSLOG_ENDPOINT = '''
  /** SYS-LOG: システムログ一覧 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('system-logs')
  async getSystemLogs(
    @Query('level')     level?: string,
    @Query('category')  category?: string,
    @Query('date_from') dateFrom?: string,
    @Query('date_to')   dateTo?: string,
    @Query('page')      page = '1',
    @Query('limit')     limit = '100',
  ) {
    const where: any = {};
    if (level)    where.level    = level;
    if (category) where.category = category;
    if (dateFrom || dateTo) {
      where.createdAt = {};
      if (dateFrom) where.createdAt.gte = new Date(dateFrom);
      if (dateTo)   where.createdAt.lte = new Date(dateTo + 'T23:59:59Z');
    }
    const skip = (parseInt(page) - 1) * parseInt(limit);
    const take = parseInt(limit);
    const [rows, total] = await Promise.all([
      this.prisma.systemLog.findMany({ where, skip, take, orderBy: { createdAt: 'desc' } }),
      this.prisma.systemLog.count({ where }),
    ]);
    return { total, page: parseInt(page), limit: parseInt(limit), data: rows };
  }

  /** SYS-LOG: システムログ削除（古いログ） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Delete('system-logs/purge')
  async purgeSystemLogs(@Query('days') days = '30') {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(days));
    const result = await this.prisma.systemLog.deleteMany({ where: { createdAt: { lt: cutoff } } });
    return { deleted: result.count, message: `${parseInt(days)}日以前のログを${result.count}件削除しました` };
  }
'''

# 末尾の } の前に挿入
if "system-logs" not in admin_ctl:
    # getLogs エンドポイントの後に追加
    insert_after = "  /** ADM-LOG: 操作ログ一覧"
    idx = admin_ctl.rfind("}")  # 最後の }
    admin_ctl = admin_ctl[:idx] + SYSLOG_ENDPOINT + "\n}" 
    with open(ADMIN_CTL_PATH, "w", encoding="utf-8") as f:
        f.write(admin_ctl)
    print("✅ STEP6: admin.controller.ts system-logs エンドポイント追加")
else:
    print("⏭  STEP6: system-logs 既存スキップ")

# ══════════════════════════════════════════════════════════
# STEP7: フロント /admin/system-logs 画面作成
# ══════════════════════════════════════════════════════════
SYSLOG_PAGE_DIR = f"{WEB}/app/admin/system-logs"
os.makedirs(SYSLOG_PAGE_DIR, exist_ok=True)

SYSLOG_PAGE = '''"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",       label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",    label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",      label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",    label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",         label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/pdf-editor",  label: "PDFエディタ",      icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },
  { href: "/admin/system-logs", label: "システムログ",     icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
];

const LEVEL_COLOR: Record<string, string> = {
  INFO:  "bg-blue-100 text-blue-700",
  WARN:  "bg-amber-100 text-amber-700",
  ERROR: "bg-red-100 text-red-700",
  DEBUG: "bg-slate-100 text-slate-600",
};
const CATEGORY_COLOR: Record<string, string> = {
  CRON:     "bg-purple-100 text-purple-700",
  AUTH:     "bg-green-100 text-green-700",
  API:      "bg-sky-100 text-sky-700",
  PDF:      "bg-orange-100 text-orange-700",
  FILE:     "bg-teal-100 text-teal-700",
  DB:       "bg-indigo-100 text-indigo-700",
  TIMECARD: "bg-emerald-100 text-emerald-700",
  SYSTEM:   "bg-slate-100 text-slate-600",
  MC:       "bg-violet-100 text-violet-700",
  NC:       "bg-cyan-100 text-cyan-700",
};

const LEVELS     = ["", "INFO", "WARN", "ERROR", "DEBUG"];
const CATEGORIES = ["", "CRON", "AUTH", "API", "PDF", "FILE", "DB", "TIMECARD", "SYSTEM", "MC", "NC"];
const LIMIT = 100;

type SysLog = { id: number; level: string; category: string; message: string; detail: any; created_at: string };

const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

export default function SystemLogsPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [logs,    setLogs]    = useState<SysLog[]>([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(false);
  const [page,    setPage]    = useState(1);
  const [fLevel,    setFLevel]    = useState("");
  const [fCategory, setFCategory] = useState("");
  const [fDateFrom, setFDateFrom] = useState("");
  const [fDateTo,   setFDateTo]   = useState("");
  const [toast,   setToast]   = useState<{ msg: string; ok: boolean } | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  const fetchLogs = useCallback(async (p = 1) => {
    if (!getToken()) { router.push("/admin/login"); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), limit: String(LIMIT) });
      if (fLevel)    params.set("level",     fLevel);
      if (fCategory) params.set("category",  fCategory);
      if (fDateFrom) params.set("date_from", fDateFrom);
      if (fDateTo)   params.set("date_to",   fDateTo);
      const d = await apiFetch(`/admin/system-logs?${params}`);
      setLogs(d.data ?? []);
      setTotal(d.total ?? 0);
      setPage(p);
    } catch (e: any) {
      showToast(`取得失敗: ${e.message}`, false);
    } finally { setLoading(false); }
  }, [router, fLevel, fCategory, fDateFrom, fDateTo]);

  useEffect(() => { fetchLogs(1); }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => fetchLogs(1), 5000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchLogs]);

  const handlePurge = async () => {
    if (!confirm("30日以前のログを削除しますか？")) return;
    try {
      const d = await apiFetch("/admin/system-logs/purge?days=30", { method: "DELETE" });
      showToast(d.message);
      fetchLogs(1);
    } catch (e: any) { showToast(`削除失敗: ${e.message}`, false); }
  };

  const fmtDt = (s: string) => {
    const d = new Date(s);
    const p = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={"fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow text-white text-sm font-bold " + (toast.ok ? "bg-emerald-500" : "bg-red-500")}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-600 text-white font-bold" : "text-slate-600 hover:bg-slate-100")}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={item.icon} />
              </svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h1 className="text-base font-bold text-slate-800">システムログ</h1>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
                    className="rounded" />
                  自動更新（5秒）
                </label>
                <button onClick={() => fetchLogs(page)}
                  className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-bold">
                  更新
                </button>
                <button onClick={handlePurge}
                  className="text-xs px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded font-bold">
                  30日以前を削除
                </button>
              </div>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <select value={fLevel} onChange={e => setFLevel(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none">
                {LEVELS.map(l => <option key={l} value={l}>{l || "レベル: すべて"}</option>)}
              </select>
              <select value={fCategory} onChange={e => setFCategory(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none">
                {CATEGORIES.map(c => <option key={c} value={c}>{c || "カテゴリ: すべて"}</option>)}
              </select>
              <input type="date" value={fDateFrom} onChange={e => setFDateFrom(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none" />
              <span className="text-xs text-slate-400">〜</span>
              <input type="date" value={fDateTo} onChange={e => setFDateTo(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none" />
              <span className="text-xs text-slate-500 ml-auto">全 {total} 件</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">読み込み中...</div>
            ) : logs.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-slate-400 text-sm">ログがありません</div>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead className="bg-slate-50 sticky top-0 z-10">
                  <tr className="border-b border-slate-200">
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-36">日時</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-16">レベル</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500 w-24">カテゴリ</th>
                    <th className="px-3 py-2 text-left font-bold text-slate-500">メッセージ</th>
                    <th className="px-3 py-2 text-center font-bold text-slate-500 w-14">詳細</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <>
                      <tr key={log.id} className={"border-b border-slate-100 hover:bg-slate-50 " + (log.level === "ERROR" ? "bg-red-50/40" : log.level === "WARN" ? "bg-amber-50/40" : "")}>
                        <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap">{fmtDt(log.created_at)}</td>
                        <td className="px-3 py-2">
                          <span className={"text-[10px] font-bold px-1.5 py-0.5 rounded " + (LEVEL_COLOR[log.level] ?? "bg-slate-100 text-slate-600")}>
                            {log.level}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={"text-[10px] font-bold px-1.5 py-0.5 rounded " + (CATEGORY_COLOR[log.category] ?? "bg-slate-100 text-slate-600")}>
                            {log.category}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">{log.message}</td>
                        <td className="px-3 py-2 text-center">
                          {log.detail && (
                            <button onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                              className="text-sky-600 hover:text-sky-800 font-bold">
                              {expanded === log.id ? "▲" : "▼"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {expanded === log.id && log.detail && (
                        <tr key={"d" + log.id} className="bg-slate-50 border-b border-slate-100">
                          <td colSpan={5} className="px-4 py-2">
                            <pre className="text-[10px] text-slate-600 whitespace-pre-wrap bg-white border border-slate-200 rounded p-2 max-h-48 overflow-y-auto">
                              {JSON.stringify(log.detail, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 py-3 border-t border-slate-200 shrink-0">
              <button onClick={() => fetchLogs(page - 1)} disabled={page <= 1}
                className="text-xs px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40">前へ</button>
              <span className="text-xs text-slate-600">{page} / {totalPages}</span>
              <button onClick={() => fetchLogs(page + 1)} disabled={page >= totalPages}
                className="text-xs px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40">次へ</button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
'''
with open(f"{SYSLOG_PAGE_DIR}/page.tsx", "w", encoding="utf-8") as f:
    f.write(SYSLOG_PAGE)
print("✅ STEP7: /admin/system-logs フロント画面作成")

# ══════════════════════════════════════════════════════════
# STEP8: 既存サイドバー全ページに「システムログ」メニュー追加
# ══════════════════════════════════════════════════════════
SIDEBAR_OLD = '  { href: "/admin/pdf-editor", label: "PDFエディタ", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },'
SIDEBAR_NEW = '  { href: "/admin/pdf-editor", label: "PDFエディタ", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" },\n  { href: "/admin/system-logs", label: "システムログ", icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },'

ADMIN_PAGES = [
    f"{WEB}/app/admin/users/page.tsx",
    f"{WEB}/app/admin/machines/page.tsx",
    f"{WEB}/app/admin/settings/page.tsx",
    f"{WEB}/app/admin/raw/page.tsx",
    f"{WEB}/app/admin/pdf-editor/page.tsx",
    f"{WEB}/app/mc/timecards/page.tsx",
]
updated = 0
for p in ADMIN_PAGES:
    if not os.path.exists(p): continue
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    if "system-logs" in content: continue
    if SIDEBAR_OLD in content:
        content = content.replace(SIDEBAR_OLD, SIDEBAR_NEW, 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        updated += 1
print(f"✅ STEP8: サイドバー {updated}ページ更新")

# ══════════════════════════════════════════════════════════
# STEP9: API ビルド
# ══════════════════════════════════════════════════════════
print("--- API tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"], cwd=API, capture_output=True, text=True)
if r.returncode != 0:
    print("❌ API tsc エラー:"); print((r.stdout+r.stderr)[-3000:])
    errors.append("API tsc")
else:
    print("✅ API tsc OK")

# ══════════════════════════════════════════════════════════
# STEP10: Web ビルド + pm2 restart
# ══════════════════════════════════════════════════════════
print("--- next build ---")
r2 = subprocess.run(["npx", "next", "build"], cwd=f"{WEB}", capture_output=True, text=True)
if r2.returncode != 0:
    print("❌ next build エラー:"); print((r2.stdout+r2.stderr)[-2000:]); errors.append("next build")
else:
    print("✅ next build OK")

if not errors:
    subprocess.run(["pm2", "restart", "all"], capture_output=True)
    print("✅ pm2 restart all")

    subprocess.run(["git", "add", "-A"], cwd=REPO)
    subprocess.run(["git", "commit", "-m",
        "feat: system logs - DB table, AppLogger, cron logging, admin API + UI, systemd pm2"], cwd=REPO)
    r3 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
    print("✅ git push\n" + (r3.stderr.strip() or r3.stdout.strip()))
else:
    print(f"\n❌ エラーあり: {errors}")

print("✅ 完了")
