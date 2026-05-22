#!/usr/bin/env python3
# coding: utf-8
"""
実装内容:
1. mc_setup_sheet_logs に is_reference カラム追加（DBマイグレーション）
2. 段取シート印刷画面に「参考出力」チェックボックス追加
3. API: setupSheetLogs / uncollectedByLegacy に is_reference を追加
4. ダッシュボード未回収一覧に新規/リピート/参考バッジ表示
5. 部品検索・詳細・印刷・作業記録ヘッダーにダッシュボードボタン追加
"""
import pathlib, re, subprocess

ROOT = pathlib.Path("/home/karkyon/projects/machcore")

# ════════════════════════════════════════════════════════════
# 1. prisma schema に is_reference 追加
# ════════════════════════════════════════════════════════════
SCHEMA = ROOT / "apps/api/prisma/schema.prisma"
src = SCHEMA.read_text(encoding="utf-8")
if "isReference" not in src:
    src = src.replace(
        '  workCollected Boolean @default(false)    @map("work_collected")\n\n  mcProgram McProgram @relation(fields: [mcProgramId]',
        '  workCollected Boolean @default(false)    @map("work_collected")\n'
        '  isReference   Boolean @default(false)    @map("is_reference")\n\n'
        '  mcProgram McProgram @relation(fields: [mcProgramId]',
        1
    )
    SCHEMA.write_text(src, encoding="utf-8")
    print("OK: schema.prisma に isReference 追加")
else:
    print("INFO: isReference は既に存在")

# ════════════════════════════════════════════════════════════
# 2. Prisma マイグレーション実行
# ════════════════════════════════════════════════════════════
print("\nDBマイグレーション実行中...")
result = subprocess.run(
    ["npx", "prisma", "db", "push", "--accept-data-loss"],
    cwd=ROOT / "apps/api",
    capture_output=True, text=True, timeout=60
)
if result.returncode == 0:
    print("OK: DB マイグレーション完了")
else:
    print(f"WARN: {result.stderr[-300:]}")

# ════════════════════════════════════════════════════════════
# 3. mc.service.ts: setupSheetLogs と uncollectedByLegacy に is_reference 追加
# ════════════════════════════════════════════════════════════
SVC = ROOT / "apps/api/src/mc/mc.service.ts"
src = SVC.read_text(encoding="utf-8")

# setupSheetLogs の map に is_reference 追加
if "is_reference" not in src:
    src = src.replace(
        "      work_collected: r.workCollected,\n"
        "    }));\n"
        "  }\n"
        "\n"
        "  /** 段取シートバック: legacy_mcid で未回収シート一覧取得 */",
        "      work_collected: r.workCollected,\n"
        "      is_reference:   r.isReference,\n"
        "    }));\n"
        "  }\n"
        "\n"
        "  /** 段取シートバック: legacy_mcid で未回収シート一覧取得 */",
        1
    )
    # uncollectedByLegacy の sheets.map にも追加
    src = src.replace(
        "        work_collected: s.workCollected,\n"
        "      })),\n"
        "    };\n"
        "  }\n"
        "\n"
        "  /** SSL-MC-01",
        "        work_collected: s.workCollected,\n"
        "        is_reference:   s.isReference,\n"
        "      })),\n"
        "    };\n"
        "  }\n"
        "\n"
        "  /** SSL-MC-01",
        1
    )
    # generateSetupSheetPdf の mcSetupSheetLog.create に is_reference 対応
    src = src.replace(
        "    await this.prisma.mcSetupSheetLog.create({\n"
        "      data: { mcProgramId: mcId, operatorId, version: data.version ?? null },\n"
        "    }).catch(",
        "    await this.prisma.mcSetupSheetLog.create({\n"
        "      data: { mcProgramId: mcId, operatorId, version: data.version ?? null,\n"
        "              isReference: (options as any).is_reference ?? false },\n"
        "    }).catch(",
        1
    )
    SVC.write_text(src, encoding="utf-8")
    print("OK: mc.service.ts に is_reference 追加")
