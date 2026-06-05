# fix_v130_step2h.py
# バックアップから update メソッドの正しい構造を確認し、
# 正規化後の正しい形に完全書き直す

import subprocess, sys, re
from pathlib import Path

BASE     = Path("/home/karkyon/projects/machcore")
MC_SVC   = BASE / "apps/api/src/mc/mc.service.ts"

def log(msg): print(f"[step2h] {msg}")

src = MC_SVC.read_text(encoding="utf-8")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# update メソッド全体を正規化後の正しい形に置換
# step2f の rc 除去正規表現が `\n` を含むフィールド行を壊した
# → McMachiningDetail.update data ブロックを完全な形で再書き込み
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UPDATE_METHOD_OLD = re.compile(
    r"  // ══.*?MC-05: 更新.*?\n"
    r"  async update\(id: number, dto: UpdateMcDto, operatorId: number\) \{.*?"
    r"  \}(?=\n\n  // ══)",
    re.DOTALL
)

UPDATE_METHOD_NEW = """\
  // ══════════════════════════════════════════
  // MC-05: 更新
  // ══════════════════════════════════════════
  async update(id: number, dto: UpdateMcDto, operatorId: number) {
    const mc = await this.prisma.mcProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!mc) throw new NotFoundException(`MC_id ${id} が存在しません`);
    const mach = (mc as any).machining ?? {};

    // version はバージョンインクリしない（finalize で行う）
    const verStr   = mach.version ?? '1.0001';
    const verFloat = parseFloat(verStr) || 1.0001;
    const newVer1  = Math.floor(verFloat);
    const newVer2  = Math.round((verFloat - newVer1) * 10000);
    const newVersion = `${newVer1}.${String(newVer2).padStart(4, '0')}`;

    return this.prisma.$transaction(async (tx) => {
      // McMachiningDetail: 加工プログラム本体フィールドを更新
      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data: {
          machineId:      dto.machine_id      !== undefined ? dto.machine_id      : mach.machineId,
          oNumber:        dto.o_number        !== undefined ? dto.o_number        : mach.oNumber,
          clampNote:      dto.clamp_note      !== undefined ? dto.clamp_note      : mach.clampNote,
          cycleTimeSec:   dto.cycle_time_sec  !== undefined ? dto.cycle_time_sec  : mach.cycleTimeSec,
          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,
          creatorId:      dto.creator_id      !== undefined ? dto.creator_id      : mach.creatorId,
          version:        newVersion,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : mach.sheetCreatedAt,
        },
      });
      // McProgram: 部品固有フィールドを更新
      await tx.mcProgram.update({
        where: { id },
        data: {
          machiningQty: dto.machining_qty !== undefined ? dto.machining_qty : mc.machiningQty,
          note:         dto.note         !== undefined ? dto.note         : mc.note,
          status:       'CHANGING',
        },
      });
      // 変更履歴はfinalize()で登録するためupdateでは登録しない
      await tx.operationLog.create({
        data: { userId: operatorId, mcProgramId: id, actionType: 'MC_EDIT_SAVE', metadata: { action: 'update' } },
      });
      return { mc_id: id, version: newVersion, message: '更新しました' };
    });
  }"""

m = UPDATE_METHOD_OLD.search(src)
if m:
    src = src[:m.start()] + UPDATE_METHOD_NEW + src[m.end():]
    log("OK: update メソッド完全置換")
else:
    log("WARN: update メソッドパターン不一致 — 部分修正で対応")
    # フォールバック: McMachiningDetail data ブロックのみ置換
    src = re.sub(
        r"(      await tx\.mcMachiningDetail\.update\(\{\n"
        r"        where: \{ machiningId: mc\.machiningId \},\n"
        r"        data: \{)[\s\S]*?(        \},\n"
        r"      \}\);)",
        r"\1\n"
        r"          machineId:      dto.machine_id      !== undefined ? dto.machine_id      : mach.machineId,\n"
        r"          oNumber:        dto.o_number        !== undefined ? dto.o_number        : mach.oNumber,\n"
        r"          clampNote:      dto.clamp_note      !== undefined ? dto.clamp_note      : mach.clampNote,\n"
        r"          cycleTimeSec:   dto.cycle_time_sec  !== undefined ? dto.cycle_time_sec  : mach.cycleTimeSec,\n"
        r"          commonPartCode: dto.common_part_code !== undefined ? dto.common_part_code : mach.commonPartCode,\n"
        r"          creatorId:      dto.creator_id      !== undefined ? dto.creator_id      : mach.creatorId,\n"
        r"          version:        newVersion,\n"
        r"          sheetCreatedAt: dto.sheet_created_at !== undefined\n"
        r"            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)\n"
        r"            : mach.sheetCreatedAt,\n"
        r"\2",
        src,
        count=1,
        flags=re.DOTALL
    )
    log("OK: McMachiningDetail data ブロック部分置換")

MC_SVC.write_text(src, encoding="utf-8")
log("mc.service.ts 書き込み完了")

# TSC確認
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
    "refactor: normalize mc_machining_details Step2 complete - TSC 0 errors"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

for f in BASE.glob("fix_v130_step2*.py"):
    f.unlink(); log(f"削除: {f.name}")
for f in BASE.glob("fix_v130_step2*.sh"):
    f.unlink(); log(f"削除: {f.name}")
log("Step2 完全完了")
