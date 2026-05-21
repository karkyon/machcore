#!/usr/bin/env python3
"""
MachCore Dashboard 実装スクリプト
omega-dev2 ~/projects/machcore で実行: python3 dashboard_deploy.py
"""
import os, subprocess, sys

ROOT  = os.path.expanduser("~/projects/machcore")
API   = os.path.join(ROOT, "apps/api")
WEB   = os.path.join(ROOT, "apps/web")
SCHEMA = os.path.join(API, "prisma/schema.prisma")

def run(cmd, cwd=None, check=True):
    print(f"  $ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd or ROOT, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip(), file=sys.stderr)
    if check and r.returncode != 0:
        print(f"ERROR: exit {r.returncode}")
        sys.exit(1)
    return r

# ─────────────────────────────────────────
# Step 1: Prismaスキーマ - McSetupSheetLog に work_collected 追加
# ─────────────────────────────────────────
print("\n[1/6] Prismaスキーマ更新...")
with open(SCHEMA) as f:
    schema = f.read()

mc_block_start = schema.find("model McSetupSheetLog")
mc_block_end   = schema.find("\n}", mc_block_start) + 2
mc_block = schema[mc_block_start:mc_block_end]

if "work_collected" in mc_block:
    print("  INFO: work_collected は既に存在します")
else:
    # sessionId の直後に追加
    old = '  sessionId   String?  @db.VarChar(36)     @map("session_id")'
    new = '  sessionId   String?  @db.VarChar(36)     @map("session_id")\n  workCollected Boolean @default(false)    @map("work_collected")'
    if old not in schema:
        # セミコロン無しパターン
        old = '  sessionId   String?  @db.VarChar(36)   @map("session_id")'
        new = '  sessionId   String?  @db.VarChar(36)   @map("session_id")\n  workCollected Boolean @default(false)    @map("work_collected")'
    if old not in schema:
        print("  ERROR: McSetupSheetLog.sessionId が見つかりません")
        print(mc_block)
        sys.exit(1)
    # McSetupSheetLog ブロック内だけ置換（1回のみ）
    before = schema[:mc_block_start]
    after  = schema[mc_block_end:]
    new_block = mc_block.replace(old, new, 1)
    schema = before + new_block + after
    with open(SCHEMA, "w") as f:
        f.write(schema)
    print("  OK: schema.prisma 更新")

# ─────────────────────────────────────────
# Step 2: Prisma migrate dev
# ─────────────────────────────────────────
print("\n[2/6] Prisma マイグレーション...")
run("npx prisma migrate dev --name add_mc_setup_sheet_work_collected --skip-seed", cwd=API)
run("npx prisma generate", cwd=API)
print("  OK")

# ─────────────────────────────────────────
# Step 3: DashboardModule 作成
# ─────────────────────────────────────────
print("\n[3/6] DashboardModule 作成...")
dash_dir = os.path.join(API, "src/dashboard")
os.makedirs(dash_dir, exist_ok=True)

# dashboard.service.ts
with open(os.path.join(dash_dir, "dashboard.service.ts"), "w") as f:
    f.write('''import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class DashboardService {
  constructor(private readonly prisma: PrismaService) {}

  async uncollectedSheets() {
    const [ncSheets, mcSheets] = await Promise.all([
      this.prisma.setupSheetLog.findMany({
        where: { workCollected: false },
        orderBy: [
          { ncProgram: { machine: { sortOrder: 'asc' } } },
          { printedAt: 'asc' },
        ],
        include: {
          operator: { select: { id: true, name: true } },
          ncProgram: {
            include: {
              part:    { select: { drawingNo: true, name: true, partId: true } },
              machine: { select: { id: true, machineCode: true, machineName: true, sortOrder: true } },
            },
          },
        },
      }),
      this.prisma.mcSetupSheetLog.findMany({
        where: { workCollected: false },
        orderBy: [
          { mcProgram: { machine: { sortOrder: 'asc' } } },
          { printedAt: 'asc' },
        ],
        include: {
          operator: { select: { id: true, name: true } },
          mcProgram: {
            include: {
              part:    { select: { drawingNo: true, name: true, partId: true } },
              machine: { select: { id: true, machineCode: true, machineName: true, sortOrder: true } },
            },
          },
        },
      }),
    ]);

    const ncRows = ncSheets.map(s => ({
      id:            s.id,
      system:        'NC' as const,
      program_id:    s.ncProgramId,
      drawing_no:    s.ncProgram.part.drawingNo,
      part_name:     s.ncProgram.part.name,
      part_id:       s.ncProgram.part.partId ?? null,
      machine_code:  s.ncProgram.machine?.machineCode ?? null,
      machine_name:  s.ncProgram.machine?.machineName ?? null,
      machine_sort:  s.ncProgram.machine?.sortOrder ?? 999,
      printed_at:    s.printedAt,
      operator_name: s.operator.name,
      version:       s.version ?? null,
    }));

    const mcRows = mcSheets.map(s => ({
      id:            s.id,
      system:        'MC' as const,
      program_id:    s.mcProgramId,
      drawing_no:    s.mcProgram.part.drawingNo,
      part_name:     s.mcProgram.part.name,
      part_id:       s.mcProgram.part.partId ?? null,
      machine_code:  s.mcProgram.machine?.machineCode ?? null,
      machine_name:  s.mcProgram.machine?.machineName ?? null,
      machine_sort:  s.mcProgram.machine?.sortOrder ?? 999,
      printed_at:    s.printedAt,
      operator_name: s.operator.name,
      version:       s.version ?? null,
    }));

    const all = [...ncRows, ...mcRows].sort((a, b) => {
      if (a.machine_sort !== b.machine_sort) return a.machine_sort - b.machine_sort;
      return new Date(a.printed_at).getTime() - new Date(b.printed_at).getTime();
    });

    return { total: all.length, nc_count: ncRows.length, mc_count: mcRows.length, items: all };
  }

  async summary() {
    const [ncTotal, mcTotal, ncPending, mcPending, ncUncollected, mcUncollected] = await Promise.all([
      this.prisma.ncProgram.count(),
      this.prisma.mcProgram.count(),
      this.prisma.ncProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.mcProgram.count({ where: { status: 'PENDING_APPROVAL' } }),
      this.prisma.setupSheetLog.count({ where: { workCollected: false } }),
      this.prisma.mcSetupSheetLog.count({ where: { workCollected: false } }),
    ]);
    return {
      nc_total: ncTotal, mc_total: mcTotal,
      nc_pending: ncPending, mc_pending: mcPending,
      uncollected_sheets: ncUncollected + mcUncollected,
    };
  }
}
''')

# dashboard.controller.ts
with open(os.path.join(dash_dir, "dashboard.controller.ts"), "w") as f:
    f.write('''import { Controller, Get } from '@nestjs/common';
import { DashboardService } from './dashboard.service';

@Controller('dashboard')
export class DashboardController {
  constructor(private readonly dashboard: DashboardService) {}

  @Get('uncollected-sheets')
  uncollectedSheets() { return this.dashboard.uncollectedSheets(); }

  @Get('summary')
  summary() { return this.dashboard.summary(); }
}
''')

# dashboard.module.ts
with open(os.path.join(dash_dir, "dashboard.module.ts"), "w") as f:
    f.write('''import { Module } from '@nestjs/common';
import { DashboardController } from './dashboard.controller';
import { DashboardService } from './dashboard.service';

@Module({
  controllers: [DashboardController],
  providers:   [DashboardService],
})
export class DashboardModule {}
''')
print("  OK: src/dashboard/ 作成")

# ─────────────────────────────────────────
# Step 4: app.module.ts に DashboardModule 追加
# ─────────────────────────────────────────
print("\n[4/6] app.module.ts 更新...")
app_mod = os.path.join(API, "src/app.module.ts")
with open(app_mod) as f:
    content = f.read()

if "DashboardModule" in content:
    print("  INFO: DashboardModule は既に登録済み")
else:
    content = content.replace(
        "import { CommonModule } from './common/common.module';",
        "import { CommonModule } from './common/common.module';\nimport { DashboardModule } from './dashboard/dashboard.module';"
    )
    content = content.replace(
        "    CommonModule,\n  ],",
        "    CommonModule,\n    DashboardModule,\n  ],"
    )
    with open(app_mod, "w") as f:
        f.write(content)
    print("  OK: app.module.ts 更新")

# ─────────────────────────────────────────
# Step 5: Web - apps/web/app/page.tsx 差し替え
# ─────────────────────────────────────────
print("\n[5/6] Web ダッシュボードページ作成...")
page_path = os.path.join(WEB, "app/page.tsx")
dashboard_code = r'''"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";

type SheetItem = {
  id: number; system: "NC" | "MC"; program_id: number;
  drawing_no: string; part_name: string; part_id: string | null;
  machine_code: string | null; machine_name: string | null;
  machine_sort: number; printed_at: string;
  operator_name: string; version: string | null;
};
type Summary = {
  nc_total: number; mc_total: number;
  nc_pending: number; mc_pending: number;
  uncollected_sheets: number;
};
type UncollectedResp = { total: number; nc_count: number; mc_count: number; items: SheetItem[] };

function elapsed(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h >= 24) return `${Math.floor(h / 24)}日前`;
  if (h > 0)   return `${h}時間${m}分前`;
  return `${m}分前`;
}
function groupByMachine(items: SheetItem[]) {
  const map = new Map<string, SheetItem[]>();
  for (const item of items) {
    const key = item.machine_code ?? "未設定";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}

export default function DashboardPage() {
  const router = useRouter();
  const [summary,  setSummary]  = useState<Summary | null>(null);
  const [sheets,   setSheets]   = useState<UncollectedResp | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [lastAt,   setLastAt]   = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([
        fetch(`${API}/dashboard/summary`).then(r => r.json()),
        fetch(`${API}/dashboard/uncollected-sheets`).then(r => r.json()),
      ]);
      setSummary(s); setSheets(u); setLastAt(new Date());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);

  const grouped = sheets ? groupByMachine(sheets.items) : new Map<string, SheetItem[]>();

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col">
      {/* ヘッダー */}
      <header className="bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-sky-600 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>
            </svg>
          </div>
          <span className="text-base font-bold text-white">MachCore</span>
          <span className="text-slate-500 text-xs">|</span>
          <span className="text-sm text-slate-300">ダッシュボード</span>
        </div>
        <div className="ml-auto flex items-center gap-3 text-xs text-slate-400">
          {lastAt && <span>更新: {lastAt.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}</span>}
          <button onClick={load}
            className="flex items-center gap-1.5 bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4-4.64 4.36A9 9 0 0 1 3.51 15"/>
            </svg>
            更新
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* サイドバー */}
        <aside className="w-[200px] shrink-0 bg-slate-800 border-r border-slate-700 flex flex-col py-5 gap-1">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">メインメニュー</div>
          {([
            { label: "ダッシュボード", href: "/",            d: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", active: true },
            { label: "NC 旋盤",       href: "/nc/search",   d: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5", active: false },
            { label: "MC マシニング", href: "/mc/search",   d: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z", active: false },
          ] as const).map(item => (
            <button key={item.href} onClick={() => router.push(item.href)}
              className={`mx-2 px-3 py-2.5 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                item.active ? "bg-sky-600 text-white" : "text-slate-400 hover:bg-slate-700 hover:text-white"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={item.d}/>
              </svg>
              {item.label}
            </button>
          ))}
          <div className="mt-4 px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">管理</div>
          <button onClick={() => router.push("/admin/login")}
            className="mx-2 px-3 py-2.5 rounded-lg flex items-center gap-2.5 text-sm text-slate-400 hover:bg-slate-700 hover:text-white transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            管理パネル
          </button>
          {sheets && sheets.total > 0 && (
            <div className="mx-3 mt-auto mb-2 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center text-[10px] font-bold text-white shrink-0">
                  {sheets.total}
                </span>
                <span className="text-xs text-amber-400 font-medium">未回収シート</span>
              </div>
            </div>
          )}
        </aside>

        {/* メイン */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* サマリーカード */}
          <section>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">システム状況</h2>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              {([
                { label: "NC 登録数",    value: summary?.nc_total,           color: "text-sky-400" },
                { label: "MC 登録数",    value: summary?.mc_total,           color: "text-teal-400" },
                { label: "NC 未承認",    value: summary?.nc_pending,         color: "text-yellow-400" },
                { label: "MC 未承認",    value: summary?.mc_pending,         color: "text-orange-400" },
                { label: "未回収シート", value: summary?.uncollected_sheets, color: summary?.uncollected_sheets ? "text-red-400" : "text-emerald-400" },
              ] as const).map(card => (
                <div key={card.label} className="bg-slate-800 rounded-xl px-4 py-3 border border-slate-700">
                  <div className="text-[10px] text-slate-400 mb-1">{card.label}</div>
                  <div className={`text-2xl font-bold ${card.color}`}>
                    {loading ? "…" : (card.value ?? 0).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 未回収段取シート */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">現在発行中の段取シート</h2>
                {sheets && (
                  <div className="flex gap-1.5">
                    <span className="text-[10px] bg-sky-500/20 text-sky-400 px-2 py-0.5 rounded-full font-bold">NC: {sheets.nc_count}</span>
                    <span className="text-[10px] bg-teal-500/20 text-teal-400 px-2 py-0.5 rounded-full font-bold">MC: {sheets.mc_count}</span>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-500">機械ID順 / 印刷日時順</span>
            </div>

            {loading ? (
              <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center text-slate-500 text-sm">読み込み中…</div>
            ) : sheets?.total === 0 ? (
              <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 text-center">
                <div className="text-4xl mb-2">✅</div>
                <p className="text-emerald-400 font-bold text-sm">未回収シートはありません</p>
                <p className="text-slate-500 text-xs mt-1">すべての段取シートが回収済みです</p>
              </div>
            ) : (
              <div className="space-y-4">
                {Array.from(grouped.entries()).map(([machineCode, items]) => (
                  <div key={machineCode} className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                    <div className="px-4 py-2.5 bg-slate-700/50 border-b border-slate-700 flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"/>
                      <span className="font-mono font-bold text-sm text-white">{machineCode}</span>
                      <span className="text-slate-400 text-xs">{items[0]?.machine_name ?? ""}</span>
                      <span className="ml-auto text-xs text-amber-400 font-bold">{items.length}枚 未回収</span>
                    </div>
                    <div className="divide-y divide-slate-700/50">
                      {items.map(item => (
                        <button key={`${item.system}-${item.id}`}
                          onClick={() => router.push(item.system === "NC" ? `/nc/${item.program_id}/record` : `/mc/${item.program_id}/record`)}
                          className="w-full px-4 py-3 flex items-center gap-4 hover:bg-slate-700/40 transition-colors text-left">
                          <span className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            item.system === "NC" ? "bg-sky-500/20 text-sky-400 border-sky-500/30" : "bg-teal-500/20 text-teal-400 border-teal-500/30"
                          }`}>{item.system}</span>
                          {item.version && <span className="shrink-0 text-[10px] text-slate-400 font-mono">v{item.version}</span>}
                          <div className="flex-1 min-w-0">
                            <span className="font-mono text-sm text-sky-300 font-bold">{item.drawing_no}</span>
                            <span className="text-slate-400 text-xs ml-2">{item.part_name}</span>
                          </div>
                          <span className="shrink-0 text-xs text-slate-400">{item.operator_name}</span>
                          <span className={`shrink-0 text-xs font-bold ${
                            Date.now() - new Date(item.printed_at).getTime() > 3600000 * 8 ? "text-red-400" : "text-amber-400"
                          }`}>{elapsed(item.printed_at)}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-slate-600">
                            <path d="M9 18l6-6-6-6"/>
                          </svg>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* クイックアクセス */}
          <section>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">クイックアクセス</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {([
                { label: "NC 部品検索",   desc: "旋盤プログラム管理",   href: "/nc/search",   color: "bg-sky-600 hover:bg-sky-500" },
                { label: "MC 部品検索",   desc: "マシニング管理",       href: "/mc/search",   color: "bg-teal-600 hover:bg-teal-500" },
                { label: "MC 新規登録",   desc: "新しいMCプログラム",   href: "/mc/new",      color: "bg-slate-600 hover:bg-slate-500" },
                { label: "管理パネル",    desc: "ユーザ・機械管理",     href: "/admin/login", color: "bg-slate-600 hover:bg-slate-500" },
              ] as const).map(item => (
                <button key={item.href} onClick={() => router.push(item.href)}
                  className={`${item.color} rounded-xl px-4 py-4 text-left transition-colors`}>
                  <div className="text-sm font-bold text-white">{item.label}</div>
                  <div className="text-xs text-white/60 mt-0.5">{item.desc}</div>
                </button>
              ))}
            </div>
          </section>

          <footer className="text-center text-xs text-slate-600 py-2">
            MachCore — 製造現場プログラム管理システム
          </footer>
        </main>
      </div>
    </div>
  );
}
'''

with open(page_path, "w") as f:
    f.write(dashboard_code)
print("  OK: apps/web/app/page.tsx 更新")

# ─────────────────────────────────────────
# Step 6: ビルド & デプロイ
# ─────────────────────────────────────────
print("\n[6/6] API ビルド & PM2 再起動...")
run("npx tsc", cwd=API)
run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && pm2 restart machcore-api',
    cwd=ROOT
)
import time
time.sleep(9)

# 疎通確認
import urllib.request, urllib.error
for ep in [
    "http://localhost:3011/api/dashboard/summary",
    "http://localhost:3011/api/dashboard/uncollected-sheets",
]:
    try:
        with urllib.request.urlopen(ep, timeout=5) as resp:
            print(f"  ✅ {ep} → HTTP {resp.status}")
    except Exception as e:
        print(f"  ❌ {ep} → {e}")

print("\n--- Web ビルド ---")
run("npm run build", cwd=WEB)
run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    cwd=ROOT
)

print("\n✅ ダッシュボード実装完了")
print("   ブラウザで http://192.168.1.11:3010/ を確認してください")
