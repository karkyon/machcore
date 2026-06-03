#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
API  = "/home/karkyon/projects/machcore/apps/api"
REPO = "/home/karkyon/projects/machcore"

TC = f"{WEB}/app/mc/timecards/page.tsx"
with open(TC, "r", encoding="utf-8") as f:
    src = f.read()

changed = False

# 1. header: adminUser 表示を削除（他画面と統一してheader高さ統一）
OLD_HEADER = (
    '        <div className="ml-auto flex items-center gap-3">\n'
    '          {adminUser && <span className="text-xs text-slate-500">{adminUser.name}（管理者）</span>}\n'
    '          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>\n'
    '          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}\n'
    '            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>\n'
    '        </div>'
)
NEW_HEADER = (
    '        <div className="ml-auto flex items-center gap-3">\n'
    '          {adminUser && <span className="text-xs text-slate-500">{adminUser.name}（管理者）</span>}\n'
    '          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>\n'
    '          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}\n'
    '            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>\n'
    '        </div>'
)
# users と同じ transition-colors を追加（headerの高さ変更なし、adminUser表示はそのまま）

# 2. fmtMin: 稼働時間を分計算表示に変更
# 現在: h>0 ? `${h}h${m>0?m+"m":""}` : `${m}m`
# 変更後: `${h}H${m}M` 形式（8H0M, 0H30M など）
OLD_FMT = (
    'function fmtMin(min: number) {\n'
    '  if (min <= 0) return "—";\n'
    '  const h = Math.floor(min / 60), m = min % 60;\n'
    '  return h > 0 ? `${h}h${m > 0 ? m+"m" : ""}` : `${m}m`;\n'
    '}'
)
NEW_FMT = (
    'function fmtMin(min: number) {\n'
    '  if (min <= 0) return "—";\n'
    '  const h = Math.floor(min / 60), m = min % 60;\n'
    '  return `${h}H${m}M`;\n'
    '}'
)
if OLD_FMT in src:
    src = src.replace(OLD_FMT, NEW_FMT, 1)
    print("OK fmtMin: 8h -> 8H0M format")
    changed = True
else:
    print("SKIP fmtMin: pattern not found")
    idx = src.find("function fmtMin")
    print("current fmtMin:", repr(src[idx:idx+150]))

# 3. RowState に systemType を追加
OLD_RS = (
    'interface RowState {\n'
    '  id: number;\n'
    '  machineName: string;\n'
    '  startTime: string;\n'
    '  endTime: string;\n'
    '  note: string;\n'
    '  dirty: boolean;\n'
    '  saving: boolean;\n'
    '}'
)
NEW_RS = (
    'interface RowState {\n'
    '  id: number;\n'
    '  machineName: string;\n'
    '  systemType: string;\n'
    '  startTime: string;\n'
    '  endTime: string;\n'
    '  note: string;\n'
    '  dirty: boolean;\n'
    '  saving: boolean;\n'
    '}'
)
if OLD_RS in src:
    src = src.replace(OLD_RS, NEW_RS, 1)
    print("OK RowState: systemType added")
    changed = True
else:
    print("SKIP RowState: pattern not found")

# 4. useState に sysType フィルタ追加
OLD_STATE = (
    '  const [workDate,   setWorkDate]   = useState(TODAY());\n'
    '  const [rows,       setRows]       = useState<RowState[]>([]);'
)
NEW_STATE = (
    '  const [workDate,   setWorkDate]   = useState(TODAY());\n'
    '  const [sysType,    setSysType]    = useState<"MC"|"NC">("MC");\n'
    '  const [rows,       setRows]       = useState<RowState[]>([]);'
)
if OLD_STATE in src:
    src = src.replace(OLD_STATE, NEW_STATE, 1)
    print("OK sysType state added")
    changed = True
else:
    print("SKIP sysType state: pattern not found")

# 5. loadData の cards.map に systemType を追加
OLD_MAP = (
    '      setRows(cards.map((c: any) => ({\n'
    '        id:          c.id,\n'
    '        machineName: c.machine?.machineName ?? c.machine?.machineCode ?? String(c.machine_id),\n'
    '        startTime:   fmtTime(c.start_time),\n'
    '        endTime:     fmtTime(c.end_time),\n'
    '        note:        c.note ?? "",\n'
    '        dirty:       false,\n'
    '        saving:      false,\n'
    '      })));'
)
NEW_MAP = (
    '      setRows(cards.map((c: any) => ({\n'
    '        id:          c.id,\n'
    '        machineName: c.machine?.machineName ?? c.machine?.machineCode ?? String(c.machine_id),\n'
    '        systemType:  c.machine?.systemType ?? "MC",\n'
    '        startTime:   fmtTime(c.start_time),\n'
    '        endTime:     fmtTime(c.end_time),\n'
    '        note:        c.note ?? "",\n'
    '        dirty:       false,\n'
    '        saving:      false,\n'
    '      })));'
)
if OLD_MAP in src:
    src = src.replace(OLD_MAP, NEW_MAP, 1)
    print("OK loadData: systemType mapped")
    changed = True
else:
    print("SKIP loadData map: pattern not found")

