#!/usr/bin/env python3
"""
fix_v114:
ツーリング描画の問題を修正:
1. フォントサイズをDBのfont_size列から取得（固定6.0/6.5をやめる）
2. LINE_X_END を最後のカラムX + note列の幅 で計算（固定+80をやめる）
3. カラムヘッダのhdrY計算もフォントサイズ対応
"""
import subprocess, sys, os, shutil, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()
bak = SVC + ".v114_pre.bak"
shutil.copy(SVC, bak)
print("バックアップ完了")

# ══════════════════════════════════════════════════════════════
# 修正1: T_COLSにfont_sizeとwidthを追加、LINE_X_ENDをnote幅で計算
# ══════════════════════════════════════════════════════════════

OLD_TCOLS = """      type TCol = { dataKey: string; x: number; label: string };
      const T_COLS: TCol[] = [
        { dataKey:'toolNo',    x: getColX('col_n',30),        label:'N'     },
        { dataKey:'toolName',  x: getColX('col_tool_name',50), label:'工具'  },
        { dataKey:'tNumber',   x: getColX('col_t_no',155),    label:'T'     },
        { dataKey:'hValue',    x: getColX('col_h_val',180),   label:'H'     },
        { dataKey:'dRegister', x: getColX('col_d_reg',205),   label:'D'     },
        { dataKey:'dValue',    x: getColX('col_d_val',235),   label:'D値'   },
        { dataKey:'subPgNo',   x: getColX('col_sub_pg',265),  label:'SUB'   },
        { dataKey:'note',      x: getColX('col_note',320),    label:'コメント'},
      ];
      const LINE_X_START = T_COLS[0].x;
      const LINE_X_END   = T_COLS[T_COLS.length-1].x + 80;"""

NEW_TCOLS = """      // フォントサイズとカラム幅をDBから取得するヘルパー
      const getColFS = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f ? Number(f.font_size) : def;
      };
      const getColW = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f && f.note ? parseFloat(f.note) : def;
      };

      type TCol = { dataKey: string; x: number; label: string; fs: number; w: number };
      const T_COLS: TCol[] = [
        { dataKey:'toolNo',    x: getColX('col_n',37),         label:'N',       fs: getColFS('col_n',8),         w: getColW('col_n',20)   },
        { dataKey:'toolName',  x: getColX('col_tool_name',68), label:'工具',    fs: getColFS('col_tool_name',8), w: getColW('col_tool_name',105) },
        { dataKey:'tNumber',   x: getColX('col_t_no',169.7),   label:'T',       fs: getColFS('col_t_no',8),      w: getColW('col_t_no',25)  },
        { dataKey:'hValue',    x: getColX('col_h_val',223.3),  label:'H',       fs: getColFS('col_h_val',8),     w: getColW('col_h_val',25) },
        { dataKey:'dRegister', x: getColX('col_d_reg',278.4),  label:'D',       fs: getColFS('col_d_reg',8),     w: getColW('col_d_reg',30) },
        { dataKey:'dValue',    x: getColX('col_d_val',320.3),  label:'D値',     fs: getColFS('col_d_val',8),     w: getColW('col_d_val',30) },
        { dataKey:'subPgNo',   x: getColX('col_sub_pg',369.7), label:'SUB',     fs: getColFS('col_sub_pg',8),    w: getColW('col_sub_pg',55) },
        { dataKey:'note',      x: getColX('col_note',423.9),   label:'コメント', fs: getColFS('col_note',8),     w: getColW('col_note',236) },
      ];
      const LINE_X_START = T_COLS[0].x;
      // LINE_X_END: 最後のカラムX + そのカラムの幅(note列から取得)
      const lastCol = T_COLS[T_COLS.length - 1];
      const LINE_X_END = lastCol.x + lastCol.w;"""

if OLD_TCOLS in src:
    src = src.replace(OLD_TCOLS, NEW_TCOLS)
    print("OK: T_COLS拡張（fs/w追加）+ LINE_X_END修正")
else:
    print("ERROR: T_COLSパターン未検出"); sys.exit(1)

# ══════════════════════════════════════════════════════════════
# 修正2: drawColHeaderのフォントサイズをDB値使用
# ══════════════════════════════════════════════════════════════
OLD_HDR = """      // カラムヘッダ描画関数
      const drawColHeader = async () => {
        await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H * 2, toolingTplDoc);
        const hdrY = curY - COL_HDR_H + (COL_HDR_H - 6.5 * 0.72) / 2;
        T_COLS.forEach(col => drawTxt(col.label, col.x + 2, hdrY, 6.0));
        drawHLine(LINE_X_START, LINE_X_END, curY - COL_HDR_H);
        curY -= COL_HDR_H;
      };"""

