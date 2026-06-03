#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess, sys, datetime

START = datetime.date(2026, 4, 1)
TODAY = datetime.date.today()
PSQL = ['docker','exec','-i','machcore-postgres','psql','-U','machcore','-d','machcore_dev','-t','-A']

def sql(q):
    r = subprocess.run(PSQL, input=q.encode(), capture_output=True)
    return r.stdout.decode().strip()

machines_raw = sql('SELECT id FROM machines WHERE is_active = true ORDER BY sort_order;')
machine_ids = [int(x) for x in machines_raw.split('\n') if x.strip()]
print('machines:', len(machine_ids), machine_ids)

holidays_raw = sql('SELECT work_date::text FROM business_calendars WHERE is_holiday = true;')
holidays = set(x.strip() for x in holidays_raw.split('\n') if x.strip())
print('holidays:', len(holidays))

existing_raw = sql("SELECT machine_id, work_date::text FROM machine_timecards WHERE work_date >= '2026-04-01' AND work_date <= '" + str(TODAY) + "';")
existing = set()
for line in existing_raw.split('\n'):
    if '|' in line:
        mid, wd = line.split('|')
        existing.add((int(mid.strip()), wd.strip()[:10]))
print('existing records:', len(existing))

cur = START
vals = []
skipped = 0
while cur <= TODAY:
    ds = cur.isoformat()
    if cur.weekday() >= 5 or ds in holidays:
        skipped += 1
        cur += datetime.timedelta(days=1)
        continue
    for mid in machine_ids:
        if (mid, ds) not in existing:
            vals.append("(" + str(mid) + ", 1, '" + ds + "', '08:00:00', '17:00:00')")
    cur += datetime.timedelta(days=1)

print('skipped days:', skipped, '  rows to insert:', len(vals))
if not vals:
    print('nothing to insert')
    sys.exit(0)

batch = 100
total = 0
for i in range(0, len(vals), batch):
    chunk = vals[i:i+batch]
    q = 'INSERT INTO machine_timecards (machine_id, operator_id, work_date, start_time, end_time) VALUES ' + ','.join(chunk) + ' ON CONFLICT DO NOTHING;'
    r = subprocess.run(PSQL, input=q.encode(), capture_output=True)
    if r.returncode != 0:
        print('ERROR:', r.stderr.decode())
        sys.exit(1)
    total += len(chunk)
    print('inserted:', i+1, '-', min(i+batch, len(vals)))

print('DONE:', total, 'rows inserted')
