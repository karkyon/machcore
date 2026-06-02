#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_tc_modal_v5.py
修正点:
1. TimecardModal の machineCode を選択中機械から解決（detail.machine固定→machines.find）
2. TCバーを量産ブロックの下に移動
"""
import subprocess, shutil, os, sys

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"
REPO   = "/home/karkyon/projects/machcore"

shutil.copy(TARGET, TARGET + ".bak_v5")

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

print(f"元ファイル: {len(src.splitlines())}行")
errors = []

# ══════════════════════════════════════════════════════════
# STEP1: TCバーを段取・量産の間から量産ブロックの下に移動
# 段取・量産の間のTCバーを削除
# ══════════════════════════════════════════════════════════
OLD1 = '''              {/* 機械タイムカード参照バー（段取・量産共通） */}
              {detail?.machine && (
                <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0 flex items-center gap-4 flex-wrap">
                    <span className="text-xs font-bold text-slate-600">&#128197; 機械タイムカード</span>
                    {setupKadouMin !== null && (
                      <span className="text-xs text-blue-700 font-bold bg-blue-50 px-2 py-0.5 rounded">{"段取稼働: " + Math.floor(setupKadouMin/60) + "H " + (setupKadouMin%60) + "M"}</span>
                    )}
                    {machKadouMin !== null && (
                      <span className="text-xs text-green-700 font-bold bg-green-50 px-2 py-0.5 rounded">{"量産稼働: " + Math.floor(machKadouMin/60) + "H " + (machKadouMin%60) + "M"}</span>
                    )}
                    {setupKadouMin === null && machKadouMin === null && (
                      <span className="text-xs text-slate-400">タイムカードを参照して稼働時間を確認できます</span>
                    )}
                  </div>
                  <button type="button" onClick={() => setTcModalOpen(true)}
                    className="shrink-0 flex items-center gap-1.5 text-xs px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                    タイムカード参照
                  </button>
                </div>
              )}

              {/* 量産グループ */}'''
NEW1 = '''              {/* 量産グループ */}'''
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    print("✅ STEP1: 段取・量産間のTCバー削除")
else:
    errors.append("STEP1: 段取・量産間のTCバーが見つかりません")

# ══════════════════════════════════════════════════════════
# STEP2: 量産ブロックの閉じタグの後にTCバーを挿入
# 量産グループ </div> の後 → プログラムブロックの前
# ══════════════════════════════════════════════════════════
OLD2 = '''              {/* プログラム */}
              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">'''
NEW2 = '''              {/* 機械タイムカード参照バー（段取・量産共通） */}
              {machineId && (
                <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0 flex items-center gap-4 flex-wrap">
                    <span className="text-xs font-bold text-slate-600">&#128197; 機械タイムカード</span>
                    {setupKadouMin !== null && (
                      <span className="text-xs text-blue-700 font-bold bg-blue-50 px-2 py-0.5 rounded">{"段取稼働: " + Math.floor(setupKadouMin/60) + "H " + (setupKadouMin%60) + "M"}</span>
                    )}
                    {machKadouMin !== null && (
                      <span className="text-xs text-green-700 font-bold bg-green-50 px-2 py-0.5 rounded">{"量産稼働: " + Math.floor(machKadouMin/60) + "H " + (machKadouMin%60) + "M"}</span>
                    )}
                    {setupKadouMin === null && machKadouMin === null && (
                      <span className="text-xs text-slate-400">機械のタイムカードを確認・編集して稼働時間を参照できます</span>
                    )}
                  </div>
                  <button type="button" onClick={() => setTcModalOpen(true)}
                    className="shrink-0 flex items-center gap-1.5 text-xs px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-bold transition-colors whitespace-nowrap shadow-sm">
                    タイムカード参照
                  </button>
                </div>
              )}

              {/* プログラム */}
              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">'''
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)
    print("✅ STEP2: 量産ブロック下にTCバー挿入")
else:
    errors.append("STEP2: プログラムブロックコメントが見つかりません")

# ══════════════════════════════════════════════════════════
# STEP3: TimecardModal への machineCode を選択中機械から解決
# detail.machine.machineCode → machines.find(m => m.id === parseInt(machineId))?.machineCode ?? ""
# ══════════════════════════════════════════════════════════
OLD3 = '''      {tcModalOpen && detail?.machine && (
        <TimecardModal
          open={tcModalOpen}
          onClose={() => setTcModalOpen(false)}
          machineCode={detail.machine.machineCode}
          machineId={parseInt(machineId) || 0}'''
NEW3 = '''      {tcModalOpen && machineId && (
        <TimecardModal
          open={tcModalOpen}
          onClose={() => setTcModalOpen(false)}
          machineCode={machines.find(m => String(m.id) === machineId)?.machineCode ?? ""}
          machineId={parseInt(machineId) || 0}'''
if OLD3 in src:
    src = src.replace(OLD3, NEW3, 1)
    print("✅ STEP3: TimecardModal machineCode を選択中機械から解決")
else:
    errors.append("STEP3: TimecardModal マウント箇所が見つかりません")

# エラーチェック
if errors:
    print("\n❌ エラー:")
    for e in errors: print(f"  - {e}")
    shutil.copy(TARGET + ".bak_v5", TARGET)
    print("⏪ ロールバック"); sys.exit(1)

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)
print(f"書き込み完了: {len(src.splitlines())}行")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"], cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:"); print((r.stdout+r.stderr)[-3000:])
    shutil.copy(TARGET + ".bak_v5", TARGET); print("⏪ ロールバック"); sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r2 = subprocess.run(["npx", "next", "build"], cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r2.returncode != 0:
    print("❌ next build エラー:"); print((r2.stdout+r2.stderr)[-2000:])
    shutil.copy(TARGET + ".bak_v5", TARGET); print("⏪ ロールバック"); sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "fix: record page - TC modal uses selected machine, TC bar below sanpro"], cwd=REPO)
r3 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r3.stderr.strip() or r3.stdout.strip()))
os.remove(TARGET + ".bak_v5")
print("✅ 完了")