NEW_HDR = """      // カラムヘッダ描画関数
      const drawColHeader = async () => {
        await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H * 2, toolingTplDoc);
        T_COLS.forEach(col => {
          const hdrY = curY - COL_HDR_H + (COL_HDR_H - col.fs * 0.72) / 2;
          drawTxt(col.label, col.x + 2, hdrY, col.fs);
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - COL_HDR_H);
        curY -= COL_HDR_H;
      };"""

if OLD_HDR in src:
    src = src.replace(OLD_HDR, NEW_HDR)
    print("OK: drawColHeaderフォントサイズDB値化")
else:
    print("ERROR: drawColHeaderパターン未検出"); sys.exit(1)

# ══════════════════════════════════════════════════════════════
# 修正3: 明細行描画もDB値フォントサイズ使用
# ══════════════════════════════════════════════════════════════
OLD_ROW = """      let needsColHdr = false;
      for (const t of tooling) {
        if (needsColHdr) { await drawColHeader(); needsColHdr = false; }
        const sz = 6.5;
        // 各カラムの折り返し行を計算
        const colLines = T_COLS.map((col, i) => wrapTxt(getTV(t, col.dataKey), colWidths[i], sz));
        const maxLines = Math.max(1, ...colLines.map(l => l.length));
        const rowH = Math.max(ROW_H, maxLines * (sz * 1.4));
        const prevY = curY;
        await ensureSpace(rowH + ROW_MARGIN, null); // A4白紙で新ページ（縮小防止）
        if (curY > prevY) { needsColHdr = true; continue; }
        T_COLS.forEach((col, ci) => {
          colLines[ci].forEach((line, li) => {
            if (line) drawTxt(line, col.x + 2, curY - sz * 1.0 - li * (sz * 1.4), sz);
          });
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - rowH);
        curY -= (rowH + ROW_MARGIN);
      }"""

NEW_ROW = """      let needsColHdr = false;
      for (const t of tooling) {
        if (needsColHdr) { await drawColHeader(); needsColHdr = false; }
        // 各カラムの折り返し行を計算（カラムごとのフォントサイズ使用）
        const colLines = T_COLS.map((col, i) => wrapTxt(getTV(t, col.dataKey), colWidths[i], col.fs));
        const maxLines = Math.max(1, ...colLines.map(l => l.length));
        const maxFs = Math.max(...T_COLS.map(c => c.fs));
        const rowH = Math.max(ROW_H, maxLines * (maxFs * 1.4));
        const prevY = curY;
        await ensureSpace(rowH + ROW_MARGIN, null);
        if (curY > prevY) { needsColHdr = true; continue; }
        T_COLS.forEach((col, ci) => {
          colLines[ci].forEach((line, li) => {
            if (line) drawTxt(line, col.x + 2, curY - col.fs * 1.0 - li * (col.fs * 1.4), col.fs);
          });
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - rowH);
        curY -= (rowH + ROW_MARGIN);
      }"""

if OLD_ROW in src:
    src = src.replace(OLD_ROW, NEW_ROW)
    print("OK: 明細行フォントサイズDB値化")
else:
    print("ERROR: 明細行パターン未検出"); sys.exit(1)

# ══════════════════════════════════════════════════════════════
# 修正4: colWidths計算もwプロパティ使用
# ══════════════════════════════════════════════════════════════
OLD_CW = """      // カラム幅を計算（次カラムX - 自カラムX、最後は固定80pt）
      const colWidths: number[] = T_COLS.map((col, i) =>
        i < T_COLS.length - 1 ? T_COLS[i+1].x - col.x - 2 : 80
      );"""

NEW_CW = """      // カラム幅: note列の幅を優先、なければ次カラムXとの差
      const colWidths: number[] = T_COLS.map((col, i) =>
        col.w > 0 ? col.w : (i < T_COLS.length - 1 ? T_COLS[i+1].x - col.x - 2 : 80)
      );"""

if OLD_CW in src:
    src = src.replace(OLD_CW, NEW_CW)
    print("OK: colWidthsをDBのnote幅使用")
else:
    print("WARN: colWidthsパターン未検出（スキップ）")

assert "async directPrint(" in src
assert "async generateRepeatSetupSheetPdf(" in src
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

print("--- TSC ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"TSエラー {len(errs)}件")
    for e in errs[:5]: print(f"  {e}")
    shutil.copy(bak, SVC); sys.exit(1)
print("TSエラー: 0件")

print("--- nest build ---")
nest_bin = f"{PROJECT}/apps/api/node_modules/.bin/nest"
r2 = subprocess.run([nest_bin,"build","api"], capture_output=True, text=True,
    cwd=f"{PROJECT}/apps/api")
if r2.returncode != 0:
    print(f"nest build失敗:\n{(r2.stdout+r2.stderr)[:400]}")
    shutil.copy(bak, SVC); sys.exit(1)
print("nest build成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")

subprocess.run(["git","add","-A"], cwd=PROJECT)
r3 = subprocess.run(["git","commit","-m",
    "fix_v114: ツーリングFS/幅をDB値から取得、LINE_X_END修正"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了")