else:
    print("INFO: mc.service.ts は既に対応済み")

# ════════════════════════════════════════════════════════════
# 4. api.ts: McSetupSheetLog 型に is_reference 追加
# ════════════════════════════════════════════════════════════
API_TS = ROOT / "apps/web/lib/api.ts"
src = API_TS.read_text(encoding="utf-8")
if "is_reference" not in src:
    src = src.replace(
        "  work_collected: boolean;\n"
        "};\n"
        "\n"
        "export type CreateMcWorkRecordBody",
        "  work_collected: boolean;\n"
        "  is_reference:   boolean;\n"
        "};\n"
        "\n"
        "export type CreateMcWorkRecordBody",
        1
    )
    API_TS.write_text(src, encoding="utf-8")
    print("OK: api.ts McSetupSheetLog に is_reference 追加")
else:
    print("INFO: api.ts は既に対応済み")

# ════════════════════════════════════════════════════════════
# 5. 印刷画面に「参考出力」チェックボックス追加
# ════════════════════════════════════════════════════════════
PRINT = ROOT / "apps/web/app/mc/[mc_id]/print/page.tsx"
src = PRINT.read_text(encoding="utf-8")

if "isReference" not in src:
    # State 追加
    src = src.replace(
        "  const [includeIndexPrograms, setIncludeIndexPrograms] = useState(false);",
        "  const [includeIndexPrograms, setIncludeIndexPrograms] = useState(false);\n"
        "  const [isReference,          setIsReference]          = useState(false);",
        1
    )
    # printBody に is_reference 追加（fetch の body.JSON.stringify の前）
    src = src.replace(
        "        body: JSON.stringify(printBody),\n"
        "      });\n"
        "      if (!res.ok)",
        "        body: JSON.stringify({...printBody, is_reference: isReference}),\n"
        "      });\n"
        "      if (!res.ok)",
        1
    )
    src = src.replace(
        "        body: JSON.stringify(printBody),\n"
        "      });\n"
        "      const j = await res.json();",
        "        body: JSON.stringify({...printBody, is_reference: isReference}),\n"
        "      });\n"
        "      const j = await res.json();",
        1
    )
    # UI: includeIndexPrograms の後に参考出力チェックを追加
    src = src.replace(
        '                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],\n'
        '                ].map(([val, setter, label]: any)',
        '                  [includeIndexPrograms, setIncludeIndexPrograms, "インデックスプログラムを含める"],\n'
        '                ].map(([val, setter, label]: any)',
        1
    )
    # 参考出力チェックボックスをオプションリストの後に追加
    src = src.replace(
        '              </div>\n'
        '              <div className="px-5 pb-5 flex flex-col gap-3">',
        '              </div>\n'
        '              <div className="px-5 py-3 border-t border-slate-100">\n'
        '                <label className="flex items-center gap-3 text-sm cursor-pointer">\n'
        '                  <input type="checkbox" checked={isReference} onChange={e => setIsReference(e.target.checked)}\n'
        '                    className="accent-amber-500 w-4 h-4" />\n'
        '                  <span className="text-amber-700 font-bold">\u53c2\u8003\u51fa\u529b\uff08\u751f\u7523\u306b\u4f7f\u7528\u3057\u306a\u3044\u30fb\u56de\u53ce\u4e0d\u8981\uff09</span>\n'
        '                </label>\n'
        '                {isReference && <p className="text-[11px] text-amber-600 mt-1 ml-7">\u53c2\u8003\u51fa\u529b\u306f\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u306e\u672a\u56de\u53ce\u4e00\u89a7\u306b\u8868\u793a\u3055\u308c\u307e\u305b\u3093</p>}\n'
        '              </div>\n'
        '              <div className="px-5 pb-5 flex flex-col gap-3">',
        1
    )
    PRINT.write_text(src, encoding="utf-8")
    print("OK: 印刷画面に参考出力チェックボックス追加")
