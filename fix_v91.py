#!/usr/bin/env python3
"""
fix_v91: mc/[mc_id]/print/page.tsx
① isNew=false（リピート）時：タブ・ヘッダーボタン 全活性に戻す
② 認証前画面（未認証）：オプションチェックボックスブロック非表示
③ 認証後画面（印刷ボタン表示）：同じオプション（図を含める のみ、isNew=falseでは+参考出力）を表示
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def rep(content, old, new, label):
    if old not in content:
        print(f"WARN: {label} — 不一致"); return content
    print(f"OK: {label}"); return content.replace(old, new, 1)

PRINT = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page.tsx"
p = read(PRINT)

# ① タブのisNew非活性を全解除（リピートでも全活性）
# MC詳細タブ
p = rep(p,
  'onClick={() => !isNew && router.push(`/mc/${mcId}`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>',
  'onClick={() => router.push(`/mc/${mcId}`)}\n          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">',
  "タブ:MC詳細 isNew非活性除去")

# 変更・登録タブ
p = rep(p,
  'onClick={() => !isNew && router.push(`/mc/${mcId}/edit`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ?',
  'onClick={() => router.push(`/mc/${mcId}/edit`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (false ?',
  "タブ:変更登録 isNew非活性除去")

# 作業記録タブ
p = rep(p,
  'onClick={() => !isNew && router.push(`/mc/${mcId}/record`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNew ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>',
  'onClick={() => router.push(`/mc/${mcId}/record`)}\n          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">',
  "タブ:作業記録 isNew非活性除去")

# ヘッダー← MC詳細ボタン
p = rep(p,
  'onClick={() => !isNew && router.push(`/mc/${mcId}`)}\n          disabled={isNew}\n          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${isNew ?',
  'onClick={() => router.push(`/mc/${mcId}`)}\n          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${false ?',
  "ヘッダー:← MC詳細 isNew非活性除去")

# ② 認証前のオプションチェックボックスブロック削除
# 現在の認証前画面に機械/主Oナンバ/CT/ツーリング情報 + オプションチェック + 「この作業を開始する」がある
# オプションチェックのブロックのみ非表示に（isNew判定込みのブロック全体）
OLD_OPT_BLOCK = '''              {/* オプション */}
              <div className="mb-5 border border-slate-100 rounded-xl overflow-hidden">
                <div className="px-5 py-3 bg-slate-50 border-b border-slate-100">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">段取シート発行オプション</span>
                </div>
                <div className="px-5 py-4 space-y-3">
                  <label className="flex items-center gap-3 text-sm cursor-pointer">
                    <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                      className="accent-teal-600 w-4 h-4" />
                    <span className="text-slate-700">図を含める</span>
                  </label>
                  {!isNew && (
                    <>
                      {([
                        ["ツーリングリストを含める", includeTooling, setIncludeTooling],
                        ["クランプ情報を含める",     includeClamp,   setIncludeClamp],
                        ["ワークオフセットを含める", includeWorkOffsets, setIncludeWorkOffsets],
                        ["インデックスプログラムを含める", includeIndexPrograms, setIncludeIndexPrograms],
                      ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
                        <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                          <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                            className="accent-teal-600 w-4 h-4" />
                          <span className="text-slate-700">{label}</span>
                        </label>
                      ))}
                    </>
                  )}
                </div>
                {!isNew && (
                  <div className="px-5 py-3 border-t border-slate-100">
                    <label className="flex items-center gap-3 text-sm cursor-pointer">
                      <input type="checkbox" checked={isReference} onChange={e => setIsReference(e.target.checked)}
                        className="accent-amber-500 w-4 h-4" />
                      <span className="text-amber-700 font-bold">参考出力（生産に使用しない・回収不要）</span>
                    </label>
                    {isReference && <p className="text-[11px] text-amber-600 mt-1 ml-7">参考出力はダッシュボードの未回収一覧に表示されません</p>}
                  </div>
                )}
              </div>'''

# このブロックは認証前に表示されていた、削除（認証後に移動）
p = rep(p, OLD_OPT_BLOCK, '', "認証前オプションブロック削除")

# ③ 認証後の印刷ボタン上にオプションブロックを追加
# 現在の認証後ブロック先頭（段取シート発行オプション → ボタン）
OLD_AUTH_BTN = '''              <div className="px-5 py-4 pb-6 flex flex-col gap-4 border-t border-slate-100 mt-2">
                <button onClick={handlePrint} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : isNew ? "📄 プレビュー（透かし入り・記録なし）" : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>
                <button onClick={handleDirectPrint} disabled={directPrinting}
                  className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
                  {directPrinting ? "送信中..." : "🖨 プリンタに直接印刷"}
                </button>
              </div>'''

NEW_AUTH_BTN = '''              {/* 認証後オプション */}
              <div className="px-5 py-4 border-t border-slate-100 space-y-3">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">段取シート発行オプション</p>
                <label className="flex items-center gap-3 text-sm cursor-pointer">
                  <input type="checkbox" checked={includeDrawings} onChange={e => setIncludeDrawings(e.target.checked)}
                    className="accent-teal-600 w-4 h-4" />
                  <span className="text-slate-700">図を含める</span>
                </label>
                {!isNew && (
                  <>
                    {([
                      ["ツーリングリストを含める", includeTooling, setIncludeTooling],
                      ["クランプ情報を含める",     includeClamp,   setIncludeClamp],
                      ["ワークオフセットを含める", includeWorkOffsets, setIncludeWorkOffsets],
                      ["インデックスプログラムを含める", includeIndexPrograms, setIncludeIndexPrograms],
                    ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
                      <label key={label} className="flex items-center gap-3 text-sm cursor-pointer">
                        <input type="checkbox" checked={val} onChange={e => setter(e.target.checked)}
                          className="accent-teal-600 w-4 h-4" />
                        <span className="text-slate-700">{label}</span>
                      </label>
                    ))}
                    <div className="pt-2 border-t border-slate-100">
                      <label className="flex items-center gap-3 text-sm cursor-pointer">
                        <input type="checkbox" checked={isReference} onChange={e => setIsReference(e.target.checked)}
                          className="accent-amber-500 w-4 h-4" />
                        <span className="text-amber-700 font-bold">参考出力（生産に使用しない・回収不要）</span>
                      </label>
                      {isReference && <p className="text-[11px] text-amber-600 mt-1 ml-7">参考出力はダッシュボードの未回収一覧に表示されません</p>}
                    </div>
                  </>
                )}
              </div>
              <div className="px-5 py-4 pb-6 flex flex-col gap-4 border-t border-slate-100">
                <button onClick={handlePrint} disabled={printing}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-300 text-white font-bold py-3.5 rounded-xl text-sm">
                  {printing ? "PDF生成中..." : isNew ? "📄 プレビュー（透かし入り・記録なし）" : "📄 PDFプレビュー（ブラウザで開く）"}
                </button>
                <button onClick={handleDirectPrint} disabled={directPrinting}
                  className="w-full bg-slate-700 hover:bg-slate-800 disabled:bg-slate-400 text-white font-bold py-3.5 rounded-xl text-sm">
                  {directPrinting ? "送信中..." : "🖨 プリンタに直接印刷"}
                </button>
              </div>'''

p = rep(p, OLD_AUTH_BTN, NEW_AUTH_BTN, "認証後オプションブロック追加")

write(PRINT, p)

print("\n--- build web ---")
r = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-3000:]); 
if r.stderr: print("STDERR:", r.stderr[-2000:])
if r.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-2000:])
if r.stderr: print("STDERR:", r.stderr[-1500:])
if r.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v91): リピート時タブ活性化+オプション認証後表示に移動"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v91")
