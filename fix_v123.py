#!/usr/bin/env python3
"""
fix_v123: pdf-editor page.tsx プレビューモード/編集モード切り替え
- loadFullPreview / loadNewFullPreview 後 → isPreviewMode=true
- loadPreview（テンプレート表示）後 → isPreviewMode=false（編集モード復帰）
- isPreviewMode=true 時:
  - SVGオーバーレイ非表示
  - フィールドリスト操作無効（opacity-40 pointer-events-none）
  - 一括保存ボタン無効
  - テンプレート表示ボタンを「← 編集に戻る」オレンジで強調
"""
import shutil, subprocess, sys
from pathlib import Path

PAGE = Path('/home/karkyon/projects/machcore/apps/web/app/admin/pdf-editor/page.tsx')
BAK  = PAGE.with_suffix('.tsx.v123_pre.bak')

src = PAGE.read_text(encoding='utf-8')
shutil.copy(PAGE, BAK)
print(f'バックアップ完了: {BAK.name}')

# ① isPreviewMode state 追加
OLD_STATE = '  const renderingRef = useRef(false);'
NEW_STATE = '''  const renderingRef = useRef(false);
  // プレビューモード: 全体プレビュー後はtrue、テンプレート表示で戻す
  const [isPreviewMode, setIsPreviewMode] = useState(false);'''

if OLD_STATE not in src:
    print('ERROR: renderingRef が見つかりません'); sys.exit(1)
src = src.replace(OLD_STATE, NEW_STATE, 1)
print('OK: isPreviewMode state 追加')

# ② loadPreview（テンプレート表示）に setIsPreviewMode(false) 追加
OLD_LOAD_PREVIEW = '  const loadPreview = async () => {\n    setPdfLoading(true);'
NEW_LOAD_PREVIEW = '  const loadPreview = async () => {\n    setIsPreviewMode(false);\n    setPdfLoading(true);'

if OLD_LOAD_PREVIEW not in src:
    print('ERROR: loadPreview 関数が見つかりません'); sys.exit(1)
src = src.replace(OLD_LOAD_PREVIEW, NEW_LOAD_PREVIEW, 1)
print('OK: loadPreview に isPreviewMode=false 追加')

# ③ loadFullPreview に setIsPreviewMode(true) 追加（リピート全体プレビュー）
OLD_FULL = '''      setPdfData(new Uint8Array(ab));
      setPreviewPage(1);
      setPdfTotalPages(1);
    } catch (e: any) { showToast(`全体プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  // 全体プレビュー（新規段取シート）'''

NEW_FULL = '''      setPdfData(new Uint8Array(ab));
      setPreviewPage(1);
      setPdfTotalPages(1);
      setIsPreviewMode(true);
    } catch (e: any) { showToast(`全体プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  // 全体プレビュー（新規段取シート）'''

if OLD_FULL not in src:
    print('ERROR: loadFullPreview の setPdfTotalPages 箇所が見つかりません'); sys.exit(1)
src = src.replace(OLD_FULL, NEW_FULL, 1)
print('OK: loadFullPreview に isPreviewMode=true 追加')

# ④ loadNewFullPreview にも setIsPreviewMode(true) 追加
OLD_NEW_FULL = '''      setPdfData(new Uint8Array(ab));
      setPreviewPage(1);
      setPdfTotalPages(1);
    } catch (e: any) { showToast(`全体プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  const handleUpload'''

NEW_NEW_FULL = '''      setPdfData(new Uint8Array(ab));
      setPreviewPage(1);
      setPdfTotalPages(1);
      setIsPreviewMode(true);
    } catch (e: any) { showToast(`全体プレビュー失敗: ${e.message}`, false); }
    finally { setPdfLoading(false); }
  };

  const handleUpload'''

if OLD_NEW_FULL not in src:
    print('ERROR: loadNewFullPreview の setPdfTotalPages 箇所が見つかりません'); sys.exit(1)
src = src.replace(OLD_NEW_FULL, NEW_NEW_FULL, 1)
print('OK: loadNewFullPreview に isPreviewMode=true 追加')

# ⑤ SVGオーバーレイを !isPreviewMode 時のみ表示
OLD_SVG = '''                {/* ④修正: SVGはPDF座標系(595×842)固定のviewBoxで描画 */}
                <svg'''
NEW_SVG = '''                {/* フィールドオーバーレイ: 編集モードのみ表示 */}
                {!isPreviewMode && <svg'''

if OLD_SVG not in src:
    print('ERROR: SVGオーバーレイ開始が見つかりません'); sys.exit(1)
src = src.replace(OLD_SVG, NEW_SVG, 1)
print('OK: SVGオーバーレイ条件追加')

# ⑥ SVGの閉じタグ修正（JSX条件式を閉じる）
OLD_SVG_END = '''                </svg>
              </div>
            )}
          </div>
          </div>

        </div>
      </div>
    </div>
  );
}'''

