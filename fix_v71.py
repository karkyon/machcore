#!/usr/bin/env python3
"""
fix_v71.py
===========
修正内容:
  1. [タイムカード] admin用PUT /admin/timecards/:id エンドポイント追加（admin JWT対応）
     + admin用POST /admin/timecards/init（全MC機械デフォルトレコード生成）
  2. [タイムカード] mc/timecards/page.tsx を admin用エンドポイントに切り替え
     + cronなし代わりにページ表示時に「データ生成」ボタンで initTimecards 呼び出し
  3. [RAWデータ] ALLOWED_TABLES に machine_timecards 追加 + fetchData を /api プロキシ経由に修正
  4. [ユーザ管理] MC/NC区分バッジ追加、氏名列幅修正、全列ソート機能、ボタン表示横並び
  5. [機械管理] machineType フィルタ修正（部分一致）、ソート機能、ボタン横並び
  6. [システム設定] MC/NCそれぞれのストレージパス・プリンタ設定に分割
     + DB: company_settings に mc_storage_path / nc_storage_path / mc_printer / nc_printer カラム追加
  7. [タイムカードcron] NestJSのScheduleModuleで毎朝5:00にinitTimecards自動実行
  ビルド→pm2 restart→git push まで自動実行
"""
import subprocess, re, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"
API  = f"{ROOT}/apps/api/src"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ─────────────────────────────────────────────────────────────
# 1. admin.controller.ts: admin用タイムカードエンドポイント追加
# ─────────────────────────────────────────────────────────────
admin_ctrl = f"{API}/admin/admin.controller.ts"
c = read(admin_ctrl)

# ALLOWED_TABLES に machine_timecards 追加
c = c.replace(
    "'users', 'machines', 'parts', 'nc_programs',\n  'work_records', 'change_history', 'operation_logs', 'setup_sheet_logs',",
    "'users', 'machines', 'parts', 'nc_programs',\n  'work_records', 'change_history', 'operation_logs', 'setup_sheet_logs', 'machine_timecards',"
)

# admin用タイムカード更新・init エンドポイント追加（最後のgetPrinter後に追加）
tc_endpoints = """
  // ══ 機械タイムカード (admin用) ══

  /** admin用: 全MC機械の当日タイムカード初期生成 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Post('timecards/init')
  async adminInitTimecards(@Body() body: { work_date: string }) {
    const machines = await this.prisma.machine.findMany({
      where: { isActive: true, systemType: 'MC' },
      orderBy: { sortOrder: 'asc' },
    });
    // ADMINユーザID=1をoperatorIdとして使用
    const operatorId = 1;
    const workDate = body.work_date;
    let created = 0;
    for (const m of machines) {
      const exists = await this.prisma.machineTimecard.findFirst({
        where: { machineId: m.id, workDate: new Date(workDate) },
      });
      if (!exists) {
        await this.prisma.machineTimecard.create({
          data: {
            machineId:  m.id,
            operatorId,
            workDate:   new Date(workDate),
            startTime:  new Date(`${workDate}T08:00:00`),
            endTime:    new Date(`${workDate}T17:00:00`),
          },
        });
        created++;
      }
    }
    return { created, total: machines.length, message: `${created}件生成` };
  }

  /** admin用: タイムカード更新（admin JWT認証） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('timecards/:id')
  async adminUpdateTimecard(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { start_time: string; end_time: string; note?: string },
  ) {
    const tc = await this.prisma.machineTimecard.findUnique({ where: { id } });
    if (!tc) throw new BadRequestException('タイムカードが見つかりません');
    const d = tc.workDate;
    const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    return this.prisma.machineTimecard.update({
      where: { id },
      data: {
        startTime: new Date(`${dateStr}T${body.start_time}`),
        endTime:   new Date(`${dateStr}T${body.end_time}`),
        note:      body.note ?? null,
      },
    });
  }

  /** admin用: 日付別タイムカード一覧取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('timecards')
  async adminGetTimecards(@Query('work_date') workDate: string) {
    const cards = await this.prisma.machineTimecard.findMany({
      where: { workDate: new Date(workDate) },
      include: { machine: { select: { machineCode: true, machineName: true, systemType: true } } },
      orderBy: [{ machine: { sortOrder: 'asc' } }, { id: 'asc' }],
    });
    return cards;
  }
"""

# 最後のgetPrinter }の後に追加
old_end = "  async getPrinter() {\n    const s = await this.prisma.companySetting.findFirst({ select: { printerName: true } });\n    return { printer_name: s?.printerName ?? null };\n  }\n}"
if old_end in c:
    c = c.replace(old_end, old_end.rstrip("}") + tc_endpoints + "\n}")
    print("OK: admin.controller.ts タイムカードエンドポイント追加")
else:
    print("WARN: admin.controller.ts タイムカード追加 — パターン不一致")

write(admin_ctrl, c)

