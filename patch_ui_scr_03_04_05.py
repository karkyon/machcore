#!/usr/bin/env python3
"""
MachCore UI改善パッチ
対象: SCR-03 (edit), SCR-04 (print), SCR-05 (record)
変更: バックボタン強化 / タブナビ追加 / ロック画面刷新
"""
import shutil
from pathlib import Path

BASE = Path("/home/karkyon/projects/machcore/apps/web/app/nc/[nc_id]")
FILES = {
    "edit":   BASE / "edit/page.tsx",
    "print":  BASE / "print/page.tsx",
    "record": BASE / "record/page.tsx",
}

def backup(p: Path):
    bak = p.with_suffix(".tsx.bak_ui_improve")
    if not bak.exists():
        shutil.copy2(p, bak)
        print(f"  backup: {bak.name}")

def apply_patch(path: Path, replacements: list, name: str):
    if not path.exists():
        print(f"  X {name}: ファイルが存在しません -> {path}")
        return
    content = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  OK {name}: パッチ適用")
        else:
            print(f"  SKIP {name}: 対象文字列が見つかりません")
    path.write_text(content, encoding="utf-8")

# ══════════════════════════════════════════════════════════════
# SCR-03 edit/page.tsx
# ══════════════════════════════════════════════════════════════
print("=== SCR-03 edit/page.tsx ===")
p = FILES["edit"]
backup(p)

apply_patch(p, [(
    '          className="text-slate-400 hover:text-white text-xs transition-colors"\n        >\n          <- NC\u8a73\u7d30\n        </button>',
    '          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-sky-900 border border-slate-600 hover:border-sky-500 rounded-lg text-xs font-medium text-sky-300 hover:text-sky-200 transition-colors"\n        >\n          <span className="w-4 h-4 rounded-full bg-sky-800 flex items-center justify-center text-[10px]">\u2190</span>\n          NC\u8a73\u7d30\u306b\u623b\u308b\n        </button>'
)], "edit[1] back button")

