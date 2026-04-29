#!/usr/bin/env python3
# =============================================================================
# MachCore MCID表示修正パッチ v2（完全版）
# 方針A: legacy_mcid を表示用MCIDとして使用
#        URL/内部IDは mc_programs.id のまま維持
#
# 実行方法:
#   python3 /tmp/fix_mcid_display.py
# =============================================================================

import os

BASE = os.path.expanduser('~/projects/machcore')


def patch_file(rel_path, patches, encoding='utf-8'):
    full = os.path.join(BASE, rel_path)
    if not os.path.exists(full):
        print(f"  WARNING: ファイルなし: {full}")
        return 0
    with open(full, 'r', encoding=encoding) as f:
        content = f.read()
    applied = 0
    for old, new in patches:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
            print(f"  OK: {old.strip()[:60]!r}")
        else:
            print(f"  SKIP: {old.strip()[:60]!r}")
    with open(full, 'w', encoding=encoding) as f:
        f.write(content)
    return applied


print("=== [1] mc.service.ts ===")
patch_file('apps/api/src/mc/mc.service.ts', [
    # MCID検索 → legacyMcid で検索
    (
        "      if (key === 'mcid') {\n        const n = parseInt(kw);\n        if (!isNaN(n)) where.id = n;",
        "      if (key === 'mcid') {\n        const n = parseInt(kw);\n        if (!isNaN(n)) where.legacyMcid = n;"
    ),
    # search() 返却に legacy_mcid 追加
    (
        "        mc_id:         r.id,\n          part_db_id:    r.partId,",
        "        mc_id:         r.id,\n        legacy_mcid:   r.legacyMcid ?? null,\n          part_db_id:    r.partId,"
    ),
    # recent() の select に legacyMcid 追加
    (
        "            id: true, version: true, status: true, oNumber: true,\n            part:    { select: { drawingNo: true, name: true } },\n            machine: { select: { machineCode: true } },",
        "            id: true, legacyMcid: true, version: true, status: true, oNumber: true,\n            part:    { select: { drawingNo: true, name: true } },\n            machine: { select: { machineCode: true } },"
    ),
    # recent() の map 返却に legacy_mcid 追加
    (
        "      mc_id:        l.mcProgram?.id,\n      drawing_no:   l.mcProgram?.part.drawingNo,",
        "      mc_id:        l.mcProgram?.id,\n      legacy_mcid:  l.mcProgram?.legacyMcid ?? null,\n      drawing_no:   l.mcProgram?.part.drawingNo,"
    ),
])

print("\n=== [2] api.ts ===")
patch_file('apps/web/lib/api.ts', [
    # McSearchResult 型に legacy_mcid 追加
    (
        "export type McSearchResult = {\n  mc_id:            number;",
        "export type McSearchResult = {\n  mc_id:            number;\n  legacy_mcid:      number | null;"
    ),
    # McDetail 型に legacyMcid 追加
    (
        "  registeredAt:   string;\n  approvedAt:     string | null;",
        "  legacyMcid:     number | null;\n  registeredAt:   string;\n  approvedAt:     string | null;"
    ),
])

print("\n=== [3] mc/search/page.tsx ===")
patch_file('apps/web/app/mc/search/page.tsx', [
    # 検索結果リスト MCID 表示
    ('MCID : {r.mc_id}', 'MCID : {r.legacy_mcid ?? r.mc_id}'),
    # 最近のアクセス MCID 表示
    ('MCID:{r.mc_id}', 'MCID:{r.legacy_mcid ?? r.mc_id}'),
    # 検索フォームラベル
    (
        '<label className="text-sm font-bold text-slate-700 block mb-1">MC ID</label>',
        '<label className="text-sm font-bold text-slate-700 block mb-1">MC ID <span className="text-[10px] text-slate-400 font-normal">(旧MCID)</span></label>'
    ),
])

print("\n=== [4] mc/[mc_id]/page.tsx ===")
patch_file('apps/web/app/mc/[mc_id]/page.tsx', [
    ('<span>MCID: {d.id}</span>', '<span>MCID: {d.legacyMcid ?? d.id}</span>'),
])

print("\n=== [5] mc/[mc_id]/print/page.tsx ===")
patch_file('apps/web/app/mc/[mc_id]/print/page.tsx', [
    ('<span>MCID: {d.id}</span>', '<span>MCID: {d.legacyMcid ?? d.id}</span>'),
])

print("\n=== [6] mc/[mc_id]/edit/page.tsx ===")
patch_file('apps/web/app/mc/[mc_id]/edit/page.tsx', [
    ('<span>MCID: {d.id}</span>', '<span>MCID: {d.legacyMcid ?? d.id}</span>'),
])

print("\n=== [7] mc/[mc_id]/record/page.tsx ===")
patch_file('apps/web/app/mc/[mc_id]/record/page.tsx', [
    ('<span>MCID: {d.id}</span>', '<span>MCID: {d.legacyMcid ?? d.id}</span>'),
])

print("""
=== 完了 ===
次のコマンドをomega-dev2で実行してください:

# API再ビルド
cd ~/projects/machcore/apps/api && npx tsc && pm2 restart machcore-api

# Webビルド・再起動
cd ~/projects/machcore/apps/web && npx next build 2>&1 | tail -5 && pm2 restart machcore-web

# Git Push
cd ~/projects/machcore && git add -A && git commit -m 'fix: MCID表示をlegacy_mcid(旧AccessMCID)に修正' && git push origin main
""")
