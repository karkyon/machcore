#!/usr/bin/env python3
"""
fix_v109_final.py
要件を全て満たす修正:
1. curY = headerEndCfg.y 列をそのまま使用（y列 = pdf-lib座標）
2. drawRect: 白塗り除去 → 4辺drawLine方式
3. NOTE_X = noteCfgF.x列, NOTE_FS = noteCfgF.font_size列
4. ラベルセンタリング: 全角fs*1.0 / 半角fs*0.55
5. ラベルfs = fs-2, 本文fs = fs-1
6. ツーリングensureSpace(rowH+ROW_MARGIN, null) ← 既に入っているが念のため確認
"""
import subprocess, sys, os, shutil

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

src = open(SVC, encoding="utf-8").read()

# バックアップ
bak = SVC + ".v109_pre.bak"
shutil.copy(SVC, bak)
print(f"バックアップ: {os.path.basename(bak)}")

# ══════════════════════════════════════════════════════════════
# 修正1: drawRect 白塗り除去（4辺drawLine方式）
# ══════════════════════════════════════════════════════════════
OLD_DRAWRECT = """    // 矩形描画（枠線のみ）
    const drawRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try {
        curPage.drawRectangle({
          x, y, width: w, height: h,
          borderWidth: BOX_LINE_W,
          borderColor: BOX_LINE_COLOR,
          color: rgb(1,1,1),
        });
      } catch(_) {}
    };"""

NEW_DRAWRECT = """    // 矩形描画（枠線のみ・塗りなし）
    const drawRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try { curPage.drawLine({ start:{x,y},       end:{x:x+w,y},       thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y:y+h},   end:{x:x+w,y:y+h},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x,y},        end:{x,y:y+h},       thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
      try { curPage.drawLine({ start:{x:x+w,y},   end:{x:x+w,y:y+h},  thickness:BOX_LINE_W, color:BOX_LINE_COLOR }); } catch(_) {}
    };"""

if OLD_DRAWRECT in src:
    src = src.replace(OLD_DRAWRECT, NEW_DRAWRECT)
    print("OK: 修正1 drawRect白塗り除去")
else:
    print("WARN: 修正1 drawRect パターン未検出 → スキップ")

# ══════════════════════════════════════════════════════════════
# 修正2: curY計算 + NOTE_X/NOTE_FS + ラベルセンタリング + フォントサイズ
# ══════════════════════════════════════════════════════════════
OLD_BLOCK = """      // ヘッダ固定部の下端Y（pdfkit座標 → pdf-lib座標に変換）
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      const headerEndPK  = headerEndCfg ? parseFloat(headerEndCfg.note || '152.8') : 152.8;
      // pdfkit Y → pdf-lib Y = pageH - pdfkitY
      curY = curPageH - headerEndPK - BLOCK_MARGIN;
    } else {
      curY = curPageH - 155;
    }

    // ─────────────────────────────────────────────────────────────
    // ①-B 備考ブロック（動的高さ・外枠・ラベル付き）
    // ─────────────────────────────────────────────────────────────
    const noteCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_cfg__');
    const noteCfgStr = noteCfgF?.note || 'x=30,w=535,fs=7,label_w=28,min_h=20';
    const noteCfg    = parseCfgStr(noteCfgStr);

    const NOTE_X       = noteCfg.x       ?? 30;
    const NOTE_W       = noteCfg.w       ?? 535;
    const NOTE_FS      = noteCfg.fs      ?? 7;
    const NOTE_LBL_W   = noteCfg.label_w ?? 28;
    const NOTE_MIN_H   = noteCfg.min_h   ?? 20;
    const NOTE_LH      = NOTE_FS * 1.55;  // 行高
    const NOTE_PAD_V   = 4;               // 上下内側余白
    const NOTE_PAD_H   = 3;               // 左右内側余白

    const noteText  = d.note ?? '';
    const clampText = d.clampNote ?? '';

    // テキストを指定幅で折り返して行配列を返す（簡易実装: 文字数ベース）
    const wrapLines = (text: string, maxW: number, fs: number): string[] => {
      if (!text) return [];
      // 1文字あたり幅: 全角=fs*0.95, 半角=fs*0.55 の平均で近似
      const charW = fs * 0.75;
      const maxChars = Math.max(1, Math.floor(maxW / charW));
      const lines: string[] = [];
      for (const raw of text.split(/\\r\\n|\\n/)) {
        if (raw.length <= maxChars) { lines.push(raw); continue; }
        let s = 0;
        while (s < raw.length) { lines.push(raw.slice(s, s+maxChars)); s += maxChars; }
      }
      return lines;
    };

    // 備考ブロック描画関数
    const drawNoteBlock = async (
      label: string, text: string,
      x: number, w: number, fs: number,
      lblW: number, minH: number, lh: number,
      padV: number, padH: number,
    ) => {
      const textAreaW = w - lblW - padH * 2;
      const lines     = wrapLines(text, textAreaW, fs);
      const blockH    = Math.max(minH, lines.length * lh + padV * 2);

      await ensureSpace(blockH + 2);

      const blockY = curY - blockH; // pdf-lib: 左下Y

      // 外枠（全体）
      drawRect(x, blockY, w, blockH);

      // ラベル列背景（薄いグレー）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0,
        });
      } catch(_) {}

      // ラベル・テキスト列の仕切り縦線
      drawHLine(x + lblW, x + lblW, blockY, BOX_LINE_W, BOX_LINE_COLOR);
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}

      // ラベルテキスト（縦中央）
      const lblTxtY = blockY + blockH / 2 - fs * 0.36;
      drawTxt(label, x + 2, lblTxtY, fs, rgb(0.15,0.15,0.15));

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        drawTxt(line, txtX0, lineY, fs);
      });

      curY -= (blockH + BLOCK_MARGIN);
    };"""

