#!/usr/bin/env python3
# coding: utf-8
import pathlib

BASE = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app")

# ─────────────────────────────────────────────────────────────
# 1. page.tsx
#    (a) 図番列のバッジ2重表示を削除（min-w-0 span内の参考/新規/リピートバッジ）
#    (b) 文字色を濃く
#    (c) 新規フロー: ボタン1つ + sessionStorage セット
# ─────────────────────────────────────────────────────────────
root = BASE / "page.tsx"
src = root.read_text(encoding="utf-8")

# (a) 図番列の重複バッジを削除
# 対象: min-w-0 span内の is_reference/sheet_type バッジ3span + 改行
OLD_DUP_BADGES = '''                            <span className="min-w-0">
                              {item.is_reference && <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded font-bold mr-1">参考</span>}
                            {!item.is_reference && item.sheet_type === "NEW" && <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold mr-1">新規</span>}
                            {!item.is_reference && item.sheet_type === "REPEAT" && <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold mr-1">リピート</span>}
                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>'''
NEW_NO_DUP_BADGES = '''                            <span className="min-w-0">
                            <span className="font-mono text-sm text-teal-600 font-bold">{item.drawing_no}</span>'''

if OLD_DUP_BADGES in src:
    src = src.replace(OLD_DUP_BADGES, NEW_NO_DUP_BADGES)
    print("OK: 図番列の重複バッジ削除")
else:
    print("WARN: 重複バッジパターン不一致")

# (b) 文字色を濃く: legacy_mcid, machining_id, part_id, operator_name 列
src = src.replace(
    '<span className="font-mono text-xs text-slate-500">{item.legacy_mcid ?? "-"}</span>\n                            <span className="font-mono text-xs text-slate-500">{item.machining_id}</span>\n                            <span className="font-mono text-xs text-slate-600">{item.part_id}</span>',
    '<span className="font-mono text-xs text-slate-700">{item.legacy_mcid ?? "-"}</span>\n                            <span className="font-mono text-xs text-slate-700">{item.machining_id}</span>\n                            <span className="font-mono text-xs text-slate-800">{item.part_id}</span>'
)
src = src.replace(
    '<span className="text-xs text-slate-500">{item.operator_name}</span>',
    '<span className="text-xs text-slate-700">{item.operator_name}</span>'
)
src = src.replace(
    '<span className="text-slate-600 text-xs ml-2">{item.part_name}</span>',
    '<span className="text-slate-800 text-xs ml-2">{item.part_name}</span>'
)
print("OK: 文字色を濃く")

# (c) 新規フロー: 「マシニング情報を登録（新規）」のみ表示 + sessionStorage
OLD_NEW_BUTTONS = '''                    {isNew ? (
                      <>
                        <button
                          onClick={() => { setSbModalOpen(false); router.push(`/mc/${sbSelectedSheet.mc_id}/edit`); }}
                          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors">
                          マシニング情報を登録（新規）
                        </button>
                        <button
                          onClick={() => { setSbModalOpen(false); router.push(`/mc/${sbSelectedSheet.mc_id}/record`); }}
                          className="w-full py-2 bg-slate-600 hover:bg-slate-700 text-white text-sm font-bold rounded-xl transition-colors">
                          作業記録のみ入力
                        </button>
                      </>'''
NEW_NEW_BUTTONS = '''                    {isNew ? (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-1">
                          <p className="text-xs font-bold text-blue-700 mb-1">新規シート — 必須作業フロー</p>
                          <div className="flex items-center gap-2 text-xs text-blue-600">
                            <span className="bg-blue-600 text-white rounded-full w-4 h-4 flex items-center justify-center font-bold shrink-0">1</span>
                            <span>マシニング情報を登録</span>
                            <span className="text-blue-400">→</span>
                            <span className="bg-teal-600 text-white rounded-full w-4 h-4 flex items-center justify-center font-bold shrink-0">2</span>
                            <span>作業記録を入力</span>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            if (typeof window !== "undefined") {
                              sessionStorage.setItem("sb_next_record", String(sbSelectedSheet.mc_id));
                            }
                            setSbModalOpen(false);
                            router.push(`/mc/${sbSelectedSheet.mc_id}/edit`);
                          }}
                          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-colors">
                          STEP 1: マシニング情報を登録（新規）
                        </button>
                      </>'''

if OLD_NEW_BUTTONS in src:
    src = src.replace(OLD_NEW_BUTTONS, NEW_NEW_BUTTONS)
    print("OK: 新規フロー ボタン修正")
else:
    print("WARN: 新規ボタンパターン不一致")

root.write_text(src, encoding="utf-8")
print("OK: page.tsx 書き込み完了")

# ─────────────────────────────────────────────────────────────
# 2. mc/[mc_id]/edit/page.tsx
#    handleSave 後: sessionStorage に sb_next_record があれば record へ遷移
# ─────────────────────────────────────────────────────────────
edit_page = BASE / "mc" / "[mc_id]" / "edit" / "page.tsx"
esrc = edit_page.read_text(encoding="utf-8")

OLD_SAVE_REDIRECT = "      showToast(\"✅ 保存しました\");\n      logout();\n      setTimeout(() => router.push(`/mc/${mcId}`), 1200);"
NEW_SAVE_REDIRECT = '''      showToast("✅ 保存しました");
      logout();
      setTimeout(() => {
        if (typeof window !== "undefined") {
          const nextMcId = sessionStorage.getItem("sb_next_record");
          if (nextMcId && parseInt(nextMcId) === mcId) {
            sessionStorage.removeItem("sb_next_record");
            router.push(`/mc/${mcId}/record`);
            return;
          }
        }
        router.push(`/mc/${mcId}`);
      }, 1200);'''

if OLD_SAVE_REDIRECT in esrc:
    esrc = esrc.replace(OLD_SAVE_REDIRECT, NEW_SAVE_REDIRECT)
    print("OK: edit/page.tsx 保存後リダイレクト修正")
else:
    print("WARN: edit保存パターン不一致")

edit_page.write_text(esrc, encoding="utf-8")
print("OK: edit/page.tsx 書き込み完了")

print("\n全処理完了")