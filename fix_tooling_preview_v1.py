#!/usr/bin/env python3
"""
fix_tooling_preview_v1.py
解析結果プレビューテーブルを「ツーリングプログラム読取り」ブロック下に追加
"""
import subprocess, sys, os, shutil

BASE      = "/home/karkyon/projects/machcore"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

shutil.copy2(EDIT_PAGE, EDIT_PAGE + ".bak")
with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 現状: parseResult があれば件数テキストのみ表示
OLD_PREVIEW = '''                  {parseResult && (
                    <div className="mt-3 text-xs text-amber-700">{parseResult.length}本の工具を検出しました。「取り込む」で確定します。</div>
                  )}
                </div>'''

NEW_PREVIEW = '''                  {parseResult && (
                    <div className="mt-3 text-xs text-amber-700 font-bold">{parseResult.length}本の工具を検出しました。内容を確認して「取り込む」で確定します。</div>
                  )}
                </div>

                {/* 解析結果プレビューテーブル */}
                {parseResult && parseResult.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden">
                    <div className="bg-amber-100 px-4 py-2 border-b border-amber-200 flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-800">📋 解析プレビュー（{parseResult.length}件）— 取り込み前に確認</span>
                      <button
                        onClick={() => setParseResult(null)}
                        className="text-xs text-amber-600 hover:text-amber-800 font-bold px-2 py-0.5 rounded hover:bg-amber-200">
                        ✕ 閉じる
                      </button>
                    </div>
                    <div className="overflow-y-auto max-h-[40vh]">
                      <table className="text-xs w-auto border-collapse">
                        <colgroup>
                          <col style={{width:"36px"}} />
                          <col style={{width:"70px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"180px"}} />
                          <col style={{width:"50px"}} />
                          <col style={{width:"50px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"180px"}} />
                          <col style={{width:"60px"}} />
                        </colgroup>
                        <thead className="sticky top-0 z-10 bg-amber-200">
                          <tr>
                            <th className="px-2 py-1.5 text-center text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">#</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">N</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">T</th>
                            <th className="px-2 py-1.5 text-left text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">工具名</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">H</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">D</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">D値</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">SUB</th>
                            <th className="px-2 py-1.5 text-left text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">コメント</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">順番</th>
                          </tr>
                        </thead>
                        <tbody>
                          {parseResult.map((item, i) => (
                            <tr key={i} className={i % 2 === 0 ? "bg-white hover:bg-amber-50" : "bg-amber-50 hover:bg-amber-100"}>
                              <td className="px-2 py-1 text-center text-slate-400 font-mono">{i + 1}</td>
                              <td className="px-2 py-1 font-mono font-bold text-teal-700">{item.tool_no ?? "—"}</td>
                              <td className="px-2 py-1 font-mono text-slate-700">{item.t_no ?? "—"}</td>
                              <td className="px-2 py-1 text-slate-800 max-w-[180px] truncate" title={item.tool_name ?? ""}>{item.tool_name || "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-slate-600">{item.length_offset_no ?? "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-slate-600">{item.dia_offset_no ?? "—"}</td>
                              <td className="px-2 py-1 text-center text-slate-600">{item.d_value_content || "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-indigo-600">{item.sub_pg_no || "—"}</td>
                              <td className="px-2 py-1 text-slate-500 max-w-[180px] truncate" title={item.note ?? ""}>{item.note || "—"}</td>
                              <td className="px-2 py-1 text-center text-slate-400 font-mono">{item.sort_order}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="px-4 py-2 border-t border-amber-200 flex justify-end">
                      <button
                        onClick={() => {
                          if (!parseResult) return;
                          setToolingRows(parseResult.map((item, i) => ({
                            sort_order:       item.sort_order       ?? (i + 1) * 10,
                            tool_no:          item.tool_no          ?? "",
                            t_no:             item.t_no             ?? "",
                            tool_name:        item.tool_name        ?? "",
                            length_offset_no: item.length_offset_no ?? "",
                            dia_offset_no:    item.dia_offset_no    ?? "",
                            diameter:         item.diameter         ?? null,
                            d_value_content:  item.d_value_content  ?? "",
                            sub_pg_no:        item.sub_pg_no        ?? "",
                            tool_type:        item.tool_type        ?? "",
                            note:             item.note             ?? "",
                            raw_program_line: item.raw_program_line ?? "",
                          })));
                          setParseResult(null);
                          setToolingText("");
                          showToast("ツーリングデータを取り込みました");
                        }}
                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs px-6 py-2 rounded-lg font-bold">
                        ✅ {parseResult.length}本を取り込む
                      </button>
                    </div>
                  </div>
                )}'''

if OLD_PREVIEW in src:
    src = src.replace(OLD_PREVIEW, NEW_PREVIEW)
    with open(EDIT_PAGE, "w") as f:
        f.write(src)
    print("=== [1] プレビューテーブル追加 OK ===")
else:
    print("=== [1] SKIP: アンカー不一致 ===")
    sys.exit(1)

# ── Next.js build ────────────────────────────────────────────────
print("=== [2] Next.js build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/web && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build 2>&1 | tail -20"],
    capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    sys.exit(1)
print("  OK")

# ── PM2 再起動 ────────────────────────────────────────────────────
print("=== [3] PM2 再起動 ===")
subprocess.run(
    ["bash", "-c", "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-web"],
    capture_output=False
)

# ── クリーンアップ & git push ────────────────────────────────────
print("=== [4] クリーンアップ & git push ===")
if os.path.exists(EDIT_PAGE + ".bak"): os.remove(EDIT_PAGE + ".bak")

import glob
for s in glob.glob(f"{BASE}/fix_tooling_parse_v1b.py"):
    try: os.remove(s)
    except: pass

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'feat: tooling parse preview table with all fields' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
