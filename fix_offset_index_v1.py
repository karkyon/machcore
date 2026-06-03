#!/usr/bin/env python3
"""
fix_offset_index_v1.py
ワークオフセット・インデックスPG 参照画面 + 編集画面 修正
"""
import subprocess, sys, shutil

BASE      = "/home/karkyon/projects/machcore"
REF_PAGE  = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

for f in [REF_PAGE, EDIT_PAGE]:
    shutil.copy2(f, f + ".bak2")

# ─────────────────────────────────────────────────────────
# [1] 参照画面 - ワークオフセット ヘッダー修正
# ─────────────────────────────────────────────────────────
print("=== [1] 参照画面 ワークオフセット修正 ===")
with open(REF_PAGE, "r") as f:
    src = f.read()

OLD_REF_WO_HDR = '''                  <thead className="bg-teal-50 text-teal-700">
                    <tr>{["G座標","X","Y","Z","A","R","備考"].map(h =>
                      <th key={h} className="px-3 py-2 text-center font-bold border-b border-teal-100">{h}</th>)}</tr>
                  </thead>'''

NEW_REF_WO_HDR = '''                  <thead className="bg-teal-50 text-teal-700 sticky top-0 z-10">
                    <tr>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">G</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">X</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">Y</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">Z</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">A / C</th>
                      <th className="px-3 py-2 text-center font-bold border-b border-teal-100 whitespace-nowrap">R / B</th>
                      <th className="px-3 py-2 text-left font-bold border-b border-teal-100 whitespace-nowrap">備考</th>
                    </tr>
                  </thead>'''

if OLD_REF_WO_HDR in src:
    src = src.replace(OLD_REF_WO_HDR, NEW_REF_WO_HDR)
    print("  OK: 参照 ワークオフセット ヘッダー修正")
else:
    print("  WARN: 参照 ワークオフセット ヘッダー が見つからない")

# ワークオフセット参照テーブルにスクロール対応・件数→レコード
OLD_REF_WO_WRAP = '''              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ワークオフセット ({d.workOffsets.length}件)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.workOffsets.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ワークオフセットデータがありません</div>
              ) : (
                <table className="w-full text-xs">'''

NEW_REF_WO_WRAP = '''              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600">ワークオフセット ({d.workOffsets.length}レコード)</span>
                <button onClick={() => router.push(`/mc/${mcId}/edit`)} className="text-xs text-teal-600 font-bold">✏️ 編集</button>
              </div>
              {d.workOffsets.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">ワークオフセットデータがありません</div>
              ) : (
                <div className="overflow-y-auto max-h-[55vh]">
                <table className="w-full text-xs">'''

if OLD_REF_WO_WRAP in src:
    src = src.replace(OLD_REF_WO_WRAP, NEW_REF_WO_WRAP)
    print("  OK: 参照 ワークオフセット ラベル/スクロール")
else:
    print("  WARN: 参照 WO ラップが見つからない")

# 対応する閉じタグを修正
OLD_REF_WO_END = '''              </table>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''
NEW_REF_WO_END = '''              </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''

if OLD_REF_WO_END in src:
    src = src.replace(OLD_REF_WO_END, NEW_REF_WO_END, 1)
    print("  OK: 参照 WO 閉じタグ修正")
else:
    print("  WARN: 参照 WO 閉じタグが見つからない")

# ─────────────────────────────────────────────────────────
# [2] 参照画面 - インデックスPG ヘッダー修正
# ─────────────────────────────────────────────────────────
print("=== [2] 参照画面 インデックスPG修正 ===")

OLD_REF_IP_HDR = '''              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
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
                  </thead>'''

NEW_REF_IP_HDR = '''              <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
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
                  </thead>'''

if OLD_REF_IP_HDR in src:
    src = src.replace(OLD_REF_IP_HDR, NEW_REF_IP_HDR)
    print("  OK: 参照 インデックスPG ヘッダー修正")
