#!/usr/bin/env python3
# coding: utf-8
import pathlib

ROOT = pathlib.Path("/home/karkyon/projects/machcore")

# ═══════════════════════════════════════════════════════
# 1. dashboard.service.ts: uncollectedMc に is_reference と sheet_type を追加
#    また mcSetupSheetLog の findMany で is_reference と
#    全印刷回数（sheet_type 判別用）を取得する
# ═══════════════════════════════════════════════════════
f = ROOT / "apps/api/src/dashboard/dashboard.service.ts"
src = f.read_text(encoding="utf-8")

# items の map に is_reference を追加
# 現在の末尾: version: s.version ?? null, printed_at: s.printedAt, operator_name: ...
OLD_MAP_END = (
    '      version:        s.version ?? null,\n'
    '      printed_at:     s.printedAt,\n'
    '      operator_name:  s.operator.name,\n'
    '    }));\n'
    '    return { total: items.length, items };\n'
    '  }'
)
NEW_MAP_END = (
    '      version:        s.version ?? null,\n'
    '      printed_at:     s.printedAt,\n'
    '      operator_name:  s.operator.name,\n'
    '      is_reference:   (s as any).isReference ?? false,\n'
    '      sheet_type:     sheetTypeMap.get(s.mcProgramId) ?? null,\n'
    '    }));\n'
    '    return { total: items.length, items };\n'
    '  }'
)

# sheet_type 判別のために全印刷回数を取得するロジックを rows の後に追加
OLD_ROWS_END = (
    '    const items = rows.map(s => ({\n'
    '      id:             s.id,\n'
)
NEW_ROWS_END = (
    '    // sheet_type 判別: 各プログラムの全印刷回数を取得\n'
    '    const programIds = [...new Set(rows.map(s => s.mcProgramId))];\n'
    '    const allCounts = await this.prisma.mcSetupSheetLog.groupBy({\n'
    '      by: [\'mcProgramId\'],\n'
    '      where: { mcProgramId: { in: programIds } },\n'
    '      _count: { id: true },\n'
    '    });\n'
    '    const sheetTypeMap = new Map(allCounts.map(r => [\n'
    '      r.mcProgramId,\n'
    '      r._count.id <= 1 ? \'NEW\' : \'REPEAT\',\n'
    '    ]));\n'
    '    const items = rows.map(s => ({\n'
    '      id:             s.id,\n'
)

if 'sheetTypeMap' not in src:
    if OLD_MAP_END in src and OLD_ROWS_END in src:
        src = src.replace(OLD_MAP_END, NEW_MAP_END, 1)
        src = src.replace(OLD_ROWS_END, NEW_ROWS_END, 1)
        f.write_text(src, encoding="utf-8")
        print("OK: dashboard.service.ts に is_reference/sheet_type 追加")
    else:
        print("WARN: dashboard.service.ts パターンなし")
        # フォールバック: operator_name の後に追加
        src = src.replace(
            "      operator_name:  s.operator.name,\n    }));\n    return { total: items.length, items };\n  }",
            "      operator_name:  s.operator.name,\n      is_reference:   (s as any).isReference ?? false,\n    }));\n    return { total: items.length, items };\n  }",
            1
        )
        f.write_text(src, encoding="utf-8")
        print("OK: dashboard.service.ts に is_reference のみ追加（フォールバック）")
else:
    print("INFO: dashboard.service.ts は既に対応済み")

# ═══════════════════════════════════════════════════════
# 2. page.tsx: サイドバーの段取シートバックパネルを
#    ナビリンクの直下（overflow-y-auto の外）に固定配置
#    → aside を flex-col から変更し、パネルを固定表示
# ═══════════════════════════════════════════════════════
f = ROOT / "apps/web/app/page.tsx"
src = f.read_text(encoding="utf-8")

# aside を overflow-y-auto なしに変更して
# 段取シートバックパネルを固定表示させる
# 現在: <aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">
# 変更: overflow-y-auto を削除し、ナビ部分だけ overflow-y-auto にする
src = src.replace(
    '<aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-y-auto">',
    '<aside className="w-[200px] shrink-0 bg-white border-r border-slate-200 flex flex-col">',
    1
)

# ナビメニュー部分を overflow-y-auto で囲む
# 「MC マシニング」ナビと「管理」ブロックを flex-1 overflow-y-auto の div でラップ
src = src.replace(
    '            <div className="p-4 border-b border-slate-100">\n'
    '              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">MC \u30de\u30b7\u30cb\u30f3\u30b0</p>',
    '            <div className="flex-1 overflow-y-auto">\n'
    '            <div className="p-4 border-b border-slate-100">\n'
    '              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">MC \u30de\u30b7\u30cb\u30f3\u30b0</p>',
    1
)

# 管理パネルブロックの後に閉じタグを追加
src = src.replace(
    '              \u7ba1\u7406\u30d1\u30cd\u30eb\n'
    '            </button>\n'
    '            </div>\n'
    '\n'
    '            {/* \u6bb5\u53d6\u30b7\u30fc\u30c8\u30d0\u30c3\u30af \u30d1\u30cd\u30eb */}',
    '              \u7ba1\u7406\u30d1\u30cd\u30eb\n'
    '            </button>\n'
    '            </div>\n'
    '            </div>{/* end flex-1 overflow-y-auto */}\n'
    '\n'
    '            {/* \u6bb5\u53d6\u30b7\u30fc\u30c8\u30d0\u30c3\u30af \u30d1\u30cd\u30eb */}',
    1
)

# mt-2 を削除して段取シートバックパネルを固定
src = src.replace(
    '            <div className="mx-3 mb-3 mt-2">',
    '            <div className="mx-3 mb-3 mt-0 shrink-0">',
    1
)

f.write_text(src, encoding="utf-8")
print("OK: page.tsx サイドバー構造修正（段取シートバックパネル固定表示）")

print("\ncd ~/projects/machcore/apps/api && npx tsc && pm2 restart machcore-api && sleep 5")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")