#!/usr/bin/env python3
"""
fix_v122: WO枠ブロック
要件:
  - ツーリングの続き（同ページ）にWOを描画
  - スペース不足の時だけ woTplDoc でページ追加（ensureSpace方式に戻す）
  - テンプレートの罫線をコードで再現（drawRect + drawHLine + drawVLine）
  - 4レコード横並び
  - フォントサイズ: 各行フィールドのfont_size=12
  - テンプレートに準拠した枠デザイン:
    - 外枠（drawRect）
    - 各行の横罫線（drawHLine）
    - ラベル列と値列の縦罫線（drawVLine）
    - ラベル列幅はDBのG行x=103から計算（値列はラベル列の右側）
"""
import shutil, subprocess, sys
from pathlib import Path

SVC = Path('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts')
BAK = SVC.with_suffix('.ts.v122_pre.bak')

src = SVC.read_text(encoding='utf-8')
shutil.copy(SVC, BAK)
print(f'バックアップ完了: {BAK.name}')

idx_start = src.find('    // ③ WO枠（ワークオフセット）')
if idx_start == -1:
    print('ERROR: WOブロック開始が見つかりません')
    sys.exit(1)

idx_end = src.find('    // ④ インデックスプログラム', idx_start)
if idx_end == -1:
    print('ERROR: ④ブロックが見つかりません')
    sys.exit(1)

print(f'WOブロック検出: {len(src[idx_start:idx_end])}文字')

NEW_WO = r'''    // ③ WO枠（ワークオフセット）
    // ══════════════════════════════════════════════════════════
    // 方式: curY基準で相対描画（同ページ継続 + スペース不足時のみページ追加）
    // テンプレートの枠・罫線はコードで再現
    // 4レコード横並び。各列はcol_w幅
    // ──────────────────────────────────────────────────────────
    // テンプレートのDB座標（参考値）:
    //   G行: x=103, y=744  X行: x=104, y=731
    //   Y行: x=102.7, y=716  Z行: x=103.3, y=702
    //   A/C行: x=102, y=688.7  R/B行: x=102, y=674
    //   列幅(3列): x=201.3
    //   → 1列値のX=103, ラベル幅≒28, 行高≒(744-674)/5=14, 全体高≒(744-674+14)=84
    // ══════════════════════════════════════════════════════════
    const workOffsets: any[] = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woTplDoc  = await loadTpl('repeat_wo.pdf');
      const woFields  = fieldsByTpl('repeat_wo');

      // 値行フィールド（G行/X行/Y行/Z行/A/C行/R/B行）sort_order順
      const WO_ROW_FIELDS = woFields
        .filter((f:any) => {
          const k = f.field_key;
          if (k.startsWith('__')) return false;
          if (f.label === '\u5217\u5e45(3\u5217)' || k === '\u5217\u5e45(3\u5217)') return false;
          if (f.label === 'WO\u8a2d\u5b9a'  || k === 'WO\u8a2d\u5b9a') return false;
          return true;
        })
        .sort((a:any,b:any) => a.sort_order - b.sort_order);

      const woFs   = WO_ROW_FIELDS.length > 0 ? Number(WO_ROW_FIELDS[0].font_size) : 12;
      const N_ROWS = WO_ROW_FIELDS.length || 6; // G/X/Y/Z/A/C/R/B の行数

      // レイアウト定数（テンプレートDB座標から導出）
      const WO_ROW_H  = 14.0;   // 1行高さ(pt)
      const WO_LBL_W  = 28.0;   // ラベル列幅(pt)
      // 列幅フィールドのx値 = 1列分の幅（3列設計）
      const colWF = woFields.find((f:any) => f.label === '\u5217\u5e45(3\u5217)' || f.label === '__col_w__');
      const COL_W3 = colWF ? Number(colWF.x) : 201.3; // 3列設計の列幅
      // 4列に変更: ページ左端X〜右端565の範囲を4等分
      const WO_X0    = WO_ROW_FIELDS.length > 0 ? Number(WO_ROW_FIELDS[0].x) - WO_LBL_W : 75; // ブロック左端X
      const WO_X_END = 565;    // ブロック右端X
      const COLS     = 4;      // 横並び列数
      const COL_W    = Math.floor((WO_X_END - WO_X0) / COLS); // 1列幅 = (565-75)/4 = 122.5 → 122
      const BLK_H    = N_ROWS * WO_ROW_H + 2; // ブロック高さ（余白2pt含む）

      // 各行の値キー（sort_order順）
      const WO_DATA_KEYS = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];

      // 縦罫線ヘルパー
      const drawVLine = (x: number, yBot: number, yTop: number) => {
        if (!curPage) return;
        try { curPage.drawLine({ start:{x,y:yBot}, end:{x,y:yTop}, thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      };

      // WOブロック描画関数（curY位置に1ブロック描画）
      const drawWoBlock = (chunk: any[]) => {
        const topY = curY;
        const botY = topY - BLK_H;

        // 各列の枠・罫線・値を描画
        for (let ci = 0; ci < COLS; ci++) {
          const gx    = WO_X0 + ci * COL_W;
          const valX  = gx + WO_LBL_W;
          const valW  = COL_W - WO_LBL_W;

          // 列外枠
          drawRect(gx, botY, COL_W, BLK_H);
          // ラベル-値間縦罫線
          drawVLine(valX, botY, topY);

          if (ci >= chunk.length) continue; // データなし列はスキップ
          const wo = chunk[ci];

          // 各行
          for (let ri = 0; ri < N_ROWS; ri++) {
            const rowTopY = topY - ri * WO_ROW_H;
            const rowBotY = rowTopY - WO_ROW_H;
            const txtY    = rowBotY + (WO_ROW_H - woFs * 0.72) / 2;

            // 行下罫線（ラベル列・値列にまたがる）
            if (ri > 0) drawHLine(gx, gx + COL_W, rowTopY);

            // ラベルテキスト（DBのフィールドラベルを使用）
            if (ri < WO_ROW_FIELDS.length) {
              const lbl = WO_ROW_FIELDS[ri].label.replace('\u884c',''); // "G行"→"G"
              drawTxt(lbl, gx + 2, txtY, woFs);
            }

            // 値テキスト
            if (ri < WO_DATA_KEYS.length) {
              const raw = wo[WO_DATA_KEYS[ri]];
              if (raw != null && raw !== '') {
                const val = typeof raw === 'number' ? raw.toFixed(3) : String(raw);
                drawTxt(val, valX + 2, txtY, woFs);
              }
            }
          }
        }

        curY -= (BLK_H + 4);
      };

      // 4レコードずつチャンクに分割
      const chunks: any[][] = [];
      for (let i = 0; i < workOffsets.length; i += COLS) {
        chunks.push(workOffsets.slice(i, i + COLS));
      }

      for (const chunk of chunks) {
        await ensureSpace(BLK_H + 4, woTplDoc);
        drawWoBlock(chunk);
      }

      curY -= BLOCK_MARGIN;
    }

'''

