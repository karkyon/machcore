#!/usr/bin/env python3
"""
page.tsx のシート行に回収ボタンを追加
・grid の最後列を 16px → 80px に拡張
・行全体ボタンを「行ナビ部分」と「回収ボタン」に分割
"""
import os, sys

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = os.path.join(ROOT, "apps/web")
page = os.path.join(WEB, "app/page.tsx")

with open(page) as f:
    content = f.read()

# ─── patch 1: ヘッダー行の grid-cols と最後の <span/> を修正 ───
OLD_HEADER = '''                    <div className="grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-1.5 bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase">
                      <span>MCID</span><span>加工ID</span><span>部品ID</span><span>工程</span><span>図番 / 部品名 / 納入先</span><span>印刷日時</span><span>印刷者</span><span>経過</span><span/>
                    </div>'''
NEW_HEADER = '''                    <div className="grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_80px] gap-x-2 px-4 py-1.5 bg-slate-50 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase">
                      <span>MCID</span><span>加工ID</span><span>部品ID</span><span>工程</span><span>図番 / 部品名 / 納入先</span><span>印刷日時</span><span>印刷者</span><span>経過</span><span>回収</span>
                    </div>'''

if OLD_HEADER not in content:
    print("ERROR: ヘッダーアンカーが見つかりません")
    sys.exit(1)
content = content.replace(OLD_HEADER, NEW_HEADER, 1)
print("OK: ヘッダー行修正")

# ─── patch 2: シート行ボタンを分割 ───
# 現在の形:
#   <button key={item.id}
#     onClick={() => router.push("/mc/" + item.mc_id + "/record")}
#     className={"w-full grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_16px] ...}>
#     ...内容...
#     <svg.../> ← 最後列の矢印アイコン
#   </button>
# 変更後:
#   <div key={item.id} className="flex items-stretch">
#     <button onClick={...navigate} className="flex-1 grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px] ...">
#       ...内容（svgなし）...
#     </button>
#     <button onClick={...collect} className="w-20 ...">🔄 回収</button>
#   </div>

OLD_ROW_START = '''                        <button key={item.id}
                          onClick={() => router.push("/mc/" + item.mc_id + "/record")}
                          className={"w-full grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px_16px] gap-x-2 px-4 py-2.5 items-center text-left transition-colors " + rowCls(item.printed_at)}>'''

NEW_ROW_START = '''                        <div key={item.id} className="flex items-stretch divide-x divide-slate-100">
                        <button
                          onClick={() => router.push("/mc/" + item.mc_id + "/record")}
                          className={"flex-1 grid grid-cols-[70px_70px_70px_100px_1fr_120px_100px_80px] gap-x-2 px-4 py-2.5 items-center text-left transition-colors " + rowCls(item.printed_at)}>'''

if OLD_ROW_START not in content:
    print("ERROR: 行ボタン開始アンカーが見つかりません")
    # デバッグ
    for i, line in enumerate(content.split('\n')):
        if 'router.push("/mc/"' in line and 'record' in line:
            print(f"  L{i+1}: {line.rstrip()}")
    sys.exit(1)
content = content.replace(OLD_ROW_START, NEW_ROW_START, 1)
print("OK: 行ボタン開始部分修正")

# 矢印アイコン + </button> を 矢印アイコンなし + </button> + 回収ボタン + </div> に
OLD_ROW_END = '''                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300"><path d="M9 18l6-6-6-6"/></svg>
                        </button>'''
NEW_ROW_END = '''                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); handleCollectClick("MC", item.id, item.mc_id); }}
                          className="w-20 shrink-0 flex items-center justify-center text-[11px] font-bold text-teal-600 hover:bg-teal-50 transition-colors">
                          🔄 回収
                        </button>
                        </div>'''

if OLD_ROW_END not in content:
    print("ERROR: 行ボタン終了アンカーが見つかりません")
    for i, line in enumerate(content.split('\n')):
        if 'M9 18l6-6-6-6' in line:
            print(f"  L{i+1}: {line.rstrip()}")
    sys.exit(1)
content = content.replace(OLD_ROW_END, NEW_ROW_END, 1)
print("OK: 行ボタン終了部分修正 + 回収ボタン追加")

with open(page, 'w') as f:
    f.write(content)

print("\n✅ 完了")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
