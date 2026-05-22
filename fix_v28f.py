#!/usr/bin/env python3
# coding: utf-8
import pathlib

edit = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/edit/page.tsx")
src = edit.read_text(encoding="utf-8")

# 壊れたツーリングセクションを正しい構造に置換
OLD_BROKEN = '''                  <div className="relative">
                    <textarea value={toolingText} onChange={e => setToolingText(e.target.value)}
                      onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-amber-500","bg-amber-100"); }}
                      onDragLeave={e => { e.currentTarget.classList.remove("border-amber-500","bg-amber-100"); }}
                      onDrop={e => {
                        e.preventDefault();
                        e.currentTarget.classList.remove("border-amber-500","bg-amber-100");
                        const file = e.dataTransfer.files[0];
                        if (file) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(file, "shift-jis"); }
                      }}
                      placeholder="ツーリングプログラムをここに貼り付け、またはファイルをドラッグ＆ドロップ..."
                      rows={6}
                      className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono focus:ring-2 focus:ring-amber-400 focus:outline-none resize-none" />
                  <div className="flex gap-2 mt-2">
                    <div className="flex items-center gap-2 mb-2">
                    <label className="px-3 py-1.5 bg-white border border-amber-400 text-amber-700 text-xs font-bold rounded cursor-pointer hover:bg-amber-50 transition-colors">
                      📂 ファイルを選択
                      <input type="file" accept=".min,.spf,.mpf,.nc,.cnc,.tap,.prg,.txt" className="hidden"
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (file) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(file, "shift-jis"); e.target.value = ""; }
                        }} />
                    </label>
                    <span className="text-[10px] text-amber-600">またはテキストを貼り付け / ファイルをD&D</span>
                  </div>
                  <button onClick={handleParseTooling}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-4 py-2 rounded-lg font-bold">解析・プレビュー</button>'''

NEW_FIXED = '''                  <textarea value={toolingText} onChange={e => setToolingText(e.target.value)}
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-amber-500","bg-amber-100"); }}
                    onDragLeave={e => { e.currentTarget.classList.remove("border-amber-500","bg-amber-100"); }}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-amber-500","bg-amber-100");
                      const f = e.dataTransfer.files[0];
                      if (f) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(f, "shift-jis"); }
                    }}
                    placeholder="ツーリングプログラムをここに貼り付け、またはファイルをドラッグ＆ドロップ..."
                    rows={6}
                    className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono focus:ring-2 focus:ring-amber-400 focus:outline-none resize-none" />
                  <div className="flex items-center gap-2 mt-2 mb-2">
                    <label className="px-3 py-1.5 bg-white border border-amber-400 text-amber-700 text-xs font-bold rounded cursor-pointer hover:bg-amber-50 transition-colors">
                      ファイルを選択
                      <input type="file" accept=".min,.spf,.mpf,.nc,.cnc,.tap,.prg,.txt" className="hidden"
                        onChange={e => {
                          const f2 = e.target.files?.[0];
                          if (f2) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(f2, "shift-jis"); e.target.value = ""; }
                        }} />
                    </label>
                    <span className="text-[10px] text-amber-600">またはテキストを貼り付け / D&D</span>
                  </div>
                  <div className="flex gap-2">
                  <button onClick={handleParseTooling}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-4 py-2 rounded-lg font-bold">解析・プレビュー</button>'''

if OLD_BROKEN in src:
    src = src.replace(OLD_BROKEN, NEW_FIXED)
    print("OK: ツーリングJSX構造修正")
else:
    print("WARN: パターン不一致")
    # デバッグ用: relativeを含む行を表示
    for i, l in enumerate(src.splitlines(), 1):
        if 'relative' in l or 'flex gap-2 mt-2' in l or 'flex items-center gap-2 mb-2' in l:
            print(f"L{i}: {l}")

edit.write_text(src, encoding="utf-8")
print("完了")