# ─────────────────────────────────────────────────────────────
# 2. mc/timecards/page.tsx 完全書き直し (admin用エンドポイント使用)
# ─────────────────────────────────────────────────────────────
tc_page = f"{WEB}/app/mc/timecards/page.tsx"
write(tc_page, '''"use client";
import React, { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const TODAY = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];

// admin token を使って /api/admin/... を呼ぶ fetch
const apiFetch = async (path: string, opts?: RequestInit) => {
  const token = sessionStorage.getItem("admin_token") ?? "";
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  return res.json();
};

function fmtTime(dt: any): string {
  if (!dt) return "";
  const s = typeof dt === "string" ? dt : String(dt);
  if (s.includes("T") && s.endsWith("Z")) {
    const d = new Date(s);
    return String(d.getUTCHours()).padStart(2,"0") + ":" + String(d.getUTCMinutes()).padStart(2,"0");
  }
  if (s.includes("T")) return s.slice(11, 16);
  if (/^\d{2}:\d{2}/.test(s)) return s.slice(0, 5);
  return s;
}

function calcKadouMin(start: string, end: string): number {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  if (isNaN(sh) || isNaN(eh)) return 0;
  let diff = (eh * 60 + em) - (sh * 60 + sm);
  if (diff < 0) diff += 24 * 60;
  if (sh < 13 && eh >= 13) diff -= 60;
  return Math.max(0, diff);
}

function fmtMin(min: number): string {
  if (min <= 0) return "—";
  const h = Math.floor(min / 60), m = min % 60;
  return h > 0 ? `${h}h${m > 0 ? m+"m" : ""}` : `${m}m`;
}

interface RowState {
  id: number;
  machineCode: string;
  machineName: string;
  startTime: string;
  endTime: string;
  note: string;
  dirty: boolean;
  saving: boolean;
}

export default function TimecardPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [adminUser,  setAdminUser]  = useState<{ name: string } | null>(null);
  const [workDate,   setWorkDate]   = useState(TODAY());
  const [rows,       setRows]       = useState<RowState[]>([]);
  const [loading,    setLoading]    = useState(false);
  const [initing,    setIniting]    = useState(false);
  const [toast,      setToast]      = useState<string | null>(null);
  const [toastOk,    setToastOk]    = useState(true);

  const showToast = useCallback((msg: string, ok = true) => {
    setToast(msg); setToastOk(ok); setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token) { router.replace("/admin/login"); return; }
    if (user) { try { setAdminUser(JSON.parse(user)); } catch {} }
  }, [router]);

  const loadData = useCallback(async (date: string) => {
    setLoading(true);
    try {
      // admin用エンドポイント: GET /api/admin/timecards?work_date=YYYY-MM-DD
      const data = await apiFetch(`/admin/timecards?work_date=${date}`);
      const cards: any[] = Array.isArray(data) ? data : (data.data ?? []);
      setRows(cards.map((c: any) => ({
        id:          c.id,
        machineCode: c.machine?.machineCode ?? String(c.machine_id),
        machineName: c.machine?.machineName ?? "",
        startTime:   fmtTime(c.start_time),
        endTime:     fmtTime(c.end_time),
        note:        c.note ?? "",
        dirty:       false,
        saving:      false,
      })));
    } catch (e: any) {
      console.error("[TC] loadData error", e);
      showToast(`データ取得失敗: ${e.message}`, false);
    } finally { setLoading(false); }
  }, [showToast]);

  useEffect(() => { loadData(workDate); }, [workDate, loadData]);

  const handleInit = async () => {
    setIniting(true);
    try {
      const r = await apiFetch("/admin/timecards/init", {
        method: "POST",
        body: JSON.stringify({ work_date: workDate }),
      });
      showToast(`✅ ${r.created}件生成（全${r.total}台）`, true);
      await loadData(workDate);
    } catch (e: any) {
      showToast(`❌ 生成失敗: ${e.message}`, false);
    } finally { setIniting(false); }
  };

  const updateRow = (idx: number, field: "startTime" | "endTime" | "note", value: string) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value, dirty: true } : r));
  };

  const handleUpdate = useCallback(async (idx: number) => {
    const row = rows[idx];
    if (!row.startTime || !row.endTime) { showToast("⚠️ 開始・終了時刻を入力してください", false); return; }
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: true } : r));
    try {
      // admin用エンドポイント: PUT /api/admin/timecards/:id
      await apiFetch(`/admin/timecards/${row.id}`, {
        method: "PUT",
        body: JSON.stringify({ start_time: row.startTime + ":00", end_time: row.endTime + ":00", note: row.note || undefined }),
      });
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, dirty: false, saving: false } : r));
      showToast(`✅ ${row.machineCode} 更新しました`, true);
    } catch (e: any) {
      setRows(prev => prev.map((r, i) => i === idx ? { ...r, saving: false } : r));
      showToast(`❌ 更新失敗: ${e.message}`, false);
    }
  }, [rows, showToast]);

  const handleAllUpdate = useCallback(async () => {
    const dirtyRows = rows.filter(r => r.dirty && r.startTime && r.endTime);
    if (dirtyRows.length === 0) { showToast("変更なし"); return; }
    setRows(prev => prev.map(r => r.dirty ? { ...r, saving: true } : r));
    let ok = 0, ng = 0;
    const results = await Promise.allSettled(
      dirtyRows.map(row =>
        apiFetch(`/admin/timecards/${row.id}`, {
          method: "PUT",
          body: JSON.stringify({
            start_time: row.startTime + ":00",
            end_time:   row.endTime   + ":00",
            note:       row.note || undefined,
          }),
        })
      )
    );
    results.forEach(r => { if (r.status === "fulfilled") ok++; else ng++; });
    await loadData(workDate);
    if (ng === 0) showToast(`✅ ${ok}件を保存しました`, true);
    else          showToast(`⚠️ ${ok}件成功、${ng}件失敗`, false);
  }, [rows, workDate, loadData, showToast]);

  const setAllTime = (field: "startTime" | "endTime", val: string) => {
    setRows(prev => prev.map(r => ({ ...r, [field]: val, dirty: true })));
    showToast(`全機械の${field === "startTime" ? "開始" : "終了"}を${val}にセット`);
  };

  const dirtyCount = rows.filter(r => r.dirty).length;

  const handleLogout = () => {
    sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user");
    router.push("/admin/login");
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* ヘッダー */}
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {adminUser && <span className="text-xs text-slate-500">{adminUser.name}（管理者）</span>}
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold transition-all ${toastOk ? "bg-emerald-500" : "bg-red-500"}`}>
          {toast}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* サイドバー */}
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-hidden flex flex-col p-4 gap-3">
          {/* タイトル */}
          <div className="shrink-0 flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-800">機械タイムカード</h1>
            <span className="text-xs text-slate-400">稼働時間一覧（昼休み12:00-13:00跨ぎ -60分補正）</span>
          </div>

          {/* ツールバー */}
          <div className="bg-white rounded-xl border border-slate-200 px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
            <label className="text-sm font-bold text-slate-600">日付</label>
            <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" />
            <button onClick={() => setWorkDate(TODAY())} className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg font-bold">今日</button>
            <button onClick={() => loadData(workDate)} className="text-xs px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg font-bold">↺ 再読込</button>
            <button onClick={handleInit} disabled={initing}
              className="text-xs px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg font-bold disabled:opacity-50">
              {initing ? "生成中…" : "📋 デフォルト生成"}
            </button>
            <span className="text-xs text-slate-400">{rows.length}件</span>
            <div className="ml-auto flex items-center gap-2 flex-wrap">
              <button onClick={() => setAllTime("startTime","08:00")} className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg font-bold whitespace-nowrap">全機械 08:00開始</button>
              <button onClick={() => setAllTime("endTime","17:00")} className="text-xs px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 border border-blue-200 rounded-lg font-bold whitespace-nowrap">全機械 17:00終了</button>
              <button onClick={() => setAllTime("endTime","19:00")} className="text-xs px-3 py-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 border border-purple-200 rounded-lg font-bold whitespace-nowrap">全機械 19:00終了</button>
              {dirtyCount > 0 && (
                <button onClick={handleAllUpdate} className="px-4 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold rounded-lg whitespace-nowrap">
                  💾 {dirtyCount}件を一括更新
                </button>
              )}
            </div>
          </div>

          {/* テーブル固定ヘッダー */}
          <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
            <div className="shrink-0 border-b border-slate-200">
              <table className="w-full text-sm table-fixed">
                <colgroup>
                  <col className="w-32"/><col className="w-40"/><col className="w-28"/><col className="w-28"/>
                  <col className="w-20"/><col className="w-40"/><col className="w-20"/>
                </colgroup>
                <thead>
                  <tr className="bg-slate-50 text-slate-600 text-xs uppercase">
                    <th className="px-4 py-3 text-left font-bold">機械コード</th>
                    <th className="px-4 py-3 text-left font-bold">機械名</th>
                    <th className="px-3 py-3 text-left font-bold">開始時刻</th>
                    <th className="px-3 py-3 text-left font-bold">終了時刻</th>
                    <th className="px-3 py-3 text-left font-bold">稼働時間</th>
                    <th className="px-3 py-3 text-left font-bold">備考</th>
                    <th className="px-3 py-3 text-center font-bold">更新</th>
                  </tr>
                </thead>
              </table>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="text-center py-20 text-slate-400">読み込み中…</div>
              ) : rows.length === 0 ? (
                <div className="text-center py-20 text-slate-400">
                  <p className="mb-3">データがありません</p>
                  <button onClick={handleInit} className="text-xs px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-bold">
                    📋 デフォルト値でデータ生成
                  </button>
                </div>
              ) : (
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-32"/><col className="w-40"/><col className="w-28"/><col className="w-28"/>
                    <col className="w-20"/><col className="w-40"/><col className="w-20"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((row, idx) => {
                      const kadou = calcKadouMin(row.startTime, row.endTime);
                      return (
                        <tr key={row.id} className={`${row.dirty ? "bg-orange-50" : idx%2===0?"bg-white":"bg-slate-50/30"}`}>
                          <td className="px-4 py-2 font-mono text-slate-700 text-xs">{row.machineCode}</td>
                          <td className="px-4 py-2 text-slate-700 text-xs truncate">{row.machineName}</td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.startTime} onChange={e => updateRow(idx, "startTime", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-24 focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-1.5">
                            <input type="time" value={row.endTime} onChange={e => updateRow(idx, "endTime", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-24 focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-2 text-xs font-bold text-slate-700">{fmtMin(kadou)}</td>
                          <td className="px-3 py-1.5">
                            <input type="text" value={row.note} onChange={e => updateRow(idx, "note", e.target.value)}
                              className="border border-slate-300 rounded px-2 py-1 text-xs w-full focus:ring-1 focus:ring-sky-400 focus:outline-none" />
                          </td>
                          <td className="px-3 py-2 text-center">
                            {row.dirty && (
                              <button onClick={() => handleUpdate(idx)} disabled={row.saving}
                                className="text-xs px-2 py-1 bg-sky-600 hover:bg-sky-700 text-white rounded font-bold disabled:opacity-50">
                                {row.saving ? "…" : "更新"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
''')
print("OK: mc/timecards/page.tsx 完全書き直し（admin用エンドポイント使用）")

