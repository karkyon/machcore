#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

WEB  = "/home/karkyon/projects/machcore/apps/web"
API  = "/home/karkyon/projects/machcore/apps/api"
REPO = "/home/karkyon/projects/machcore"

def patch(path, fixes, label):
    if not os.path.exists(path):
        print(f"  WARNING  {label}: not found"); return
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    orig = src
    for old, new, name in fixes:
        if old in src:
            src = src.replace(old, new, 1)
            print(f"  OK [{label}] {name}")
        else:
            print(f"  SKIP [{label}] {name}: pattern not found")
    if src != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)

OLD_MAP_BT = '''          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}'''

NEW_MAP_BT = '''          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ); })()}'''

OLD_MAP_SC = '''          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
              {item.label}
            </a>
          ))}'''

NEW_MAP_SC = '''          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor").map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {(() => { const item = SIDEBAR_ITEMS.find(i => i.href === "/admin/pdf-editor")!; return (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
              {item.label}
            </a>
          ); })()}'''

FILES_BT = [
    f"{WEB}/app/admin/users/page.tsx",
    f"{WEB}/app/admin/machines/page.tsx",
    f"{WEB}/app/mc/timecards/page.tsx",
    f"{WEB}/app/admin/settings/page.tsx",
    f"{WEB}/app/admin/raw/page.tsx",
    f"{WEB}/app/admin/pdf-editor/page.tsx",
    f"{WEB}/app/admin/system-logs/page.tsx",
]
FILES_SC = [
    f"{WEB}/app/admin/calendar/page.tsx",
]

for fpath in FILES_BT + FILES_SC:
    name = fpath.split("/")[-2]
    if not os.path.exists(fpath):
        print(f"  WARNING {name}: not found"); continue
    with open(fpath, "r", encoding="utf-8") as f:
        src = f.read()
    if "filter(i => i.href" in src:
        print(f"  OK [sidebar] {name}: already patched"); continue
    old = OLD_MAP_BT if fpath in FILES_BT else OLD_MAP_SC
    new = NEW_MAP_BT if fpath in FILES_BT else NEW_MAP_SC
    if old in src:
        src = src.replace(old, new, 1)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"  OK [sidebar] {name}")
    else:
        print(f"  SKIP [sidebar] {name}: pattern not found")

# calendar fit
CAL = f"{WEB}/app/admin/calendar/page.tsx"
patch(CAL, [
    (
        '<main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">',
        '<main className="flex-1 overflow-hidden flex flex-col p-4 gap-2">',
        "main: overflow-y-auto->hidden, p5->p4 gap-3->gap-2"
    ),
    (
        '          <div className="space-y-4">',
        '          <div className="flex flex-col gap-2 min-h-0 flex-1">',
        "wrapper: space-y-4 -> flex col"
    ),
    (
        '<div className="bg-white rounded-xl border border-slate-200 p-4">\n              <div className="flex items-center justify-between mb-4">',
        '<div className="bg-white rounded-xl border border-slate-200 p-2">\n              <div className="flex items-center justify-between mb-1">',
        "calendar card p4->p2 mb-4->mb-1"
    ),
    (
        '<div className="grid grid-cols-7 gap-1 mb-2">',
        '<div className="grid grid-cols-7 gap-0.5 mb-1">',
        "dow header gap-1->0.5"
    ),
    (
        '<div className="grid grid-cols-7 gap-1">',
        '<div className="grid grid-cols-7 gap-0.5">',
        "cell grid gap-1->0.5"
    ),
    (
        '"relative aspect-square rounded-lg flex flex-col items-center justify-center text-sm font-bold transition-colors border "',
        '"relative h-12 rounded flex flex-col items-center justify-center text-xs font-bold transition-colors border "',
        "cell: aspect-square->h-12 text-sm->text-xs"
    ),
], "calendar")

# mc.service.ts: initTimecards + cron reschedule
SVC = f"{API}/src/mc/mc.service.ts"
patch(SVC, [
    (
        '''    const created: number[] = [];
    for (const m of machines) {
      try {
        const tc = await this.prisma.machineTimecard.upsert({
          where: {
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-ignore — Prisma generates compound unique key after migration
            machine_timecards_machine_id_work_date_key: { machineId: m.id, workDate: new Date(workDate) },
          },
          update: {}, // 既存レコードは更新しない
          create: {
            machineId:  m.id,
            operatorId,
            workDate:   new Date(workDate),
            startTime:  new Date(`${workDate}T08:00:00`),
            endTime:    new Date(`${workDate}T17:00:00`),
          },
        });
        created.push(tc.id);
      } catch {
        // UNIQUE制約違反（既存あり）は無視
      }
    }
    return { created: created.length, message: `処理完了` };''',
        '''    const created: number[] = [];
    for (const m of machines) {
      const exists = await this.prisma.machineTimecard.findFirst({
        where: { machineId: m.id, workDate: new Date(workDate) },
        select: { id: true },
      });
      if (exists) continue;
      const tc = await this.prisma.machineTimecard.create({
        data: {
          machineId:  m.id,
          operatorId,
          workDate:   new Date(workDate),
          startTime:  new Date(`${workDate}T08:00:00`),
          endTime:    new Date(`${workDate}T17:00:00`),
        },
      });
      created.push(tc.id);
    }
    return { created: created.length, message: `処理完了` };''',
        "initTimecards: upsert->findFirst+create"
    ),
], "mc.service.ts")

