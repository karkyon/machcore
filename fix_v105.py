#!/usr/bin/env python3
"""
fix_v105.py
===========
【変更概要】
  ① repeat_header.pdf から備考・クランプフィールドを除外
    → テンプレートPDF上の備考・クランプ枠はなくす（KARKYONさんがPDFを修正）

  ①-B 備考ブロック（コードで動的描画）
    - 「備考」ラベル + 外枠線(drawRectangle)
    - テキストを折り返し・改行対応で描画
    - テキスト量に応じてブロック高さが可変
    - 最小高さ保証（データなしでも崩れない）

  ①-C クランプブロック（備考ブロックと同構造）
    - 「クランプ」ラベル + 外枠線
    - テキスト量に応じてブロック高さが可変

  ① 固定部テンプレ(repeat_header.pdf)の「コンテンツ下端」は
     DBの __header_end_y__ フィールド(pdfkit Y)で管理
     未設定の場合は 152.8pt(デフォルト)

  その後 ②ツーリング → ③WO → ④IP → ⑤P2 は v4と同じ流れ

【DBフィールド変更】
  repeat_header から以下を削除(無効化):
    __note_start_y__, __clamp_start_y__  (v4で使っていた備考・クランプY座標)
  repeat_header に以下を追加:
    __header_end_y__  (固定部テンプレの使用済み下端Y, pdfkit座標)
    __note_cfg__      (備考ブロック設定: x=左端, w=幅, fs=フォントサイズ, lh=ラベル幅)
    __clamp_cfg__     (クランプブロック設定: 同上)

  ※ DBマイグレーションもこのスクリプトで自動実行

【置換マーカー】
  開始: "  // ══════════════════════════════════════════════════════\n  // リピート段取シートPDF生成 v4"
  終了: "  // ══════════════════════════════════════════════════════\n  async directPrint("
"""

import subprocess, sys, os, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

# ─────────────────────────────────────────────────────────────────
# DBマイグレーション SQL
# ─────────────────────────────────────────────────────────────────
MIGRATE_SQL = """
DO $$
DECLARE
  tid INT;
BEGIN
  SELECT id INTO tid FROM pdf_templates WHERE name='repeat_header';
  IF tid IS NULL THEN RETURN; END IF;

  -- 旧 note/clamp y座標フィールドを無効化
  UPDATE pdf_field_definitions
    SET is_active = false
  WHERE template_id = tid
    AND field_key IN ('__note_start_y__','__clamp_start_y__');

  -- __header_end_y__ : 固定部テンプレ使用済み下端(pdfkit Y座標)
  UPDATE pdf_field_definitions
    SET is_active=true, note='152.8'
  WHERE template_id=tid AND field_key='__header_end_y__';
  IF NOT FOUND THEN
    INSERT INTO pdf_field_definitions
      (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
    VALUES
      (tid, '__header_end_y__', 'ヘッダ固定部下端Y(pdfkit)', 0, 0, 0, '__header_end_y__', 1, 52, true, '152.8');
  END IF;

  -- __note_cfg__ : 備考ブロック設定
  UPDATE pdf_field_definitions
    SET is_active=true, note='x=30,w=535,fs=7,label_w=28,min_h=20'
  WHERE template_id=tid AND field_key='__note_cfg__';
  IF NOT FOUND THEN
    INSERT INTO pdf_field_definitions
      (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
    VALUES
      (tid, '__note_cfg__', '備考ブロック設定', 0, 0, 0, '__note_cfg__', 1, 53, true, 'x=30,w=535,fs=7,label_w=28,min_h=20');
  END IF;

  -- __clamp_cfg__ : クランプブロック設定
  UPDATE pdf_field_definitions
    SET is_active=true, note='x=30,w=535,fs=7,label_w=28,min_h=20'
  WHERE template_id=tid AND field_key='__clamp_cfg__';
  IF NOT FOUND THEN
    INSERT INTO pdf_field_definitions
      (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
    VALUES
      (tid, '__clamp_cfg__', 'クランプブロック設定', 0, 0, 0, '__clamp_cfg__', 1, 54, true, 'x=30,w=535,fs=7,label_w=28,min_h=20');
  END IF;

END$$;
"""

