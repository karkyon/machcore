#!/usr/bin/env python3
# coding: utf-8
import pathlib

ROOT = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app")

# ═══════════════════════════════════════════
# 1. 印刷ページ: タブナビ内のダッシュボードボタンを削除 → ヘッダーに追加
# ═══════════════════════════════════════════
f = ROOT / "mc/[mc_id]/print/page.tsx"
src = f.read_text(encoding="utf-8")

# タブナビ内のダッシュボードボタンを削除
DASH_IN_NAV = (
    '        <button onClick={() => router.push("/mc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors">\n'
    '          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>\n'
    '          \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078\n'
    '        </button>\n'
)
if DASH_IN_NAV in src:
    src = src.replace(DASH_IN_NAV, '', 1)
    print("OK: \u5370\u5237\u30da\u30fc\u30b8 \u30bf\u30d6\u30ca\u30d3\u5185\u306e\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u30dc\u30bf\u30f3\u3092\u524a\u9664")
else:
    print("WARN: \u5370\u5237\u30da\u30fc\u30b8 \u30bf\u30d6\u30ca\u30d3\u5185\u30d1\u30bf\u30fc\u30f3\u306a\u3057")

# ヘッダーに「ダッシュボードへ」ボタンを追加
# ヘッダーは「MachCore」の span の直前に部品名等がある構造
# `<header className="bg-slate-800` の直後にボタンを追加する
# 実際の構造: header > (部品情報ブロック) > タブナビ
# 印刷ページのヘッダーを探す
HDR_ANCHOR = '<header className="bg-slate-800 text-white'
if HDR_ANCHOR in src:
    # ヘッダーの直後（最初の > の後）にダッシュボードボタンを追加
    # ヘッダー内の最初の span (MachCore) の前に追加
    OLD_HDR_CONTENT = '        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>'
    NEW_HDR_CONTENT = (
        '        <button onClick={() => router.push("/mc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">\n'
        '          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>\n'
        '          \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078\n'
        '        </button>\n'
        '        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>'
    )
    if '\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078' not in src and OLD_HDR_CONTENT in src:
        src = src.replace(OLD_HDR_CONTENT, NEW_HDR_CONTENT, 1)
        print("OK: \u5370\u5237\u30da\u30fc\u30b8 \u30d8\u30c3\u30c0\u30fc\u306b\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u30dc\u30bf\u30f3\u8ffd\u52a0")
    else:
        print("INFO: \u5370\u5237\u30da\u30fc\u30b8 \u30d8\u30c3\u30c0\u30fc\u306f\u65e2\u306b\u5bfe\u5fdc\u6e08\u307f")
else:
    print("WARN: \u5370\u5237\u30da\u30fc\u30b8 \u30d8\u30c3\u30c0\u30fc\u30d1\u30bf\u30fc\u30f3\u306a\u3057")

f.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════
# 2. 作業記録ページ: ヘッダーにダッシュボードボタン追加
# ═══════════════════════════════════════════
f = ROOT / "mc/[mc_id]/record/page.tsx"
src = f.read_text(encoding="utf-8")

OLD_REC_HDR = '        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>'
NEW_REC_HDR = (
    '        <button onClick={() => router.push("/mc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">\n'
    '          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>\n'
    '          \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078\n'
    '        </button>\n'
    '        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>'
)
if '\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3078' not in src and OLD_REC_HDR in src:
    src = src.replace(OLD_REC_HDR, NEW_REC_HDR, 1)
    print("OK: \u4f5c\u696d\u8a18\u9332\u30da\u30fc\u30b8 \u30d8\u30c3\u30c0\u30fc\u306b\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u30dc\u30bf\u30f3\u8ffd\u52a0")
else:
    print("INFO: \u4f5c\u696d\u8a18\u9332\u30da\u30fc\u30b8\u306f\u65e2\u306b\u5bfe\u5fdc\u6e08\u307f\u307e\u305f\u306f\u30d1\u30bf\u30fc\u30f3\u306a\u3057")
f.write_text(src, encoding="utf-8")

# ═══════════════════════════════════════════
# 3. ダッシュボード: サイドバーのパネルをスクロールなしで見えるように
#    flex-col の aside に overflow-y-auto があるため
#    mt-4 を削除して管理パネルの直後に段取シートバックパネルを配置
# ═══════════════════════════════════════════
f = ROOT / "page.tsx"
src = f.read_text(encoding="utf-8")

# 管理パネルブロックとサイドバーパネルの間の div を確認
# 現在: 管理パネル > mx-3 mb-3 mt-4 > 段取シートバック
# 変更: mt-4 を mt-2 にして、flex-1でスペースを埋めない
src = src.replace(
    '            <div className="mx-3 mb-3 mt-4">',
    '            <div className="mx-3 mb-3 mt-2">',
    1
)
print("OK: \u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9 mt \u4fee\u6b63")
f.write_text(src, encoding="utf-8")

print("\ncd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")