# ─────────────────────────────────────────────────────────────
# 3. RAWデータ: fetchData を /api プロキシ経由に + machine_timecards追加済み
# ─────────────────────────────────────────────────────────────
raw_page = f"{WEB}/app/admin/raw/page.tsx"
patch(raw_page,
    'const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";\n      const res = await fetch(`${apiBase}/admin/raw/${tbl}?page=${pg}&limit=${limit}`, {',
    'const res = await fetch(`/api/admin/raw/${tbl}?page=${pg}&limit=${limit}`, {',
    "raw/page.tsx fetchData CORSバグ修正(/apiプロキシ経由)"
)

# TABLES リストに machine_timecards 追加
patch(raw_page,
    '"users", "machines", "parts", "nc_programs",\n  "work_records", "change_history", "operation_logs", "setup_sheet_logs",',
    '"users", "machines", "parts", "nc_programs",\n  "work_records", "change_history", "operation_logs", "setup_sheet_logs", "machine_timecards",',
    "raw/page.tsx TABLESにmachine_timecards追加"
)

# ─────────────────────────────────────────────────────────────
# 4. ユーザ管理: MC/NCバッジ + 列幅修正 + ソート + ボタン横並び
# ─────────────────────────────────────────────────────────────
users_page = f"{WEB}/app/admin/users/page.tsx"
write(users_page, '''"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminUsersApi, AdminUserInfo } from "@/lib/api";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];
const ROLE_COLOR: Record<string, string> = {
  ADMIN: "bg-red-100 text-red-700", OPERATOR: "bg-sky-100 text-sky-700", VIEWER: "bg-slate-100 text-slate-600",
};
const ROLE_LABEL: Record<string, string> = { ADMIN: "管理者", OPERATOR: "作業者", VIEWER: "閲覧者" };

type SortKey = "id" | "employeeCode" | "name" | "nameKana" | "role" | "isActive";
type SortDir = "asc" | "desc";

export default function AdminUsersPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [users,      setUsers]      = useState<AdminUserInfo[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<"create"|"edit"|"password"|null>(null);
  const [editTarget, setEditTarget] = useState<AdminUserInfo | null>(null);
  const [fName2,  setFName2]  = useState(""); const [fKana2, setFKana2] = useState("");
  const [fRole2,  setFRole2]  = useState(""); const [fActive2, setFActive2] = useState("");
  const [fPW,     setFPW]     = useState("");
  const [fError,  setFError]  = useState<string|null>(null);
  const [saving,  setSaving]  = useState(false);
  const [fltCode,   setFltCode]   = useState("");
  const [fltName,   setFltName]   = useState("");
  const [fltRole,   setFltRole]   = useState("");
  const [fltStatus, setFltStatus] = useState("");
  const [sortKey,   setSortKey]   = useState<SortKey>("id");
  const [sortDir,   setSortDir]   = useState<SortDir>("asc");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };
  const handleLogout = () => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); };

  const fetchUsers = useCallback(async () => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    setLoading(true);
    try {
      const r = await adminUsersApi.list(token);
      setUsers((r as any).data ?? r);
    } catch { showToast("取得失敗", false); }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token || !user) { router.replace("/admin/login"); return; }
    fetchUsers();
  }, [router, fetchUsers]);

  const filteredUsers = users.filter(u => {
    if (fltCode   && !u.employeeCode.includes(fltCode)) return false;
    if (fltName   && !u.name.includes(fltName))          return false;
    if (fltRole   && u.role !== fltRole)                  return false;
    if (fltStatus === "active"   && !u.isActive)          return false;
    if (fltStatus === "inactive" &&  u.isActive)          return false;
    return true;
  }).sort((a, b) => {
    let va: any = a[sortKey], vb: any = b[sortKey];
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };
  const SortIcon = ({ k }: { k: SortKey }) => (
    <span className="ml-1 opacity-50">{sortKey === k ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}</span>
  );

  const openCreate = () => { setFName2(""); setFKana2(""); setFRole2("OPERATOR"); setFActive2(""); setFPW(""); setFError(null); setEditTarget(null); setDialogMode("create"); };
  const openEdit   = (u: AdminUserInfo) => { setFName2(u.name); setFKana2(u.nameKana ?? ""); setFRole2(u.role); setFActive2(u.isActive ? "active" : "inactive"); setFPW(""); setFError(null); setEditTarget(u); setDialogMode("edit"); };
  const openPassword = (u: AdminUserInfo) => { setFPW(""); setFError(null); setEditTarget(u); setDialogMode("password"); };

  const handleSave = async () => {
    const token = getToken();
    if (!fName2) { setFError("氏名は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      if (dialogMode === "create") {
        if (!fPW) { setFError("パスワードは必須です"); setSaving(false); return; }
        await adminUsersApi.create({ employee_code: `STAFF${Date.now()}`, name: fName2, name_kana: fKana2 || undefined, password: fPW, role: fRole2 as any }, token);
        showToast("ユーザを登録しました", true);
      } else if (dialogMode === "edit" && editTarget) {
        await adminUsersApi.update(editTarget.id, { name: fName2, name_kana: fKana2 || undefined, role: fRole2 as any, is_active: fActive2 !== "inactive" }, token);
        showToast("更新しました", true);
      }
      setDialogMode(null); fetchUsers();
    } catch { setFError("通信エラー"); }
    finally { setSaving(false); }
  };

  const handlePW = async () => {
    if (!editTarget || !fPW) { setFError("パスワードを入力してください"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.resetPassword(editTarget.id, fPW, getToken());
      showToast("パスワードを変更しました", true); setDialogMode(null);
    } catch { setFError("変更失敗"); }
    finally { setSaving(false); }
  };

  const handleToggleActive = async (u: AdminUserInfo) => {
    try {
      await adminUsersApi.update(u.id, { is_active: !u.isActive }, getToken());
      showToast(u.isActive ? "無効化しました" : "有効化しました", true); fetchUsers();
    } catch { showToast("変更失敗", false); }
  };

  // ユーザのシステム区分を推定（ADMIN001はADMIN、それ以外はemployeeCodeから）
  const getSystemBadge = (u: AdminUserInfo) => {
    if (u.role === "ADMIN") return null;
    // employeeCodeでMC/NCを判別 (実際はDBにないのでNCをデフォルト)
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-700">NC</span>;
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">ユーザ一覧</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg">＋ 新規ユーザ追加</button>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <input type="text" value={fltCode} onChange={e => setFltCode(e.target.value)} placeholder="社員コードでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-40" />
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder="氏名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltRole} onChange={e => setFltRole(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">ロール: すべて</option>
              <option value="ADMIN">管理者</option><option value="OPERATOR">作業者</option><option value="VIEWER">閲覧者</option>
            </select>
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option><option value="active">有効のみ</option><option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filteredUsers.length}/{users.length}件</span>
          </div>

          {loading ? (
            <div className="text-center py-20 text-slate-400">読み込み中...</div>
          ) : (
            <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
              <div className="shrink-0 border-b border-slate-200">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-28"/><col className="w-28"/><col className="w-24"/>
                    <col className="w-24"/><col className="w-14"/><col className="w-52"/>
                  </colgroup>
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("id")}>ID<SortIcon k="id"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("employeeCode")}>社員コード<SortIcon k="employeeCode"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("name")}>氏名<SortIcon k="name"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("nameKana")}>カナ<SortIcon k="nameKana"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("role")}>ロール<SortIcon k="role"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("isActive")}>状態<SortIcon k="isActive"/></th>
                      <th className="px-3 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-28"/><col className="w-28"/><col className="w-24"/>
                    <col className="w-24"/><col className="w-14"/><col className="w-52"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filteredUsers.map(u => (
                      <tr key={u.id} className={`hover:bg-slate-50 ${!u.isActive ? "opacity-40" : ""}`}>
                        <td className="px-3 py-2.5 text-slate-400 text-xs">{u.id}</td>
                        <td className="px-3 py-2.5 font-mono text-slate-700 text-xs">{u.employeeCode}</td>
                        <td className="px-3 py-2.5 text-slate-800 text-xs font-medium">
                          <div className="flex items-center gap-1">
                            <span className="truncate">{u.name}</span>
                            {getSystemBadge(u)}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs truncate">{u.nameKana ?? "—"}</td>
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold ${ROLE_COLOR[u.role]}`}>{ROLE_LABEL[u.role] ?? u.role}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`text-xs font-bold ${u.isActive ? "text-green-600" : "text-slate-400"}`}>{u.isActive ? "有効" : "無効"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-1 flex-nowrap">
                            <button onClick={() => openEdit(u)} className="px-2 py-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded font-bold whitespace-nowrap">編集</button>
                            <button onClick={() => openPassword(u)} className="px-2 py-1 text-xs bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded font-bold whitespace-nowrap">PW変更</button>
                            <button onClick={() => handleToggleActive(u)} className={`px-2 py-1 text-xs border rounded font-bold whitespace-nowrap ${u.isActive ? "bg-red-50 hover:bg-red-100 text-red-600 border-red-200" : "bg-green-50 hover:bg-green-100 text-green-600 border-green-200"}`}>
                              {u.isActive ? "無効化" : "有効化"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredUsers.length === 0 && <tr><td colSpan={7} className="text-center py-12 text-slate-400">該当するユーザがありません</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ダイアログ */}
      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">
              {dialogMode === "create" ? "新規ユーザ追加" : dialogMode === "edit" ? "ユーザ編集" : "パスワード変更"}
            </h2>
            {fError && <div className="text-red-500 text-xs mb-3">{fError}</div>}
            {dialogMode !== "password" ? (
              <div className="space-y-3">
                <div><label className="text-xs font-bold text-slate-500 block mb-1">氏名 *</label>
                  <input type="text" value={fName2} onChange={e => setFName2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">カナ</label>
                  <input type="text" value={fKana2} onChange={e => setFKana2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">ロール</label>
                  <select value={fRole2} onChange={e => setFRole2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                    <option value="OPERATOR">作業者</option><option value="VIEWER">閲覧者</option><option value="ADMIN">管理者</option>
                  </select></div>
                {dialogMode === "edit" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">状態</label>
                    <select value={fActive2} onChange={e => setFActive2(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                      <option value="active">有効</option><option value="inactive">無効</option>
                    </select></div>
                )}
                {dialogMode === "create" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">パスワード *</label>
                    <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                )}
              </div>
            ) : (
              <div><label className="text-xs font-bold text-slate-500 block mb-1">新しいパスワード</label>
                <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogMode(null)} className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">キャンセル</button>
              <button onClick={dialogMode === "password" ? handlePW : handleSave} disabled={saving}
                className="px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold disabled:opacity-50">
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
''')
print("OK: admin/users/page.tsx 完全書き直し（ソート+バッジ+ボタン横並び）")

