#!/usr/bin/env python3
"""
fix_v92: 新規登録→段取シート遷移を ?from=new で判定
① mc/new/page.tsx: router.push に ?from=new を付加
② mc/[mc_id]/print/page.tsx: isNew→isNewEntry(from=new)でタブ制御
   タブ非活性は isNewEntry のみ。isNew(status)は印刷ボタンラベルにのみ使用
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

# ① mc/new/page.tsx: ?from=new を付加
NEW_PAGE = f"{ROOT}/apps/web/app/mc/new/page.tsx"
p = read(NEW_PAGE)
p = rep(p,
    "router.push(`/mc/${d.mc_id}/print`);",
    "router.push(`/mc/${d.mc_id}/print?from=new`);",
    "mc/new: router.push に ?from=new 付加")
write(NEW_PAGE, p)

# ② mc/[mc_id]/print/page.tsx: useSearchParams追加 + isNewEntry判定
PRINT = f"{ROOT}/apps/web/app/mc/[mc_id]/print/page.tsx"
p = read(PRINT)

# useSearchParams import追加
p = rep(p,
    'import { useParams, useRouter } from "next/navigation";',
    'import { useParams, useRouter, useSearchParams } from "next/navigation";',
    "print: useSearchParams import追加")

# useSearchParams使用 + isNewEntry定義（useRouter直後）
p = rep(p,
    "  const router = useRouter();\n\n  const [nc, setNc]",
    "  const router = useRouter();\n  const searchParams = useSearchParams();\n  // 新規登録画面から来た場合のみタブ非活性（マシニングデータ未登録のため）\n  const isNewEntry = searchParams.get('from') === 'new';\n\n  const [nc, setNc]",
    "print: isNewEntry定義")

# タブ: MC詳細 — false→isNewEntry
p = rep(p,
    'onClick={() => router.push(`/mc/${mcId}`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (false ?',
    'onClick={() => !isNewEntry && router.push(`/mc/${mcId}`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ?',
    "print: タブ MC詳細 isNewEntry制御")

# タブ: 変更・登録
p = rep(p,
    'onClick={() => router.push(`/mc/${mcId}/edit`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (false ?',
    'onClick={() => !isNewEntry && router.push(`/mc/${mcId}/edit`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ?',
    "print: タブ 変更登録 isNewEntry制御")

# タブ: 作業記録
p = rep(p,
    'onClick={() => router.push(`/mc/${mcId}/record`)}\n          className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">',
    'onClick={() => !isNewEntry && router.push(`/mc/${mcId}/record`)}\n          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + (isNewEntry ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>',
    "print: タブ 作業記録 isNewEntry制御")

# ヘッダー← MC詳細ボタン
p = rep(p,
    'onClick={() => router.push(`/mc/${mcId}`)}\n          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${false ?',
    'onClick={() => !isNewEntry && router.push(`/mc/${mcId}`)}\n          disabled={isNewEntry}\n          className={`inline-flex items-center gap-2 px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors shrink-0 ${isNewEntry ?',
    "print: ヘッダー← MC詳細 isNewEntry制御")

write(PRINT, p)

# Suspense でuseSearchParamsをラップする必要がある場合の確認
# Next.js 13+ではuseSearchParamsはSuspenseが必要な場合あり
# print/page.tsxがexport defaultで直接返している場合はSuspenseでラップ
# 現在のコードはexport defaultで直接返しているのでSuspenseでラップ
p = read(PRINT)
if 'export default function McPrintPage' in p and 'Suspense' not in p:
    p = rep(p,
        '"use client";\nimport { useState, useEffect, useRef, useCallback } from "react";\nimport { useParams, useRouter, useSearchParams } from "next/navigation";',
        '"use client";\nimport { useState, useEffect, useRef, useCallback, Suspense } from "react";\nimport { useParams, useRouter, useSearchParams } from "next/navigation";',
        "print: Suspense import追加")
    # 関数名変更してSuspenseでラップ
    p = rep(p,
        'export default function McPrintPage() {',
        'function McPrintPageInner() {',
        "print: 関数名をInnerに変更")
    # ファイル末尾にexport defaultを追加
    p = p.rstrip() + '\n\nexport default function McPrintPage() {\n  return (\n    <Suspense fallback={<div className="flex items-center justify-center h-screen text-slate-400">読み込み中…</div>}>\n      <McPrintPageInner />\n    </Suspense>\n  );\n}\n'
    write(PRINT, p)
    print("OK: print: Suspenseラップ追加")

print("\n--- build web ---")
r = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-3000:])
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
subprocess.run(["git","commit","-m","fix(v92): 新規登録from=newでタブ制御・部品検索からは全活性"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v92")