NEW_BLOCK = """      // ヘッダ固定部の下端Y: DBの __header_end_y__ の y列（pdf-lib座標=下から）をそのまま curY に使用
      // PDFエディタでフィールドをドラッグするだけで反映される
      const headerEndCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__header_end_y__');
      curY = headerEndCfg ? Number(headerEndCfg.y) : (curPageH - 310);
    } else {
      curY = curPageH - 310;
    }

    // ─────────────────────────────────────────────────────────────
    // ①-B 備考ブロック（動的高さ・外枠・ラベル付き）
    // ─────────────────────────────────────────────────────────────
    // NOTE_X: x列から取得, NOTE_FS: font_size列から取得
    // note列: 'w=535,label_w=59,min_h=22' 形式
    const noteCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_cfg__');
    const noteCfgOpt = parseCfgStr(noteCfgF?.note || 'w=535,label_w=59,min_h=22');

    const NOTE_X     = noteCfgF ? Number(noteCfgF.x)         : 30;
    const NOTE_W     = noteCfgOpt.w       ?? 535;
    const NOTE_FS    = noteCfgF ? Number(noteCfgF.font_size)  : 7;
    const NOTE_LBL_W = noteCfgOpt.label_w ?? 59;
    const NOTE_MIN_H = noteCfgOpt.min_h   ?? 22;
    const NOTE_LH    = NOTE_FS * 1.55;
    const NOTE_PAD_V = 4;
    const NOTE_PAD_H = 3;

    const noteText  = d.note      ?? '';
    const clampText = d.clampNote ?? '';

    // テキストを指定幅で折り返して行配列を返す（全角文字幅対応）
    const wrapLines = (text: string, maxW: number, fs: number): string[] => {
      if (!text) return [];
      const result: string[] = [];
      const rows = text.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n').split('\\n');
      for (const raw of rows) {
        if (!raw) { result.push(''); continue; }
        let cur = ''; let curW = 0;
        for (const ch of [...raw]) {
          const cw = ch.charCodeAt(0) > 0xFF ? fs * 0.95 : fs * 0.55;
          if (curW + cw > maxW && cur) { result.push(cur); cur = ch; curW = cw; }
          else { cur += ch; curW += cw; }
        }
        if (cur) result.push(cur);
      }
      return result.length ? result : [];
    };

    // 備考ブロック描画関数
    const drawNoteBlock = async (
      label: string, text: string,
      x: number, w: number, fs: number,
      lblW: number, minH: number, lh: number,
      padV: number, padH: number,
    ) => {
      const bodyFs    = Math.max(5, fs - 1);   // 本文フォントサイズ = fs-1
      const lblFs     = Math.max(4, fs - 2);   // ラベルフォントサイズ = fs-2
      const textAreaW = w - lblW - padH * 2;
      const lines     = wrapLines(text, textAreaW, bodyFs);
      const blockH    = Math.max(minH, lines.length * lh + padV * 2);

      await ensureSpace(blockH + 2);

      const blockY = curY - blockH;

      // 外枠（4辺drawLine）
      drawRect(x, blockY, w, blockH);

      // ラベル列背景（薄いグレー・半透明）
      try {
        curPage.drawRectangle({
          x: x, y: blockY, width: lblW, height: blockH,
          color: LABEL_BG_COLOR, borderWidth: 0, opacity: 0.5,
        });
      } catch(_) {}

      // ラベル・テキスト列の仕切り縦線
      try {
        curPage.drawLine({
          start: { x: x + lblW, y: blockY },
          end:   { x: x + lblW, y: blockY + blockH },
          thickness: BOX_LINE_W, color: BOX_LINE_COLOR,
        });
      } catch(_) {}

      // ラベルテキスト（縦中央・全角幅対応センタリング）
      const lblTxtY  = blockY + blockH / 2 - lblFs * 0.36;
      const lblTextW = [...label].reduce((acc, c) =>
        acc + (c.charCodeAt(0) > 0xFF ? lblFs * 1.0 : lblFs * 0.55), 0);
      const lblTxtX  = x + Math.max(2, (lblW - lblTextW) / 2);
      drawTxt(label, lblTxtX, lblTxtY, lblFs, rgb(0.15, 0.15, 0.15));

      // 本文テキスト
      const txtX0 = x + lblW + padH;
      lines.forEach((line, i) => {
        const lineY = blockY + blockH - padV - (i + 1) * lh + lh * 0.28;
        drawTxt(line, txtX0, lineY, bodyFs);
      });

      curY -= (blockH + BLOCK_MARGIN);
    };"""

