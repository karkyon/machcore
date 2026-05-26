#!/usr/bin/env python3
"""fix_v98: edit/page.tsx と record/page.tsx のヘッダを print/page.tsx に合わせて統一"""
import subprocess, sys, os, re

ROOT = os.path.expanduser("~/projects/machcore")
def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def rep(content, old, new, label):
    if old not in content:
        print(f"WARN: {label} — 不一致"); return content
    print(f"OK: {label}"); return content.replace(old, new, 1)

# ─────────────────────────────────────────────────────────────────
# 統一ヘッダコンポーネント（print/page.tsxと同じ構造）
# 各ページで detail/d の変数名が違うので引数で渡す
# ─────────────────────────────────────────────────────────────────

# ① edit/page.tsx ヘッダ統一
# 現在のeditヘッダ: 黒ヘッダ(MC詳細ボタン+ダッシュボード) + 部品情報エリア(白帯)
# print/page.tsxと同じ構造にする（部品情報エリアを2行構成で統一）
EDIT = f"{ROOT}/apps/web/app/mc/[mc_id]/edit/page.tsx"
e = read(EDIT)

# edit の部品情報バー（現在は detail変数を使用）を print と同じ2行構成に統一
OLD_EDIT_INFO = """      {/* 部品情報バー */}
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-2.5 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1">
            <span className="font-mono text-teal-600 font-bold text-xl leading-none">{d.part.drawingNo}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
            {d.part.mainModel && <>
              <span className="text-slate-300 font-light">/</span>
              <span className="text-slate-500 font-medium leading-none">{d.part.mainModel}</span>
            </>}
            <div className="flex items-center gap-2 ml-2">
              {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
              <StatusBadge status={d.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(detail as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(detail as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? d.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
            {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
          </div>
        </div>
      )}"""

NEW_EDIT_INFO = """      {/* 部品情報バー */}
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
            {d.part.mainModel && <>
              <span className="text-slate-300 text-xl font-light">/</span>
              <span className="text-slate-500 text-lg font-medium leading-none">{d.part.mainModel}</span>
            </>}
            <div className="flex items-center gap-2 ml-2">
              {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
              <StatusBadge status={d.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(detail as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(detail as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? d.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
            {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
          </div>
        </div>
      )}"""

e = rep(e, OLD_EDIT_INFO, NEW_EDIT_INFO, "edit: 部品情報バー py統一")
write(EDIT, e)

# ② record/page.tsx ヘッダ統一
# 現在: 黒ヘッダ(MC詳細ボタン) + 部品情報バー(図番/名称/MCID/加工ID/Ver — print と違いVer表示・機械・mainModel欠如)
RECORD = f"{ROOT}/apps/web/app/mc/[mc_id]/record/page.tsx"
r = read(RECORD)

# 部品情報バーを print と同じ2行構成に差し替え
OLD_REC_INFO = """      {/* 部品情報バー */}
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-2 flex items-center gap-4 shrink-0 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 text-sm">{detail.part?.drawingNo ?? "—"}</span>
            <span className="text-slate-400">/</span>
            <span className="text-sm text-slate-600">{detail.part?.name ?? "—"}</span>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            <span>MCID: <span className="text-slate-700">{detail.legacyMcid ?? detail.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{detail.machiningId}</span></span>
            <span className="text-slate-400">|</span>
            <span>Ver: <span className="text-slate-700">{detail.version}</span></span>
          </div>
        </div>
      )}"""

NEW_REC_INFO = """      {/* 部品情報バー */}
      {detail && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{detail.part?.drawingNo ?? "—"}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{detail.part?.name ?? "—"}</span>
            {(detail as any).part?.mainModel && <>
              <span className="text-slate-300 text-xl font-light">/</span>
              <span className="text-slate-500 text-lg font-medium leading-none">{(detail as any).part.mainModel}</span>
            </>}
            <div className="flex items-center gap-2 ml-2">
              {(detail as any).machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{(detail as any).machine.machineCode}</span>}
              <StatusBadge status={detail.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {detail.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(detail as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(detail as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{detail.legacyMcid ?? detail.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{detail.machiningId}</span></span>
            {detail.part?.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{detail.part.partId}</span></span></>}
          </div>
        </div>
      )}"""

r = rep(r, OLD_REC_INFO, NEW_REC_INFO, "record: 部品情報バー print と統一")

# record の StatusBadge import 確認・追加
if 'StatusBadge' not in r:
    r = rep(r,
        'import { useAuth } from "@/contexts/AuthContext";',
        'import { StatusBadge } from "@/components/nc/StatusBadge";\nimport { useAuth } from "@/contexts/AuthContext";',
        "record: StatusBadge import追加")

write(RECORD, r)

print("\n--- build web ---")
r2 = subprocess.run(["pnpm","--filter","web","build"], cwd=ROOT, capture_output=True, text=True)
print(r2.stdout[-3000:])
if r2.stderr: print("STDERR:", r2.stderr[-2000:])
if r2.returncode != 0: print("BUILD FAILED (web)"); sys.exit(1)

print("\n--- build api ---")
r2 = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r2.stdout[-2000:])
if r2.stderr: print("STDERR:", r2.stderr[-1000:])
if r2.returncode != 0: print("BUILD FAILED (api)"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v98): edit/record ヘッダを print と統一"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v98")
