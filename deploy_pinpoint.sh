#!/bin/bash
# deploy_pinpoint.sh - サーバーで実行してfix_v130_pinpoint.pyを生成
cat > /home/karkyon/projects/machcore/fix_v130_pinpoint.py << 'PYEOF'
import subprocess, sys, re
from pathlib import Path

BASE    = Path("/home/karkyon/projects/machcore")
MC_SVC  = BASE / "apps/api/src/mc/mc.service.ts"
DASH    = BASE / "apps/api/src/dashboard/dashboard.service.ts"
TSC     = BASE / "apps/api/node_modules/.bin/tsc"

def log(msg): print(f"[pinpoint] {msg}")

src  = MC_SVC.read_text(encoding="utf-8")
dash = DASH.read_text(encoding="utf-8")

# 1. getPrintData commonGroup select: version:true -> machining.version
src = src.replace(
    "      select:  { id: true, version: true, part: { select: { drawingNo: true, name: true } } },",
    "      select:  { id: true, part: { select: { drawingNo: true, name: true } }, machining: { select: { version: true } } },"
)
log("OK: getPrintData commonGroup select")

# 2. create: McProgram.create data から旧マシニングフィールド除去
OLD = (
    "      const mc = await tx.mcProgram.create({\n"
    "        data: {\n"
    "          partId:        dto.part_id,\n"
    "          machiningId:   dto.machining_id,\n"
    "          mcProcessNo:   dto.mc_process_no   ?? null,\n"
    "          fileName:      dto.file_name       ?? null,\n"
    "          machineId:     dto.machine_id     ?? null,\n"
    "          oNumber:       dto.o_number       ?? null,\n"
    "          clampNote:     dto.clamp_note     ?? null,\n"
    "          cycleTimeSec:  dto.cycle_time_sec ?? null,\n"
    "          machiningQty:  dto.machining_qty  ?? 1,\n"
    "          commonPartCode: dto.common_part_code ?? null,\n"
    "          note:          dto.note           ?? null,\n"
    "          legacyMcid:    dto.machining_id,\n"
    "          registeredBy:  operatorId,\n"
    "          status:        'NEW',\n"
    "          version:       '1.0001',\n"
    "        },\n"
    "      });\n"
    "      await tx.mcChangeHistory.create({\n"
    "        data: {\n"
    "          mcProgramId:  mc.id,\n"
    "          changeType:   'NEW_REGISTRATION',\n"
    "          operatorId,\n"
    "          versionAfter: mc.version,"
)
NEW = (
    "      const mc = await tx.mcProgram.create({\n"
    "        data: {\n"
    "          partId:        dto.part_id,\n"
    "          machiningId:   dto.machining_id,\n"
    "          machiningQty:  dto.machining_qty  ?? 1,\n"
    "          note:          dto.note           ?? null,\n"
    "          legacyMcid:    dto.machining_id,\n"
    "          registeredBy:  operatorId,\n"
    "          status:        'NEW',\n"
    "        },\n"
    "      });\n"
    "      await tx.mcChangeHistory.create({\n"
    "        data: {\n"
    "          mcProgramId:  mc.id,\n"
    "          changeType:   'NEW_REGISTRATION',\n"
    "          operatorId,\n"
    "          versionAfter: '1.0001',"
)
if OLD in src:
    src = src.replace(OLD, NEW, 1)
    log("OK: create McProgram.create 旧フィールド除去")
else:
    log("SKIP: create 既に修正済み")

# 3. dashboard mcProcessNo TS2871
dash = re.sub(
    r"\(s\.mcProgram as any\)\.machining\?\.mcProcessNo \?\? null",
    "(s as any).mcProgram?.machining?.mcProcessNo ?? null",
    dash
)
log("OK: dashboard mcProcessNo")

MC_SVC.write_text(src, encoding="utf-8")
DASH.write_text(dash, encoding="utf-8")
log("書き込み完了")

log("TSC確認...")
tsc = subprocess.run([str(TSC), "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)
if tsc.returncode != 0:
    log(f"TSCエラー残存 (rc={tsc.returncode})")
    sys.exit(1)

log("TSC OK: 0エラー")

log("API ビルド...")
build = subprocess.run([str(TSC)],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
if build.returncode != 0:
    print(build.stderr[-3000:]); log("ビルド失敗"); sys.exit(1)
log("ビルド OK")

subprocess.run(["pm2", "restart", "machcore-api"], cwd=str(BASE))
log("PM2 OK")

subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m", "fix: TSC errors normalize mc_machining_details complete"], cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

for f in list(BASE.glob("fix_v130_*.py")) + list(BASE.glob("deploy_*.sh")):
    f.unlink(); log(f"削除: {f.name}")
log("完了")
PYEOF
echo "fix_v130_pinpoint.py 生成完了"
python3 /home/karkyon/projects/machcore/fix_v130_pinpoint.py