else:
    print("  WARN: 参照 インデックスPG ヘッダーが見つからない")

# 参照インデックスPGのデータ行 No. → sortOrder を axis0 へ (STEP/Nカラムはaxis0の値)
OLD_REF_IP_ROW = '''                        <td className="px-3 py-2 text-center font-mono">{p.sortOrder}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>'''

NEW_REF_IP_ROW = '''                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>'''

# STEP/N列はaxis0の値、第0軸もaxis0、第1軸axis1、第2軸axis2
# 実際のデータ行を正確に置換
OLD_REF_IP_ROW2 = '''                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 text-center font-mono">{p.sortOrder}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>'''

NEW_REF_IP_ROW2 = '''                      <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 font-mono font-bold text-teal-700">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis0 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis1 ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{p.axis2 ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{p.note ?? ""}</td>
                      </tr>'''

if OLD_REF_IP_ROW2 in src:
    src = src.replace(OLD_REF_IP_ROW2, NEW_REF_IP_ROW2)
    print("  OK: 参照 インデックスPG データ行修正")
else:
    print("  WARN: 参照 インデックスPG データ行が見つからない")

# インデックスPG参照の閉じタグ
OLD_REF_IP_END = '''            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}'''
NEW_REF_IP_END = '''                </div>
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}'''

if OLD_REF_IP_END in src:
    src = src.replace(OLD_REF_IP_END, NEW_REF_IP_END, 1)
    print("  OK: 参照 インデックスPG 閉じタグ修正")
else:
    print("  WARN: 参照 インデックスPG 閉じタグが見つからない")

