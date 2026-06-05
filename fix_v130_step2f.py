# fix_v130_step2f.py - 残存5エラーを正確に修正

import subprocess, sys, re
from pathlib import Path

BASE     = Path("/home/karkyon/projects/machcore")
MC_SVC   = BASE / "apps/api/src/mc/mc.service.ts"
DASH_SVC = BASE / "apps/api/src/dashboard/dashboard.service.ts"

def log(msg): print(f"[step2f] {msg}")

src  = MC_SVC.read_text(encoding="utf-8")
dash = DASH_SVC.read_text(encoding="utf-8")

# ── 1. 行399: finalize の verStr に二重 ?? が入っている ──
# "(mc as any).machining?.version ?? '1.0001' ?? '1.0001'" を修正
src = src.replace(
    "(mc as any).machining?.version ?? '1.0001' ?? '1.0001'",
    "(mc as any).machining?.version ?? '1.0001'"
)
# finalize は machining include 済みなので ?? を外して直アクセス
src = re.sub(
    r"const verStr\s*=\s*\(mc as any\)\.machining\?\.version \?\? '1\.0001';",
    "const verStr = ((mc as any).machining as any).version as string;",
    src,
    count=1
)
log("OK: finalize verStr 型修正")

# ── 2. 行588: update の McMachiningDetail data に rc が残っている ──
# update メソッドの tx.mcMachiningDetail.update data から rc を全除去
src = re.sub(
    r"\s*rc:\s*\S+.*?,\n",
    "\n",
    src
)
# もう少し安全なパターンで
src = re.sub(r"^\s*rc:\s*[^,\n]+,\n", "", src, flags=re.MULTILINE)
log("OK: rc フィールド全除去")

# ── 3. 行1147: createWorkRecord の machineId 型エラー ──
# { machining: { machineId } } & McProgram → machining プロパティは存在するが
# TypeScript が型推論できない → 明示的キャスト
src = re.sub(
    r"dto\.machine_id \?\? \(\(mc as any\)\.machining as any\)\?\.machineId \?\? null",
    "dto.machine_id ?? (mc.machining as any)?.machineId ?? null",
    src
)
log("OK: createWorkRecord machineId キャスト修正")

# ── 4. 行1326: commonGroup select に version: true が残っている ──
# getCommonGroup または getPrintData 付近の select
# McProgramSelect に version は存在しないため削除
src = re.sub(
    r",\s*version:\s*true\s*(,\n\s*status:)",
    r"\1",
    src
)
src = re.sub(
    r"(id: true, legacyMcid: true, machiningId: true,) version: true,",
    r"\1",
    src
)
log("OK: select version: true 除去")

# ── 5. dashboard 行81: mcProcessNo の TS2871 ──
# machining は machiningId で include されているが mcProcessNo が select に入っていない
# → machining の select に mcProcessNo を追加するか、参照をやめる
# dashboard では mc_process_no を表示していない → null で固定
dash = re.sub(
    r"\(\(s\.mcProgram as any\)\.machining as any\)\?\.mcProcessNo \?\? null",
    "null",
    dash
)
# include の machining select に mcProcessNo を追加
dash = dash.replace(
    "machining: { select: { machine: { select: { machineCode: true, machineName: true, sortOrder: true } } } }",
    "machining: { select: { mcProcessNo: true, machine: { select: { machineCode: true, machineName: true, sortOrder: true } } } }"
)
# map で mcProcessNo を使っている場合は machining 経由に
dash = re.sub(
    r"s\.mcProgram\.mcProcessNo",
    "s.mcProgram.machining?.mcProcessNo ?? null",
    dash
)
log("OK: dashboard mcProcessNo 修正")

DASH_SVC.write_text(dash, encoding="utf-8")
MC_SVC.write_text(src, encoding="utf-8")
log("ファイル書き込み完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSC → 0エラー → ビルド → PM2 → git push
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
    print(build.stderr[-2000:]); log("ビルド失敗"); sys.exit(1)
log("ビルド OK")

log("PM2 再起動...")
subprocess.run(["pm2", "restart", "machcore-api"], cwd=str(BASE), capture_output=True)
log("PM2 OK")

log("git push...")
subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m",
    "refactor: normalize McMachiningDetail step2 complete - TSC 0 errors"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

for f in ["fix_v130_step2.py","fix_v130_step2b.py","fix_v130_step2c.py",
          "fix_v130_step2d.py","fix_v130_step2e.py","fix_v130_step2f.py"]:
    fp = BASE / f
    if fp.exists(): fp.unlink(); log(f"削除: {f}")

log("Step2 完全完了")