apply_patch(p, [(
    """        {/* \u30e1\u30a4\u30f3\u30b3\u30f3\u30c6\u30f3\u30c4 */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="max-w-2xl mx-auto">

            {/* \u30ed\u30c3\u30af\u72b6\u614b\u30d0\u30ca\u30fc */}
            {!isAuthenticated && (
              <div className="mb-5 bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="text-amber-800 font-bold text-sm">\U0001f512 \u7de8\u96c6\u306b\u306fWork Session\u8a8d\u8a3c\u304c\u5fc5\u8981\u3067\u3059</p>
                  <p className="text-amber-600 text-xs mt-0.5">\u62c5\u5f53\u8005\u3092\u9078\u629e\u3057\u3066\u30d1\u30b9\u30ef\u30fc\u30c9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044</p>
                </div>
                <button
                  onClick={() => setAuthOpen(true)}
                  className="bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
                >
                  \u3053\u306e\u4f5c\u696d\u3092\u958b\u59cb\u3059\u308b
                </button>
              </div>
            )}

            {/* \u30a8\u30e9\u30fc\u8868\u793a */}
            {saveError && (""",

    """        {/* \u30bf\u30d6\u30ca\u30d3\u30b2\u30fc\u30b7\u30e7\u30f3 */}
        <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
          {([
            { href: `/nc/${ncId}`,        label: "NC\u8a73\u7d30",    icon: "\U0001f4cb", active: false, dot: "" },
            { href: `/nc/${ncId}/edit`,   label: "\u5909\u66f4\u30fb\u767b\u9332", icon: "\u270f\ufe0f",  active: true,  dot: isAuthenticated ? "red" : "" },
            { href: `/nc/${ncId}/print`,  label: "\u6bb5\u53d6\u30b7\u30fc\u30c8", icon: "\U0001f5a8",  active: false, dot: "" },
            { href: `/nc/${ncId}/record`, label: "\u4f5c\u696d\u8a18\u9332",  icon: "\u23f1",  active: false, dot: "" },
          ] as {href:string;label:string;icon:string;active:boolean;dot:string}[]).map(tab => (
            <button key={tab.href} onClick={() => router.push(tab.href)}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active ? "text-sky-400 border-sky-400" : "text-slate-400 hover:text-slate-200 border-transparent"
              }`}>
              {tab.dot === "red" && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />}
              {tab.icon} {tab.label}
            </button>
          ))}
        </nav>

        {/* \u30e1\u30a4\u30f3\u30b3\u30f3\u30c6\u30f3\u30c4 */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="max-w-2xl mx-auto">

            {/* \u8a8d\u8a3c\u524d\u30ed\u30c3\u30af\u30ab\u30fc\u30c9 */}
            {!isAuthenticated && (
              <div className="flex flex-col items-center justify-center py-12 gap-5 text-center">
                <div className="w-14 h-14 rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#A32D2D" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </div>
                <div>
                  <div className="text-base font-medium text-slate-800">\u5909\u66f4\u30fb\u767b\u9332 \u2014 \u4f5c\u696d\u958b\u59cb\u524d</div>
                  <div className="text-sm text-slate-500 mt-1 max-w-xs">\u5909\u66f4\u30fb\u767b\u9332\u3092\u884c\u3046\u306b\u306f\u62c5\u5f53\u8005\u306e\u78ba\u8a8d\uff08\u30d1\u30b9\u30ef\u30fc\u30c9\uff09\u304c\u5fc5\u8981\u3067\u3059\u3002</div>
                </div>
                {d && (
                  <div className="w-full max-w-sm opacity-50 pointer-events-none rounded-xl border border-slate-200 overflow-hidden text-xs">
                    <div className="bg-slate-100 text-slate-500 text-[10px] font-medium px-3 py-2">\u73fe\u5728\u306e\u30c7\u30fc\u30bf</div>
                    <div className="grid grid-cols-3 divide-x divide-slate-100">
                      <div className="p-2.5 border-b border-slate-100"><div className="text-slate-400">\u6a5f\u68b0</div><div className="font-medium text-slate-700">{d.machineName ?? "\u2014"}</div></div>
                      <div className="p-2.5 border-b border-slate-100"><div className="text-slate-400">\u30d5\u30a1\u30a4\u30eb\u540d</div><div className="font-mono font-medium text-slate-700">{d.fileName ?? "\u2014"}</div></div>
                      <div className="p-2.5 border-b border-slate-100"><div className="text-slate-400">\u52a0\u5de5\u6642\u9593</div><div className="font-mono font-medium text-slate-700">{d.machiningTime != null ? `${d.machiningTime} \u5206` : "\u2014"}</div></div>
                    </div>
                    <div className="p-2.5"><div className="text-slate-400">\u5099\u8003</div><div className="text-slate-600 truncate">{d.clampNote ? d.clampNote.slice(0, 40) + (d.clampNote.length > 40 ? "\u2026" : "") : "\u2014"}</div></div>
                  </div>
                )}
                <button onClick={() => setAuthOpen(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-blue-700 hover:bg-blue-800 text-white rounded-xl text-sm font-medium transition-colors">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  \u3053\u306e\u4f5c\u696d\u3092\u958b\u59cb\u3059\u308b\uff08\u62c5\u5f53\u8005\u78ba\u8a8d\uff09
                </button>
                <div className="text-xs text-slate-400">\u62c5\u5f53\u8005\u306e\u9078\u629e\u3068\u30d1\u30b9\u30ef\u30fc\u30c9\u78ba\u8a8d\u5f8c\u306b\u7de8\u96c6\u3067\u304d\u307e\u3059</div>
              </div>
            )}

            {/* \u30a8\u30e9\u30fc\u8868\u793a */}
            {isAuthenticated && saveError && ("""
)], "edit[2] lock card + tabs")

apply_patch(p, [(
    """            {/* \u30a8\u30e9\u30fc\u8868\u793a */}
            {saveError && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-600 text-sm">
                \u26a0\ufe0f {saveError}
              </div>
            )}

            {/* \u7de8\u96c6\u30d5\u30a9\u30fc\u30e0 */}
            <div className={`bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${!isAuthenticated ?""",

    """            {/* \u30a8\u30e9\u30fc\u8868\u793a */}
            {isAuthenticated && saveError && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-600 text-sm">
                \u26a0\ufe0f {saveError}
              </div>
            )}

            {/* \u7de8\u96c6\u30d5\u30a9\u30fc\u30e0\uff08\u8a8d\u8a3c\u5f8c\u306e\u307f\u8868\u793a\uff09 */}
            {isAuthenticated && (
            <div className={`bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${!isAuthenticated ?"""
)], "edit[3] form auth-guard")

apply_patch(p, [(
    """          </div>
        </div>

      {/* \u8a8d\u8a3c\u30e2\u30fc\u30c0\u30eb */}
      {authOpen && (""",

    """          </div>
            )}
        </div>

      {/* \u8a8d\u8a3c\u30e2\u30fc\u30c0\u30eb */}
      {authOpen && ("""
)], "edit[4] form wrapper close")