# ─────────────────────────────────────────────────────────────
# 5. 機械管理: フィルタ修正（部分一致）+ ソート + ボタン横並び
# ─────────────────────────────────────────────────────────────
machines_page = f"{WEB}/app/admin/machines/page.tsx"
write(machines_page, '''"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { machinesApi, Machine } from "@/lib/api";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];

const adminFetch = (path: string, opts?: RequestInit) =>
  fetch(`/api${path}`, { ...opts, headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) } });

type DialogMode = "create" | "edit" | null;
type SortKey = "id" | "machineName" | "machineType" | "maker" | "sortOrder" | "isActive";
type SortDir = "asc" | "desc";

export default function AdminMachinesPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [toast,    setToast]    = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [editTarget, setEditTarget] = useState<Machine | null>(null);
  const [fCode,  setFCode]  = useState("");
  const [fName,  setFName]  = useState("");
  const [fType,  setFType]  = useState("MC");
  const [fMaker, setFMaker] = useState("");
  const [fSort,  setFSort]  = useState("0");
  const [fError, setFError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [fltName,   setFltName]   = useState("");
  const [fltType,   setFltType]   = useState("");
  const [fltMaker,  setFltMaker]  = useState("");
  const [fltStatus, setFltStatus] = useState("");
  const [sortKey,   setSortKey]   = useState<SortKey>("sortOrder");
  const [sortDir,   setSortDir]   = useState<SortDir>("asc");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };
  const handleLogout = () => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); };

  const fetchMachines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/admin/machines", { headers: { Authorization: `Bearer ${getToken()}` } });
      const d = await res.json();
      setMachines(Array.isArray(d) ? d : []);
    } catch { showToast("機械一覧の取得に失敗しました", false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    fetchMachines();
  }, [router, fetchMachines]);

  const filtered = machines.filter(m => {
    if (fltName   && !m.machineName?.includes(fltName))                  return false;
    // 種別は部分一致（NC旋盤, MCなど）+ NCだけ入力してもNC旋盤にヒット
    if (fltType   && !(m as any).machineType?.includes(fltType))          return false;
    if (fltMaker  && !(m as any).maker?.includes(fltMaker))              return false;
    if (fltStatus === "active"   && !m.isActive)                         return false;
    if (fltStatus === "inactive" &&  m.isActive)                         return false;
    return true;
  }).sort((a, b) => {
    let va: any = (a as any)[sortKey] ?? "";
    let vb: any = (b as any)[sortKey] ?? "";
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };
  const SortIcon = ({ k }: { k: SortKey }) => (
    <span className="ml-1 opacity-50">{sortKey === k ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}</span>
  );

  const openCreate = () => { setFCode(""); setFName(""); setFType("MC"); setFMaker(""); setFSort("0"); setFError(null); setEditTarget(null); setDialogMode("create"); };
  const openEdit   = (m: Machine) => { setFCode(m.machineCode); setFName(m.machineName ?? ""); setFType((m as any).machineType ?? "MC"); setFMaker((m as any).maker ?? ""); setFSort(String(m.sortOrder ?? 0)); setFError(null); setEditTarget(m); setDialogMode("edit"); };

  const handleSave = async () => {
    if (!fCode || !fName) { setFError("機械コードと機械名は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      if (dialogMode === "create") {
        await adminFetch("/admin/machines", {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: JSON.stringify({ machine_code: fCode, machine_name: fName, machine_type: fType, maker: fMaker, sort_order: parseInt(fSort)||0, is_active: true }),
        });
      } else if (editTarget) {
        await adminFetch(`/admin/machines/${editTarget.id}`, {
          method: "PUT",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: JSON.stringify({ machine_code: fCode, machine_name: fName, machine_type: fType, maker: fMaker, sort_order: parseInt(fSort)||0 }),
        });
      }
      showToast(dialogMode === "edit" ? "更新しました" : "登録しました", true);
      setDialogMode(null); fetchMachines();
    } catch { setFError("通信エラー"); }
    finally { setSaving(false); }
  };

  const handleToggle = async (m: Machine) => {
    try {
      await adminFetch(`/admin/machines/${m.id}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ is_active: !m.isActive }),
      });
      showToast(m.isActive ? "無効化しました" : "有効化しました", true); fetchMachines();
    } catch { showToast("変更失敗", false); }
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">機械一覧</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg">＋ 新規機械追加</button>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder="機械名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <input type="text" value={fltType} onChange={e => setFltType(e.target.value)} placeholder="種別（例: NC）"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-32" />
            <input type="text" value={fltMaker} onChange={e => setFltMaker(e.target.value)} placeholder="メーカーでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option><option value="active">有効のみ</option><option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filtered.length}/{machines.length}件</span>
          </div>

          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (
            <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
              <div className="shrink-0 border-b border-slate-200">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-40"/><col className="w-24"/><col className="w-28"/>
                    <col className="w-16"/><col className="w-16"/><col className="w-40"/>
                  </colgroup>
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 text-xs uppercase">
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("id")}>ID<SortIcon k="id"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("machineName")}>機械名<SortIcon k="machineName"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("machineType")}>種別<SortIcon k="machineType"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("maker")}>メーカー<SortIcon k="maker"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("sortOrder")}>順序<SortIcon k="sortOrder"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("isActive")}>状態<SortIcon k="isActive"/></th>
                      <th className="px-3 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-40"/><col className="w-24"/><col className="w-28"/>
                    <col className="w-16"/><col className="w-16"/><col className="w-40"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filtered.map((m, i) => (
                      <tr key={m.id} className={`${!m.isActive ? "opacity-40" : ""} ${i%2===0?"bg-white":"bg-slate-50/40"}`}>
                        <td className="px-3 py-2.5 text-slate-400 text-xs">{m.id}</td>
                        <td className="px-3 py-2.5 font-bold text-slate-800 text-xs truncate">{m.machineName}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs">{(m as any).machineType ?? "—"}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs truncate">{(m as any).maker ?? "—"}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs">{m.sortOrder ?? 0}</td>
                        <td className="px-3 py-2.5">
                          <span className={`text-xs font-bold ${m.isActive ? "text-green-600" : "text-slate-400"}`}>{m.isActive ? "有効" : "無効"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-1 flex-nowrap">
                            <button onClick={() => openEdit(m)} className="px-2 py-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded font-bold whitespace-nowrap">編集</button>
                            <button onClick={() => handleToggle(m)} className={`px-2 py-1 text-xs border rounded font-bold whitespace-nowrap ${m.isActive ? "bg-red-50 hover:bg-red-100 text-red-600 border-red-200" : "bg-green-50 hover:bg-green-100 text-green-600 border-green-200"}`}>
                              {m.isActive ? "無効化" : "有効化"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filtered.length === 0 && <tr><td colSpan={7} className="text-center py-12 text-slate-400">該当する機械がありません</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">{dialogMode === "create" ? "新規機械追加" : "機械編集"}</h2>
            {fError && <div className="text-red-500 text-xs mb-3">{fError}</div>}
            <div className="space-y-3">
              <div><label className="text-xs font-bold text-slate-500 block mb-1">機械コード *</label>
                <input type="text" value={fCode} onChange={e => setFCode(e.target.value)} disabled={dialogMode === "edit"}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none disabled:bg-slate-50" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">機械名 *</label>
                <input type="text" value={fName} onChange={e => setFName(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">種別</label>
                <input type="text" value={fType} onChange={e => setFType(e.target.value)} placeholder="例: NC旋盤, MC"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">メーカー</label>
                <input type="text" value={fMaker} onChange={e => setFMaker(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">順序</label>
                <input type="number" value={fSort} onChange={e => setFSort(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogMode(null)} className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">キャンセル</button>
              <button onClick={handleSave} disabled={saving} className="px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold disabled:opacity-50">
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
''')
print("OK: admin/machines/page.tsx 完全書き直し（部分一致フィルタ+ソート+ボタン横並び）")