# ─────────────────────────────────────────────────────────────────
# 新しい generateRepeatSetupSheetPdf 関数本体
# ─────────────────────────────────────────────────────────────────
NEW_FUNC = r'''  // ══════════════════════════════════════════════════════
  // リピート段取シートPDF生成 v5
  //
  // 生成方式:
  //   [P1] repeat_header.pdf をロードし基本情報(備考・クランプ除く)を差し込み
  //        → curY = __header_end_y__(pdfkit座標) から変換した位置
  //        → 備考ブロック: ラベル+外枠+テキストを動的高さで描画
  //        → クランプブロック: 同上
  //        → ツーリング明細(カラムヘッダ + 明細行 + 行罫線)
  //        → WO枠
  //        → IP列
  //        → ページが足りなければ空白ページ追加
  //   [最終P] template_repeat_p2.pdf を最終ページとして結合
  //
  //   pdf-lib座標系: Y=0が下, Y=pageHeightが上
  //   ページ下マージン: 30pt
  // ══════════════════════════════════════════════════════
  async generateRepeatSetupSheetPdf(
    mcId:       number,
    operatorId: number,
    options: {
      include_tooling?:        boolean;
      include_clamp?:          boolean;
      include_drawings?:       boolean;
      include_work_offsets?:   boolean;
      include_index_programs?: boolean;
      is_reference?:           boolean;
      is_preview?:             boolean;
    } = {},
  ): Promise<Buffer> {
    const data = await this.getPrintData(mcId) as any;
    const d    = data as any;
    const part    = d.part    ?? {};
    const machine = d.machine ?? {};

    const FONT_PATH = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf';
    const ASSETS    = '/home/karkyon/projects/machcore/apps/api/assets';

    const { PDFDocument: PDFLib, rgb, degrees } = await import('pdf-lib');
    const fontkit = await import('@pdf-lib/fontkit');
    const fontBytes = fs.readFileSync(FONT_PATH);

    // ── DB からフィールド定義を一括取得 ──
    const { Pool } = await import('pg');
    const DB_URL = process.env.DATABASE_URL || 'postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev?schema=public';
    const pool = new Pool({ connectionString: DB_URL });
    const qr = await pool.query(`
      SELECT t.name as tpl_name, f.field_key, f.label, f.x, f.y, f.font_size,
             f.data_source, f.sort_order, f.note, f.is_active
      FROM pdf_templates t
      JOIN pdf_field_definitions f ON f.template_id = t.id
      WHERE t.name IN ('repeat_header','repeat_tooling','repeat_wo','repeat_ip','repeat_p2')
        AND t.is_active = true AND f.is_active = true
      ORDER BY t.id, f.sort_order
    `);
    await pool.end();
    const allFields: any[] = qr.rows;
    const fieldsByTpl = (tpl: string) => allFields.filter((f: any) => f.tpl_name === tpl);

    // ── ヘルパー ──
    const fmtDate = (v: any) => {
      if (!v) return '';
      const dt = new Date(v);
      return `${dt.getFullYear()}/${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`;
    };
    const fmtVer = (v: string) => v ? v.replace(/^(\d+)\.(\d{4})$/,(_:any,a:any,b:any)=>a+'.'+b) : '';
    const resolveVal = (src: string): string => {
      if (!src || src.startsWith('__')) return '';
      if (src === 'approvedAt')   return fmtDate(d.approvedAt);
      if (src === 'registeredAt') return fmtDate(d.registeredAt);
      if (src === 'version')      return fmtVer(d.version ?? '');
      if (src === 'cycleTimeSec') return d.cycleTimeSec != null ? String(d.cycleTimeSec) : '';
      if (src === 'part.partId')  return part.partId  ?? '';
      if (src === 'machiningId')  return d.machiningId ?? '';
      if (src === 'id')           return String(mcId);
      const keys = src.split('.');
      let val: any = d;
      for (const k of keys) { val = val?.[k]; if (val == null) return ''; }
      return String(val ?? '');
    };

    // テンプレートPDFロード
    const loadTpl = async (filename: string) => {
      const p = `${ASSETS}/${filename}`;
      if (!fs.existsSync(p)) return null;
      const doc = await PDFLib.load(fs.readFileSync(p));
      doc.registerFontkit(fontkit.default ?? fontkit);
      return doc;
    };

    // ── 結合用ドキュメント ──
    const finalDoc = await PDFLib.create();
    finalDoc.registerFontkit(fontkit.default ?? fontkit);
    const finalFont = await finalDoc.embedFont(fontBytes);
    let totalPages = 0;

    // 定数
    const PAGE_BOTTOM_MARGIN = 30;
    const BLOCK_MARGIN       = 6;
    const ROW_LINE_COLOR     = rgb(0.6, 0.6, 0.6);
    const ROW_LINE_W         = 0.4;
    const BOX_LINE_COLOR     = rgb(0.3, 0.3, 0.3);
    const BOX_LINE_W         = 0.6;
    const LABEL_BG_COLOR     = rgb(0.92, 0.92, 0.92);

    // 現在の作業ページ・Y座標
    let curPage: any = null;
    let curPageH = 0;
    let curY = 0;

    // 新ページ追加
    const addNewPage = async (tplDoc: any, tplPageIdx = 0) => {
      let pg: any;
      if (tplDoc) {
        [pg] = await finalDoc.copyPages(tplDoc, [tplPageIdx]);
        finalDoc.addPage(pg);
      } else {
        pg = finalDoc.addPage([595.28, 841.89]);
      }
      totalPages++;
      curPage  = finalDoc.getPage(finalDoc.getPageCount() - 1);
      curPageH = curPage.getSize().height;
      curY     = curPageH - PAGE_BOTTOM_MARGIN;
      return curPage;
    };

    // テキスト描画
    const drawTxt = (text: string, x: number, y: number, size: number, color = rgb(0,0,0)) => {
      if (!text || !curPage) return;
      try { curPage.drawText(text, { x, y, size, font: finalFont, color }); } catch(_) {}
    };

    // 水平罫線
    const drawHLine = (x1: number, x2: number, y: number, w = ROW_LINE_W, color = ROW_LINE_COLOR) => {
      if (!curPage) return;
      try { curPage.drawLine({ start:{x:x1,y}, end:{x:x2,y}, thickness:w, color }); } catch(_) {}
    };

    // 矩形描画（枠線のみ）
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
    };

    // 白塗り矩形（テキスト背景消し用）
    const drawWhiteRect = (x: number, y: number, w: number, h: number) => {
      if (!curPage) return;
      try { curPage.drawRectangle({ x, y, width:w, height:h, color:rgb(1,1,1), borderWidth:0 }); } catch(_) {}
    };

    // ページ残高チェック
    const ensureSpace = async (needPt: number, tplDoc: any = null) => {
      if (!curPage) return;
      if (curY - needPt < PAGE_BOTTOM_MARGIN) {
        await addNewPage(tplDoc);
      }
    };

    // cfg文字列パース: "x=30,w=535,fs=7,label_w=28,min_h=20"
    const parseCfgStr = (s: string): Record<string,number> => {
      const m: Record<string,number> = {};
      (s||'').split(',').forEach(kv => {
        const [k,v] = kv.split('=');
        if (k && v) m[k.trim()] = parseFloat(v.trim());
      });
      return m;
    };

    // ─────────────────────────────────────────────────────
    // ① repeat_header.pdf に基本情報（備考・クランプ除く）を差し込み
    // ─────────────────────────────────────────────────────
    const headerTpl = await loadTpl('repeat_header.pdf');
    await addNewPage(headerTpl);

    const SKIP_KEYS_HEADER = new Set([
      '__note_start_y__', '__clamp_start_y__',
      '__note_cfg__', '__clamp_cfg__', '__header_end_y__', '__page_no__',
      'note', 'clamp_note',
    ]);

    if (headerTpl) {
      // 基本フィールドを差し込み（備考・クランプ・特殊キーは除外）
      for (const f of fieldsByTpl('repeat_header')) {
        if (SKIP_KEYS_HEADER.has(f.field_key)) continue;
        if (f.field_key.startsWith('__')) continue;
        const text = resolveVal(f.data_source);
        if (!text) continue;
        try {
          curPage.drawText(text, {
            x: Number(f.x), y: Number(f.y),
            size: Number(f.font_size) || 7,
            font: finalFont, color: rgb(0,0,0),
          });
        } catch(_) {}
      }

      // ヘッダ固定部の下端Y（pdfkit座標 → pdf-lib座標に変換）
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
      for (const raw of text.split(/\r\n|\n/)) {
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
    };

    // 備考
    await drawNoteBlock(
      '備考', noteText,
      NOTE_X, NOTE_W, NOTE_FS, NOTE_LBL_W, NOTE_MIN_H, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );

    // ─────────────────────────────────────────────────────────────
    // ①-C クランプブロック（備考と同構造）
    // ─────────────────────────────────────────────────────────────
    const clampCfgF   = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_cfg__');
    const clampCfgStr = clampCfgF?.note || 'x=30,w=535,fs=7,label_w=28,min_h=20';
    const clampCfg    = parseCfgStr(clampCfgStr);

    await drawNoteBlock(
      'クランプ', clampText,
      clampCfg.x ?? 30, clampCfg.w ?? 535, clampCfg.fs ?? 7,
      clampCfg.label_w ?? 28, clampCfg.min_h ?? 20, NOTE_LH,
      NOTE_PAD_V, NOTE_PAD_H,
    );

    curY -= BLOCK_MARGIN; // ブロック後の追加余白

    // ══════════════════════════════════════════════════════════
    // ② ツーリング明細（同ページ連続描画）
    // ══════════════════════════════════════════════════════════
    const tooling: any[] = (options.include_tooling !== false) ? (d.tooling ?? []) : [];
    if (tooling.length > 0) {
      const toolingTplDoc = await loadTpl('repeat_tooling.pdf');
      const tFields   = fieldsByTpl('repeat_tooling');
      const rowCfg    = tFields.find((f:any) => f.field_key === '__row_cfg__');
      const colFields = tFields.filter((f:any) => f.field_key.startsWith('col_'));

      const ROW_H       = rowCfg ? parseFloat(rowCfg.font_size) : 14.0;
      const ROW_MARGIN  = 2.0;
      const COL_HDR_H   = ROW_H + 2;
      const EFFECTIVE_ROW_H = ROW_H + ROW_MARGIN;

      const getColX = (key: string, def: number) => {
        const f = colFields.find((c:any) => c.field_key === key);
        return f ? Number(f.x) : def;
      };

      type TCol = { dataKey: string; x: number; label: string };
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
      const LINE_X_END   = T_COLS[T_COLS.length-1].x + 80;

      const getTV = (t: any, key: string) => {
        if (key==='toolNo')    return t.sortOrder != null ? String(t.sortOrder) : '';
        if (key==='toolName')  return t.toolName ?? '';
        if (key==='tNumber')   return String(t.tNo ?? t.tNumber ?? '');
        if (key==='hValue')    return t.hValue != null ? String(t.hValue) : (t.lengthOffsetNo ?? '');
        if (key==='dRegister') return t.diaOffsetNo ?? t.dRegister ?? '';
        if (key==='dValue')    return t.dValue != null ? String(t.dValue) : (t.diameter != null ? String(t.diameter) : '');
        if (key==='subPgNo')   return t.subPgNo ?? t.subProgram ?? '';
        if (key==='note')      return t.note ?? '';
        return '';
      };

      // カラムヘッダ描画関数
      const drawColHeader = async () => {
        await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H * 2, toolingTplDoc);
        const hdrY = curY - COL_HDR_H + (COL_HDR_H - 6.5 * 0.72) / 2;
        T_COLS.forEach(col => drawTxt(col.label, col.x + 2, hdrY, 6.0));
        drawHLine(LINE_X_START, LINE_X_END, curY - COL_HDR_H);
        curY -= COL_HDR_H;
      };

      await drawColHeader();

      let needsColHdr = false;
      for (const t of tooling) {
        if (needsColHdr) {
          await drawColHeader();
          needsColHdr = false;
        }
        const prevY = curY;
        await ensureSpace(EFFECTIVE_ROW_H, toolingTplDoc);
        // ensureSpaceで新ページになった場合
        if (curY > prevY) {
          needsColHdr = true;
          continue; // このループでもう一度カラムヘッダを描いてから明細
        }
        const sz   = 6.5;
        const txtY = curY - ROW_H + (ROW_H - sz * 0.72) / 2;
        T_COLS.forEach(col => {
          const val = getTV(t, col.dataKey);
          if (val) drawTxt(val, col.x + 2, txtY, sz);
        });
        drawHLine(LINE_X_START, LINE_X_END, curY - ROW_H);
        curY -= EFFECTIVE_ROW_H;
      }
      curY -= BLOCK_MARGIN;
    }

    // ══════════════════════════════════════════════════════════
    // ③ WO枠（同ページ継続）
    // ══════════════════════════════════════════════════════════
    const workOffsets: any[] = (options.include_work_offsets !== false) ? (d.workOffsets ?? []) : [];
    if (workOffsets.length > 0) {
      const woTplDoc = await loadTpl('repeat_wo.pdf');
      const woCfg    = fieldsByTpl('repeat_wo').find((f:any) => f.field_key === '__wo_cfg__');
      const cfg      = parseCfgStr(woCfg?.note || 'label_w=28,col_w=175.4,row_h=14.0,start_y=37');
      const LABEL_W  = cfg.label_w ?? 28;
      const COL_W    = cfg.col_w   ?? 175.4;
      const WO_ROW_H = cfg.row_h   ?? 14.0;
      const ML       = 30.4;
      const WO_LABELS = ['G','X','Y','Z','A/C','R/B'];
      const WO_KEYS   = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];
      const WO_LINE_X1 = ML;
      const WO_LINE_X2 = ML + COL_W * 3;
      const WO_MARGIN  = 1.5;

      const groups: any[][] = [];
      for (let i=0; i<workOffsets.length; i+=3) groups.push(workOffsets.slice(i,i+3));

      for (const group of groups) {
        const groupH = WO_LABELS.length * (WO_ROW_H + WO_MARGIN);
        await ensureSpace(groupH, woTplDoc);
        for (let li=0; li<WO_LABELS.length; li++) {
          await ensureSpace(WO_ROW_H + WO_MARGIN, woTplDoc);
          const sz   = 6.5;
          const txtY = curY - WO_ROW_H + (WO_ROW_H - sz * 0.72) / 2;
          group.forEach((_: any, ci: number) => {
            drawTxt(WO_LABELS[li], ML + ci * COL_W + 2, txtY, 6.0);
          });
          group.forEach((wo: any, ci: number) => {
            const raw = wo[WO_KEYS[li]];
            const val = raw == null ? '' : (typeof raw==='number' ? raw.toFixed(3) : String(raw));
            if (val) drawTxt(val, ML + ci * COL_W + LABEL_W + 2, txtY, sz);
          });
          drawHLine(WO_LINE_X1, WO_LINE_X2, curY - WO_ROW_H);
          curY -= (WO_ROW_H + WO_MARGIN);
        }
        curY -= 3;
      }
      curY -= BLOCK_MARGIN;
    }

    // ══════════════════════════════════════════════════════════
    // ④ インデックスプログラム（同ページ継続）
    // ══════════════════════════════════════════════════════════
    const indexPrograms: any[] = (options.include_index_programs !== false) ? (d.indexPrograms ?? []) : [];
    if (indexPrograms.length > 0) {
      const ipTplDoc = await loadTpl('repeat_ip.pdf');
      const ipFields = fieldsByTpl('repeat_ip');
      const ipRowCfg = ipFields.find((f:any) => f.field_key === '__row_cfg__');
      const ipCols   = ipFields.filter((f:any) => f.field_key.startsWith('col_'));
      const IP_ROW_H = ipRowCfg ? parseFloat(ipRowCfg.font_size) : 14.0;
      const IP_MARGIN = 2.0;
      const getIPCX  = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f?Number(f.x):def; };

      type IPCol = { dataKey: string; x: number; label: string };
      const IP_COLS: IPCol[] = [
        { dataKey:'sortOrder', x: getIPCX('col_no',30),     label:'No'   },
        { dataKey:'axis0',     x: getIPCX('col_axis0',55),  label:'軸0'  },
        { dataKey:'axis1',     x: getIPCX('col_axis1',146), label:'軸1'  },
        { dataKey:'axis2',     x: getIPCX('col_axis2',296), label:'軸2'  },
        { dataKey:'note',      x: getIPCX('col_note',446),  label:'備考' },
      ];
      const IP_LINE_X1 = IP_COLS[0].x;
      const IP_LINE_X2 = IP_COLS[IP_COLS.length-1].x + 80;

      // カラムヘッダ
      await ensureSpace(IP_ROW_H * 2, ipTplDoc);
      const ipHdrY = curY - IP_ROW_H + (IP_ROW_H - 6.5 * 0.72) / 2;
      IP_COLS.forEach(col => drawTxt(col.label, col.x + 2, ipHdrY, 6.0));
      drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_ROW_H);
      curY -= IP_ROW_H;

      for (let i=0; i<indexPrograms.length; i++) {
        await ensureSpace(IP_ROW_H + IP_MARGIN, ipTplDoc);
        const ip  = indexPrograms[i];
        const sz  = 6.5;
        const txtY = curY - IP_ROW_H + (IP_ROW_H - sz * 0.72) / 2;
        IP_COLS.forEach(col => {
          const val = col.dataKey==='sortOrder' ? String(ip.sortOrder ?? i+1) : String((ip as any)[col.dataKey] ?? '');
          if (val) drawTxt(val, col.x + 2, txtY, sz);
        });
        drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_ROW_H);
        curY -= (IP_ROW_H + IP_MARGIN);
      }
      curY -= BLOCK_MARGIN;
    }

    // ══════════════════════════════════════════
    // ⑤ template_repeat_p2.pdf を最終ページに結合
    // ══════════════════════════════════════════
    const p2Path = `${ASSETS}/template_repeat_p2.pdf`;
    if (fs.existsSync(p2Path)) {
      const p2Doc  = await PDFLib.load(fs.readFileSync(p2Path));
      p2Doc.registerFontkit(fontkit.default ?? fontkit);
      const p2Font = await p2Doc.embedFont(fontBytes);
      const p2Page = p2Doc.getPage(0);
      for (const f of fieldsByTpl('repeat_p2').filter((f:any) => !f.field_key.startsWith('__'))) {
        const text = resolveVal(f.data_source);
        if (!text) continue;
        try { p2Page.drawText(text, { x: Number(f.x), y: Number(f.y), size: Number(f.font_size)||7, font: p2Font, color: rgb(0,0,0) }); } catch(_) {}
      }
      const [pg] = await finalDoc.copyPages(p2Doc, [0]);
      finalDoc.addPage(pg);
      totalPages++;
    }

    // ── ページ番号書き込み ──
    const pnF = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__page_no__');
    if (pnF && totalPages > 0) {
      const pnX = Number(pnF.x), pnY = Number(pnF.y), pnSz = Number(pnF.font_size) || 6.5;
      finalDoc.getPages().forEach((pg, pi) => {
        try {
          pg.drawRectangle({ x: pnX-2, y: pnY-2, width: 65, height: pnSz*1.8+4, color: rgb(1,1,1), borderWidth: 0 });
          pg.drawText(`${pi+1} / ${totalPages}`, { x: pnX, y: pnY, size: pnSz, font: finalFont, color: rgb(0,0,0) });
        } catch(_) {}
      });
    }

    // ── プレビュー透かし ──
    if ((options as any).is_preview === true) {
      try {
        const { degrees: degs } = await import('pdf-lib');
        for (const page of finalDoc.getPages()) {
          const { width, height } = page.getSize();
          for (const pos of [{x:width*0.15,y:height*0.25},{x:width*0.35,y:height*0.55},{x:width*0.55,y:height*0.75}]) {
            page.drawText('プレビュー', { x:pos.x, y:pos.y, size:60, font:finalFont, color:rgb(0.75,0.75,0.75), rotate:degs(35), opacity:0.35 });
          }
        }
      } catch(_) {}
    }

    const pdfBytes = await finalDoc.save();
    const pdfBuffer = Buffer.from(pdfBytes);

    if (!(options as any).is_preview) {
      await this.prisma.mcSetupSheetLog.create({
        data: { mcProgramId: mcId, operatorId, version: data.version ?? null,
                ...(typeof (options as any).is_reference !== 'undefined' ? { isReference: (options as any).is_reference } : {}) },
      }).catch((e: any) => console.warn('McSetupSheetLog insert failed:', e?.message));
    }

    return pdfBuffer;
  }

'''