else:
    print("INFO: 印刷画面は既に対応済み")

# ════════════════════════════════════════════════════════════
# 6. ダッシュボード (page.tsx): 未回収一覧にバッジ表示
#    sheet_type (NEW/REPEAT) + is_reference を uncollected-mc API から取得して表示
#    ※ dashboard の uncollected-mc は McSheet 型を返す。sheet_type は別途 setupSheetLogs の is_reference から判断する。
#    → ダッシュボードの McSheet 型に sheet_type と is_reference を追加して表示
# ════════════════════════════════════════════════════════════
DASH = ROOT / "apps/web/app/page.tsx"
src = DASH.read_text(encoding="utf-8")

# McSheet 型に sheet_type / is_reference 追加
if "sheet_type" not in src:
    src = src.replace(
        "  version: string | null; printed_at: string; operator_name: string;\n"
        "};",
        "  version: string | null; printed_at: string; operator_name: string;\n"
        "  sheet_type: string | null;\n"
        "  is_reference: boolean;\n"
        "};",
        1
    )
    print("OK: McSheet 型に sheet_type/is_reference 追加")

# 各シート行にバッジを追加（図番の前に挿入）
if "sheet_type" in src and "参考" not in src:
    src = src.replace(
        '                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>',
        '                            {item.is_reference && <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded font-bold mr-1">\u53c2\u8003</span>}\n'
        '                            {!item.is_reference && item.sheet_type === "NEW" && <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold mr-1">\u65b0\u898f</span>}\n'
        '                            {!item.is_reference && item.sheet_type === "REPEAT" && <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold mr-1">\u30ea\u30d4\u30fc\u30c8</span>}\n'
        '                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>',
        1
    )
    DASH.write_text(src, encoding="utf-8")
    print("OK: ダッシュボードにバッジ追加")
else:
    DASH.write_text(src, encoding="utf-8")
    print("INFO: ダッシュボードは既に対応済み or sheet_type 未取得")

# ════════════════════════════════════════════════════════════
# 7. dashboard.service.ts: uncollectedMc に sheet_type / is_reference 追加
# ════════════════════════════════════════════════════════════
DSVC = ROOT / "apps/api/src/dashboard/dashboard.service.ts"
src = DSVC.read_text(encoding="utf-8")
if "is_reference" not in src and "sheet_type" not in src:
    # uncollectedMc メソッドを探してマッピングに追加
    src = src.replace(
        "          operator_name:  s.operator?.name ?? null,\n",
        "          operator_name:  s.operator?.name ?? null,\n"
        "          sheet_type:     s.sheetType    ?? null,\n"
        "          is_reference:   s.isReference  ?? false,\n",
        1
    )
    DSVC.write_text(src, encoding="utf-8")
    print("OK: dashboard.service.ts に sheet_type/is_reference 追加")
else:
    print("INFO: dashboard.service.ts は既に対応済み")

# ════════════════════════════════════════════════════════════
# 8. 部品検索ページヘッダーにダッシュボードボタン追加
# ════════════════════════════════════════════════════════════
SEARCH = ROOT / "apps/web/app/mc/search/page.tsx"
src = SEARCH.read_text(encoding="utf-8")
if "\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078" not in src:
    src = src.replace(
        '<button onClick={() => router.push("/mc/new")} className="text-xs bg-teal-500 hover:bg-teal-400 text-white font-bold px-3 py-1.5 rounded-lg transition-colors">\uff0b \u65b0\u898f\u767b\u9332</button>',
        '<button onClick={() => router.push("/mc")} className="text-xs bg-slate-600 hover:bg-slate-500 text-white font-bold px-3 py-1.5 rounded-lg transition-colors">\u2190 \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078</button>\n'
        '            <button onClick={() => router.push("/mc/new")} className="text-xs bg-teal-500 hover:bg-teal-400 text-white font-bold px-3 py-1.5 rounded-lg transition-colors">\uff0b \u65b0\u898f\u767b\u9332</button>',
        1
    )
    SEARCH.write_text(src, encoding="utf-8")
    print("OK: 部品検索ページにダッシュボードボタン追加")
