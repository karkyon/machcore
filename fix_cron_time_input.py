#!/usr/bin/env python3
import subprocess, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/admin/settings/page.tsx"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

original = src

# 1) state: cronHour/cronMinute -> cronTime
src = src.replace(
    '  const [cronHour,     setCronHour]     = useState("5");\n  const [cronMinute,   setCronMinute]   = useState("0");',
    '  const [cronTime,     setCronTime]     = useState("05:00");'
)

# 2) useEffect: setCronHour/setCronMinute -> setCronTime
src = src.replace(
    '      setCronHour(get("cron_timecard_hour", "5"));\n      setCronMinute(get("cron_timecard_minute", "0"));',
    '      const h = get("cron_timecard_hour", "5").padStart(2,"0");\n      const m = get("cron_timecard_minute", "0").padStart(2,"0");\n      setCronTime(`${h}:${m}`);'
)

# 3) saveCronSettings: cronHour/cronMinute -> split cronTime
src = src.replace(
    '          { key: "cron_timecard_enabled",  value: String(cronEnabled) },\n          { key: "cron_timecard_hour",     value: cronHour },\n          { key: "cron_timecard_minute",   value: cronMinute },',
    '          { key: "cron_timecard_enabled",  value: String(cronEnabled) },\n          { key: "cron_timecard_hour",     value: cronTime.split(":")[0] },\n          { key: "cron_timecard_minute",   value: cronTime.split(":")[1] },'
)

# 4) JSX: 実行時刻（時）/実行時刻（分）の2カラム -> 1フィールド HH:MM
old_jsx = '''                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">実行時刻（時）</label>
                    <input type="number" min="0" max="23" value={cronHour} onChange={e => setCronHour(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">実行時刻（分）</label>
                    <input type="number" min="0" max="59" value={cronMinute} onChange={e => setCronMinute(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>'''

new_jsx = '''                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">実行時刻（24時間表記）</label>
                    <input type="time" value={cronTime} onChange={e => setCronTime(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
                  </div>
                  <div>'''

src = src.replace(old_jsx, new_jsx)

# 5) 説明テキスト: cronHour:cronMinute -> cronTime
src = src.replace(
    '<p className="text-xs text-slate-400">毎日 {cronHour}:{String(cronMinute).padStart(2,"0")} に有効機械全台のタイムカードを自動生成します（営業カレンダーの休日はスキップ）</p>',
    '<p className="text-xs text-slate-400">毎日 {cronTime} に有効機械全台のタイムカードを自動生成します（営業カレンダーの休日はスキップ）</p>'
)

if src == original:
    print("ERROR: no changes made - pattern mismatch")
    sys.exit(1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)
print("OK settings: cronTime single HH:MM input")

# next build
print("--- next build ---")
r = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && cd /home/karkyon/projects/machcore && npm run build --workspace=apps/web 2>&1",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
out = r.stdout + r.stderr
if "error" in out.lower() and "warn" not in out.lower().replace("error",""):
    # check for actual build error
    if "Build error" in out or "Type error" in out or "SyntaxError" in out:
        print("ERROR next build:")
        print(out[-2000:])
        sys.exit(1)
print("OK next build")

# pm2 restart web
r2 = subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-web 2>&1",
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print("OK pm2 restart machcore-web")

# git push
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && git add -A && git commit -m 'fix: cron settings - single HH:MM time input' && git push 2>&1",
    shell=True, capture_output=True, text=True
)
print(r3.stdout + r3.stderr)
print("DONE")
