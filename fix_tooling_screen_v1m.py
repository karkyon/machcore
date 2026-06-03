#!/usr/bin/env python3
"""
fix_tooling_screen_v1m.py
1. プログラム読取りブロックをリストの下に移動
2. 工具列 140→210px、コメント列→flex-grow で残り全幅
3. ツーリングリスト直上に「ツーリングを保存」ボタンを追加
4. colgroup を拡大してスクロールバーなし
"""
import subprocess, sys

BASE = "/home/karkyon/projects/machcore"
EDIT = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

print("=== [1] edit/page.tsx 修正 ===")
with open(EDIT, "r") as f:
    esrc = f.read()

# ── ツーリングセクション全体を特定 ──
SEC_START = '            {/* ツーリング */}\n            {activeSection === "tooling" && ('
SEC_END   = '            {/* ワークオフセット */'
idx_s = esrc.find(SEC_START)
idx_e = esrc.find(SEC_END)
if idx_s == -1 or idx_e == -1:
    print("  ERROR: セクション境界が見つかりません")
    sys.exit(1)

old_section = esrc[idx_s:idx_e]

# ── tbody の中身を保持 ──
tbody_start = old_section.find('                      <tbody>')
tbody_end   = old_section.find('                      </tbody>') + len('                      </tbody>')
if tbody_start == -1 or tbody_end == -1:
    print("  ERROR: tbody が見つかりません")
    sys.exit(1)
tbody_inner = old_section[tbody_start + len('                      <tbody>'):old_section.find('                      </tbody>')]

# ── プログラム読取りブロック（amber）を抽出 ──
amber_start = old_section.find('                <div className="bg-amber-50')
amber_end_marker = '                </div>\n\n                <div className="bg-white rounded-xl border border-slate-200">'
amber_end   = old_section.find(amber_end_marker)
if amber_start == -1 or amber_end == -1:
    print("  ERROR: amber ブロックが見つかりません")
    print("  CONTEXT:", repr(old_section[400:700]))
    sys.exit(1)
amber_block = old_section[amber_start:amber_end + len('                </div>')]

# ── 新しいセクションを組み立て ──
NEW_SECTION = (
    '            {/* ツーリング */}\n'
    '            {activeSection === "tooling" && (\n'
    '              <div className="space-y-4">\n'
    '\n'
    '                {/* ツーリングリスト */}\n'
    '                <div className="bg-white rounded-xl border border-slate-200">\n'
    '                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">\n'
    '                    <span className="text-xs font-bold text-slate-600">\u30c4\u30fc\u30ea\u30f3\u30b0\u30ea\u30b9\u30c8 ({toolingRows.length}\u30ec\u30b3\u30fc\u30c9)</span>\n'
    '                    <div className="flex items-center gap-2">\n'
    '                      <button\n'
    '                        onClick={async () => {\n'
    '                          if (!token) { alert("\u8a8d\u8a3c\u304c\u5fc5\u8981\u3067\u3059"); return; }\n'
    '                          try {\n'
    '                            await mcApi.saveTooling(mcId, toolingRows.map((t, idx) => ({\n'
    '                              sort_order:       t.sort_order       ?? idx,\n'
    '                              tool_no:          t.tool_no          ?? "",\n'
    '                              t_no:             t.t_no             ?? undefined,\n'
    '                              tool_name:        t.tool_name        ?? undefined,\n'
    '                              length_offset_no: t.length_offset_no ?? undefined,\n'
    '                              dia_offset_no:    t.dia_offset_no    ?? undefined,\n'
    '                              diameter:         t.diameter         ?? undefined,\n'
    '                              d_value_content:  t.d_value_content  ?? undefined,\n'
    '                              sub_pg_no:        t.sub_pg_no        ?? undefined,\n'
    '                              tool_type:        t.tool_type        ?? undefined,\n'
    '                              note:             t.note             ?? undefined,\n'
    '                              raw_program_line: t.raw_program_line ?? undefined,\n'
    '                            })), token);\n'
    '                            showToast("\u2705 \u30c4\u30fc\u30ea\u30f3\u30b0\u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f");\n'
    '                          } catch { showToast("\u274c \u4fdd\u5b58\u306b\u5931\u6557\u3057\u307e\u3057\u305f"); }\n'
    '                        }}\n'
    '                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">\n'
    '                        \u2713 \u30c4\u30fc\u30ea\u30f3\u30b0\u3092\u4fdd\u5b58\n'
    '                      </button>\n'
    '                      <button onClick={() => setToolingRows(prev => [...prev, { sort_order: (prev.length + 1) * 10, tool_no: "", tool_name: "", length_offset_no: "", dia_offset_no: "" }])}\n'
    '                        className="text-xs text-teal-600 font-bold">+ \u8ffd\u52a0</button>\n'
    '                    </div>\n'
    '                  </div>\n'
    '                  <div className="overflow-y-auto max-h-[55vh]">\n'
    '                    <table className="text-xs w-full border-collapse">\n'
    '                      <colgroup>\n'
    '                        <col style={{width:"72px"}}/>\n'
    '                        <col style={{width:"90px"}}/>\n'
    '                        <col style={{width:"210px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col/>\n'
    '                        <col style={{width:"60px"}}/>\n'
    '                        <col style={{width:"54px"}}/>\n'
    '                      </colgroup>\n'
    '                      <thead className="bg-teal-50 sticky top-0 z-10">\n'
    '                        <tr>\n'
    '                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">N</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">\u5de5\u5177</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">T</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">H</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">D</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">D\u5024</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">SUB</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">\u30b3\u30e1\u30f3\u30c8</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">\u9806\u756a</th>\n'
    '                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>\n'
    '                        </tr>\n'
    '                      </thead>\n'
    '                      <tbody>\n'
    + tbody_inner +
    '                      </tbody>\n'
    '                    </table>\n'
    '                  </div>\n'
    '                </div>\n'
    '\n'
    '                {/* プログラム読取り（リストの下） */}\n'
    + amber_block + '\n'
    '\n'
    '              </div>\n'
    '            )}\n\n'
)

esrc = esrc[:idx_s] + NEW_SECTION + esrc[idx_e:]
with open(EDIT, "w") as f:
    f.write(esrc)
print("  OK: プログラム読取りをリスト下に移動、保存ボタン追加、工具列210px")

# ─────────────────────────────────────────────
print("\n=== [2] Next.js ビルド ===")
res = subprocess.run(
    ["sh", "-c", "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -10"],
    capture_output=True, text=True
)
print(res.stdout)
if res.returncode != 0:
    print("BUILD ERROR:\n", res.stderr[-800:])
    sys.exit(1)

print("=== [3] PM2 再起動 ===")
subprocess.run(["pm2", "restart", "machcore-web"], check=True)
print("  OK")

print("=== [4] git push ===")
subprocess.run(["sh", "-c",
    'cd /home/karkyon/projects/machcore && git add -A && '
    'git commit -m "fix: tooling v1m - save button, parse block below list, wider tool/comment col" && '
    'git push origin main'
], check=True)
print("=== 完了 ===")
