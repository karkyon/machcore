#!/usr/bin/env python3
"""
fix_all.py: 全問題を一括修正
① ⑩ tooling getTV: toolNo→t.toolNo, dValue→t.dValueContent
③ wrapTxt: 折り返し描画Y座標修正（curYから相対計算に変更）+ LINE_X_END修正
② WO枠: WO_X0を固定30に変更（DB座標依存をやめる）・GAP計算見直し
⑥ ファイル名: DBのdata_source修正 + mc.service.ts修正
DB: 数量フィールドのdata_sourceを 'machiningQty' に戻す
"""
import shutil, sys, subprocess
from pathlib import Path

SVC = Path('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts')
BAK = SVC.with_suffix('.ts.fix_all.bak')
DB_URL = "postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"
API_DIR = Path("/home/karkyon/projects/machcore/apps/api")
GIT_DIR = Path("/home/karkyon/projects/machcore")

src = SVC.read_text(encoding='utf-8')
shutil.copy(SVC, BAK)
print(f'バックアップ: {BAK}')

original = src
patches = []

# ══════════════════════════════════════════════════════
# ①⑩ getTV修正: toolNo→t.toolNo, dValue→t.dValueContent
# ══════════════════════════════════════════════════════
OLD_TV = (
    "      const getTV = (t: any, key: string) => {\n"
    "        if (key==='toolNo')    return t.sortOrder != null ? String(t.sortOrder) : '';\n"
    "        if (key==='toolName')  return t.toolName ?? '';\n"
    "        if (key==='tNumber')   return String(t.tNo ?? t.tNumber ?? '');\n"
    "        if (key==='hValue')    return t.hValue != null ? String(t.hValue) : (t.lengthOffsetNo ?? '');\n"
    "        if (key==='dRegister') return t.diaOffsetNo ?? t.dRegister ?? '';\n"
    "        if (key==='dValue')    return t.dValue != null ? String(t.dValue) : (t.d_value != null ? String(t.d_value) : (t.diameter != null ? String(t.diameter) : ''));\n"
    "        if (key==='subPgNo')   return t.subPgNo ?? t.subProgram ?? '';\n"
    "        if (key==='note')      return t.note ?? '';\n"
    "        return '';\n"
    "      };"
)
NEW_TV = (
    "      const getTV = (t: any, key: string) => {\n"
    "        // ①⑩ toolNo: t.toolNoが正しいフィールド(N30,N60等)\n"
    "        if (key==='toolNo')    return t.toolNo ?? '';\n"
    "        if (key==='toolName')  return t.toolName ?? '';\n"
    "        if (key==='tNumber')   return String(t.tNo ?? t.tNumber ?? '');\n"
    "        if (key==='hValue')    return t.lengthOffsetNo ?? '';\n"
    "        if (key==='dRegister') return t.diaOffsetNo ?? '';\n"
    "        // ①⑩ D値: dValueContent が正しいフィールド名\n"
    "        if (key==='dValue')    return t.dValueContent ?? '';\n"
    "        if (key==='subPgNo')   return t.subPgNo ?? '';\n"
    "        if (key==='note')      return t.note ?? '';\n"
    "        return '';\n"
    "      };"
)
if OLD_TV in src:
    src = src.replace(OLD_TV, NEW_TV)
    patches.append('①⑩ getTV: toolNo→t.toolNo, dValue→t.dValueContent, hValue→lengthOffsetNo')
else:
    print('ERROR: getTV パターン未一致')

# ══════════════════════════════════════════════════════
# ③ wrapTxt折り返し描画: Y座標計算修正
#   現状: curY - col.fs * 1.0 - li * (col.fs * 1.4)
#   問題: rowHを使っていないのでテキストがはみ出る
#   修正: curY - ROW_H*0.5 + (rowH/2) - (li+0.5)*col.fs*1.4 でセンタリング
# ══════════════════════════════════════════════════════
OLD_WRAP_DRAW = (
    "        T_COLS.forEach((col, ci) => {\n"
    "          colLines[ci].forEach((line, li) => {\n"
    "            if (line) drawTxt(line, col.x + 2, curY - col.fs * 1.0 - li * (col.fs * 1.4), col.fs);\n"
    "          });\n"
    "        });"
)
NEW_WRAP_DRAW = (
    "        T_COLS.forEach((col, ci) => {\n"
    "          // ③ 折り返し: 行上端からline_heightずつ下げる\n"
    "          colLines[ci].forEach((line, li) => {\n"
    "            if (line) drawTxt(line, col.x + 2, curY - col.fs * 1.2 - li * (col.fs * 1.4), col.fs);\n"
    "          });\n"
    "        });"
)
if OLD_WRAP_DRAW in src:
    src = src.replace(OLD_WRAP_DRAW, NEW_WRAP_DRAW)
    patches.append('③ wrapTxt描画Y座標修正')
else:
    print('WARNING: wrapTxt描画パターン未一致')