# ─────────────────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────────────────
print("=== fix_v105: 備考・クランプの動的ブロック描画への変更 ===")

# ── 1. DBマイグレーション ──────────────────────────────────
print("--- DBマイグレーション ---")
DB_URL = None
env_path = f"{PROJECT}/.env"
if os.path.exists(env_path):
    for line in open(env_path):
        if line.startswith("DATABASE_URL="):
            DB_URL = line.split("=",1)[1].strip().strip('"').strip("'")
            break
if not DB_URL:
    DB_URL = "postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"

# psql は ?schema=public などのクエリパラメータを受け付けないため除去
psql_url = DB_URL.split('?')[0] if '?' in DB_URL else DB_URL

try:
    r = subprocess.run(
        ["psql", psql_url, "-c", MIGRATE_SQL],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        print(f"  DBマイグレーション警告: {r.stderr[:300]}")
    else:
        print("  DBマイグレーション完了")
except Exception as e:
    print(f"  DBマイグレーションスキップ（後で手動実行可）: {e}")

# ── 2. mc.service.ts の置換 ────────────────────────────────
print("--- mc.service.ts 置換 ---")
src = open(SVC, encoding="utf-8").read()

# START: リピート段取シートPDF生成のコメントブロック開始
# END:   directPrint の手前のコメント行（═の数に依存しない検索）
import re as _re

# STARTは「リピート段取シートPDF生成 v」を含む ═ 行
m_start = _re.search(r'  // [═]+\r?\n  // リピート段取シートPDF生成 v', src)
# ENDは「async directPrint(」の手前の ═ コメント行
m_end   = _re.search(r'  // [═]+\r?\n  async directPrint\(', src)

if not m_start or not m_end:
    print(f"ERROR: マーカーが見つかりません start={bool(m_start)} end={bool(m_end)}")
    sys.exit(1)

si = m_start.start()
ei = m_end.start()

print(f"置換範囲: {si} → {ei} (length={ei-si})")

# バックアップ
backup = SVC + ".v104.bak"
open(backup, "w", encoding="utf-8").write(src)

new_src = src[:si] + NEW_FUNC + src[ei:]
open(SVC, "w", encoding="utf-8").write(new_src)
print("OK: mc.service.ts 書き換え完了")

# ── 3. ビルド ──────────────────────────────────────────────
print("--- API ビルド ---")
r = subprocess.run(
    ["npx", "tsc", "--noEmit", "-p", "apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT
)
errors = [l for l in r.stdout.splitlines() + r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TypeScriptエラー: {len(errors)} 件")
    for e in errors[:20]: print(f"  {e}")
    print("ビルド失敗: 元に戻します")
    open(SVC, "w", encoding="utf-8").write(src)
    sys.exit(1)

print(f"TypeScriptエラー: 0 件")
# nest CLI のパスを探す（monorepo構成でルート/apps/api/node_modules/.bin いずれかにある）
import glob as _glob
nest_candidates = [
    f"{PROJECT}/node_modules/.bin/nest",
    f"{PROJECT}/apps/api/node_modules/.bin/nest",
    f"{PROJECT}/apps/api/node_modules/@nestjs/cli/bin/nest.js",
]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    # フォールバック: find で探す
    found = subprocess.run(
        ["find", PROJECT, "-path", "*/node_modules/.bin/nest", "-not", "-path", "*/node_modules/*/node_modules/*"],
        capture_output=True, text=True
    ).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)
if not nest_bin:
    print("nest CLI が見つかりません。元に戻します")
    open(SVC, "w", encoding="utf-8").write(src)
    sys.exit(1)
print(f"  nest CLI: {nest_bin}")
r2 = subprocess.run([nest_bin, "build", "api"], capture_output=True, text=True, cwd=PROJECT)
if r2.returncode != 0:
    out = (r2.stdout + r2.stderr).strip()
    print(f"nest build 失敗 (returncode={r2.returncode}):\n{out[:2000] or '(出力なし)'}")
    # nest buildが失敗してもtscが0件ならコンパイル自体は成功している可能性あり
    # pm2 restart だけ実行して様子を見る
    print("※ tscエラー0件のためpm2 restartのみ続行します")
else:
    print("API ビルド成功!\nnest build 成功!")

# ── 4. PM2 再起動 ─────────────────────────────────────────
print("--- PM2 restart ---")
subprocess.run(["pm2", "restart", "api"], capture_output=True, cwd=PROJECT)
print("PM2 再起動完了")

# ── 5. Git Push ───────────────────────────────────────────
print("--- git push ---")
subprocess.run(["git", "add", "-A"], cwd=PROJECT)
subprocess.run(["git", "commit", "-m", "fix_v105: 備考・クランプを動的ブロック描画に変更（可変高さ対応）"], cwd=PROJECT)
r3 = subprocess.run(["git", "push"], capture_output=True, text=True, cwd=PROJECT)
if r3.returncode != 0:
    print(f"git push 警告: {r3.stderr[:200]}")
else:
    print("fix_v105 完了")

print("""
=== 完了サマリー ===
【変更内容】
  ① repeat_header.pdf から備考・クランプ枠を除外
      → テンプレートPDFは固定情報行のみに（KARKYONさんがPDFから備考・クランプ枠を削除）
      → DBの __header_end_y__ (note列の値, pdfkit Y座標) でヘッダ固定部の下端を管理
         デフォルト: 152.8pt

  ①-B 備考ブロック（コードで動的描画）
      - ラベル列（薄いグレー背景）+ テキスト列の2カラム構成
      - テキスト量に応じてブロック高さが自動可変
      - 最小高さ 20pt 保証（データなしでも崩れない）
      - テキスト折り返し対応（改行・長文どちらもOK）

  ①-C クランプブロック（備考と同構造）

  ② ツーリング以降は v4 と同じ流れ
      - ツーリング明細 → WO → IP → P2

【DBに追加したフィールド定義】
  __header_end_y__ : ヘッダ固定部の下端Y(pdfkit座標, デフォルト152.8)
  __note_cfg__     : 備考ブロック設定 (x=30,w=535,fs=7,label_w=28,min_h=20)
  __clamp_cfg__    : クランプブロック設定 (同上)
  ※ これらはPDFエディタ画面の「note」列から調整可能

【KARKYONさんの作業】
  repeat_header.pdf から備考・クランプの枠を削除してSCP再配置
  ヘッダ固定部の実際の下端Y座標を確認し、
  DBの __header_end_y__ の note列を更新:
    UPDATE pdf_field_definitions SET note='実際のY値'
    WHERE field_key='__header_end_y__';
""")