# ══════════════════════════════════════════════════════════════
# SCR-04 print/page.tsx
# ══════════════════════════════════════════════════════════════
print("\n=== SCR-04 print/page.tsx ===")
p = FILES["print"]
backup(p)

apply_patch(p, [(
    """        <button
          onClick={() => router.push(`/nc/${ncId}`)}
          className="text-slate-400 hover:text-white text-sm transition-colors"
        >
          \u2190 \u623b\u308b
        </button>""",

    """        <button
          onClick={() => router.push(`/nc/${ncId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-amber-900 border border-slate-600 hover:border-amber-500 rounded-lg text-xs font-medium text-amber-300 hover:text-amber-200 transition-colors"
        >
          <span className="w-4 h-4 rounded-full bg-amber-900 flex items-center justify-center text-[10px]">\u2190</span>
          NC\u8a73\u7d30\u306b\u623b\u308b
        </button>"""
)], "print[1] back button")

apply_patch(p, [(
    """      {/* \u30e1\u30a4\u30f3\u30b3\u30f3\u30c6\u30f3\u30c4 */}
      <div className="flex-1 overflow-y-auto p-5">""",

    """      {/* \u30bf\u30d6\u30ca\u30d3\u30b2\u30fc\u30b7\u30e7\u30f3 */}
      <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
        {([
          { href: `/nc/${ncId}`,        label: "NC\u8a73\u7d30",    icon: "\U0001f4cb", active: false, dot: "" },
          { href: `/nc/${ncId}/edit`,   label: "\u5909\u66f4\u30fb\u767b\u9332", icon: "\u270f\ufe0f",  active: false, dot: "" },
          { href: `/nc/${ncId}/print`,  label: "\u6bb5\u53d6\u30b7\u30fc\u30c8", icon: "\U0001f5a8",  active: true,  dot: isAuthenticated ? "amber" : "" },
          { href: `/nc/${ncId}/record`, label: "\u4f5c\u696d\u8a18\u9332",  icon: "\u23f1",  active: false, dot: "" },
        ] as {href:string;label:string;icon:string;active:boolean;dot:string}[]).map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              tab.active ? "text-amber-400 border-amber-400" : "text-slate-400 hover:text-slate-200 border-transparent"
            }`}>
            {tab.dot === "amber" && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />}
            {tab.icon} {tab.label}
          </button>
        ))}
      </nav>

      {/* \u30e1\u30a4\u30f3\u30b3\u30f3\u30c6\u30f3\u30c4 */}
      <div className="flex-1 overflow-y-auto p-5">"""
)], "print[2] tabs")

apply_patch(p, [(
    """                <button
                  onClick={() => { setAuthSessionType("setup_print"); setAuthModalOpen(true); }}
                  className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-xl transition-colors"
                >
                  \U0001f510 \u3053\u306e\u4f5c\u696d\u3092\u958b\u59cb\u3059\u308b
                </button>""",

    """                <button
                  onClick={() => { setAuthSessionType("setup_print"); setAuthModalOpen(true); }}
                  className="w-full py-3 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  \u3053\u306e\u4f5c\u696d\u3092\u958b\u59cb\u3059\u308b\uff08\u62c5\u5f53\u8005\u78ba\u8a8d\uff09
                </button>
                <p className="text-xs text-slate-400 text-center mt-2">\u62c5\u5f53\u8005\u78ba\u8a8d\u5f8c\u306b\u5370\u5237\u30fbUSB\u66f8\u304d\u51fa\u3057\u304c\u3067\u304d\u307e\u3059</p>"""
)], "print[3] lock button")

# ══════════════════════════════════════════════════════════════
# SCR-05 record/page.tsx
# ══════════════════════════════════════════════════════════════
print("\n=== SCR-05 record/page.tsx ===")
p = FILES["record"]
backup(p)

content = p.read_text(encoding="utf-8")
if "text-sky-500 text-sm hover:underline shrink-0" in content:
    apply_patch(p, [(
        '    <button onClick={() => router.push(`/nc/${ncId}`)}\n          className="text-sky-500 text-sm hover:underline shrink-0">\n          \u2190 NC\u8a73\u7d30\n        </button>',
        '    <button onClick={() => router.push(`/nc/${ncId}`)}\n          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-emerald-900 border border-slate-600 hover:border-emerald-500 rounded-lg text-xs font-medium text-emerald-300 hover:text-emerald-200 transition-colors shrink-0">\n          <span className="w-4 h-4 rounded-full bg-emerald-900 flex items-center justify-center text-[10px]">\u2190</span>\n          NC\u8a73\u7d30\u306b\u623b\u308b\n        </button>'
    )], "record[1] back button")