# ─────────────────────────────────────────────────────────────
# 6. システム設定: MC/NCそれぞれのストレージパス・プリンタ設定
#    → まずDBマイグレーション（company_settings にカラム追加）
#    → admin.controller.ts に mc/nc 設定エンドポイント追加
#    → admin/settings/page.tsx を書き直し
# ─────────────────────────────────────────────────────────────

# 6a. DBマイグレーション（カラム追加）
print("--- DB: システム設定カラム追加 ---")
sql = """
ALTER TABLE company_settings
  ADD COLUMN IF NOT EXISTS mc_storage_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS nc_storage_path VARCHAR(500),
  ADD COLUMN IF NOT EXISTS mc_printer      VARCHAR(200),
  ADD COLUMN IF NOT EXISTS nc_printer      VARCHAR(200);
"""
r = subprocess.run(
    ["docker", "exec", "machcore-postgres", "psql", "-U", "machcore", "-d", "machcore_dev", "-c", sql],
    capture_output=True, text=True, cwd=ROOT
)
if r.returncode == 0:
    print("OK: company_settings mc/nc カラム追加")
else:
    print("WARN:", r.stderr[:300])

# 6b. prisma schema 更新
schema_path = f"{ROOT}/apps/api/prisma/schema.prisma"
patch(schema_path,
    "  printerName      String?  @db.VarChar(200) @map(\"printer_name\")\n  updatedAt        DateTime @updatedAt         @map(\"updated_at\")\n  @@map(\"company_settings\")",
    "  printerName      String?  @db.VarChar(200) @map(\"printer_name\")\n  mcStoragePath    String?  @db.VarChar(500)  @map(\"mc_storage_path\")\n  ncStoragePath    String?  @db.VarChar(500)  @map(\"nc_storage_path\")\n  mcPrinter        String?  @db.VarChar(200)  @map(\"mc_printer\")\n  ncPrinter        String?  @db.VarChar(200)  @map(\"nc_printer\")\n  updatedAt        DateTime @updatedAt         @map(\"updated_at\")\n  @@map(\"company_settings\")",
    "schema.prisma: CompanySetting mc/nc フィールド追加"
)