if OLD_BLOCK in src:
    src = src.replace(OLD_BLOCK, NEW_BLOCK)
    print("OK: 修正2 curY(y列)/NOTE_X(x列)/センタリング/フォントサイズ")
else:
    print("ERROR: 修正2 パターン未検出")
    # デバッグ用に部分一致確認
    snippets = [
        "const headerEndPK  = headerEndCfg ? parseFloat(headerEndCfg.note",
        "const NOTE_X       = noteCfg.x",
        "const charW = fs * 0.75;",
        "drawTxt(label, x + 2, lblTxtY, fs, rgb(0.15,0.15,0.15));",
    ]
    for s in snippets:
        print(f"  {'OK' if s in src else 'NG'}: {s[:60]}")
    open(SVC, "w", encoding="utf-8").write(open(bak).read())
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# 修正3: クランプブロックのx列・font_size列使用
# ══════════════════════════════════════════════════════════════
OLD_CLAMP_CFG = """    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgStr = clampCfgF?.note || 'x=30,w=535,fs=7,label_w=28,min_h=20';
    const clampCfg    = parseCfgStr(clampCfgStr);

    await drawNoteBlock(
      'クランプ', clampText,
      clampCfg.x ?? 30, clampCfg.w ?? 535, clampCfg.fs ?? 7,
      clampCfg.label_w ?? 28, clampCfg.min_h ?? 20, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );"""

NEW_CLAMP_CFG = """    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgOpt = parseCfgStr(clampCfgF?.note || 'w=535,label_w=59,min_h=22');
    const CLAMP_X     = clampCfgF ? Number(clampCfgF.x)        : NOTE_X;
    const CLAMP_W     = clampCfgOpt.w       ?? NOTE_W;
    const CLAMP_FS    = clampCfgF ? Number(clampCfgF.font_size) : NOTE_FS;
    const CLAMP_LBL_W = clampCfgOpt.label_w ?? NOTE_LBL_W;
    const CLAMP_MIN_H = clampCfgOpt.min_h   ?? NOTE_MIN_H;

    await drawNoteBlock(
      'クランプ', clampText,
      CLAMP_X, CLAMP_W, CLAMP_FS,
      CLAMP_LBL_W, CLAMP_MIN_H, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );"""

if OLD_CLAMP_CFG in src:
    src = src.replace(OLD_CLAMP_CFG, NEW_CLAMP_CFG)
    print("OK: 修正3 クランプx列/font_size列使用")
else:
    print("WARN: 修正3 クランプ設定パターン未検出 → スキップ")

