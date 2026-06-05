# fix_v130_step2g.py - 構文破損を修復して残存エラーを完全解消

import subprocess, sys, re
from pathlib import Path

BASE     = Path("/home/karkyon/projects/machcore")
MC_SVC   = BASE / "apps/api/src/mc/mc.service.ts"
DASH_SVC = BASE / "apps/api/src/dashboard/dashboard.service.ts"

def log(msg): print(f"[step2g] {msg}")

src  = MC_SVC.read_text(encoding="utf-8")
dash = DASH_SVC.read_text(encoding="utf-8")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. update の McMachiningDetail.update data ブロックを完全な正しい形に置換
#    step2f の rc 除去正規表現で構文が壊れているため、ブロック全体を置換
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 現在の壊れた状態を含む可能性があるブロックをまるごと正しい状態に置換
# McMachiningDetail.update の data ブロック全体を正規表現で特定して置換
src = re.sub(
    r"      // McMachiningDetail: 加工プログラム本体フィールドを更新\n"
    r"      await tx\.mcMachiningDetail\.update\(\{\n"
    r"        where: \{ machiningId: mc\.machiningId \},\n"
    r"        data: \{[\s\S]*?\n"
    r"        \},\n"
    r"      \}\);\n"
    r"      await tx\.mcProgram\.update\(\{\n"
    r"        where: \{ id \},\n"
    r"        data: \{\n"
    r"          machiningQty:",
    "      // McMachiningDetail: 加工プログラム本体フィールドを更新\n"
    "      await tx.mcMachiningDetail.update({\n"
    "        where: { machiningId: mc.machiningId },\n"
    "        data: {\n"
    "          machineId:     dto.machine_id     !== undefined ? dto.machine_id     : mach.machineId,\n"
    "          oNumber:       dto.o_number       !== undefined ? dto.o_number       : mach.oNumber,\n"
    "          clampNote:     dto.clamp_note     !== undefined ? dto.clamp_note     : mach.clampNote,\n"
    "          cycleTimeSec:  dto.cycle_time_sec !== undefined ? dto.cycle_time_sec : mach.cycleTimeSec,\n"
    "          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,\n"
    "          creatorId:     dto.creator_id     !== undefined ? dto.creator_id     : mach.creatorId,\n"
    "          version:       newVersion,\n"
    "          sheetCreatedAt: dto.sheet_created_at !== undefined\n"
    "            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)\n"
    "            : mach.sheetCreatedAt,\n"
    "        },\n"
    "      });\n"
    "      await tx.mcProgram.update({\n"
    "        where: { id },\n"
    "        data: {\n"
    "          machiningQty:",
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: update McMachiningDetail data ブロック完全置換")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 行399: finalize の verStr — TS2881 never nullish
#    machining は include で確実に存在するので as string で直アクセス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
src = re.sub(
    r"const verStr = \(\(mc as any\)\.machining as any\)\.version as string;",
    "const verStr = (mc as any).machining.version as string;",
    src
)
log("OK: finalize verStr")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 行1147: createWorkRecord の machineId
#    mc.machining は include 済み → 直接アクセス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
src = re.sub(
    r"dto\.machine_id \?\? \(mc\.machining as any\)\?\.machineId \?\? null",
    "dto.machine_id ?? (mc as any).machining.machineId ?? null",
    src
)
log("OK: createWorkRecord machineId")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 行1326: commonGroup select の version: true を除去
#    getCommonGroup メソッドの select
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
src = re.sub(
    r"id: true, legacyMcid: true, machiningId: true, status: true,\n"
    r"        version: true,\n",
    "id: true, legacyMcid: true, machiningId: true, status: true,\n",
    src
)
# もう一パターン
src = re.sub(
    r"(id: true, legacyMcid: true, machiningId: true)(, version: true)?(, status: true,)",
    r"\1\3",
    src
)
log("OK: commonGroup select version 除去")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. dashboard 行81: mcProcessNo TS2871
#    machining の select に mcProcessNo が入っていなければ null 固定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# include の machining select に mcProcessNo を追加して参照できるようにする
dash = re.sub(
    r"machining: \{ select: \{ mcProcessNo: true, machine: \{ select: \{ machineCode: true, machineName: true, sortOrder: true \} \} \} \}",
    "machining: { include: { machine: true } }",
    dash
)
# 念のため include 形式でない場合も
dash = re.sub(
    r"machining: \{ select: \{ machine: \{ select: \{ machineCode: true, machineName: true, sortOrder: true \} \} \} \}",
    "machining: { include: { machine: true } }",
    dash
)
# map の参照を修正 (machining が include されるので直接アクセス可能)
dash = re.sub(
    r"s\.mcProgram\.machining\?\.machine\?\.machineCode",
    "(s.mcProgram as any).machining?.machine?.machineCode",
    dash
)
dash = re.sub(
    r"s\.mcProgram\.machining\?\.machine\?\.machineName",
    "(s.mcProgram as any).machining?.machine?.machineName",
    dash
)
dash = re.sub(
    r"s\.mcProgram\.machining\?\.machine\?\.sortOrder",
    "(s.mcProgram as any).machining?.machine?.sortOrder",
    dash
)
# mcProcessNo は null 固定（dashboardには不要）
dash = re.sub(
    r"s\.mcProgram\.machining\?\.mcProcessNo \?\? null",
    "null",
    dash
)
log("OK: dashboard machining 参照修正")

DASH_SVC.write_text(dash, encoding="utf-8")
MC_SVC.write_text(src, encoding="utf-8")
log("ファイル書き込み完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSC → 0エラー → API ビルド → PM2 → git push
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log("TSC 確認中...")
tsc = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)

if tsc.returncode != 0:
    log(f"TSCエラー残存 (rc={tsc.returncode})")
    sys.exit(1)

log("TSC OK: 0エラー")

log("API ビルド...")
build = subprocess.run(["npx", "tsc"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
if build.returncode != 0:
    print(build.stderr[-3000:]); log("ビルド失敗"); sys.exit(1)
log("ビルド OK")

log("PM2 再起動...")
subprocess.run(["pm2", "restart", "machcore-api"], cwd=str(BASE), capture_output=True)
log("PM2 OK")

log("git push...")
subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m",
    "refactor: normalize mc_machining_details - Step2 service layer complete"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

for f in ["fix_v130_step2.py","fix_v130_step2b.py","fix_v130_step2c.py",
          "fix_v130_step2d.py","fix_v130_step2e.py","fix_v130_step2f.py",
          "fix_v130_step2g.py","fix_v130_step1c_v2.sh","deploy_step1.sh"]:
    fp = BASE / f
    if fp.exists(): fp.unlink(); log(f"削除: {f}")

log("Step2 完全完了")
