#!/usr/bin/env python3
import subprocess, sys, os

ROOT = '/home/karkyon/projects/machcore'

def read(p):
    with open(f'{ROOT}/{p}', encoding='utf-8') as f: return f.read()
def write(p, c):
    with open(f'{ROOT}/{p}', 'w', encoding='utf-8') as f: f.write(c)
def bash(cmd, cwd=None):
    return subprocess.run(['/bin/bash','-c',f'. "$NVM_DIR/nvm.sh" && {cmd}'], cwd=cwd or ROOT, capture_output=True, text=True)

# ── isNew を printBody の前に移動 ──
print('=== PATCH: isNew 宣言位置修正 ===')
path = 'apps/web/app/mc/[mc_id]/print/page.tsx'
content = read(path)
old = '''  const printBody = {
    include_tooling:        includeTooling,
    include_clamp:          includeClamp,
    include_drawings:       includeDrawings,
    include_work_offsets:   includeWorkOffsets,
    include_index_programs: includeIndexPrograms,
    ...(!isNew && repeatConfirmed ? {
      purpose:    repeatPurpose,
      quantity:   repeatPurpose !== 'reference' ? repeatQty : undefined,
      machine_id: repeatPurpose !== 'reference' ? repeatMachineId ?? undefined : undefined,
    } : {}),
  };

  const isNew = nc?.status === "NEW";'''
new = '''  const isNew = nc?.status === "NEW";

  const printBody = {
    include_tooling:        includeTooling,
    include_clamp:          includeClamp,
    include_drawings:       includeDrawings,
    include_work_offsets:   includeWorkOffsets,
    include_index_programs: includeIndexPrograms,
    ...(!isNew && repeatConfirmed ? {
      purpose:    repeatPurpose,
      quantity:   repeatPurpose !== 'reference' ? repeatQty : undefined,
      machine_id: repeatPurpose !== 'reference' ? repeatMachineId ?? undefined : undefined,
    } : {}),
  };'''
if old not in content:
    if new in content: print('  SKIP: 適用済み')
    else: print('  FAIL'); sys.exit(1)
else:
    write(path, content.replace(old, new, 1)); print('  OK')

# ── Prisma Generate ──
print('=== Prisma Generate ===')
r = bash('npx prisma generate', cwd=f'{ROOT}/apps/api')
if r.returncode != 0: print(r.stdout+r.stderr); sys.exit(1)
print('  OK')

# ── API TSC ──
print('=== API TSC ===')
r = bash('npx tsc --noEmit -p tsconfig.json', cwd=f'{ROOT}/apps/api')
if r.returncode != 0: print('ERROR:\n'+(r.stdout+r.stderr)[-3000:]); sys.exit(1)
print('  OK')

# ── WEB TSC ──
print('=== WEB TSC ===')
r = bash('npx tsc --noEmit', cwd=f'{ROOT}/apps/web')
if r.returncode != 0: print('ERROR:\n'+(r.stdout+r.stderr)[-4000:]); sys.exit(1)
print('  OK')

# ── Push ──
print('=== GitHub Push ===')
subprocess.run(['git','add','-A'], cwd=ROOT)
r3 = subprocess.run(['git','commit','-m','feat: リピート段取シート発行前確認UI + 履歴に用途/W数/機械保存'], cwd=ROOT, capture_output=True, text=True)
r4 = subprocess.run(['git','push'], cwd=ROOT, capture_output=True, text=True)
print(r3.stdout.strip() or r3.stderr.strip())
print(r4.stdout.strip() or r4.stderr.strip())

# ── API PM2 ──
bash('pm2 restart machcore-api')
print('API PM2: OK')

# ── Web Build ──
print('=== Next.js Build ===')
r = bash('npx next build', cwd=f'{ROOT}/apps/web')
if r.returncode != 0: print('FAILED:\n'+(r.stdout+r.stderr)[-4000:]); sys.exit(1)
print('  OK')

# ── Web PM2 ──
bash(f'pm2 delete machcore-web 2>/dev/null; pm2 start {ROOT}/ecosystem.config.js --only machcore-web')
print('Web PM2: OK')

# ── 後片付け ──
for f in ['fix_v157.py','fix_v157b.py','fix_v157c.py','fix_v157d.py',
          'build_v157.py','build_v157b.py','build_v157c.py','fix_final.py']:
    p = f'{ROOT}/{f}'
    if os.path.exists(p): os.remove(p); print(f'  削除: {f}')

print('\n✅ 完了')
