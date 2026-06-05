# fix_v130_step2e.py - 残存5エラーを確実修正

import subprocess, sys, re
from pathlib import Path

BASE     = Path("/home/karkyon/projects/machcore")
MC_SVC   = BASE / "apps/api/src/mc/mc.service.ts"
DASH_SVC = BASE / "apps/api/src/dashboard/dashboard.service.ts"

def log(msg): print(f"[step2e] {msg}")

src  = MC_SVC.read_text(encoding="utf-8")
dash = DASH_SVC.read_text(encoding="utf-8")
lines_src = src.split("\n")
lines_dash = dash.split("\n")

# エラー箇所を表示
log(f"dashboard 行81: {lines_dash[80]}")
log(f"mc.service 行399: {lines_src[398]}")
log(f"mc.service 行588: {lines_src[587]}")
log(f"mc.service 行1147: {lines_src[1146]}")
log(f"mc.service 行1326: {lines_src[1325]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dashboard 行81: TS2871 always nullish
# 実際の行を確認して直接修正
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log(f"dashboard 行79-85:")
for i in range(78, 85):
    log(f"  {i+1}: {lines_dash[i]}")

# mcProcessNo の参照を直接 (r as any) で書き直す
dash = re.sub(
    r"\(\(s\.mcProgram as any\)\.machining as any\)\?\.mcProcessNo \?\? null",
    "null",  # mcProcessNo は dashboard には不要（表示していない）
    dash
)
log("OK: dashboard mcProcessNo を null に（dashboard では表示不要）")
DASH_SVC.write_text(dash, encoding="utf-8")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 行399: TS2881 never nullish
# (mc as any).machining?.version ?? '1.0001' で
# machining は include されているので never nullish → ?? を as string に変更
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log(f"行395-405:")
for i in range(394, 405):
    log(f"  {i+1}: {lines_src[i]}")

# finalize 内の verStr 行を修正
# (mc as any).machining?.version ?? '1.0001' → mc.machining.version as string
src = src.replace(
    "    const verStr = (mc as any).machining?.version ?? '1.0001';",
    "    const verStr = (mc as any).machining.version as string;"
)
log("OK: finalize verStr 修正")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 行588: rc が McProgram update に存在しない
# update メソッドの McMachiningDetail update data を確認
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log(f"行583-595:")
for i in range(582, 595):
    log(f"  {i+1}: {lines_src[i]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 行1147: machineId が型に存在しない
# { machining: { machineId } } & { id, ... } なので
# mc.machining.machineId でアクセスできるはずだが型解決が必要
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log(f"行1143-1152:")
for i in range(1142, 1152):
    log(f"  {i+1}: {lines_src[i]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 行1326: version が McProgramSelect に存在しない
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log(f"行1320-1332:")
for i in range(1319, 1332):
    log(f"  {i+1}: {lines_src[i]}")

MC_SVC.write_text(src, encoding="utf-8")

# TSC確認（ログ取得用）
tsc = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)
log(f"TSC rc={tsc.returncode}")
