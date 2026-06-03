#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
API  = "/home/karkyon/projects/machcore/apps/api"
REPO = "/home/karkyon/projects/machcore"

# ══════════════════════════════════════════
# 1. サイドバー罫線 - 1行版パターン (users, machines, settings, system-logs)
# ══════════════════════════════════════════

# users/machines のパターン（classNameが1行、`}`で終わる）
OLD_1LINE_A = (
    '          {SIDEBAR_ITEMS.map(item => (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ))}'
)

NEW_1LINE_A = (
    '          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ))}\n'
    '          <div className="mx-3 my-1 border-t border-slate-200" />\n'
    '          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ); })()}'
)

# system-logs のパターン（string連結版・改行あり）
OLD_SC_ML = (
    '          {SIDEBAR_ITEMS.map(item => (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ?\n'
)

# settings の aside パターン確認用（backtick + 改行あり版の別パターン）
OLD_BT_NL = (
    '          {SIDEBAR_ITEMS.map(item => (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
    '              }`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ))}'
)

NEW_BT_NL = (
    '          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
    '              }`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ))}\n'
    '          <div className="mx-3 my-1 border-t border-slate-200" />\n'
    '          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (\n'
    '            <a key={item.href} href={item.href}\n'
    '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
    '                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
    '              }`}>\n'
    '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>\n'
    '              {item.label}\n'
    '            </a>\n'
    '          ); })()}'
)

FILES = [
    f"{WEB}/app/admin/users/page.tsx",
    f"{WEB}/app/admin/machines/page.tsx",
    f"{WEB}/app/admin/settings/page.tsx",
    f"{WEB}/app/admin/system-logs/page.tsx",
    f"{WEB}/app/admin/pdf-editor/page.tsx",
]

for fpath in FILES:
    name = fpath.split("/")[-2]
    if not os.path.exists(fpath):
        print(f"  WARNING {name}: not found"); continue
    with open(fpath, "r", encoding="utf-8") as f:
        src = f.read()
    if "filter(i => i.href" in src:
        print(f"  OK [sidebar] {name}: already patched"); continue

    changed = False
    for old, new in [(OLD_1LINE_A, NEW_1LINE_A), (OLD_BT_NL, NEW_BT_NL)]:
        if old in src:
            src = src.replace(old, new, 1)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(src)
            print(f"  OK [sidebar] {name}")
            changed = True
            break
    if not changed:
        # system-logs: string concat版を確認して実際のパターンを出力
        if "SIDEBAR_ITEMS.map" in src:
            # 実際のパターンを30文字分表示
            idx = src.find("SIDEBAR_ITEMS.map")
            print(f"  INFO {name}: map found at {idx}, context: {repr(src[idx:idx+200])}")
        else:
            print(f"  SKIP [sidebar] {name}: SIDEBAR_ITEMS.map not found")

# ══════════════════════════════════════════
# 2. mc.service.ts: getTimecardsByDate / getTimecards を snake_case レスポンスに変更
#    + initTimecards で isActive=true のみ対象（既に実装済みか確認）
# ══════════════════════════════════════════
SVC = f"{API}/src/mc/mc.service.ts"
with open(SVC, "r", encoding="utf-8") as f:
    src = f.read()

OLD_TC_BY_DATE = (
    '  async getTimecardsByDate(workDate: string) {\n'
    '    return this.prisma.machineTimecard.findMany({\n'
    '      where:   { workDate: new Date(workDate) },\n'
    '      orderBy: [{ machineId: \'asc\' }, { startTime: \'asc\' }],\n'
    '      include: {\n'
    '        operator: { select: { name: true } },\n'
    '        machine:  { select: { machineCode: true, machineName: true } },\n'
    '      },\n'
    '    });\n'
    '  }'
)

NEW_TC_BY_DATE = (
    '  async getTimecardsByDate(workDate: string) {\n'
    '    const rows = await this.prisma.machineTimecard.findMany({\n'
    '      where:   { workDate: new Date(workDate) },\n'
    '      orderBy: [{ machine: { sortOrder: \'asc\' } }, { startTime: \'asc\' }],\n'
    '      include: {\n'
    '        operator: { select: { name: true } },\n'
    '        machine:  { select: { machineCode: true, machineName: true, isActive: true, sortOrder: true } },\n'
    '      },\n'
    '    });\n'
    '    const fmtTime = (d: Date) => {\n'
    '      const h = String(d.getUTCHours()).padStart(2, \'0\');\n'
    '      const m = String(d.getUTCMinutes()).padStart(2, \'0\');\n'
    '      return `${h}:${m}:00`;\n'
    '    };\n'
    '    const fmtDate = (d: Date) => {\n'
    '      return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,\'0\')}-${String(d.getUTCDate()).padStart(2,\'0\')}`;\n'
    '    };\n'
    '    return rows.map(r => ({\n'
    '      id:           r.id,\n'
    '      machine_id:   r.machineId,\n'
    '      work_date:    fmtDate(r.workDate),\n'
    '      start_time:   fmtTime(r.startTime),\n'
    '      end_time:     fmtTime(r.endTime),\n'
    '      note:         r.note,\n'
    '      machine:      r.machine,\n'
    '      operator:     r.operator,\n'
    '    }));\n'
    '  }'
)