NEW_SVG_END = '''                </svg>}
              </div>
            )}
          </div>
          </div>

        </div>
      </div>
    </div>
  );
}'''

if OLD_SVG_END not in src:
    print('ERROR: SVGオーバーレイ閉じタグが見つかりません')
    # 末尾200文字を確認
    idx = src.rfind('</svg>')
    print('最後の</svg>位置:', idx)
    print('周辺:', repr(src[idx-20:idx+200]))
    sys.exit(1)
src = src.replace(OLD_SVG_END, NEW_SVG_END, 1)
print('OK: SVGオーバーレイ閉じタグ修正')

# ⑦ フィールドリストをプレビューモード時に無効化
OLD_FIELD_LIST = '            {/* フィールドリスト */}\n            <div className="flex-1 overflow-y-auto">'
NEW_FIELD_LIST = '            {/* フィールドリスト: プレビューモード時は操作無効 */}\n            <div className={`flex-1 overflow-y-auto${isPreviewMode ? " opacity-40 pointer-events-none select-none" : ""}`}>'

if OLD_FIELD_LIST not in src:
    print('ERROR: フィールドリストコンテナが見つかりません'); sys.exit(1)
src = src.replace(OLD_FIELD_LIST, NEW_FIELD_LIST, 1)
print('OK: フィールドリスト プレビューモード無効化')

# ⑧ 一括保存ボタンのdisabled条件に isPreviewMode 追加
OLD_SAVE = '                <button onClick={saveAll} disabled={saving}'
NEW_SAVE = '                <button onClick={saveAll} disabled={saving || isPreviewMode}'

if OLD_SAVE not in src:
    print('WARN: 一括保存ボタンが見つかりません（スキップ）')
else:
    src = src.replace(OLD_SAVE, NEW_SAVE, 1)
    print('OK: 一括保存ボタン無効化')

# ⑨ テンプレート表示ボタンをプレビューモード時に強調 + ラベル変更
OLD_TPL_DISP_BTN = '''                  className="flex-1 px-2 py-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/>
                  </svg>
                  テンプレート表示'''

NEW_TPL_DISP_BTN = '''                  className={`flex-1 px-2 py-1 text-white text-xs font-bold rounded disabled:opacity-50 whitespace-nowrap flex items-center justify-center gap-1 ${isPreviewMode ? "bg-amber-500 hover:bg-amber-600 ring-2 ring-amber-300" : "bg-teal-600 hover:bg-teal-700"}`}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/>
                  </svg>
                  {isPreviewMode ? "← 編集に戻る" : "テンプレート表示"}'''

if OLD_TPL_DISP_BTN not in src:
    print('WARN: テンプレート表示ボタンが見つかりません（スキップ）')
else:
    src = src.replace(OLD_TPL_DISP_BTN, NEW_TPL_DISP_BTN, 1)
    print('OK: テンプレート表示ボタン スタイル変更')

PAGE.write_text(src, encoding='utf-8')
print('OK: page.tsx 書き換え完了')

# ─── TSC (Web) ───
print('--- TSC (Web) ---')
r = subprocess.run(['npx','tsc','--noEmit'],
    cwd='/home/karkyon/projects/machcore/apps/web',
    capture_output=True, text=True)
errs = [l for l in (r.stdout+r.stderr).splitlines() if 'error TS' in l]
print(f'Webエラー: {len(errs)}件')
for e in errs[:5]: print(' ', e)
if errs:
    shutil.copy(BAK, PAGE); sys.exit(1)

# ─── Next.js build + PM2 ───
print('--- Next.js build ---')
r2 = subprocess.run(['npm','run','build'],
    cwd='/home/karkyon/projects/machcore/apps/web',
    capture_output=True, text=True, timeout=300)
b_out = r2.stdout + r2.stderr
if r2.returncode != 0:
    print('build失敗:')
    for l in b_out.splitlines()[-20:]: print(' ', l)
    shutil.copy(BAK, PAGE); sys.exit(1)
print('build成功!')

import time
subprocess.run(['pm2','delete','machcore-web'], cwd='/home/karkyon/projects/machcore')
time.sleep(2)
subprocess.run(['pm2','start','ecosystem.config.js','--only','machcore-web'],
    cwd='/home/karkyon/projects/machcore')
time.sleep(5)
print('PM2再起動完了(web)')

subprocess.run(['git','add','-A'], cwd='/home/karkyon/projects/machcore')
r3 = subprocess.run(['git','commit','-m',
    'fix_v123: pdf-editor プレビューモード（SVGオーバーレイ非表示・左パネル無効・テンプレート表示で復帰）'],
    cwd='/home/karkyon/projects/machcore', capture_output=True, text=True)
print(r3.stdout.strip())
subprocess.run(['git','push','origin','main'], cwd='/home/karkyon/projects/machcore')
print('git push完了')