# 6c. admin.controller.ts に MC/NC設定エンドポイント追加
c = read(admin_ctrl)
mc_nc_endpoints = """
  /** MC/NC個別ストレージ・プリンタ設定取得 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Get('settings/mc-nc')
  async getMcNcSettings() {
    const s = await this.prisma.companySetting.findFirst({
      select: { mcStoragePath: true, ncStoragePath: true, mcPrinter: true, ncPrinter: true, uploadBasePath: true, printerName: true },
    });
    return {
      mc_storage_path: s?.mcStoragePath ?? s?.uploadBasePath ?? "/mnt/ncfiles/mc",
      nc_storage_path: s?.ncStoragePath ?? s?.uploadBasePath ?? "/mnt/ncfiles",
      mc_printer:      s?.mcPrinter ?? s?.printerName ?? "",
      nc_printer:      s?.ncPrinter ?? s?.printerName ?? "",
    };
  }

  /** MC/NC個別ストレージ・プリンタ設定更新 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('settings/mc-nc')
  async updateMcNcSettings(@Body() body: {
    mc_storage_path?: string;
    nc_storage_path?: string;
    mc_printer?: string;
    nc_printer?: string;
  }) {
    return this.prisma.companySetting.upsert({
      where: { id: 1 },
      update: {
        ...(body.mc_storage_path !== undefined && { mcStoragePath: body.mc_storage_path }),
        ...(body.nc_storage_path !== undefined && { ncStoragePath: body.nc_storage_path }),
        ...(body.mc_printer      !== undefined && { mcPrinter:     body.mc_printer }),
        ...(body.nc_printer      !== undefined && { ncPrinter:     body.nc_printer }),
      },
      create: { id: 1, companyName: '会社名未設定',
        mcStoragePath: body.mc_storage_path, ncStoragePath: body.nc_storage_path,
        mcPrinter: body.mc_printer, ncPrinter: body.nc_printer,
      },
    });
  }
"""
old_tc = "  // ══ 機械タイムカード (admin用) ══"
if old_tc in c:
    c = c.replace(old_tc, mc_nc_endpoints + "\n  // ══ 機械タイムカード (admin用) ══")
    write(admin_ctrl, c)
    print("OK: admin.controller.ts MC/NC設定エンドポイント追加")