with open(REF_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", REF_PAGE)

# ─────────────────────────────────────────────────────────
# [3] 編集画面 - ワークオフセット 全面刷新
# ─────────────────────────────────────────────────────────
# 列幅設計: 操作72 + G70 + X100 + Y100 + Z100 + A/C100 + R/B100 + 備考120 + 削除54 = 816px
print("=== [3] 編集画面 ワークオフセット刷新 ===")
with open(EDIT_PAGE, "r") as f:
    src = f.read()

OLD_EDIT_WO = '''            {/* ワークオフセット */}
            {activeSection === "offset" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ワークオフセット ({offsetRows.length}件)</span>
                    <button onClick={() => setOffsetRows(prev => [...prev, { g_code: `G${54 + prev.length}` }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["G座標","X","Y","Z","A","R",""].map(h =>
                        <th key={h} className="px-2 py-2 text-center font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {offsetRows.map((o, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1"><input value={o.g_code ?? o.gCode ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, g_code: e.target.value} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          {["x_offset","y_offset","z_offset","a_offset","r_offset"].map(k => (
                            <td key={k} className="px-2 py-1"><input type="number" step="0.001"
                              value={o[k] ?? o[k.replace("_offset", "Offset")] ?? ""}
                              onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                              className="w-20 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          ))}
                          <td className="px-2 py-1"><button onClick={() => setOffsetRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}'''

NEW_EDIT_WO = '''            {/* ワークオフセット */}
            {activeSection === "offset" && (
              <div className="max-w-[816px]">
                <div className="bg-white rounded-xl border border-slate-200">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between rounded-t-xl">
                    <span className="text-xs font-bold text-slate-600">ワークオフセット ({offsetRows.length}レコード)</span>
                    <div className="flex items-center gap-2">
                      <button onClick={async () => {
                        const token = sessionStorage.getItem("admin_token") || "";
                        try {
                          await mcApi.saveWorkOffsets(mcId, offsetRows.map((o: any) => ({
                            g_code:   o.g_code   ?? o.gCode   ?? "",
                            x_offset: o.x_offset != null && o.x_offset !== "" ? Number(o.x_offset) : undefined,
                            y_offset: o.y_offset != null && o.y_offset !== "" ? Number(o.y_offset) : undefined,
                            z_offset: o.z_offset != null && o.z_offset !== "" ? Number(o.z_offset) : undefined,
                            a_offset: o.a_offset != null && o.a_offset !== "" ? Number(o.a_offset) : undefined,
                            r_offset: o.r_offset != null && o.r_offset !== "" ? Number(o.r_offset) : undefined,
                            note:     o.note     ?? undefined,
                          })), token);
                          showToast("✅ ワークオフセットを保存しました");
                        } catch { showToast("❌ 保存に失敗しました"); }
                      }}
                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                        ✓ ワークオフセットを保存
                      </button>
                      <button onClick={() => setOffsetRows(prev => [...prev, { g_code: `G${54 + prev.length}` }])}
                        className="text-xs text-teal-600 font-bold">+ 追加</button>
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-[55vh]">
                    <table className="text-xs w-full border-collapse">
                      <colgroup>
                        <col style={{width:"72px"}}/>
                        <col style={{width:"70px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"120px"}}/>
                        <col style={{width:"54px"}}/>
                      </colgroup>
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>
                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">G</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">X</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">Y</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">Z</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">A / C</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">R / B</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">備考</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {offsetRows.map((o, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-1 py-1">
                              <div className="flex gap-0.5">
                                <button onClick={() => {
                                  if (i === 0) return;
                                  setOffsetRows(r => {
                                    const a = [...r]; [a[i-1], a[i]] = [a[i], a[i-1]]; return a;
                                  });
                                }} disabled={i===0} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↑</button>
                                <button onClick={() => {
                                  if (i === offsetRows.length - 1) return;
                                  setOffsetRows(r => {
                                    const a = [...r]; [a[i], a[i+1]] = [a[i+1], a[i]]; return a;
                                  });
                                }} disabled={i===offsetRows.length-1} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↓</button>
                                <button onClick={() => {
                                  setOffsetRows(r => {
                                    const a = [...r];
                                    a.splice(i + 1, 0, { g_code: "" });
                                    return a;
                                  });
                                }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                              </div>
                            </td>
                            <td className="px-1 py-1"><input value={o.g_code ?? o.gCode ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, g_code: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                            {["x_offset","y_offset","z_offset","a_offset","r_offset"].map(k => (
                              <td key={k} className="px-1 py-1"><input type="number" step="0.001"
                                value={o[k] ?? ""}
                                onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                            ))}
                            <td className="px-1 py-1"><input value={o.note ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                            <td className="px-1 py-1 text-center">
                              <button onClick={() => setOffsetRows(r => r.filter((_,j) => j !== i))}
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
            )}'''

if OLD_EDIT_WO in src:
    src = src.replace(OLD_EDIT_WO, NEW_EDIT_WO)
    print("  OK: 編集 ワークオフセット 全面刷新")
else:
    print("  WARN: 編集 ワークオフセット ブロックが見つからない")
    # コンテキスト表示
    idx = src.find("activeSection === \"offset\"")
    if idx != -1:
        print("  CONTEXT:", src[idx:idx+200])

# setOffsetRows のデータ読み込み変換（camelCase→snake_case）
OLD_OFFSET_LOAD = '''      setOffsetRows(d.workOffsets ?? []);'''
NEW_OFFSET_LOAD = '''      setOffsetRows((d.workOffsets ?? []).map((o: any) => ({
        g_code:   o.gCode   ?? o.g_code   ?? "",
        x_offset: o.xOffset != null ? String(o.xOffset) : (o.x_offset != null ? String(o.x_offset) : ""),
        y_offset: o.yOffset != null ? String(o.yOffset) : (o.y_offset != null ? String(o.y_offset) : ""),
        z_offset: o.zOffset != null ? String(o.zOffset) : (o.z_offset != null ? String(o.z_offset) : ""),
        a_offset: o.aOffset != null ? String(o.aOffset) : (o.a_offset != null ? String(o.a_offset) : ""),
        r_offset: o.rOffset != null ? String(o.rOffset) : (o.r_offset != null ? String(o.r_offset) : ""),
        note:     o.note    ?? "",
      })));'''

if OLD_OFFSET_LOAD in src:
    src = src.replace(OLD_OFFSET_LOAD, NEW_OFFSET_LOAD)
    print("  OK: setOffsetRows camelCase→snake_case変換追加")
else:
    print("  WARN: setOffsetRows が見つからない（既に変換済みか確認要）")

# ─────────────────────────────────────────────────────────
# [4] 編集画面 - インデックスPG 全面刷新
# ─────────────────────────────────────────────────────────
# 列幅設計: 操作72 + STEP/N90 + 第0軸240 + 第1軸240 + 第2軸200 + 備考120 + 削除54 = 1016px
print("=== [4] 編集画面 インデックスPG刷新 ===")

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
                    <tbody>
                      {indexRows.map((p, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1 text-center text-slate-400">{i+1}</td>
                          {["axis_0","axis_1","axis_2"].map(k => (
                            <td key={k} className="px-2 py-1"><input value={p[k] ?? p[k.replace("_","").replace("axis",k==="axis_0"?"axis0":k==="axis_1"?"axis1":"axis2")] ?? ""}
                              onChange={e => setIndexRows(r => r.map((x,j) => j===i ?'''

# まず末尾部分も含めた完全ブロックを探す
idx_start = src.find('            {/* インデックスプログラム */}\n            {activeSection === "index"')
if idx_start == -1:
    print("  WARN: インデックスPGブロック開始が見つからない")
else:
    # ブロック終了を探す
    # "            )}" が activeSection === "index" ブロックの終わり
    search_from = idx_start + 100
    depth = 0
    i = idx_start
    brace_count = 0
    # JSXブロック全体を取得するためにシンプルに次の activeSection or {/* を探す
    idx_end = src.find('\n            {/* ファイル', idx_start)
    if idx_end == -1:
        idx_end = src.find('\n          </div>\n\n          {/* ファイル', idx_start)
    if idx_end == -1:
        print("  WARN: インデックスPGブロック終了が見つからない")
    else:
        old_ip_block = src[idx_start:idx_end]
        new_ip_block = '''            {/* インデックスプログラム */}
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
            )}'''
        src = src[:idx_start] + new_ip_block + src[idx_end:]
        print("  OK: 編集 インデックスPG 全面刷新")

# setIndexRows のデータ読み込み変換
OLD_INDEX_LOAD = '''      setIndexRows(d.indexPrograms ?? []);'''
NEW_INDEX_LOAD = '''      setIndexRows((d.indexPrograms ?? []).map((p: any) => ({
        sort_order: p.sortOrder ?? p.sort_order ?? 0,
        axis_0:     p.axis0    ?? p.axis_0     ?? "",
        axis_1:     p.axis1    ?? p.axis_1     ?? "",
        axis_2:     p.axis2    ?? p.axis_2     ?? "",
        note:       p.note     ?? "",
      })));'''

if OLD_INDEX_LOAD in src:
    src = src.replace(OLD_INDEX_LOAD, NEW_INDEX_LOAD)
    print("  OK: setIndexRows camelCase→snake_case変換追加")
else:
    print("  WARN: setIndexRows が見つからない（既に変換済みか確認要）")

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

# ─────────────────────────────────────────────────────────
# [5] Next.js ビルド
# ─────────────────────────────────────────────────────────
print("=== [5] Next.js ビルド (apps/web) ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -20",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr)
    sys.exit(1)

# ─────────────────────────────────────────────────────────
# [6] PM2 再起動
# ─────────────────────────────────────────────────────────
print("=== [6] PM2 再起動 ===")
r = subprocess.run("pm2 restart machcore-web && pm2 ls", shell=True, capture_output=True, text=True)
print(r.stdout)
print("  OK")

# ─────────────────────────────────────────────────────────
# [7] git push
# ─────────────────────────────────────────────────────────
print("=== [7] git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: offset/index v1 - column names, save button, row ops, delete UI" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
