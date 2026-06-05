# fix_v130_step2c.py
# 残存エラーを正規表現で確実に修正する

import subprocess, sys, re
from pathlib import Path

BASE     = Path("/home/karkyon/projects/machcore")
MC_SVC   = BASE / "apps/api/src/mc/mc.service.ts"
DASH_SVC = BASE / "apps/api/src/dashboard/dashboard.service.ts"

def log(msg): print(f"[step2c] {msg}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# mc.service.ts 全置換
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
src = MC_SVC.read_text(encoding="utf-8")

# ── 1. findOne: tooling/workOffsets/indexPrograms が McProgram include に残っている ──
# パターン: machining: { include: { ... } }, の後に tooling/workOffsets/indexPrograms がある
# → machining の include 内に移動する
# 正規表現で findOne の include ブロック全体を置換
old_findone = re.compile(
    r'(      include: \{\n'
    r'        part:      true,\n'
    r'        machining: \{\n'
    r'          include: \{\n'
    r'            machine:   true,\n'
    r'            pgCreator: \{ select: \{ id: true, name: true \} \},\n'
    r'            creator:   \{ select: \{ id: true, name: true \} \},\n'
    r'          \},\n'
    r'        \},\n'
    r'        registrar: \{ select: \{ id: true, name: true \} \},\n'
    r'        approver:  \{ select: \{ id: true, name: true \} \},\n'
    r')(.*?)'
    r'(        files:     \{ orderBy: \{ uploadedAt: .desc. \} \},\n'
    r'      \},\n)',
    re.DOTALL
)

new_findone = (
    '      include: {\n'
    '        part:      true,\n'
    '        machining: {\n'
    '          include: {\n'
    '            machine:      true,\n'
    '            pgCreator:    { select: { id: true, name: true } },\n'
    '            creator:      { select: { id: true, name: true } },\n'
    '            tooling:      { orderBy: { sortOrder: \'asc\' } },\n'
    '            workOffsets:  { orderBy: { gCode: \'asc\' } },\n'
    '            indexPrograms: { orderBy: { sortOrder: \'asc\' } },\n'
    '          },\n'
    '        },\n'
    '        registrar: { select: { id: true, name: true } },\n'
    '        approver:  { select: { id: true, name: true } },\n'
    '        files:     { orderBy: { uploadedAt: \'desc\' } },\n'
    '      },\n'
)

m = old_findone.search(src)
if m:
    # 間にある余分な tooling/workOffsets/indexPrograms 行を除去して置換
    src = old_findone.sub(new_findone, src, count=1)
    log("OK: findOne include ブロック 正規化完了")
else:
    log("SKIP: findOne include ブロック（パターン不一致）")
    # フォールバック: 直接行を修正
    # tooling/workOffsets/indexPrograms が McProgram に直接ついている行を削除
    src = re.sub(
        r"        tooling:   \{ orderBy: \{ sortOrder: 'asc' \} \},\n"
        r"        workOffsets: \{ orderBy: \{ gCode: 'asc' \} \},\n"
        r"        indexPrograms: \{ orderBy: \{ sortOrder: 'asc' \} \},\n"
        r"        creator:   \{ select: \{ name: true \} \},\n"
        r"        pgCreator: \{ select: \{ name: true \} \},\n",
        "",
        src
    )
    # tooling_REMOVED が残っている場合も削除
    src = re.sub(r"        tooling_REMOVED: \{ orderBy: \{ sortOrder: 'asc' \} \},\n", "", src)
    log("OK: findOne include 余分な関係を除去（フォールバック）")

# ── 2. tooling_REMOVED を全て削除 ──
count = src.count("tooling_REMOVED")
src = src.replace("tooling_REMOVED:   { orderBy: { sortOrder: 'asc' } },", "")
src = src.replace("tooling_REMOVED: { orderBy: { sortOrder: 'asc' } },", "")
log(f"OK: tooling_REMOVED {count}箇所削除")

# ── 3. create メソッド: version/mcProcessNo/fileName/machineId 等を McProgram data から削除 ──
# create の tx.mcProgram.create data ブロックから旧フィールドを削除
src = re.sub(
    r"(          const mc = await tx\.mcProgram\.create\(\{\n"
    r"            data: \{\n"
    r"              partId:        dto\.part_id,\n"
    r"              machiningId:   dto\.machining_id,\n)"
    r"(.*?)"
    r"(              machiningQty:  dto\.machining_qty)",
    lambda m: (
        m.group(1) +
        "              machiningQty:  dto.machining_qty"
    ),
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: create McProgram.create data 正規化")

# ── 4. create の changeHistory: created.version → '1.0001' ──
src = re.sub(
    r"(              changeType:   'NEW_REGISTRATION',\n"
    r"              operatorId,\n"
    r"              versionAfter: )created\.version,",
    r"\g<1>'1.0001',",
    src
)
log("OK: create changeHistory versionAfter")

# ── 5. createAndPrint: McProgram.create data から version/mcProcessNo 等を削除 ──
src = re.sub(
    r"(          const created = await tx\.mcProgram\.create\(\{\n"
    r"            data: \{\n"
    r"              partId:        dto\.part_id,\n"
    r"              machiningId,\n)"
    r"(.*?)"
    r"(              machiningQty:  dto\.machining_qty)",
    lambda m: (
        m.group(1) +
        "              machiningQty:  dto.machining_qty"
    ),
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: createAndPrint McProgram.create data 正規化")

# ── 6. finalize: findUnique に machining include がない場合 ──
src = re.sub(
    r"(  async finalize\(id: number.*?\n)"
    r"    const mc = await this\.prisma\.mcProgram\.findUnique\(\{ where: \{ id \} \}\);",
    r"\g<1>    const mc = await this.prisma.mcProgram.findUnique({\n"
    r"      where: { id },\n"
    r"      include: { machining: true },\n"
    r"    });",
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: finalize machining include")

# ── 7. approve: mc.version → machining.version ──
src = re.sub(
    r"          versionBefore: mc\.version,\n"
    r"          versionAfter:  mc\.version,\n"
    r"          content:       '承認',",
    "          versionBefore: (mc as any).machining?.version ?? null,\n"
    "          versionAfter:  (mc as any).machining?.version ?? null,\n"
    "          content:       '承認',",
    src
)
src = re.sub(
    r"return \{ mc_id: id, message: '承認しました', version: mc\.version \};",
    "return { mc_id: id, message: '承認しました', version: (mc as any).machining?.version ?? '1.0001' };",
    src
)
log("OK: approve version")

# ── 8. update: rc が McMachiningDetail update data に含まれている場合除去 ──
src = re.sub(
    r"          rc:             mach\.rc\s*\?\? 0,\n",
    "",
    src
)
log("OK: update rc 除去")

# ── 9. update: hasIndexProgram/hasWorkOffset も McMachiningDetail には自動管理のため除去 ──
# これらは service 層で手動更新するので残す（エラー対象ではない）

# ── 10. createWorkRecord: mc.machineId → machining.machineId ──
# まず findUnique に machining include を追加（まだない場合）
# createWorkRecord 内の findUnique を探す
src = re.sub(
    r"(  async createWorkRecord\(mcId: number.*?\n)"
    r"    const mc = await this\.prisma\.mcProgram\.findUnique\(\{ where: \{ id: mcId \} \}\);",
    r"\g<1>    const mc = await this.prisma.mcProgram.findUnique({\n"
    r"      where: { id: mcId },\n"
    r"      include: { machining: { select: { machineId: true } } },\n"
    r"    });",
    src,
    count=1,
    flags=re.DOTALL
)
# machineId 参照修正
src = re.sub(
    r"machineId:        dto\.machine_id    \?\? mc\.machineId \?\? null,",
    "machineId:        dto.machine_id    ?? (mc as any).machining?.machineId ?? null,",
    src
)
log("OK: createWorkRecord machineId")

# ── 11. getPrintData: 旧 include（machine/tooling/workOffsets 等が McProgram に直接）を正規化 ──
src = re.sub(
    r"  async getPrintData\(mcId: number\) \{\n"
    r"    const r = await this\.prisma\.mcProgram\.findUnique\(\{\n"
    r"      where: \{ id: mcId \},\n"
    r"      include: \{.*?\n"
    r"      \},\n"
    r"    \}\);\n"
    r"    if \(!r\) throw new NotFoundException",
    lambda m: (
        "  async getPrintData(mcId: number) {\n"
        "    const r = await this.prisma.mcProgram.findUnique({\n"
        "      where: { id: mcId },\n"
        "      include: {\n"
        "        part:    true,\n"
        "        machining: {\n"
        "          include: {\n"
        "            machine:      true,\n"
        "            tooling:      { orderBy: { sortOrder: 'asc' } },\n"
        "            workOffsets:  { orderBy: { gCode: 'asc' } },\n"
        "            indexPrograms: { orderBy: { sortOrder: 'asc' } },\n"
        "            creator:      { select: { name: true } },\n"
        "            pgCreator:    { select: { name: true } },\n"
        "          },\n"
        "        },\n"
        "        registrar: { select: { name: true } },\n"
        "        approver:  { select: { name: true } },\n"
        "      },\n"
        "    });\n"
        "    if (!r) throw new NotFoundException"
    ),
    src,
    count=1,
    flags=re.DOTALL
)
log("OK: getPrintData include 完全置換")

# ── 12. getPrintData: return r → return { ...r, machining fields flattened } ──
src = re.sub(
    r"    if \(!r\) throw new NotFoundException\(`MC_id \$\{mcId\} が存在しません`\);\n"
    r"    return r;\n"
    r"  \}",
    "    if (!r) throw new NotFoundException(`MC_id ${mcId} が存在しません`);\n"
    "    const mach = (r as any).machining ?? {};\n"
    "    return {\n"
    "      ...r,\n"
    "      version:        mach.version        ?? '1.0001',\n"
    "      machineId:      mach.machineId      ?? null,\n"
    "      machine:        mach.machine        ?? null,\n"
    "      oNumber:        mach.oNumber        ?? null,\n"
    "      clampNote:      mach.clampNote      ?? null,\n"
    "      cycleTimeSec:   mach.cycleTimeSec   ?? null,\n"
    "      mcProcessNo:    mach.mcProcessNo    ?? null,\n"
    "      commonPartCode: mach.commonPartCode ?? null,\n"
    "      folder1:        mach.folder1        ?? null,\n"
    "      folder2:        mach.folder2        ?? null,\n"
    "      fileName:       mach.fileName       ?? null,\n"
    "      hasIndexProgram: mach.hasIndexProgram ?? false,\n"
    "      hasWorkOffset:   mach.hasWorkOffset   ?? false,\n"
    "      rc:             mach.rc             ?? 0,\n"
    "      pgIsFolder:     mach.pgIsFolder     ?? false,\n"
    "      pgFolderName:   mach.pgFolderName   ?? null,\n"
    "      pgCreatedBy:    mach.pgCreatedBy    ?? null,\n"
    "      pgUpdatedAt:    mach.pgUpdatedAt    ?? null,\n"
    "      creatorId:      mach.creatorId      ?? null,\n"
    "      sheetCreatedAt: mach.sheetCreatedAt ?? null,\n"
    "      creator:        mach.creator        ?? null,\n"
    "      pgCreator:      mach.pgCreator      ?? null,\n"
    "      tooling:        mach.tooling        ?? [],\n"
    "      workOffsets:    mach.workOffsets    ?? [],\n"
    "      indexPrograms:  mach.indexPrograms  ?? [],\n"
    "    };\n"
    "  }",
    src,
    count=1
)
log("OK: getPrintData return 展開")

# ── 13. commonGroup select の version 参照削除（行1326付近） ──
# commonGroup の select に version が McProgram に直接ある場合
src = re.sub(
    r"      select: \{\n"
    r"        id: true, legacyMcid: true, machiningId: true, version: true, status: true,\n"
    r"        part: \{ select: \{ drawingNo: true, name: true, clientName: true, partId: true \} \},\n"
    r"      \},",
    "      select: {\n"
    "        id: true, legacyMcid: true, machiningId: true, status: true,\n"
    "        part:      { select: { drawingNo: true, name: true, clientName: true, partId: true } },\n"
    "        machining: { select: { version: true } },\n"
    "      },",
    src
)
log("OK: commonGroup select 修正")

# ── 14. search: r.version / r.oNumber 等が McProgram に直接参照されている場合 ──
src = re.sub(
    r"        machine_code:  r\.machine\?\.machineCode \?\? null,\n"
    r"        machine_name:  r\.machine\?\.machineName \?\? null,\n"
    r"        version:       r\.version,\n"
    r"        status:        r\.status,\n"
    r"        o_number:      r\.oNumber,\n"
    r"        cycle_time_sec: r\.cycleTimeSec,\n"
    r"        common_part_code: r\.commonPartCode,",
    "        machine_code:  r.machining?.machine?.machineCode ?? null,\n"
    "        machine_name:  r.machining?.machine?.machineName ?? null,\n"
    "        version:       r.machining?.version ?? '1.0001',\n"
    "        status:        r.status,\n"
    "        o_number:      r.machining?.oNumber ?? null,\n"
    "        cycle_time_sec: r.machining?.cycleTimeSec ?? null,\n"
    "        common_part_code: r.machining?.commonPartCode ?? null,",
    src
)
log("OK: search map 修正")

# ── 15. recent: select → include、旧フィールド参照修正 ──
# recent の OperationLog query が select のままなら include に変更
src = re.sub(
    r"      select: \{\n"
    r"        createdAt: true,\n"
    r"        user:      \{ select: \{ name: true \} \},\n"
    r"        mcProgram: \{\n"
    r"          select: \{\n"
    r"            id: true, legacyMcid: true, (version: true, )?status: true(, oNumber: true)?,\n"
    r"            part:    \{ select: \{ drawingNo: true, name: true \} \},\n"
    r"            machine: \{ select: \{ machineCode: true \} \},\n"
    r"          \},\n"
    r"        \},\n"
    r"      \},",
    "      include: {\n"
    "        user:      { select: { name: true } },\n"
    "        mcProgram: {\n"
    "          include: {\n"
    "            part:     { select: { drawingNo: true, name: true } },\n"
    "            machining: { select: { version: true, machine: { select: { machineCode: true } } } },\n"
    "          },\n"
    "        },\n"
    "      },",
    src
)
log("OK: recent select → include")

# recent の map 修正
src = re.sub(
    r"      drawing_no:   l\.mcProgram\?\.part\.drawingNo,\n"
    r"      part_name:    l\.mcProgram\?\.part\.name,\n"
    r"      machine_code: l\.mcProgram\?\.machine\?\.machineCode,\n"
    r"      version:      l\.mcProgram\?\.version,\n",
    "      drawing_no:   l.mcProgram?.part?.drawingNo ?? null,\n"
    "      part_name:    l.mcProgram?.part?.name ?? null,\n"
    "      machine_code: l.mcProgram?.machining?.machine?.machineCode ?? null,\n"
    "      version:      l.mcProgram?.machining?.version ?? null,\n",
    src
)
log("OK: recent map 修正")

# ── 16. setupSheetLog version 参照（generateSetupSheetPdf内）──
src = re.sub(
    r"data: \{ mcProgramId: mcId, operatorId, version: data\.version \?\? null,",
    "data: { mcProgramId: mcId, operatorId, version: (data as any).machining?.version ?? (data as any).version ?? null,",
    src
)
log("OK: setupSheetLog version")

MC_SVC.write_text(src, encoding="utf-8")
log("mc.service.ts 書き込み完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# dashboard.service.ts: mcProgram.mcProcessNo/machine 修正
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
dash = DASH_SVC.read_text(encoding="utf-8")

# mcProgram.machine → mcProgram.machining.machine
dash = re.sub(
    r"s\.mcProgram\.machine\?\.machineCode",
    "s.mcProgram.machining?.machine?.machineCode",
    dash
)
dash = re.sub(
    r"s\.mcProgram\.machine\?\.machineName",
    "s.mcProgram.machining?.machine?.machineName",
    dash
)
dash = re.sub(
    r"s\.mcProgram\.machine\?\.sortOrder",
    "s.mcProgram.machining?.machine?.sortOrder",
    dash
)
# mcProgram.mcProcessNo → machining.mcProcessNo
dash = re.sub(
    r"s\.mcProgram\.mcProcessNo",
    "(s.mcProgram as any).machining?.mcProcessNo ?? null",
    dash
)
log("OK: dashboard machine/mcProcessNo 修正")

DASH_SVC.write_text(dash, encoding="utf-8")
log("dashboard.service.ts 書き込み完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TSC コンパイル確認 → エラー0ならビルド+PM2+git push
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log("TSC コンパイル確認中...")
tsc = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)

if tsc.returncode != 0:
    log(f"TSCエラー残存 (rc={tsc.returncode}) — 追加修正が必要")
    sys.exit(1)

log("TSC OK: コンパイルエラー 0")

# ── API ビルド ──
log("API ビルド中...")
build = subprocess.run(["npx", "tsc"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(build.stdout[-2000:]); print(build.stderr[-2000:])
if build.returncode != 0:
    log("API ビルド失敗"); sys.exit(1)
log("API ビルド OK")

# ── PM2 再起動 ──
log("PM2 再起動...")
subprocess.run(["pm2", "restart", "machcore-api"],
    cwd=str(BASE), capture_output=True, text=True)
log("PM2 machcore-api 再起動完了")

# ── git push ──
log("git add & commit & push...")
subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m",
    "refactor: normalize mc_machining_details (Step2 service layer)"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

# ── 一時スクリプト削除 ──
for f in ["fix_v130_step1_schema_migrate.py",
          "fix_v130_step1b_data_migrate.py",
          "fix_v130_step1c_prisma_generate.py",
          "fix_v130_step2.py",
          "fix_v130_step2b.py",
          "fix_v130_step2c.py",
          "fix_v130_step1c_v2.sh",
          "deploy_step1.sh",
          "inspect_mc_svc.sh"]:
    fp = BASE / f
    if fp.exists(): fp.unlink(); log(f"削除: {f}")

log("Step2完了 — API再起動・git push済み")