new_src = src[:idx_start] + NEW_WO + src[idx_end:]
SVC.write_text(new_src, encoding='utf-8')
print('OK: WOブロック置換完了（同ページ継続・コード描画・4列）')

# ─── TSC ───
print('--- TSC ---')
r = subprocess.run(['npx','tsc','--noEmit'],
    cwd='/home/karkyon/projects/machcore/apps/api',
    capture_output=True, text=True)
errs = [l for l in (r.stdout+r.stderr).splitlines() if 'error TS' in l]
print(f'TSエラー: {len(errs)}件')
for e in errs[:5]: print(' ', e)
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
    for l in b_out.splitlines()[-15:]: print(' ', l)
    shutil.copy(BAK, SVC); sys.exit(1)
print('nest build成功!')

import time
subprocess.run(['pm2','restart','machcore-api'], cwd='/home/karkyon/projects/machcore')
time.sleep(8)
print('PM2再起動完了')

# BAKクリーンアップ
import glob, os
for f in glob.glob('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts.v1*.bak'):
    if 'v122_pre' not in f:
        os.remove(f); print(f'削除: {os.path.basename(f)}')
for f in glob.glob('/home/karkyon/projects/machcore/fix_v1*.py'):
    if 'fix_v122' not in f:
        os.remove(f); print(f'削除: {os.path.basename(f)}')

subprocess.run(['git','add','-A'], cwd='/home/karkyon/projects/machcore')
r3 = subprocess.run(['git','commit','-m',
    'fix_v122: WO枠 同ページ継続+コード描画+4列横並び'],
    cwd='/home/karkyon/projects/machcore', capture_output=True, text=True)
print(r3.stdout.strip())
subprocess.run(['git','push','origin','main'], cwd='/home/karkyon/projects/machcore')
print('git push完了')