with open(SVC, "r", encoding="utf-8") as f:
    src = f.read()
OLD_CRON = '''      } catch (e: any) {
        this.logger.error('CRON', `機械タイムカード自動生成 失敗: ${workDate}`, { error: e?.message ?? String(e) });
      }
    }, ms);'''
NEW_CRON = '''      } catch (e: any) {
        this.logger.error('CRON', `機械タイムカード自動生成 失敗: ${workDate}`, { error: e?.message ?? String(e) });
      } finally {
        // reschedule next day
        this.scheduleCronTimecards(hour, minute);
      }
    }, ms);'''
if OLD_CRON in src:
    src = src.replace(OLD_CRON, NEW_CRON, 1)
    with open(SVC, "w", encoding="utf-8") as f:
        f.write(src)
    print("  OK [mc.service.ts] cron finally reschedule added")
elif "scheduleCronTimecards(hour, minute)" in src and "finally" in src:
    print("  OK [mc.service.ts] cron reschedule already present")
else:
    print("  SKIP [mc.service.ts] cron reschedule: pattern not found")

# seed script (pure ASCII strings, no Japanese in triple-quotes)
SEED = f"{REPO}/seed_timecards_v2.py"
seed_lines = [
    "#!/usr/bin/env python3",
    "# -*- coding: utf-8 -*-",
    "import subprocess, sys, datetime",
    "",
    "START = datetime.date(2026, 4, 1)",
    "TODAY = datetime.date.today()",
    "PSQL = ['docker','exec','-i','machcore-postgres','psql','-U','machcore','-d','machcore_dev','-t','-A']",
    "",
    "def sql(q):",
    "    r = subprocess.run(PSQL, input=q.encode(), capture_output=True)",
    "    return r.stdout.decode().strip()",
    "",
    "machines_raw = sql('SELECT id FROM machines WHERE is_active = true ORDER BY sort_order;')",
    "machine_ids = [int(x) for x in machines_raw.split('\\n') if x.strip()]",
    "print('machines:', len(machine_ids), machine_ids)",
    "",
    "holidays_raw = sql('SELECT work_date::text FROM business_calendars WHERE is_holiday = true;')",
    "holidays = set(x.strip() for x in holidays_raw.split('\\n') if x.strip())",
    "print('holidays:', len(holidays))",
    "",
    "existing_raw = sql(\"SELECT machine_id, work_date::text FROM machine_timecards WHERE work_date >= '2026-04-01' AND work_date <= '\" + str(TODAY) + \"';\")",
    "existing = set()",
    "for line in existing_raw.split('\\n'):",
    "    if '|' in line:",
    "        mid, wd = line.split('|')",
    "        existing.add((int(mid.strip()), wd.strip()[:10]))",
    "print('existing records:', len(existing))",
    "",
    "cur = START",
    "vals = []",
    "skipped = 0",
    "while cur <= TODAY:",
    "    ds = cur.isoformat()",
    "    if cur.weekday() >= 5 or ds in holidays:",
    "        skipped += 1",
    "        cur += datetime.timedelta(days=1)",
    "        continue",
    "    for mid in machine_ids:",
    "        if (mid, ds) not in existing:",
    "            vals.append(\"(\" + str(mid) + \", 1, '\" + ds + \"', '08:00:00', '17:00:00')\")",
    "    cur += datetime.timedelta(days=1)",
    "",
    "print('skipped days:', skipped, '  rows to insert:', len(vals))",
    "if not vals:",
    "    print('nothing to insert')",
    "    sys.exit(0)",
    "",
    "batch = 100",
    "total = 0",
    "for i in range(0, len(vals), batch):",
    "    chunk = vals[i:i+batch]",
    "    q = 'INSERT INTO machine_timecards (machine_id, operator_id, work_date, start_time, end_time) VALUES ' + ','.join(chunk) + ' ON CONFLICT DO NOTHING;'",
    "    r = subprocess.run(PSQL, input=q.encode(), capture_output=True)",
    "    if r.returncode != 0:",
    "        print('ERROR:', r.stderr.decode())",
    "        sys.exit(1)",
    "    total += len(chunk)",
    "    print('inserted:', i+1, '-', min(i+batch, len(vals)))",
    "",
    "print('DONE:', total, 'rows inserted')",
]
with open(SEED, "w", encoding="utf-8") as f:
    f.write("\n".join(seed_lines) + "\n")
print("  OK seed_timecards_v2.py generated")

# API tsc
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

print("\n--- seed past timecards ---")
r = subprocess.run(["python3", SEED], capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print("ERROR seed:\n" + r.stderr[-1000:])

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m",
    "fix: sidebar divider, calendar fit-screen, initTimecards findFirst+create, cron reschedule, seed timecards"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
