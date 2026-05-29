#!/usr/bin/env python3
"""
fix_v119: WO枠ブロックを完全再実装
- EXTレコードをグループヘッダ行として描画
- グループ外枠 (drawRect)
- ラベル列・値列間の縦罫線 (drawVLine)
- 横並び列数をDBの cols_per_row から取得（デフォルト3）
- タイトル行: EXT (X=xxx Y=xxx Z=xxx) を1行で描画
"""

import re, shutil, subprocess, sys
from pathlib import Path

SVC = Path('/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts')
BAK = SVC.with_suffix('.ts.v119_pre.bak')

src = SVC.read_text(encoding='utf-8')
shutil.copy(SVC, BAK)
print(f'バックアップ完了: {BAK.name}')

# ──────────────────────────────────────────────────────────────
# 旧 WO ブロック（③）を新実装に置換
# パターン: "// ③ WO枠（同ページ継続）" から "curY -= BLOCK_MARGIN;" まで
# ──────────────────────────────────────────────────────────────
OLD_PATTERN = r'    // ③ WO枠（同ページ継続）\n    // ═+\n    const workOffsets.*?curY -= BLOCK_MARGIN;\n    }'
OLD_PATTERN_SIMPLE = '    // ③ WO枠（同ページ継続）'

# まず該当ブロックの開始位置を特定
idx_start = src.find('    // ③ WO枠（同ページ継続）')
if idx_start == -1:
    print('ERROR: WOブロック開始パターンが見つかりません')
    sys.exit(1)

# ブロック終端を特定: ④ インデックスプログラムの手前
idx_end = src.find('    // ══════════════════════════════════════════════════════════\n    // ④ インデックスプログラム', idx_start)
if idx_end == -1:
    # ④のパターン（コメント形式が違う場合）
    idx_end = src.find('    // ④ インデックスプログラム', idx_start)
    if idx_end == -1:
        print('ERROR: ④ブロック開始が見つかりません')
        print('idx_start周辺:', repr(src[idx_start:idx_start+200]))
        sys.exit(1)

old_wo_block = src[idx_start:idx_end]
print(f'WOブロック検出: {len(old_wo_block)}文字')
print(f'先頭: {repr(old_wo_block[:80])}')
print(f'末尾: {repr(old_wo_block[-80:])}')

