#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
API  = "/home/karkyon/projects/machcore/apps/api"
REPO = "/home/karkyon/projects/machcore"
PSQL = ["docker","exec","-i","machcore-postgres",
        "psql","-U","machcore","-d","machcore_dev","-t","-A"]

def sql(q):
    r = subprocess.run(PSQL, input=q.encode(), capture_output=True)
    return r.stdout.decode().strip()

# ══════════════════════════════════════════
# 1. DBの既存タイムカードの start_time/end_time を確認
# ══════════════════════════════════════════
print("=== DB check ===")
cnt = sql("SELECT COUNT(*) FROM machine_timecards;")
print("total timecards:", cnt)

sample = sql("SELECT id, machine_id, work_date::text, start_time::text, end_time::text FROM machine_timecards ORDER BY work_date DESC, id LIMIT 5;")
print("sample (latest):", sample)

sample2 = sql("SELECT id, machine_id, work_date::text, start_time::text, end_time::text FROM machine_timecards WHERE work_date = '2026-04-01' LIMIT 3;")
print("sample 2026-04-01:", sample2)

# ══════════════════════════════════════════
# 2. 6/3のデータの時刻を確認・修正
#    DBにはすでに46件あるが start_time が 00:00:00 になっている可能性
# ══════════════════════════════════════════
print("\n=== check 2026-06-03 ===")
s = sql("SELECT COUNT(*), MIN(start_time::text), MAX(end_time::text) FROM machine_timecards WHERE work_date = '2026-06-03';")
print("06-03 count/start/end:", s)

# start_time=00:00:00 or 08:00:00 確認
s2 = sql("SELECT COUNT(*) FROM machine_timecards WHERE work_date = '2026-06-03' AND start_time = '08:00:00';")
print("06-03 correct (08:00):", s2)

# 全タイムカードのstart_time分布
s3 = sql("SELECT start_time::text, COUNT(*) FROM machine_timecards GROUP BY start_time ORDER BY COUNT(*) DESC LIMIT 5;")
print("start_time distribution:", s3)

# ══════════════════════════════════════════
# 3. もし start_time が 00:00:00 なら全件修正
# ══════════════════════════════════════════
print("\n=== fix timecards start/end time ===")
# seed_timecards_v2.py で INSERT した値は '08:00:00' だが、
# DBのTime型はUTCで保存されるため '08:00:00' JST = '08:00:00' UTC として保存されている
# しかし表示時に getTimecardsByDate が `getUTCHours()` で読んでいる
# → DBに '08:00:00' で入っていれば UTC Hours = 8 で正しい

# 確認: 実際にDBに何時で入っているか
s4 = sql("SELECT start_time::text FROM machine_timecards WHERE work_date='2026-04-01' LIMIT 1;")
print("raw start_time in DB:", s4)

# もし '00:00:00' なら修正が必要
wrong = sql("SELECT COUNT(*) FROM machine_timecards WHERE start_time = '00:00:00';")
print("wrong start_time (00:00:00) count:", wrong)

if wrong.strip() and int(wrong.strip()) > 0:
    print("fixing wrong timecards...")
    fix_q = "UPDATE machine_timecards SET start_time = '08:00:00', end_time = '17:00:00' WHERE start_time = '00:00:00';"
    r = subprocess.run(PSQL, input=fix_q.encode(), capture_output=True)
    print("fix result:", r.stdout.decode().strip(), r.stderr.decode().strip())

# ══════════════════════════════════════════
# 4. 4/1以降の不足データを補完
#    (holidays: 土日 + business_calendars)
# ══════════════════════════════════════════
import datetime
print("\n=== seed missing timecards ===")

holidays_raw = sql("SELECT work_date::text FROM business_calendars WHERE is_holiday = true;")
holidays = set(x.strip()[:10] for x in holidays_raw.split("\n") if x.strip())

machines_raw = sql("SELECT id FROM machines WHERE is_active = true ORDER BY sort_order;")
machine_ids = [int(x) for x in machines_raw.split("\n") if x.strip()]
print("active machines:", len(machine_ids))
print("holidays:", len(holidays))

existing_raw = sql("SELECT machine_id::text || '|' || work_date::text FROM machine_timecards WHERE work_date >= '2026-04-01';")
existing = set()
for line in existing_raw.split("\n"):
    if "|" in line:
        mid, wd = line.strip().split("|")
        existing.add((int(mid), wd[:10]))
print("existing records (4/1~):", len(existing))

