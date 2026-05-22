#!/usr/bin/env python3
# coding: utf-8
"""
fix_v38.py
  handleSave で toolingRows/offsetRows/indexRows を
  DBから取得したcamelCase Prismaオブジェクトのまま送信 → DTOバリデーション400エラー
  → snake_caseに変換してから送信するよう修正
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"
EDIT = ROOT + "/apps/web/app/mc/[mc_id]/edit/page.tsx"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    s = p.read_text(encoding="utf-8")
    if old in s:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {label}")
        return True
    print(f"WARN: {label} — パターン不一致")
    return False

# toolingRows の変換 + 送信条件修正（長さ0でもクリア目的で送る）
apply(EDIT,
    """      // ツーリング保存
      if (toolingRows.length > 0) {
        await mcApi.saveTooling(mcId, toolingRows.map((t, i) => ({ ...t, sort_order: i })), token);
      }""",
    """      // ツーリング保存（DBのcamelCase → DTOのsnake_caseに変換）
      await mcApi.saveTooling(mcId, toolingRows.map((t: any, i: number) => ({
        sort_order:       i,
        tool_no:          t.tool_no   ?? t.toolNo   ?? "",
        tool_name:        t.tool_name ?? t.toolName ?? undefined,
        diameter:         t.diameter  ?? undefined,
        length_offset_no: t.length_offset_no ?? t.lengthOffsetNo ?? undefined,
        dia_offset_no:    t.dia_offset_no    ?? t.diaOffsetNo    ?? undefined,
        tool_type:        t.tool_type        ?? t.toolType       ?? undefined,
        note:             t.note             ?? undefined,
        raw_program_line: t.raw_program_line ?? t.rawProgramLine ?? undefined,
      })), token);""",
    "toolingRows snake_case変換"
)

# offsetRows の変換
apply(EDIT,
    """      // ワークオフセット保存
      if (offsetRows.length > 0) {
        await mcApi.saveWorkOffsets(mcId, offsetRows, token);
      }""",
    """      // ワークオフセット保存（DBのcamelCase → DTOのsnake_caseに変換）
      if (offsetRows.length > 0) {
        await mcApi.saveWorkOffsets(mcId, offsetRows.map((o: any) => ({
          g_code:   o.g_code   ?? o.gCode   ?? "",
          x_offset: o.x_offset ?? (o.xOffset != null ? Number(o.xOffset) : undefined),
          y_offset: o.y_offset ?? (o.yOffset != null ? Number(o.yOffset) : undefined),
          z_offset: o.z_offset ?? (o.zOffset != null ? Number(o.zOffset) : undefined),
          a_offset: o.a_offset ?? (o.aOffset != null ? Number(o.aOffset) : undefined),
          r_offset: o.r_offset ?? (o.rOffset != null ? Number(o.rOffset) : undefined),
          note:     o.note     ?? undefined,
        })), token);
      }""",
    "offsetRows snake_case変換"
)

# indexRows の変換
apply(EDIT,
    """      // インデックス保存
      if (indexRows.length > 0) {
        await mcApi.saveIndexPrograms(mcId, indexRows.map((r, i) => ({ ...r, sort_order: i })), token);
      }""",
    """      // インデックス保存（DBのcamelCase → DTOのsnake_caseに変換）
      if (indexRows.length > 0) {
        await mcApi.saveIndexPrograms(mcId, indexRows.map((r: any, i: number) => ({
          sort_order: i,
          axis_0: r.axis_0 ?? r.axis0 ?? undefined,
          axis_1: r.axis_1 ?? r.axis1 ?? undefined,
          axis_2: r.axis_2 ?? r.axis2 ?? undefined,
          note:   r.note   ?? undefined,
        })), token);
      }""",
    "indexRows snake_case変換"
)

# Build
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
out = r.stdout
print(out[-5000:] if len(out) > 5000 else out)
if r.returncode != 0:
    print("STDERR:", r.stderr[-3000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart web ---")
r2 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout)

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'fix: handleSave tooling/offset/index DTOsnake_case変換400エラー解消 v38' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])

print("\nDONE")
