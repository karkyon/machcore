#!/usr/bin/env python3
# coding: utf-8
import pathlib

edit = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/edit/page.tsx")
src = edit.read_text(encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# 1. 図・写真セクション: isAuthenticated条件を外して常時表示
# ─────────────────────────────────────────────────────────────
OLD_FILES_COND = "      {/* 図・写真 */}\n      {isAuthenticated && activeSection === \"files\" && ("
NEW_FILES_COND = "      {/* 図・写真 */}\n      {activeSection === \"files\" && ("

if OLD_FILES_COND in src:
    src = src.replace(OLD_FILES_COND, NEW_FILES_COND)
    print("OK: 図・写真 認証条件削除")
else:
    print("WARN: 図・写真条件パターン不一致")

# ─────────────────────────────────────────────────────────────
# 2. ファイル選択 accept 属性を削除（拡張子なしファイル対応）
#    写真選択・図選択の両方
# ─────────────────────────────────────────────────────────────
# 写真選択
src = src.replace(
    'type="file" accept="image/jpeg,image/png,image/tiff" className="hidden"',
    'type="file" className="hidden"'
)
# 図選択
src = src.replace(
    'type="file" accept="image/tiff,application/pdf,image/png,image/jpeg" className="hidden"',
    'type="file" className="hidden"'
)
print("OK: ファイル選択 accept削除")

# ─────────────────────────────────────────────────────────────
# 3. ツーリングファイル選択 accept も削除
# ─────────────────────────────────────────────────────────────
src = src.replace(
    'accept=".min,.spf,.mpf,.nc,.cnc,.tap,.prg,.txt" className="hidden"',
    'className="hidden"'
)
print("OK: ツーリングファイル選択 accept削除")

# ─────────────────────────────────────────────────────────────
# 4. セッションバナーの保存ボタン上部に sbMode用STEP1ガイドバナー追加
#    セッションバナー内の先頭に追加
# ─────────────────────────────────────────────────────────────
OLD_SESSION_BANNER = '''      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>'''
NEW_SESSION_BANNER = '''      {isAuthenticated && operator && sbMode && (
        <div className="bg-blue-700 text-white px-5 py-2 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="bg-blue-500 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold shrink-0">1</span>
            <span className="font-bold">段取シートバック STEP1: 基本情報・ツーリング・図写真などを登録してください</span>
            <span className="text-blue-300">→ 登録完了後 STEP2(作業記録)へ自動遷移します</span>
          </div>
          <button onClick={handleSave} disabled={saving}
            className="bg-white text-blue-700 px-4 py-1 rounded font-bold hover:bg-blue-50 disabled:opacity-50 text-sm">
            {saving ? "保存中..." : "STEP1完了 → STEP2(作業記録)へ"}
          </button>
        </div>
      )}
      {isAuthenticated && operator && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>'''

if OLD_SESSION_BANNER in src:
    src = src.replace(OLD_SESSION_BANNER, NEW_SESSION_BANNER)
    print("OK: sbMode STEP1バナー追加")
else:
    print("WARN: セッションバナーパターン不一致")

edit.write_text(src, encoding="utf-8")
print("OK: edit/page.tsx 書き込み完了")
print("\n全処理完了")