today = datetime.date.today()
start = datetime.date(2026, 4, 1)
vals = []
cur = start
while cur <= today:
    ds = cur.isoformat()
    if cur.weekday() < 5 and ds not in holidays:
        for mid in machine_ids:
            if (mid, ds) not in existing:
                vals.append("(" + str(mid) + ",1,'" + ds + "','08:00:00','17:00:00')")
    cur += datetime.timedelta(days=1)

print("rows to insert:", len(vals))
if vals:
    batch = 200
    total = 0
    for i in range(0, len(vals), batch):
        chunk = vals[i:i+batch]
        q = ("INSERT INTO machine_timecards (machine_id,operator_id,work_date,start_time,end_time) VALUES "
             + ",".join(chunk) + " ON CONFLICT DO NOTHING;")
        r = subprocess.run(PSQL, input=q.encode(), capture_output=True)
        if r.returncode != 0:
            print("ERROR:", r.stderr.decode()); sys.exit(1)
        total += len(chunk)
    print("inserted:", total)
else:
    print("nothing to insert")

final_cnt = sql("SELECT COUNT(*) FROM machine_timecards WHERE work_date >= '2026-04-01';")
print("final count (4/1~):", final_cnt)

# ══════════════════════════════════════════
# 5. サイドバー罫線 - system-logs と pdf-editor
#    実際のパターンをそのまま使用
# ══════════════════════════════════════════
print("\n=== fix sidebar ===")

# system-logs: string concat版
SL = f"{WEB}/app/admin/system-logs/page.tsx"
with open(SL, "r", encoding="utf-8") as f:
    src = f.read()

if "filter(i => i.href" in src:
    print("  OK system-logs: already patched")
elif 'SIDEBAR_ITEMS.map(item => (' in src:
    # 実際のパターンを特定してfilter版に置換
    # string concat版
    OLD_SC = ('          {SIDEBAR_ITEMS.map(item => (\n'
              '            <a key={item.href} href={item.href}\n'
              '              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>\n'
              '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
              '                <path d={item.icon} />\n'
              '              </svg>\n'
              '              {item.label}\n'
              '            </a>\n'
              '          ))}')
    NEW_SC = ('          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (\n'
              '            <a key={item.href} href={item.href}\n'
              '              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>\n'
              '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
              '                <path d={item.icon} />\n'
              '              </svg>\n'
              '              {item.label}\n'
              '            </a>\n'
              '          ))}\n'
              '          <div className="mx-3 my-1 border-t border-slate-200" />\n'
              '          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (\n'
              '            <a key={item.href} href={item.href}\n'
              '              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>\n'
              '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
              '                <path d={item.icon} />\n'
              '              </svg>\n'
              '              {item.label}\n'
              '            </a>\n'
              '          ); })()}')
    if OLD_SC in src:
        src = src.replace(OLD_SC, NEW_SC, 1)
        with open(SL, "w", encoding="utf-8") as f:
            f.write(src)
        print("  OK system-logs: patched (multi-line svg)")
    else:
        # パターンが合わない場合、全体を正規表現的に探してINFOだけ出す
        idx = src.find("SIDEBAR_ITEMS.map")
        print("  INFO system-logs exact pattern:", repr(src[idx:idx+300]))
else:
    print("  SKIP system-logs: SIDEBAR_ITEMS.map not found")

# pdf-editor
PE = f"{WEB}/app/admin/pdf-editor/page.tsx"
with open(PE, "r", encoding="utf-8") as f:
    src = f.read()

if "filter(i => i.href" in src:
    print("  OK pdf-editor: already patched")
