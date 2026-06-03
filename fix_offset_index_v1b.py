#!/usr/bin/env python3
"""
fix_offset_index_v1b.py
- page.tsx: 重複WOブロック除去、インデックスPG修正
- edit/page.tsx: インデックスPGブロック刷新（v1でWARNだった箇所）
"""
import subprocess, sys, shutil

BASE      = "/home/karkyon/projects/machcore"
REF_PAGE  = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ─────────────────────────────────────────────────────────
# [1] page.tsx: 古いWOブロック（旧G座標/A/R）を削除
# ─────────────────────────────────────────────────────────
print("=== [1] 参照画面 旧WOブロック削除 ===")
with open(REF_PAGE, "r") as f:
    src = f.read()

# 旧ブロック（G座標/A/R のまま残っている古いもの）を除去
OLD_WO_STALE = '''        {/* ─── ワークオフセット ─── */}
        {mainTab === "offset" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ワークオフセット ({d.workOffsets.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.workOffsets.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ワークオフセットデータがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["G座標","X","Y","Z","A","R","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-center font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.workOffsets.map((o, i) => (
                      <tr key={o.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono font-bold text-teal-600">{o.gCode}</td>
                        {[o.xOffset, o.yOffset, o.zOffset, o.aOffset, o.rOffset].map((v, j) => (
                          <td key={j} className="px-3 py-2 text-center font-mono">{v ? Number(v).toFixed(3) : "—"}</td>
                        ))}
                        <td className="px-3 py-2 text-slate-400">{o.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["No.","第0軸","第1軸","第2軸","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.indexPrograms.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono">{p.sortOrder}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}'''

if OLD_WO_STALE in src:
    # 旧ブロックを「─── 履歴 ───」コメントだけ残して削除
    src = src.replace(OLD_WO_STALE, '\n        {/* ─── 履歴 ─── */}')
    print("  OK: 旧WO/IPブロック削除")
else:
    print("  WARN: 旧ブロックが見つからない — コンテキスト確認")
    idx = src.find('ワークオフセット ({d.workOffsets.length}件)')
    if idx != -1:
        print("  CONTEXT:", src[max(0,idx-100):idx+300])

# ─────────────────────────────────────────────────────────
# [2] page.tsx: 新しいWOブロックの閉じタグ余分div修正
#   症状: </table> → </div>(overflow) → </div> が二重になっている
# ─────────────────────────────────────────────────────────
print("=== [2] 参照画面 WO閉じタグ修正 ===")

# 現状の新WOブロック末尾（重複div）
OLD_WO_CLOSE = '''              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''

# 正しい閉じタグ（overflow-y-auto div + bg-white div + max-w-3xl div）
NEW_WO_CLOSE = '''              )}
                </div>
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''

if OLD_WO_CLOSE in src:
    src = src.replace(OLD_WO_CLOSE, NEW_WO_CLOSE, 1)
    print("  OK: WO 閉じタグ修正")
else:
    print("  WARN: WO閉じタグパターンが見つからない（既に修正済みか確認）")

# ─────────────────────────────────────────────────────────
# [3] page.tsx: インデックスPGブロック (No./旧) を新版に置換
# ─────────────────────────────────────────────────────────
print("=== [3] 参照画面 インデックスPG修正 ===")

# v1適用後の現在のIPブロック
OLD_REF_IP = '''        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[55vh]">
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                    <tr>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">STEP/N</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第0軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第1軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第2軸</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">備考</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.indexPrograms.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          </div>
        )}'''

NEW_REF_IP = '''        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[55vh]">
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                      <tr>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">STEP/N</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第0軸</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第1軸</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">第2軸</th>
                        <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">備考</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.indexPrograms.map((p, i) => (
                        <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-3 py-2 font-mono font-bold text-teal-700">{p.axis0 ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                          <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}'''

if OLD_REF_IP in src:
    src = src.replace(OLD_REF_IP, NEW_REF_IP)
    print("  OK: 参照 インデックスPGブロック修正")
else:
    # 旧版（No./件）が残っている場合
    OLD_REF_IP_LEGACY = '''        {/* ─── インデックスプログラム ─── */}
        {mainTab === "index" && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">インデックスプログラム ({d.indexPrograms.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.indexPrograms.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">インデックスプログラムがありません</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["No.","第0軸","第1軸","第2軸","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-left font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {d.indexPrograms.map((p, i) => (
                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono">{p.sortOrder}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}'''
    if OLD_REF_IP_LEGACY in src:
        src = src.replace(OLD_REF_IP_LEGACY, NEW_REF_IP)
        print("  OK: 参照 インデックスPGブロック修正 (legacy)")
    else:
        print("  WARN: 参照 インデックスPGブロックが見つからない")
        idx = src.find('mainTab === "index"')
        print("  CONTEXT:", src[max(0,idx-50):idx+500] if idx != -1 else "not found")

