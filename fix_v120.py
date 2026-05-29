#!/usr/bin/env python3
"""
fix_v120: WO枠ブロック - テンプレート方式で正しく実装
テンプレートPDF repeat_wo.pdf にはラベル(G/X/Y/Z/A/C/R/B)と罫線が印刷済み
→ コードは値のみ差し込む
→ 1ブロック = 3レコード横並び（DB col_w オフセット）
→ 3の倍数超えたら ensureSpace(woTplDoc) で次ブロックへ
→ 各行のY座標: DBの各行フィールドのy値（pdf-lib座標=下から）を
  curY を基準に相対位置で描画（ブロック最上行を curY に合わせる）
"""
import shutil, subprocess, sys
from pathlib import Path

SVC = Path('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts')
BAK = SVC.with_suffix('.ts.v120_pre.bak')

src = SVC.read_text(encoding='utf-8')
shutil.copy(SVC, BAK)
print(f'バックアップ完了: {BAK.name}')

idx_start = src.find('    // ③ WO枠（ワークオフセット）')
if idx_start == -1:
    idx_start = src.find('    // ③ WO枠（同ページ継続）')
if idx_start == -1:
    print('ERROR: WOブロック開始が見つかりません')
    sys.exit(1)

idx_end = src.find('    // ④ インデックスプログラム', idx_start)
if idx_end == -1:
    print('ERROR: ④ブロックが見つかりません')
    sys.exit(1)

print(f'WOブロック検出: {len(src[idx_start:idx_end])}文字')

NEW_WO = '''    // ③ WO枠（ワークオフセット）
    // ══════════════════════════════════════════════════════════
    // repeat_wo.pdf にラベル+罫線が印刷済み → 値のみ差し込む
    // 1ブロック = COLS(3)レコード横並び。DBのcol_w(x=201.3)でオフセット
    // ブロック高さ = 各行Y値（pdf-lib座標）の最大-最小+ROW_H で算出
    // curY基準で相対描画: 行Y = curY - BLK_H + (rowY_db - minY_db)
    // ══════════════════════════════════════════════════════════
    const workOffsets: any[] = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woTplDoc  = await loadTpl('repeat_wo.pdf');
      const woFields  = fieldsByTpl('repeat_wo');
      const woCfg     = woFields.find((f:any) => f.field_key === '__wo_cfg__');
      const cfg       = parseCfgStr(woCfg?.note || 'row_h=14.0,cols=3');
      const woFs      = woCfg ? Number(woCfg.font_size) : 8;

      // 値を差し込む6行フィールド（sort_order順・G行〜R/B行）
      const WO_ROW_FIELDS = woFields
        .filter((f:any) => !f.field_key.startsWith('__') && f.field_key !== '\u5217\u5e45(3\u5217)')
        .sort((a:any,b:any) => a.sort_order - b.sort_order);

      // 列幅フィールド（field_key='列幅(3列)' または '__col_w__'）
      const colWField = woFields.find((f:any) =>
        f.field_key === '\u5217\u5e45(3\u5217)' || f.field_key === '__col_w__' || f.label === '\u5217\u5e45(3\u5217)'
      );
      const COL_W  = colWField ? Number(colWField.x) : (cfg.col_w ?? 175.4);
      const COLS   = Math.round(cfg.cols ?? 3);
      const ROW_H  = cfg.row_h ?? 14.0;

      // DB各行のY値（pdf-lib座標）からブロック高さ算出
      const rowYvals = WO_ROW_FIELDS.map((f:any) => Number(f.y));
      const maxRowY  = Math.max(...rowYvals); // 最上行Y（最大値 = 上）
      const minRowY  = Math.min(...rowYvals); // 最下行Y（最小値 = 下）
      const BLK_H    = maxRowY - minRowY + ROW_H + 2; // +2はパディング

      // 各行の値キー（sort_order順に対応）
      const WO_KEYS = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];

      // 3レコードずつチャンクに分割
      const chunks: any[][] = [];
      for (let i = 0; i < workOffsets.length; i += COLS) {
        chunks.push(workOffsets.slice(i, i + COLS));
      }

      for (const chunk of chunks) {
        // 余白チェック: BLK_H 分必要。不足なら woTplDoc でページ追加
        await ensureSpace(BLK_H + 4, woTplDoc);

        // 各レコードを横列に差し込む
        chunk.forEach((wo: any, ci: number) => {
          const xOff = ci * COL_W;
          WO_ROW_FIELDS.forEach((f: any, fi: number) => {
            if (fi >= WO_KEYS.length) return;
            const raw = wo[WO_KEYS[fi]];
            if (raw == null || raw === '') return;
            const val = typeof raw === 'number' ? raw.toFixed(3) : String(raw);
            // curY基準でY座標を計算
            // テンプレートの最上行(maxRowY)を curY に対応させる
            // 行Y_pdflib = curY - (maxRowY - f.y)
            const absY = curY - (maxRowY - Number(f.y));
            drawTxt(val, Number(f.x) + xOff, absY, woFs);
          });
        });

        curY -= (BLK_H + 4);
      }

      curY -= BLOCK_MARGIN;
    }

'''

new_src = src[:idx_start] + NEW_WO + src[idx_end:]
SVC.write_text(new_src, encoding='utf-8')
print('OK: WOブロック置換完了（テンプレート方式・値のみ差し込み）')

# ─── TSC ───
print('--- TSC ---')
r = subprocess.run(['npx','tsc','--noEmit'],
    cwd='/home/karkyon/projects/machcore/apps/api',
    capture_output=True, text=True)
errs = [l for l in (r.stdout+r.stderr).splitlines() if 'error TS' in l]
print(f'TSエラー: {len(errs)}件')
for e in errs[:5]: print(' ',e)
if errs:
    shutil.copy(BAK, SVC); sys.exit(1)

# ─── nest build ───
print('--- nest build ---')
r2 = subprocess.run(['node_modules/.bin/nest','build'],
    cwd='/home/karkyon/projects/machcore/apps/api',
    capture_output=True, text=True, timeout=120)
b_out = r2.stdout + r2.stderr
b_errs = [l for l in b_out.splitlines() if 'error TS' in l or ('error' in l.lower() and 'Found' in l)]
if r2.returncode != 0 or b_errs:
    print('nest build失敗:')
    for l in b_out.splitlines()[-15:]: print(' ',l)
    shutil.copy(BAK, SVC); sys.exit(1)
print('nest build成功!')

import time
subprocess.run(['pm2','restart','machcore-api'], cwd='/home/karkyon/projects/machcore')
time.sleep(8)
print('PM2再起動完了')

# 不要なbakファイル削除
import glob, os
for f in glob.glob('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts.v1*.bak'):
    if 'v120_pre' not in f:
        os.remove(f)
        print(f'削除: {os.path.basename(f)}')
for f in glob.glob('/home/karkyon/projects/machcore/fix_v1*.py'):
    if 'fix_v120' not in f:
        os.remove(f)
        print(f'削除: {os.path.basename(f)}')

subprocess.run(['git','add','-A'], cwd='/home/karkyon/projects/machcore')
r3 = subprocess.run(['git','commit','-m',
    'fix_v120: WO枠テンプレート方式（値のみ差し込み・3列横並び・curY相対描画）'],
    cwd='/home/karkyon/projects/machcore',
    capture_output=True, text=True)
print(r3.stdout.strip())
subprocess.run(['git','push','origin','main'], cwd='/home/karkyon/projects/machcore')
print('git push完了')