NEW_WO_BLOCK = '''    // ③ WO枠（ワークオフセット）
    // ══════════════════════════════════════════════════════════
    // 構造:
    //   workOffsets は gCode='EXT' を区切りとして「加工IDグループ」に分割
    //   各グループは: EXT行（ヘッダ）+ G54/G55/...行（データ行）
    //   横並び列数: DBの __wo_cfg__.note の cols_per_row（デフォルト3）
    //
    //   各グループの描画:
    //     [タイトル行] EXT: X=xxx Y=xxx Z=xxx（EXTレコードの値を横並び）
    //     [データ行]   G | ラベル | 値 | ラベル | 値 ... を6行（X/Y/Z/A/C/R/B）
    //     外枠 drawRect, ラベル-値間縦罫線 drawVLine
    // ══════════════════════════════════════════════════════════
    const workOffsets: any[] = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woTplDoc = await loadTpl('repeat_wo.pdf');
      const woCfg    = fieldsByTpl('repeat_wo').find((f:any) => f.field_key === '__wo_cfg__');
      const cfg      = parseCfgStr(woCfg?.note || 'label_w=28,col_w=175.4,row_h=14.0,title_h=12.0,cols_per_row=3');
      const woFs     = woCfg ? Number(woCfg.font_size) : 8;

      const LABEL_W    = cfg.label_w    ?? 28;
      const COL_W      = cfg.col_w      ?? 175.4;  // 1グループの幅（ラベル+値）
      const WO_ROW_H   = cfg.row_h      ?? 14.0;
      const TITLE_H    = cfg.title_h    ?? 12.0;   // タイトル行の高さ
      const COLS_PER_ROW = Math.round(cfg.cols_per_row ?? 3); // 横並びグループ数
      const ML         = 30.4;                     // 左マージン
      const ROW_MARGIN = 0.5;
      const GRP_MARGIN = 4.0;                      // グループ間マージン
      const WO_LABELS  = ['X','Y','Z','A/C','R/B'];
      const WO_KEYS    = ['xOffset','yOffset','zOffset','aOffset','rOffset'];
      const VAL_W      = COL_W - LABEL_W;          // 値列幅

      // workOffsets を EXT区切りでグループに分割
      // グループ = { extRow: WO|null, dataRows: WO[] }
      const woGroups: { extRow: any|null, dataRows: any[] }[] = [];
      let curGrp: { extRow: any|null, dataRows: any[] } | null = null;
      for (const wo of workOffsets) {
        if (wo.gCode === 'EXT' || wo.gCode === 'ext') {
          if (curGrp) woGroups.push(curGrp);
          curGrp = { extRow: wo, dataRows: [] };
        } else {
          if (!curGrp) curGrp = { extRow: null, dataRows: [] };
          curGrp.dataRows.push(wo);
        }
      }
      if (curGrp && (curGrp.extRow || curGrp.dataRows.length > 0)) woGroups.push(curGrp);

      // グループを COLS_PER_ROW 個ずつ横並びにまとめる
      const rowGroups: typeof woGroups[] = [];
      for (let i = 0; i < woGroups.length; i += COLS_PER_ROW) {
        rowGroups.push(woGroups.slice(i, i + COLS_PER_ROW));
      }

      // 垂直罫線ヘルパー
      const drawVLine = (x: number, yBottom: number, yTop: number) => {
        if (!curPage) return;
        try { curPage.drawLine({ start:{x, y:yBottom}, end:{x, y:yTop}, thickness: BOX_LINE_W, color: BOX_LINE_COLOR }); } catch(_) {}
      };

      for (const rg of rowGroups) {
        // このrowのグループの最大データ行数
        const maxDataRows = Math.max(1, ...rg.map(g => Math.max(1, g.dataRows.length)));
        // タイトル行 + WO_LABELS行分の高さ
        const hasTitle = rg.some(g => g.extRow !== null);
        const titleH   = hasTitle ? TITLE_H : 0;
        const dataH    = WO_LABELS.length * (WO_ROW_H + ROW_MARGIN);
        const blockH   = titleH + dataH + 2; // +2は下パディング

        await ensureSpace(blockH + GRP_MARGIN, woTplDoc);

        const blockTopY = curY;

        // 各グループを横に描画
        rg.forEach((grp, ci) => {
          const gx = ML + ci * COL_W;
          const blockBotY = blockTopY - blockH;

          // ── グループ外枠 ──
          drawRect(gx, blockBotY, COL_W, blockH);

          // ── タイトル行（EXT行）──
          if (hasTitle) {
            const titleY    = blockTopY - titleH;
            const titleTxtY = titleY + (titleH - woFs * 0.72) / 2;
            // タイトル行下線
            drawHLine(gx, gx + COL_W, titleY);
            if (grp.extRow) {
              // G列: "EXT"
              drawTxt('EXT', gx + 2, titleTxtY, woFs);
              // X/Y/Z値をコンパクトに表示
              const ext = grp.extRow;
              const extVals = [
                ext.xOffset != null ? `X${Number(ext.xOffset).toFixed(3)}` : '',
                ext.yOffset != null ? `Y${Number(ext.yOffset).toFixed(3)}` : '',
                ext.zOffset != null ? `Z${Number(ext.zOffset).toFixed(3)}` : '',
                ext.aOffset != null ? `A${Number(ext.aOffset).toFixed(3)}` : '',
              ].filter(Boolean).join(' ');
              if (extVals) drawTxt(extVals, gx + LABEL_W + 2, titleTxtY, Math.max(5, woFs - 1));
            }
          }

          // ── データ行（G54/G55/...をG軸方向に展開）──
          // 各行: ラベル(X/Y/Z/A/C/R/B) + 各データ行のその軸値を横に並べる
          // 実際の表示: 1列グループにつき「行方向=軸（X/Y/Z...）、列内=Gコード別値」
          // しかし1グループ内に複数Gコードがある → Gコードをサブカラムとして横に並べる方式は複雑
          // ここでは: 行=Gコード、カラム内=ラベル(X/Y/Z...)+値の縦リスト方式を採用
          // つまり1グループ = 縦に Gコード行 × 軸数行

          // Gコードのリストを取得
          const gRows = grp.dataRows.length > 0 ? grp.dataRows : [];
          let dY = blockTopY - titleH;

          if (gRows.length === 0) {
            // データなし: 空グループ
          } else {
            // 各Gコード行を縦に並べる
            // 1グループ内でGコードが複数あるが、縦に全部並べると高さが不定になる
            // → WO_LABELS(軸)を行として使い、各軸の値を1つのGコードの値で表示する
            // → 複数Gコードがある場合は Gコードをサブヘッダ行として挿入

            for (const gRow of gRows) {
              // Gコードのサブヘッダ
              const subHdrH = WO_ROW_H * 0.7;
              const subHdrY = dY - subHdrH;
              const subTxtY = subHdrY + (subHdrH - (woFs - 1) * 0.72) / 2;
              drawHLine(gx, gx + COL_W, subHdrY);
              drawTxt(String(gRow.gCode ?? ''), gx + 2, subTxtY, Math.max(5, woFs - 1));
              dY = subHdrY;

              // 各軸行
              for (let li = 0; li < WO_LABELS.length; li++) {
                const rowBotY = dY - WO_ROW_H;
                const txtY    = rowBotY + (WO_ROW_H - woFs * 0.72) / 2;
                // ラベル
                drawTxt(WO_LABELS[li], gx + 2, txtY, woFs);
                // ラベル-値間縦罫線
                drawVLine(gx + LABEL_W, rowBotY, dY);
                // 値
                const raw = gRow[WO_KEYS[li]];
                const val = raw == null ? '' : (typeof raw === 'number' ? raw.toFixed(3) : String(raw));
                if (val) drawTxt(val, gx + LABEL_W + 2, txtY, woFs);
                // 行下線
                drawHLine(gx, gx + COL_W, rowBotY);
                dY = rowBotY;
              }
            }
          }
        });

        curY -= (blockH + GRP_MARGIN);
      }

      curY -= BLOCK_MARGIN;
    }

'''