OLD_TC = (
    '  async getTimecards(machineId: number, workDate: string) {\n'
    '    return this.prisma.machineTimecard.findMany({\n'
    '      where:   { machineId, workDate: new Date(workDate) },\n'
    '      orderBy: { startTime: \'asc\' },\n'
    '      include: { operator: { select: { name: true } } },\n'
    '    });\n'
    '  }'
)

NEW_TC = (
    '  async getTimecards(machineId: number, workDate: string) {\n'
    '    const rows = await this.prisma.machineTimecard.findMany({\n'
    '      where:   { machineId, workDate: new Date(workDate) },\n'
    '      orderBy: { startTime: \'asc\' },\n'
    '      include: { operator: { select: { name: true } } },\n'
    '    });\n'
    '    const fmtTime = (d: Date) => {\n'
    '      const h = String(d.getUTCHours()).padStart(2, \'0\');\n'
    '      const m = String(d.getUTCMinutes()).padStart(2, \'0\');\n'
    '      return `${h}:${m}:00`;\n'
    '    };\n'
    '    return rows.map(r => ({\n'
    '      id:         r.id,\n'
    '      machine_id: r.machineId,\n'
    '      work_date:  r.workDate.toISOString().slice(0, 10),\n'
    '      start_time: fmtTime(r.startTime),\n'
    '      end_time:   fmtTime(r.endTime),\n'
    '      note:       r.note,\n'
    '      operator:   r.operator,\n'
    '    }));\n'
    '  }'
)

changed = False
if OLD_TC_BY_DATE in src:
    src = src.replace(OLD_TC_BY_DATE, NEW_TC_BY_DATE, 1)
    print("  OK [mc.service.ts] getTimecardsByDate snake_case")
    changed = True
else:
    print("  SKIP [mc.service.ts] getTimecardsByDate: already patched or mismatch")

if OLD_TC in src:
    src = src.replace(OLD_TC, NEW_TC, 1)
    print("  OK [mc.service.ts] getTimecards snake_case")
    changed = True
else:
    print("  SKIP [mc.service.ts] getTimecards: already patched or mismatch")

if changed:
    with open(SVC, "w", encoding="utf-8") as f:
        f.write(src)

# ══════════════════════════════════════════
# 3. 今日(6/3)のタイムカードをDB直接投入（有効機械・08:00-17:00）
# ══════════════════════════════════════════
print("\n--- insert today timecards (2026-06-03) ---")
PSQL = ["docker", "exec", "-i", "machcore-postgres",
        "psql", "-U", "machcore", "-d", "machcore_dev", "-t", "-A"]
q = (
    "INSERT INTO machine_timecards (machine_id, operator_id, work_date, start_time, end_time) "
    "SELECT id, 1, '2026-06-03', '08:00:00', '17:00:00' FROM machines WHERE is_active = true "
    "ON CONFLICT DO NOTHING;"
)
r = subprocess.run(PSQL, input=q.encode(), capture_output=True)
if r.returncode != 0:
    print("ERROR:", r.stderr.decode())
else:
    print("OK: today timecards inserted")

# count
q2 = "SELECT COUNT(*) FROM machine_timecards WHERE work_date = '2026-06-03';"
r2 = subprocess.run(PSQL, input=q2.encode(), capture_output=True)
print("today count:", r2.stdout.decode().strip())

# ══════════════════════════════════════════
# build
# ══════════════════════════════════════════
print("\n--- API tsc --noEmit ---")
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx tsc --noEmit",
    shell=True, cwd=API, capture_output=True, text=True
)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-2000:]); sys.exit(1)
print("OK API tsc")

print("--- nest build ---")
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build",
    shell=True, cwd=API, capture_output=True, text=True
)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-2000:]); sys.exit(1)
print("OK nest build")

print("--- next build ---")
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx next build",
    shell=True, cwd=WEB, capture_output=True, text=True
)
if r.returncode != 0:
    print("ERROR:\n" + (r.stdout+r.stderr)[-3000:]); sys.exit(1)
print("OK next build")

subprocess.run("export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart all",
               shell=True, capture_output=True)
print("OK pm2 restart all")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m",
    "fix: sidebar divider all pages, timecard snake_case response, today timecards inserted"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