elif 'SIDEBAR_ITEMS.map(item => (' in src:
    # backtick版で改行あり (settings と同じパターン)
    OLD_BT = ('          {SIDEBAR_ITEMS.map(item => (\n'
              '            <a key={item.href} href={item.href}\n'
              '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
              '                pathname === item.href\n'
              '                  ?\n')
    if OLD_BT in src:
        idx = src.find(OLD_BT)
        end_idx = src.find('          ))}\n', idx) + len('          ))}')
        old_block = src[idx:end_idx]
        print("  INFO pdf-editor old block:", repr(old_block[:200]))
    # 実際のaside全体を直接置換する（asideの中身全部）
    OLD_ASIDE = ('        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">\n'
                 '          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>\n'
                 '          {SIDEBAR_ITEMS.map(item => (\n'
                 '            <a key={item.href} href={item.href}\n'
                 '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
                 '                pathname === item.href\n'
                 '                  ? "bg-sky-50 text-sky-700 font-bold border border-sky-200"\n'
                 '                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
                 '              }`}>\n'
                 '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
                 '                <path d={item.icon}/>\n'
                 '              </svg>\n'
                 '              {item.label}\n'
                 '            </a>\n'
                 '          ))}\n'
                 '        </aside>')
    NEW_ASIDE = ('        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">\n'
                 '          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>\n'
                 '          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (\n'
                 '            <a key={item.href} href={item.href}\n'
                 '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
                 '                pathname === item.href\n'
                 '                  ? "bg-sky-50 text-sky-700 font-bold border border-sky-200"\n'
                 '                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
                 '              }`}>\n'
                 '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
                 '                <path d={item.icon}/>\n'
                 '              </svg>\n'
                 '              {item.label}\n'
                 '            </a>\n'
                 '          ))}\n'
                 '          <div className="mx-3 my-1 border-t border-slate-200" />\n'
                 '          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (\n'
                 '            <a key={item.href} href={item.href}\n'
                 '              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${\n'
                 '                pathname === item.href\n'
                 '                  ? "bg-sky-50 text-sky-700 font-bold border border-sky-200"\n'
                 '                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"\n'
                 '              }`}>\n'
                 '              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">\n'
                 '                <path d={item.icon}/>\n'
                 '              </svg>\n'
                 '              {item.label}\n'
                 '            </a>\n'
                 '          ); })()}\n'
                 '        </aside>')
    if OLD_ASIDE in src:
        src = src.replace(OLD_ASIDE, NEW_ASIDE, 1)
        with open(PE, "w", encoding="utf-8") as f:
            f.write(src)
        print("  OK pdf-editor: patched")
    else:
        idx = src.find("SIDEBAR_ITEMS.map")
        print("  INFO pdf-editor exact pattern:", repr(src[idx:idx+400]))

# ══════════════════════════════════════════
# 6. mc.service.ts getTimecardsByDate がまだ旧版なら再度修正
#    (nest buildがキャッシュで古いコードを使っている場合に備えて強制上書き)
# ══════════════════════════════════════════
SVC = f"{API}/src/mc/mc.service.ts"
with open(SVC, "r", encoding="utf-8") as f:
    src = f.read()

# 新版が入っているか確認
if "fmtTime = (d: Date)" in src:
    print("  OK mc.service.ts: getTimecardsByDate already new version")
else:
    print("  INFO mc.service.ts: old version detected, applying patch")
    OLD_BYDATE = ('  async getTimecardsByDate(workDate: string) {\n'
                  '    return this.prisma.machineTimecard.findMany({\n'
                  '      where:   { workDate: new Date(workDate) },\n'
                  '      orderBy: [{ machineId: \'asc\' }, { startTime: \'asc\' }],\n'
                  '      include: {\n'
                  '        operator: { select: { name: true } },\n'
                  '        machine:  { select: { machineCode: true, machineName: true } },\n'
                  '      },\n'
                  '    });\n'
                  '  }')
    NEW_BYDATE = ('  async getTimecardsByDate(workDate: string) {\n'
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
                  '    const fmtDate = (d: Date) => `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,\'0\')}-${String(d.getUTCDate()).padStart(2,\'0\')}`;\n'
                  '    return rows.map(r => ({\n'
                  '      id:         r.id,\n'
                  '      machine_id: r.machineId,\n'
                  '      work_date:  fmtDate(r.workDate),\n'
                  '      start_time: fmtTime(r.startTime),\n'
                  '      end_time:   fmtTime(r.endTime),\n'
                  '      note:       r.note,\n'
                  '      machine:    r.machine,\n'
                  '      operator:   r.operator,\n'
                  '    }));\n'
                  '  }')
    OLD_TC = ('  async getTimecards(machineId: number, workDate: string) {\n'
              '    return this.prisma.machineTimecard.findMany({\n'
              '      where:   { machineId, workDate: new Date(workDate) },\n'
              '      orderBy: { startTime: \'asc\' },\n'
              '      include: { operator: { select: { name: true } } },\n'
              '    });\n'
              '  }')
    NEW_TC = ('  async getTimecards(machineId: number, workDate: string) {\n'
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
              '  }')
    changed = False
    if OLD_BYDATE in src:
        src = src.replace(OLD_BYDATE, NEW_BYDATE, 1); changed = True
        print("  OK mc.service.ts: getTimecardsByDate patched")
    if OLD_TC in src:
        src = src.replace(OLD_TC, NEW_TC, 1); changed = True
        print("  OK mc.service.ts: getTimecards patched")
    if changed:
        with open(SVC, "w", encoding="utf-8") as f:
            f.write(src)
    else:
        print("  INFO: could not match old patterns, manual check needed")

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
    "fix: sidebar divider sl/pe, timecard snake_case force, seed all past timecards, fix wrong start_time"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