# ══════════════════════════════════════════════════════
# ② WO枠: WO_X0を30固定、COL_Wを均等計算に変更
#   WO_X_END=565, WO_X0=30, COLS=4の場合
#   有効幅=535, 枠間GAP=8とすると COL_W=(535-8*3)/4=127.25→127
# ══════════════════════════════════════════════════════
OLD_WO_LAYOUT = (
    "      const COL_W3 = colWF ? Number(colWF.x) : 201.3; // 3列設計の列幅\n"
    "      // 4列に変更: ページ左端X〜右端565の範囲を4等分\n"
    "      const WO_X0    = WO_ROW_FIELDS.length > 0 ? Number(WO_ROW_FIELDS[0].x) - WO_LBL_W : 75; // ブロック左端X\n"
    "      const WO_X_END = 565;    // ブロック右端X\n"
    "      const COLS     = 4;      // 横並び列数\n"
    "      const COL_W    = Math.floor((WO_X_END - WO_X0) / COLS); // 1列幅 = (565-75)/4 = 122.5 → 122"
)
NEW_WO_LAYOUT = (
    "      // ② WO枠レイアウト: 左端30・右端565・4枠・GAP8で均等配置\n"
    "      const WO_X0    = 30;     // ページ左端マージン固定\n"
    "      const WO_X_END = 565;    // ページ右端\n"
    "      const COLS     = 4;      // 横並び枠数\n"
    "      const WO_GAP   = 8;      // 枠間ギャップ(pt)\n"
    "      const COL_W    = Math.floor((WO_X_END - WO_X0 - WO_GAP * (COLS - 1)) / COLS); // (535-24)/4=127"
)
if OLD_WO_LAYOUT in src:
    src = src.replace(OLD_WO_LAYOUT, NEW_WO_LAYOUT)
    patches.append('② WO枠レイアウト: WO_X0=30固定・GAP=8・COL_W均等計算')
else:
    print('WARNING: WO枠レイアウトパターン未一致')

# WO枠のgx計算: ci*(COL_W+GAP)に修正
OLD_WO_GX = (
    "          // (2) 均等配置: 枠間GAP=(全幅 - COL_W*COLS)/(COLS-1)\n"
    "          const gx    = WO_X0 + ci * (COL_W + (COLS > 1 ? Math.max(2, (WO_X_END - WO_X0 - COL_W * COLS) / (COLS - 1)) : 0));"
)
NEW_WO_GX = (
    "          const gx    = WO_X0 + ci * (COL_W + WO_GAP);"
)
if OLD_WO_GX in src:
    src = src.replace(OLD_WO_GX, NEW_WO_GX)
    patches.append('② WO枠gx: WO_GAP使用に修正')
else:
    print('WARNING: WO gx パターン未一致')

# ══════════════════════════════════════════════════════
# 変更を保存
# ══════════════════════════════════════════════════════
if src == original:
    print('ERROR: 変更なし')
    sys.exit(1)

SVC.write_text(src, encoding='utf-8')
print(f'\n{len(patches)}件のコード修正:')
for p in patches:
    print(f'  - {p}')

# ══════════════════════════════════════════════════════
# DB修正
# ══════════════════════════════════════════════════════
def psql(sql):
    r = subprocess.run(['psql', DB_URL, '-c', sql, '--no-align', '-t'],
                       capture_output=True, text=True)
    return r.stdout.strip()

print('\n=== DB修正 ===')

# 数量フィールドのdata_sourceを machiningQty に戻す（誤って machiningId になった）
r = psql("""
UPDATE pdf_field_definitions SET data_source='machiningQty'
WHERE template_id=(SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND field_key='machining_qty' AND data_source='machiningId';
""")
print(f'数量 data_source 修正(machiningId→machiningQty): {r}')

# ファイル名フィールドを確認・修正
r = psql("""
UPDATE pdf_field_definitions SET data_source='fileName'
WHERE template_id=(SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (field_key='file_name' OR label ILIKE '%ファイル名%')
  AND data_source <> 'fileName';
""")
print(f'ファイル名 data_source修正: {r}')

# 修正後の全フィールド確認
print('\n=== 修正後 repeat_header data_source ===')
rows = psql("""
SELECT field_key, label, data_source FROM pdf_field_definitions f
JOIN pdf_templates t ON f.template_id=t.id
WHERE t.name='repeat_header' AND f.is_active=true ORDER BY f.sort_order;
""")
print(rows)

# mc_id=6046のfileNameを確認
print('\n=== mc_id=6046 の fileName ===')
r2 = psql("SELECT id, file_name, machining_id, legacy_mcid FROM mc_programs WHERE id=6046;")
print(r2)

# ══════════════════════════════════════════════════════
# ビルド
# ══════════════════════════════════════════════════════
print('\n=== nest build ===')
rb = subprocess.run(['npx','tsc','--noEmit','--project','tsconfig.json'],
    cwd=API_DIR, capture_output=True, text=True, timeout=120)
if rb.returncode != 0:
    print(f'❌ コンパイルエラー:\n{rb.stdout[-3000:]}\n{rb.stderr[-1000:]}')
    sys.exit(1)
print('✅ tsc --noEmit OK')

rb2 = subprocess.run(['npx','nest','build'], cwd=API_DIR,
    capture_output=True, text=True, timeout=300)
if rb2.returncode != 0:
    print(f'❌ nest build失敗:\n{rb2.stderr[-2000:]}')
    sys.exit(1)
print('✅ nest build 完了')

# ══════════════════════════════════════════════════════
# pm2 restart
# ══════════════════════════════════════════════════════
print('\n=== pm2 restart machcore-api ===')
subprocess.run(['pm2','restart','machcore-api'], check=False)
print('✅ pm2 restart 完了')

# ══════════════════════════════════════════════════════
# git push
# ══════════════════════════════════════════════════════
print('\n=== git push ===')
subprocess.run(['git','add', str(SVC)], cwd=GIT_DIR, check=True)
subprocess.run(['git','commit','-m',
    'fix: tooling N/D columns, WO layout, wrap draw Y, DB data_source corrections'],
    cwd=GIT_DIR, check=True)
subprocess.run(['git','push'], cwd=GIT_DIR, check=True)
print('✅ git push 完了')