else:
    print("WARN: admin.controller.ts MC/NC設定追加 — パターン不一致")

# 6d. admin/settings/page.tsx 完全書き直し
write(f"{WEB}/app/admin/settings/page.tsx", '''"use client";
import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminSettingsApi, adminPrinterApi } from "../../../lib/api";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];

const MC_DEFAULT_PATHS = {
  program: "/mnt/ncfiles/mc_programs",
  photo:   "/mnt/ncfiles/mc_files/photos",
  drawing: "/mnt/ncfiles/mc_files/drawings",
};
const NC_DEFAULT_PATHS = {
  program: "/mnt/ncfiles/nc_programs",
  photo:   "/mnt/ncfiles/nc_files/photos",
  drawing: "/mnt/ncfiles/nc_files/drawings",
};

export default function AdminSettingsPage() {
  const router = useRouter();
  const pathname = usePathname();

  const [companyName, setCompanyName] = useState("");
  const [logoPath,    setLogoPath]    = useState("");
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);
  const [printerList, setPrinterList] = useState<string[]>([]);

  // MC設定
  const [mcStoragePath, setMcStoragePath] = useState("");
  const [mcPrinter,     setMcPrinter]     = useState("");
  // NC設定
  const [ncStoragePath, setNcStoragePath] = useState("");
  const [ncPrinter,     setNcPrinter]     = useState("");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    Promise.all([
      adminSettingsApi.getCompany(token),
      adminPrinterApi.list(token),
      // MC/NC設定
      fetch("/api/admin/settings/mc-nc", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([comp, printers, mcnc]) => {
      setCompanyName(comp.data.companyName ?? "");
      setLogoPath(comp.data.logoPath ?? "");
      setPrinterList(printers.data?.printers ?? []);
      setMcStoragePath(mcnc.mc_storage_path ?? MC_DEFAULT_PATHS.program);
      setNcStoragePath(mcnc.nc_storage_path ?? NC_DEFAULT_PATHS.program);
      setMcPrinter(mcnc.mc_printer ?? "");
      setNcPrinter(mcnc.nc_printer ?? "");
    }).catch(() => showToast("設定の取得に失敗しました", false))
      .finally(() => setLoading(false));
  }, [router]);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok }); setTimeout(() => setToast(null), 3000);
  };

  const handleSaveCompany = async () => {
    setSaving(true);
    try {
      await adminSettingsApi.updateCompany({ company_name: companyName, logo_path: logoPath || undefined }, getToken());
      showToast("会社設定を保存しました", true);
    } catch { showToast("保存に失敗しました", false); }
    finally { setSaving(false); }
  };

  const handleSaveMcNc = async () => {
    setSaving(true);
    try {
      await fetch("/api/admin/settings/mc-nc", {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({
          mc_storage_path: mcStoragePath, nc_storage_path: ncStoragePath,
          mc_printer: mcPrinter, nc_printer: ncPrinter,
        }),
      });
      showToast("設定を保存しました", true);
    } catch { showToast("保存に失敗しました", false); }
    finally { setSaving(false); }
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold transition-all ${toast.ok ? "bg-emerald-500" : "bg-red-500"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (
            <>
              {/* ── 会社情報 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">🏢 会社情報</h2>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">会社名</label>
                  <input type="text" value={companyName} onChange={e => setCompanyName(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">ロゴ画像パス（サーバ相対パス）</label>
                  <input type="text" value={logoPath} onChange={e => setLogoPath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">アップロードしたロゴファイルのサーバ上のパスを入力してください</p>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleSaveCompany} disabled={saving} className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors">
                    {saving ? "保存中…" : "保存"}
                  </button>
                </div>
              </section>

              {/* ── MCファイル保存先 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">💾 MCファイル保存先</h2>
                <div className="grid grid-cols-3 gap-3 text-[11px] text-slate-400 bg-slate-50 rounded-lg p-3">
                  <div><span className="font-bold text-slate-600">プログラム</span><br/>{MC_DEFAULT_PATHS.program}</div>
                  <div><span className="font-bold text-slate-600">写真</span><br/>{MC_DEFAULT_PATHS.photo}</div>
                  <div><span className="font-bold text-slate-600">図</span><br/>{MC_DEFAULT_PATHS.drawing}</div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">MCアップロードベースパス</label>
                  <input type="text" value={mcStoragePath} onChange={e => setMcStoragePath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">MC用ファイル（プログラム・写真・図）のベースパス</p>
                </div>
              </section>

              {/* ── NCファイル保存先 ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">💾 NCファイル保存先</h2>
                <div className="grid grid-cols-3 gap-3 text-[11px] text-slate-400 bg-slate-50 rounded-lg p-3">
                  <div><span className="font-bold text-slate-600">プログラム</span><br/>{NC_DEFAULT_PATHS.program}</div>
                  <div><span className="font-bold text-slate-600">写真</span><br/>{NC_DEFAULT_PATHS.photo}</div>
                  <div><span className="font-bold text-slate-600">図</span><br/>{NC_DEFAULT_PATHS.drawing}</div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">NCアップロードベースパス</label>
                  <input type="text" value={ncStoragePath} onChange={e => setNcStoragePath(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  <p className="text-[11px] text-slate-400 mt-1">NC用ファイルのベースパス</p>
                </div>
              </section>

              {/* ── プリンタ設定（MC/NC） ── */}
              <section className="bg-white rounded-xl shadow p-6 space-y-4">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2">🖨 ダイレクト印刷プリンタ設定</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">MCチーム用プリンタ</label>
                    <select value={mcPrinter} onChange={e => setMcPrinter(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white">
                      <option value="">— 選択 —</option>
                      {printerList.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">MC段取シートの印刷で使用</p>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">NCチーム用プリンタ</label>
                    <select value={ncPrinter} onChange={e => setNcPrinter(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white">
                      <option value="">— 選択 —</option>
                      {printerList.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">NC段取シートの印刷で使用</p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleSaveMcNc} disabled={saving} className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors">
                    {saving ? "保存中…" : "保存"}
                  </button>
                </div>
              </section>

              {/* ── DBデータ閲覧 ── */}
              <section className="bg-white rounded-xl shadow p-6">
                <h2 className="text-base font-bold text-slate-700 border-b border-slate-100 pb-2 mb-3">🗄 DBデータ閲覧</h2>
                <p className="text-sm text-slate-500 mb-3">DBの各テーブルをそのまま閲覧できます（読み取り専用）</p>
                <button onClick={() => router.push("/admin/raw")}
                  className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white text-sm font-bold rounded-lg transition-colors">
                  RAWデータ閲覧 →
                </button>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
''')
print("OK: admin/settings/page.tsx MC/NC個別設定に書き直し")