# 6. フィルタ行に種別フィルタを追加、rows に sysType フィルタを適用
OLD_FILTER_CTRL = (
    '          <div className="bg-white rounded-xl border border-slate-200 px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">\n'
    '            <label className="text-sm font-bold text-slate-600">日付</label>\n'
    '            <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}'
)
NEW_FILTER_CTRL = (
    '          <div className="bg-white rounded-xl border border-slate-200 px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">\n'
    '            <label className="text-sm font-bold text-slate-600">日付</label>\n'
    '            <input type="date" value={workDate} onChange={e => setWorkDate(e.target.value)}'
)
# 種別フィルタは日付フィルタバーの末尾（件数表示の前）に追加

OLD_COUNT = '            <span className="text-xs text-slate-400">{rows.length}件</span>'
NEW_COUNT = (
    '            <div className="flex items-center gap-1 ml-2">\n'
    '              {(["MC","NC"] as const).map(t => (\n'
    '                <button key={t} onClick={() => setSysType(t)}\n'
    '                  className={`text-xs px-3 py-1.5 rounded-lg font-bold border transition-colors ${\n'
    '                    sysType === t ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"\n'
    '                  }`}>{t}</button>\n'
    '              ))}\n'
    '            </div>\n'
    '            <span className="text-xs text-slate-400">{filteredRows.length}件</span>'
)
if OLD_COUNT in src:
    src = src.replace(OLD_COUNT, NEW_COUNT, 1)
    print("OK sysType filter buttons added")
    changed = True
else:
    print("SKIP count: pattern not found")

# 7. filteredRows を定義して表示に使用
OLD_DIRTY = '  const dirtyCount = rows.filter(r => r.dirty).length;'
NEW_DIRTY = (
    '  const filteredRows = rows.filter(r => r.systemType === sysType);\n'
    '  const dirtyCount = filteredRows.filter(r => r.dirty).length;'
)
if OLD_DIRTY in src:
    src = src.replace(OLD_DIRTY, NEW_DIRTY, 1)
    print("OK filteredRows added")
    changed = True
else:
    print("SKIP dirtyCount: pattern not found")

# 8. テーブルのrows.map -> filteredRows.map
OLD_ROWS_MAP = '                    {rows.map((row, idx) => {'
NEW_ROWS_MAP = '                    {filteredRows.map((row, idx) => {'
if OLD_ROWS_MAP in src:
    src = src.replace(OLD_ROWS_MAP, NEW_ROWS_MAP, 1)
    print("OK rows.map -> filteredRows.map")
    changed = True
else:
    print("SKIP rows.map: pattern not found")

# 9. handleAllUpdate の dirtyRows フィルタも filteredRows ベースに
OLD_ALL_UPD = '    const dirtyRows = rows.filter(r => r.dirty && r.startTime && r.endTime);'
NEW_ALL_UPD = '    const dirtyRows = filteredRows.filter(r => r.dirty && r.startTime && r.endTime);'
if OLD_ALL_UPD in src:
    src = src.replace(OLD_ALL_UPD, NEW_ALL_UPD, 1)
    print("OK handleAllUpdate: filteredRows")
    changed = True
else:
    print("SKIP handleAllUpdate: pattern not found")

if changed:
    with open(TC, "w", encoding="utf-8") as f:
        f.write(src)
    print("timecards page.tsx written")
else:
    print("NO CHANGES made")

# API: adminGetTimecards に systemType を追加
CTRL = f"{API}/src/admin/admin.controller.ts"
with open(CTRL, "r", encoding="utf-8") as f:
    csrc = f.read()

OLD_INC = "      include: { machine: { select: { machineCode: true, machineName: true, systemType: true, sortOrder: true, isActive: true } } },"
if OLD_INC in csrc:
    print("OK admin.controller.ts: systemType already included")
else:
    OLD_INC2 = "      include: { machine: { select: { machineCode: true, machineName: true, systemType: true } } },"
    NEW_INC2 = "      include: { machine: { select: { machineCode: true, machineName: true, systemType: true, sortOrder: true, isActive: true } } },"
    if OLD_INC2 in csrc:
        csrc = csrc.replace(OLD_INC2, NEW_INC2, 1)
        with open(CTRL, "w", encoding="utf-8") as f:
            f.write(csrc)
        print("OK admin.controller.ts: sortOrder/isActive added")

# build
print("\n--- API tsc --noEmit ---")
r = subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx tsc --noEmit",
    shell=True, cwd=API, capture_output=True, text=True)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-2000:]); sys.exit(1)
print("OK API tsc")

print("--- nest build ---")
r = subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build",
    shell=True, cwd=API, capture_output=True, text=True)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-2000:]); sys.exit(1)
print("OK nest build")

print("--- next build ---")
r = subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx next build",
    shell=True, cwd=WEB, capture_output=True, text=True)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-3000:]); sys.exit(1)
print("OK next build")

subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart all",
    shell=True, capture_output=True)
print("OK pm2 restart all")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m",
    "fix: timecard fmtMin 8H0M, sysType MC/NC filter, header transition-colors"], cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