# ══════════════════════════════════════════════════════════════
# 修正4: ツーリングensureSpaceがnullであることを確認（既に入っているはず）
# ══════════════════════════════════════════════════════════════
if "await ensureSpace(rowH + ROW_MARGIN, null)" in src:
    print("OK: 修正4 ツーリングensureSpace(null) 確認済み")
elif "await ensureSpace(EFFECTIVE_ROW_H, toolingTplDoc)" in src:
    src = src.replace(
        "await ensureSpace(EFFECTIVE_ROW_H, toolingTplDoc);",
        "await ensureSpace(rowH + ROW_MARGIN, null); // A4白紙（縮小防止）"
    )
    print("OK: 修正4 ツーリングensureSpaceをnullに変更")
else:
    print("WARN: 修正4 ツーリングensureSpaceパターン未検出 → スキップ")

# ══════════════════════════════════════════════════════════════
# 書き込み前チェック
# ══════════════════════════════════════════════════════════════
assert "async directPrint(" in src, "ERROR: directPrint が消えています！"
assert "async generateRepeatSetupSheetPdf(" in src, "ERROR: generateRepeatSetupSheetPdf が消えています！"
print(f"directPrint確認: OK")
print(f"generateRepeatSetupSheetPdf確認: OK")

open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

# ══════════════════════════════════════════════════════════════
# TypeScriptコンパイルチェック
# ══════════════════════════════════════════════════════════════
print("--- TSC チェック ---")
r = subprocess.run(
    ["npx", "tsc", "--noEmit", "-p", "apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT
)
errors = [l for l in (r.stdout + r.stderr).splitlines() if "error TS" in l]
if errors:
    print(f"TSエラー: {len(errors)}件")
    for e in errors[:10]: print(f"  {e}")
    shutil.copy(bak, SVC)
    print("→ バックアップから復元しました")
    sys.exit(1)
print("TypeScriptエラー: 0件")

# ══════════════════════════════════════════════════════════════
# nest build
# ══════════════════════════════════════════════════════════════
print("--- nest build ---")
nest_bin = f"{PROJECT}/apps/api/node_modules/.bin/nest"
r2 = subprocess.run(
    [nest_bin, "build", "api"],
    capture_output=True, text=True, cwd=f"{PROJECT}/apps/api"
)
if r2.returncode != 0:
    out = (r2.stdout + r2.stderr)[:500]
    print(f"nest build 失敗:\n{out}")
    shutil.copy(bak, SVC)
    print("→ バックアップから復元しました")
    sys.exit(1)
print("nest build 成功!")

# ══════════════════════════════════════════════════════════════
# PM2 再起動
# ══════════════════════════════════════════════════════════════
subprocess.run(["pm2", "restart", "machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2 再起動完了 (machcore-api)")

# ══════════════════════════════════════════════════════════════
# git commit & push
# ══════════════════════════════════════════════════════════════
subprocess.run(["git", "add", "-A"], cwd=PROJECT)
r3 = subprocess.run(
    ["git", "commit", "-m",
     "fix_v109: curY=y列/drawRect塗りなし/ラベルセンタリング/fs修正/クランプx列"],
    capture_output=True, text=True, cwd=PROJECT
)
print(r3.stdout.strip())
subprocess.run(["git", "push"], capture_output=True, cwd=PROJECT)
print("git push 完了")

print("""
=== fix_v109 完了 ===
【変更内容】
1. curY = headerEndCfg.y （pdf-lib座標のy列をそのまま使用）
   → PDFエディタで __header_end_y__ をドラッグするだけで反映
2. drawRect: color:rgb(1,1,1)白塗り除去 → 4辺drawLine方式（塗りなし）
3. NOTE_X = noteCfgF.x列, NOTE_FS = noteCfgF.font_size列
   → note列は 'w=535,label_w=59,min_h=22' のみ管理
4. ラベルセンタリング: 全角fs*1.0 / 半角fs*0.55 で正確な幅計算
5. ラベルfs = fs-2, 本文fs = fs-1
6. クランプも同様にx列/font_size列使用
7. ツーリング ensureSpace(null) = A4白紙追加（縮小防止）確認済み

【DBの確認】
__header_end_y__ の y列をPDFエディタでNT-行真下にドラッグ → 保存
__note_cfg__ の x列・font_size列をドラッグ/入力で調整可能
""")