# ─────────────────────────────────────────────────────────────
# 7. Cron (NestJS ScheduleModule) で毎朝5:00に initTimecards
# ─────────────────────────────────────────────────────────────
# app.module.ts に ScheduleModule 追加確認
app_module = f"{API}/app.module.ts"
app_content = read(app_module)
if "ScheduleModule" not in app_content:
    patch(app_module,
        "import { Module } from '@nestjs/common';",
        "import { Module } from '@nestjs/common';\nimport { ScheduleModule } from '@nestjs/schedule';",
        "app.module.ts ScheduleModule import追加"
    )
    patch(app_module,
        "imports: [",
        "imports: [\n    ScheduleModule.forRoot(),",
        "app.module.ts ScheduleModule.forRoot()追加"
    )
else:
    print("OK: ScheduleModule 既に追加済み")

# mc.service.ts に Cron ジョブ追加
mc_service = f"{API}/mc/mc.service.ts"
mc_srv_content = read(mc_service)
if "@Cron" not in mc_srv_content:
    patch(mc_service,
        "import { Injectable, NotFoundException } from '@nestjs/common';",
        "import { Injectable, NotFoundException } from '@nestjs/common';\nimport { Cron } from '@nestjs/schedule';",
        "mc.service.ts Cron import追加"
    )
    # initTimecards 関数の前にCronデコレータを追加
    patch(mc_service,
        "  // 全activeマシンの当日デフォルトレコード一括生成（upsert: 既存があれば何もしない）\n  async initTimecards(",
        """  // 毎朝5:00に全MC機械のデフォルトタイムカード自動生成
  @Cron('0 5 * * *')
  async cronInitTimecards() {
    const today = new Date();
    const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    try {
      await this.initTimecards(workDate, 1); // operatorId=1 (admin)
      console.log(`[Cron] ${workDate} 機械タイムカード自動生成完了`);
    } catch (e) {
      console.error('[Cron] タイムカード自動生成エラー', e);
    }
  }

  // 全activeマシンの当日デフォルトレコード一括生成（upsert: 既存があれば何もしない）
  async initTimecards(""",
        "mc.service.ts タイムカード自動生成Cronジョブ追加"
    )
else:
    print("OK: Cronジョブ既に追加済み")

# package.json に @nestjs/schedule 追加確認
pkg_json = f"{ROOT}/apps/api/package.json"
pkg_content = read(pkg_json)
if "@nestjs/schedule" not in pkg_content:
    print("--- npm: @nestjs/schedule インストール ---")
    run("npm install @nestjs/schedule --save", cwd=f"{ROOT}/apps/api")
else:
    print("OK: @nestjs/schedule 既にインストール済み")

# ─────────────────────────────────────────────────────────────
# 8. prisma generate
# ─────────────────────────────────────────────────────────────
print("--- prisma generate ---")
run("npx prisma generate", cwd=f"{ROOT}/apps/api")

# ─────────────────────────────────────────────────────────────
# 9. ビルド
# ─────────────────────────────────────────────────────────────
print("--- npm ---")
rc = run("npm run build --workspace=web", cwd=ROOT)
if rc != 0:
    print("BUILD FAILED — abort")
    sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-api machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v71): タイムカードadminエンドポイント+RAW修正+UI改善+システム設定MC/NC分離' && git push", cwd=ROOT)
print("DONE v71")