with open(REF_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", REF_PAGE)

# ─────────────────────────────────────────────────────────
# [4] edit/page.tsx: インデックスPGブロック刷新
#   v1でWARNだったため旧ブロックが残っている
# ─────────────────────────────────────────────────────────
print("=== [4] 編集画面 インデックスPG刷新 ===")
with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 現在の旧ブロック（v1で未修正）
OLD_EDIT_IP = '''            {/* インデックスプログラム */}
            {activeSection === "index" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">インデックスプログラム ({indexRows.length}件)</span>
                    <button onClick={() => setIndexRows(prev => [...prev, { sort_order: prev.length, axis_0: "", axis_1: "", axis_2: "" }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["No.","第0軸","第1軸","第2軸","備考",""].map(h =>
                        <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>'''

idx_start = src.find(OLD_EDIT_IP)

if idx_start == -1:
    print("  WARN: 旧インデックスPGブロック開始が見つからない")
    idx = src.find('activeSection === "index"')
    print("  CONTEXT:", src[max(0,idx-20):idx+300] if idx != -1 else "not found")
else:
    # ブロック終了を探す: 次の {/* ファイル */ または </div>\n            )}\n\n            {/* ファイル
    idx_end = src.find('\n            {/* ファイル', idx_start)
    if idx_end == -1:
        # 代替: 次のactiveSection
        idx_end = src.find('\n            {activeSection === "files"', idx_start)
    if idx_end == -1:
        print("  WARN: 旧インデックスPGブロック終了が見つからない")
    else:
        NEW_EDIT_IP = '''            {/* インデックスプログラム */}
            {activeSection === "index" && (
              <div className="max-w-[1016px]">
                <div className="bg-white rounded-xl border border-slate-200">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between rounded-t-xl">
                    <span className="text-xs font-bold text-slate-600">インデックスプログラム ({indexRows.length}レコード)</span>
                    <div className="flex items-center gap-2">
                      <button onClick={async () => {
                        const token = sessionStorage.getItem("admin_token") || "";
                        try {
                          await mcApi.saveIndexPrograms(mcId, indexRows.map((r: any, idx: number) => ({
                            sort_order: idx,
                            axis_0: r.axis_0 ?? r.axis0 ?? undefined,
                            axis_1: r.axis_1 ?? r.axis1 ?? undefined,
                            axis_2: r.axis_2 ?? r.axis2 ?? undefined,
                            note:   r.note   ?? undefined,
                          })), token);
                          showToast("✅ インデックスPGを保存しました");
                        } catch { showToast("❌ 保存に失敗しました"); }
                      }}
                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                        ✓ インデックスPGを保存
                      </button>
                      <button onClick={() => setIndexRows(prev => [...prev, { sort_order: prev.length, axis_0: "", axis_1: "", axis_2: "" }])}
                        className="text-xs text-teal-600 font-bold">+ 追加</button>
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-[55vh]">
                    <table className="text-xs w-full border-collapse">
                      <colgroup>
                        <col style={{width:"72px"}}/>
                        <col style={{width:"90px"}}/>
                        <col style={{width:"240px"}}/>
                        <col style={{width:"240px"}}/>
                        <col style={{width:"200px"}}/>
                        <col style={{width:"120px"}}/>
                        <col style={{width:"54px"}}/>
                      </colgroup>
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>
                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">STEP/N</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第0軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第1軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第2軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">備考</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {indexRows.map((p, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-1 py-1">
                              <div className="flex gap-0.5">
                                <button onClick={() => {
                                  if (i === 0) return;
                                  setIndexRows(r => {
                                    const a = [...r]; [a[i-1], a[i]] = [a[i], a[i-1]]; return a;
                                  });
                                }} disabled={i===0} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↑</button>
                                <button onClick={() => {
                                  if (i === indexRows.length - 1) return;
                                  setIndexRows(r => {
                                    const a = [...r]; [a[i], a[i+1]] = [a[i+1], a[i]]; return a;
                                  });
                                }} disabled={i===indexRows.length-1} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↓</button>
                                <button onClick={() => {
                                  setIndexRows(r => {
                                    const a = [...r];
                                    a.splice(i + 1, 0, { sort_order: i + 1, axis_0: "", axis_1: "", axis_2: "" });
                                    return a;
                                  });
                                }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                              </div>
                            </td>
                            <td className="px-1 py-1"><input value={p.axis_0 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_0: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_0 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_0: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_1 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_1: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_2 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_2: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.note ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                            <td className="px-1 py-1 text-center">
                              <button onClick={() => setIndexRows(r => r.filter((_,j) => j !== i))}
                                className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">
                                削除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
'''
        src = src[:idx_start] + NEW_EDIT_IP + src[idx_end:]
        print("  OK: 編集 インデックスPGブロック刷新")

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

# ─────────────────────────────────────────────────────────
# [5] ビルド
# ─────────────────────────────────────────────────────────
print("=== [5] Next.js ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -25",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr)
    sys.exit(1)

print("=== [6] PM2 再起動 ===")
r = subprocess.run("pm2 restart machcore-web && pm2 ls", shell=True, capture_output=True, text=True)
print(r.stdout)

print("=== [7] git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: offset/index v1b - remove stale WO block, fix IP edit/ref" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
