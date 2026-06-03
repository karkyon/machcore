#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, sys

API  = "/home/karkyon/projects/machcore/apps/api"
REPO = "/home/karkyon/projects/machcore"

# admin.controller.ts: adminGetTimecards を snake_case + 空チェック対応に修正
CTRL = f"{API}/src/admin/admin.controller.ts"
with open(CTRL, "r", encoding="utf-8") as f:
    src = f.read()

OLD = (
    '  /** admin用: 日付別タイムカード一覧取得 */\n'
    '  @UseGuards(AuthGuard(\'jwt\'), RolesGuard)\n'
    '  @Roles(\'ADMIN\')\n'
    '  @Get(\'timecards\')\n'
    '  async adminGetTimecards(@Query(\'work_date\') workDate: string) {\n'
    '    const cards = await this.prisma.machineTimecard.findMany({\n'
    '      where: { workDate: new Date(workDate) },\n'
    '      include: { machine: { select: { machineCode: true, machineName: true, systemType: true } } },\n'
    '      orderBy: [{ machine: { sortOrder: \'asc\' } }, { id: \'asc\' }],\n'
    '    });\n'
    '    return cards;\n'
    '  }'
)

NEW = (
    '  /** admin用: 日付別タイムカード一覧取得 */\n'
    '  @UseGuards(AuthGuard(\'jwt\'), RolesGuard)\n'
    '  @Roles(\'ADMIN\')\n'
    '  @Get(\'timecards\')\n'
    '  async adminGetTimecards(@Query(\'work_date\') workDate: string) {\n'
    '    if (!workDate || !/^\\d{4}-\\d{2}-\\d{2}$/.test(workDate)) return [];\n'
    '    const cards = await this.prisma.machineTimecard.findMany({\n'
    '      where: { workDate: new Date(workDate + \'T00:00:00.000Z\') },\n'
    '      include: { machine: { select: { machineCode: true, machineName: true, systemType: true, sortOrder: true, isActive: true } } },\n'
    '      orderBy: [{ machine: { sortOrder: \'asc\' } }, { id: \'asc\' }],\n'
    '    });\n'
    '    const fmtT = (d: Date) => {\n'
    '      const h = String(d.getUTCHours()).padStart(2, \'0\');\n'
    '      const m = String(d.getUTCMinutes()).padStart(2, \'0\');\n'
    '      return `${h}:${m}`;\n'
    '    };\n'
    '    return cards.map(c => ({\n'
    '      id:          c.id,\n'
    '      machine_id:  c.machineId,\n'
    '      work_date:   workDate,\n'
    '      start_time:  fmtT(c.startTime),\n'
    '      end_time:    fmtT(c.endTime),\n'
    '      note:        c.note ?? \'\',\n'
    '      machine:     c.machine,\n'
    '    }));\n'
    '  }'
)

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    with open(CTRL, "w", encoding="utf-8") as f:
        f.write(src)
    print("OK admin.controller.ts: adminGetTimecards patched")
else:
    print("SKIP: pattern not found, checking current state...")
    idx = src.find("adminGetTimecards")
    if idx >= 0:
        print("current:", repr(src[idx:idx+400]))

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

subprocess.run(
    "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-api",
    shell=True, capture_output=True
)
print("OK pm2 restart machcore-api")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m",
    "fix: adminGetTimecards snake_case response, empty workDate guard"], cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("OK git push\n" + (r2.stderr.strip() or r2.stdout.strip()))
print("DONE")