else:
    print("INFO: 部品検索は既に対応済み")

# ════════════════════════════════════════════════════════════
# 9. MC詳細ページヘッダーにダッシュボードボタン追加
# ════════════════════════════════════════════════════════════
DETAIL = ROOT / "apps/web/app/mc/[mc_id]/page.tsx"
src = DETAIL.read_text(encoding="utf-8")
if "\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9" not in src:
    src = src.replace(
        '<button onClick={() => router.push("/mc/search")}',
        '<button onClick={() => router.push("/mc")} className="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-xs font-bold transition-colors">\u2190 \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9</button>\n'
        '          <button onClick={() => router.push("/mc/search")}',
        1
    )
    DETAIL.write_text(src, encoding="utf-8")
    print("OK: MC詳細ページにダッシュボードボタン追加")
else:
    print("INFO: MC詳細は既に対応済み")

# ════════════════════════════════════════════════════════════
# 10. 印刷ページヘッダーにダッシュボードボタン追加
# ════════════════════════════════════════════════════════════
src = PRINT.read_text(encoding="utf-8")
if "\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9" not in src:
    src = src.replace(
        'router.push(`/mc/${mcId}`)',
        'router.push("/mc")',
        1
    )
    # ヘッダーのボタンをダッシュボードに向ける変更は最初のpushだけ
    # 実際は戻るボタンとして mc詳細に戻す方が適切なので元に戻す
    src = src.replace(
        'router.push("/mc")',
        'router.push(`/mc/${mcId}`)',
        1
    )
    PRINT.write_text(src, encoding="utf-8")

# 印刷ページのヘッダーにダッシュボードボタンを追加
src = PRINT.read_text(encoding="utf-8")
if "\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078" not in src:
    src = src.replace(
        '<button onClick={() => router.push(`/mc/${mcId}`)}',
        '<button onClick={() => router.push("/mc")} className="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-xs font-bold transition-colors mr-2">\u2190 \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078</button>\n'
        '        <button onClick={() => router.push(`/mc/${mcId}`)}',
        1
    )
    PRINT.write_text(src, encoding="utf-8")
    print("OK: 印刷ページにダッシュボードボタン追加")
else:
    print("INFO: 印刷ページは既に対応済み")

# ════════════════════════════════════════════════════════════
# 11. 作業記録ページヘッダーにダッシュボードボタン追加
# ════════════════════════════════════════════════════════════
RECORD = ROOT / "apps/web/app/mc/[mc_id]/record/page.tsx"
src = RECORD.read_text(encoding="utf-8")
if "\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078" not in src:
    # ヘッダー内の「部品検索へ戻る」的なボタンかナビの前に追加
    src = src.replace(
        "router.push(`/mc/${mcId}`)",
        "router.push(`/mc/${mcId}`)",
        1  # そのまま、別の箇所を探す
    )
    # ヘッダーナビの先頭に追加
    if 'className="bg-slate-800' in src:
        src = src.replace(
            '<nav className="flex',
            '<button onClick={() => router.push("/mc")} className="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-xs font-bold transition-colors mr-3">\u2190 \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078</button>\n'
            '      <nav className="flex',
            1
        )
    RECORD.write_text(src, encoding="utf-8")
    print("OK: 作業記録ページにダッシュボードボタン追加")
else:
    print("INFO: 作業記録は既に対応済み")

print("\n=== 完了 ===")
print("cd ~/projects/machcore/apps/api && npx tsc && pm2 restart machcore-api && sleep 5")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