else:
    print("  SKIP record[1]: back button class が想定と異なります")

apply_patch(p, [(
    "      {/* \u4e0a\u30da\u30a4\u30f3: \u904e\u53bb\u8a18\u9332\u4e00\u89a7 */}",

    """      {/* \u30bf\u30d6\u30ca\u30d3\u30b2\u30fc\u30b7\u30e7\u30f3 */}
      <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
        {([
          { href: `/nc/${ncId}`,        label: "NC\u8a73\u7d30",    icon: "\U0001f4cb", active: false, dot: "" },
          { href: `/nc/${ncId}/edit`,   label: "\u5909\u66f4\u30fb\u767b\u9332", icon: "\u270f\ufe0f",  active: false, dot: "" },
          { href: `/nc/${ncId}/print`,  label: "\u6bb5\u53d6\u30b7\u30fc\u30c8", icon: "\U0001f5a8",  active: false, dot: "" },
          { href: `/nc/${ncId}/record`, label: "\u4f5c\u696d\u8a18\u9332",  icon: "\u23f1",  active: true,  dot: isAuthenticated ? "green" : "" },
        ] as {href:string;label:string;icon:string;active:boolean;dot:string}[]).map(tab => (
          <button key={tab.href} onClick={() => router.push(tab.href)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              tab.active ? "text-emerald-400 border-emerald-400" : "text-slate-400 hover:text-slate-200 border-transparent"
            }`}>
            {tab.dot === "green" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
            {tab.icon} {tab.label}
          </button>
        ))}
      </nav>

      {/* \u4e0a\u30da\u30a4\u30f3: \u904e\u53bb\u8a18\u9332\u4e00\u89a7 */}"""
)], "record[2] tabs")

apply_patch(p, [(
    """        {/* \u4e0b\u30da\u30a4\u30f3: \u5165\u529b\u30d5\u30a9\u30fc\u30e0 */}
        <div className={`flex-1 overflow-y-auto transition-opacity ${
          isAuthenticated ? "opacity-100" : "opacity-50 pointer-events-none select-none"
        }`}>""",

    """        {/* \u8a8d\u8a3c\u524d\u30ed\u30c3\u30af\u30ab\u30fc\u30c9 */}
        {!isAuthenticated && (
          <div className="mx-5 my-4 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 flex flex-col items-center justify-center py-10 gap-4 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B6D11" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
            </div>
            <div>
              <div className="text-sm font-medium text-slate-800">\u4f5c\u696d\u8a18\u9332 \u2014 \u4f5c\u696d\u958b\u59cb\u524d</div>
              <div className="text-xs text-slate-500 mt-1 max-w-xs">\u6bb5\u53d6\u30fb\u52a0\u5de5\u6642\u9593\u3001\u30ef\u30fc\u30af\u6570\u3092\u8a18\u9332\u3059\u308b\u306b\u306f\u62c5\u5f53\u8005\u306e\u78ba\u8a8d\u304c\u5fc5\u8981\u3067\u3059\u3002</div>
            </div>
            <button onClick={() => setShowAuthModal(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-sm font-medium transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              \u3053\u306e\u4f5c\u696d\u3092\u958b\u59cb\u3059\u308b\uff08\u62c5\u5f53\u8005\u78ba\u8a8d\uff09
            </button>
            <div className="text-xs text-slate-400">\u62c5\u5f53\u8005\u306e\u9078\u629e\u3068\u30d1\u30b9\u30ef\u30fc\u30c9\u78ba\u8a8d\u5f8c\u306b\u8a18\u9332\u3092\u5165\u529b\u30fb\u7de8\u96c6\u3067\u304d\u307e\u3059</div>
          </div>
        )}

        {/* \u4e0b\u30da\u30a4\u30f3: \u5165\u529b\u30d5\u30a9\u30fc\u30e0 */}
        <div className={`flex-1 overflow-y-auto transition-opacity ${
          isAuthenticated ? "opacity-100" : "opacity-50 pointer-events-none select-none"
        }`}>"""
)], "record[3] lock card")

print("\n=== 完了 ===")
print("次のコマンドを実行してください:")
print("  cd ~/projects/machcore && bash dev.sh")