new_src = src[:idx_start] + NEW_WO_BLOCK + src[idx_end:]

if 'drawVLine' not in new_src:
    print('ERROR: drawVLine が埋め込まれていません')
    sys.exit(1)

if '// ③ WO枠' not in new_src:
    print('ERROR: WOブロック置換失敗')
    sys.exit(1)

if '// ④ インデックスプログラム' not in new_src:
    print('ERROR: ④ブロックが消えた')
    sys.exit(1)

SVC.write_text(new_src, encoding='utf-8')
print('OK: WOブロック置換完了')

# ─── TSC ───
print('--- TSC ---')
r = subprocess.run(
    ['npx', 'tsc', '--noEmit'],
    cwd='/home/karkyon/projects/machcore/apps/api',
    capture_output=True, text=True
)
tsc_out = r.stdout + r.stderr
errs = [l for l in tsc_out.splitlines() if 'error TS' in l]
print(f'TSエラー: {len(errs)}件')
for e in errs[:10]:
    print(' ', e)

if errs:
    print('TSエラーあり → バックアップから復元')
    shutil.copy(BAK, SVC)
    sys.exit(1)

# ─── nest build ───
print('--- nest build ---')
r2 = subprocess.run(
    ['node_modules/.bin/nest', 'build'],
    cwd='/home/karkyon/projects/machcore/apps/api',
    capture_output=True, text=True, timeout=120
)
build_out = r2.stdout + r2.stderr
build_errs = [l for l in build_out.splitlines() if 'error TS' in l or ('error' in l.lower() and 'Found' in l)]
if r2.returncode != 0 or build_errs:
    print('nest build失敗:')
    for e in build_out.splitlines()[-20:]:
        print(' ', e)
    print('バックアップから復元')
    shutil.copy(BAK, SVC)
    sys.exit(1)

print('nest build成功!')

# ─── PM2再起動 ───
subprocess.run(['pm2', 'restart', 'machcore-api'], cwd='/home/karkyon/projects/machcore')
import time; time.sleep(8)
print('PM2再起動完了')

# ─── git push ───
subprocess.run(['git', 'add', '-A'], cwd='/home/karkyon/projects/machcore')
r3 = subprocess.run(
    ['git', 'commit', '-m', 'fix_v119: WO枠ブロック完全再実装（EXTグループヘッダ・外枠・縦罫線）'],
    cwd='/home/karkyon/projects/machcore',
    capture_output=True, text=True
)
print(r3.stdout.strip())
subprocess.run(['git', 'push', 'origin', 'main'], cwd='/home/karkyon/projects/machcore')
print('git push完了')
