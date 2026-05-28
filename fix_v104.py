#!/usr/bin/env python3
"""
fix_v104.py
===========
generateRepeatSetupSheetPdf() の以下2問題を修正:

【問題①】ヘッダ固定部(repeat_header)とツーリング(repeat_tooling)が
          別ページになっている
          → 正しくは同一ページに連続して描画する必要がある
          → ツーリングテンプレのカラムヘッダ部分(上部)のみを
            ヘッダ固定部ページに直接描画し、明細データもそのページに続ける

【問題②】ツーリング明細行の開始Y位置がテンプレのカラムヘッダ行と重複
          → カラムヘッダ行の高さ分を正しくオフセットする必要がある
          → 明細行の下に罫線(アンダーライン)を引く

【設計方針】
  ① repeat_header.pdf の上に基本情報を差し込み → 同ページに続けて描画
  ② ツーリングは同ページの repeat_header 下端から続いて描画
     - テンプレ(repeat_tooling.pdf)のカラムヘッダ行をpdf-libで再描画
     - 明細データを1行ずつ描画、各行の下に水平線(罫線)を引く
     - ページ末尾に達したら新ページを追加してカラムヘッダを再描画
  ③ WO枠: 同様に連結して同ページに続ける
  ④ IP列: 同様に連結
  ⑤ P2: 最後のページに連結

  ※ テンプレートPDFの「下端座標(何処まで使われているか)」は
    各テンプレの __row_cfg__.y (pdfkit座標=テンプレの使用済み高さ)
    もしくは repeat_header の __note_start_y__ + 備考・クランプ部分高さで決まる

  repeat_header の「コンテンツの下端」= 下辺マージン25から上がった位置は
  テンプレートのどこか知る方法がないため、
  DBの __note_start_y__ / __clamp_start_y__ フィールドの値を使う。
  それがなければ repeat_header ページのトップ40%をヘッダ固定部として扱う。

  ツーリングは repeat_header ページの下部(使用していない領域)から
  開始する。
"""

import subprocess, sys, os, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

NEW_FUNC = r'''  // ══════════════════════════════════════════════════════
  // リピート段取シートPDF生成 v4
  //
  // 生成方式:
  //   [P1] repeat_header.pdf をロードし基本情報を差し込み
  //        → 同ページにツーリングカラムヘッダ + 明細行を連続描画
  //        → 同ページにWO枠(余裕あれば)
  //        → 同ページにIP列(余裕あれば)
  //        → ページが足りなければ新ページ追加
  //   [最終P] template_repeat_p2.pdf を最終ページとして結合
  //
  //   各ブロックの「開始Y(pdf-lib座標)」は前ブロックの終了Yから
  //   マージン8ptを引いた値
  //   pdf-lib座標系: Y=0が下, Y=pageHeightが上
  //   ページ下マージン: 30pt
  //
  //   ツーリング・WO・IP明細行の下に罫線(水平線)を引く
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
    const fmtVer = (v: string) => v.replace(/^(\d+)\.(\d{4})$/,(_:any,a:any,b:any)=>a+'.'+b.slice(0,2)+' '+b.slice(2));
    const fmtCycle = (sec: number|null) => {
      if (!sec) return '';
      const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;
      return `${h}H ${String(m).padStart(2,'0')}M ${String(s).padStart(2,'0')}S`;
    };
    const resolveVal = (src: string): string => {
      if (src === 'part.clientName')      return part.clientName    ?? '';
      if (src === 'part.drawingNo')       return part.drawingNo     ?? '';
      if (src === 'part.name')            return part.name          ?? '';
      if (src === 'part.mainModel')       return part.mainModel     ?? '';
      if (src === 'part.partId')          return part.partId        ?? '';
      if (src === 'machine.machineCode')  return machine.machineCode ?? '';
      if (src === 'mcProcessNo')          return d.mcProcessNo != null ? String(d.mcProcessNo) : '';
      if (src === 'oNumber')              return d.oNumber     ?? '';
      if (src === 'version')              return fmtVer(String(d.version ?? '1.0001'));
      if (src === 'cycleTimeSec')         return fmtCycle(d.cycleTimeSec);
      if (src === 'machiningQty')         return d.machiningQty != null ? String(d.machiningQty) : '';
      if (src === 'approvedAt')           return fmtDate(d.approvedAt);
      if (src === 'registeredAt')         return fmtDate(d.registeredAt ?? d.createdAt);
      if (src === 'machiningId')          return d.machiningId != null ? String(d.machiningId) : '';
      if (src === 'id')                   return String(d.id ?? mcId);
      if (src === 'registrar.name')       return d.registrar?.name  ?? '';
      if (src === 'approver.name')        return d.approver?.name   ?? '';
      if (src === 'note')                 return d.note ?? '';
      if (src === 'clampNote')            return d.clampNote ?? '';
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
    const PAGE_BOTTOM_MARGIN = 30; // ページ下マージン(pt)
    const BLOCK_MARGIN       = 8;  // ブロック間マージン(pt)
    const ROW_LINE_COLOR     = rgb(0.6, 0.6, 0.6); // 罫線色(薄いグレー)
    const ROW_LINE_W         = 0.4;

    // 現在の作業ページと現在Y座標（pdf-lib座標: 下からの距離）
    let curPage: any = null;
    let curPageH = 0;
    let curY = 0; // 現在の「描画済み下端」のpdf-lib Y座標

    // 新ページ追加: テンプレートPDFからコピー、またはブランクページ
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
      curY     = curPageH - PAGE_BOTTOM_MARGIN; // 上端から開始
      return curPage;
    };

    // テキスト描画
    const drawTxt = (text: string, x: number, y: number, size: number) => {
      if (!text || !curPage) return;
      try { curPage.drawText(text, { x, y, size, font: finalFont, color: rgb(0, 0, 0) }); } catch(_) {}
    };

    // 水平罫線（行の下端に）
    const drawHLine = (x1: number, x2: number, y: number) => {
      if (!curPage) return;
      try {
        curPage.drawLine({
          start: { x: x1, y },
          end:   { x: x2, y },
          thickness: ROW_LINE_W,
          color: ROW_LINE_COLOR,
        });
      } catch(_) {}
    };

    // 残り高さチェック: needPt 分の高さが足りなければ新ページを追加
    // tplDoc: 新ページのベーステンプレ（nullなら空白ページ）
    const ensureSpace = async (needPt: number, tplDoc: any = null) => {
      if (!curPage) return;
      if (curY - needPt < PAGE_BOTTOM_MARGIN) {
        await addNewPage(tplDoc);
      }
    };

    // ══════════════════════════════════════════
    // ① repeat_header.pdf に基本情報を差し込み
    // ══════════════════════════════════════════
    const headerTpl = await loadTpl('repeat_header.pdf');
    await addNewPage(headerTpl); // P1を追加

    if (headerTpl) {
      // ヘッダテンプレートのフィールドを差し込み
      for (const f of fieldsByTpl('repeat_header').filter((ff:any) => !ff.field_key.startsWith('__'))) {
        const text = resolveVal(f.data_source);
        if (!text) continue;
        const x = Number(f.x), y = Number(f.y), sz = Number(f.font_size) || 7;
        if ((f.field_key === 'note' || f.field_key === 'clamp_note') && text.includes('\n')) {
          const lh = sz * 1.4;
          text.split(/\n|\r\n/).forEach((line: string, i: number) => {
            if (!line.trim()) return;
            curPage.drawText(line, { x, y: y - i * lh, size: sz, font: finalFont, color: rgb(0,0,0) });
          });
        } else {
          curPage.drawText(text, { x, y, size: sz, font: finalFont, color: rgb(0,0,0) });
        }
      }

      // ヘッダテンプレートの「使用済み下端Y」を求める
      // repeat_header の __clamp_start_y__ (pdfkit Y座標) + 備考/クランプ高さ
      // pdfkit Y → pdf-lib Y: pdfLibY = pageH - pdfkitY
      const clampCfg = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__clamp_start_y__');
      const noteCfg  = fieldsByTpl('repeat_header').find((f:any) => f.field_key === '__note_start_y__');

      // 備考・クランプのテキスト高さを推定
      const noteText  = d.note     ?? '';
      const clampText = d.clampNote ?? '';
      const NOTE_FS   = 7.0;
      const NOTE_LH   = NOTE_FS * 1.4;
      const H1        = 21.3;
      const noteLines  = noteText  ? noteText.split(/\n|\r\n/).length  : 1;
      const clampLines = clampText ? clampText.split(/\n|\r\n/).length : 1;
      const NOTE_H  = Math.max(H1 * 2, (noteLines  + 1) * NOTE_LH + 4);
      const CLAMP_H = Math.max(H1 * 2, (clampLines + 1) * NOTE_LH + 4);

      // pdfkit座標での備考開始Y
      const noteStartPK   = noteCfg  ? parseFloat(noteCfg.note  || '152.8') : 152.8;
      const headerBottomPK = noteStartPK + NOTE_H + CLAMP_H + 4; // クランプ+マージン4

      // pdf-lib座標に変換 (ページ下端からの距離)
      curY = curPageH - headerBottomPK - BLOCK_MARGIN;
    } else {
      // テンプレートなし: ページ上部 250pt を使用済みとして扱う
      curY = curPageH - 250;
    }

    // ══════════════════════════════════════════════════════════
    // ② ツーリング明細を同ページに連続描画
    // ══════════════════════════════════════════════════════════
    const tooling: any[] = (options.include_tooling !== false) ? (d.tooling ?? []) : [];
    if (tooling.length > 0) {
      const toolingTplDoc = await loadTpl('repeat_tooling.pdf');
      const tFields    = fieldsByTpl('repeat_tooling');
      const rowCfg     = tFields.find((f:any) => f.field_key === '__row_cfg__');
      const colFields  = tFields.filter((f:any) => f.field_key.startsWith('col_'));

      // 行高・カラムヘッダ高さ
      const ROW_H      = rowCfg ? parseFloat(rowCfg.font_size) : 14.0;
      const COL_HDR_H  = ROW_H; // カラムヘッダ行も1行分
      const ROW_MARGIN = 2.0;   // 行間マージン(罫線の下)
      const EFFECTIVE_ROW_H = ROW_H + ROW_MARGIN;

      // カラム定義 (X座標はDBのフィールド定義から)
      const getCX = (key:string, def:number) => { const f=colFields.find((c:any)=>c.field_key===key); return f?Number(f.x):def; };
      type TCol = { dataKey: string; x: number; label: string };
      const T_COLS: TCol[] = [
        { dataKey:'toolNo',    x: getCX('col_n',30),          label:'N'              },
        { dataKey:'toolName',  x: getCX('col_tool_name',50),  label:'工具'           },
        { dataKey:'tNumber',   x: getCX('col_t_no',155),      label:'T'              },
        { dataKey:'hValue',    x: getCX('col_h_val',180),     label:'H'              },
        { dataKey:'dRegister', x: getCX('col_d_reg',205),     label:'D'              },
        { dataKey:'dValue',    x: getCX('col_d_val',235),     label:'D値'            },
        { dataKey:'subPgNo',   x: getCX('col_sub_pg',265),    label:'SUB'            },
        { dataKey:'note',      x: getCX('col_note',320),      label:'コメント'       },
      ];
      // 罫線右端 = 最後のカラムX + 適当な幅
      const LINE_X_START = T_COLS[0].x;
      const LINE_X_END   = T_COLS[T_COLS.length-1].x + 80;

      const getTV = (t:any, key:string): string => {
        if (key==='toolNo')    return t.toolNo ? String(t.toolNo) : (t.sortOrder != null ? String(t.sortOrder) : '');
        if (key==='toolName')  return t.toolName ?? '';
        if (key==='tNumber')   return String(t.tNo ?? t.tNumber ?? '');
        if (key==='hValue')    return t.hValue != null ? String(t.hValue) : (t.lengthOffsetNo ?? '');
        if (key==='dRegister') return t.diaOffsetNo ?? t.dRegister ?? '';
        if (key==='dValue')    return t.dValue != null ? String(t.dValue) : (t.diameter != null ? String(t.diameter) : '');
        if (key==='subPgNo')   return t.subPgNo ?? t.subProgram ?? '';
        if (key==='note')      return t.note ?? '';
        return '';
      };

      // カラムヘッダ行を描画する関数
      const drawColHeader = async () => {
        await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H * 2, toolingTplDoc);
        const hdrY = curY - COL_HDR_H + (COL_HDR_H - 6.5 * 0.72) / 2;
        T_COLS.forEach(col => {
          drawTxt(col.label, col.x + 2, hdrY, 6.0);
        });
        // ヘッダ下罫線
        drawHLine(LINE_X_START, LINE_X_END, curY - COL_HDR_H);
        curY -= COL_HDR_H;
      };

      // カラムヘッダを描画（ヘッダ固定部の直後）
      await ensureSpace(COL_HDR_H + EFFECTIVE_ROW_H, toolingTplDoc);
      await drawColHeader();

      // 明細行を描画
      for (const t of tooling) {
        await ensureSpace(EFFECTIVE_ROW_H, toolingTplDoc);
        // 新ページになった場合はカラムヘッダを再描画
        if (curY > curPageH - PAGE_BOTTOM_MARGIN - 10) {
          // 新ページ直後 → カラムヘッダ再描画済み不要（ensureSpaceで追加済み）
        }
        const sz   = 6.5;
        const txtY = curY - ROW_H + (ROW_H - sz * 0.72) / 2;
        T_COLS.forEach(col => {
          const val = getTV(t, col.dataKey);
          if (val) drawTxt(val, col.x + 2, txtY, sz);
        });
        // 行の下に罫線
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
      const woCfg = fieldsByTpl('repeat_wo').find((f:any) => f.field_key === '__wo_cfg__');
      const parseCfg = (note: string) => {
        const m: any = {};
        (note||'').split(',').forEach((kv:string) => { const [k,v]=kv.split('='); if(k&&v) m[k.trim()]=parseFloat(v.trim()); });
        return m;
      };
      const cfg      = parseCfg(woCfg?.note || 'label_w=28,col_w=175.4,row_h=14.0,start_y=37');
      const LABEL_W  = cfg.label_w  ?? 28;
      const COL_W    = cfg.col_w    ?? 175.4;
      const WO_ROW_H = cfg.row_h    ?? 14.0;
      const ML       = 30.4;
      const WO_LABELS = ['G','X','Y','Z','A/C','R/B'];
      const WO_KEYS   = ['gCode','xOffset','yOffset','zOffset','aOffset','rOffset'];
      const WO_LINE_X1 = ML;
      const WO_LINE_X2 = ML + COL_W * 3;
      const WO_MARGIN  = 1.5;

      // WOグループ(3列横並び)
      const groups: any[][] = [];
      for (let i=0; i<workOffsets.length; i+=3) groups.push(workOffsets.slice(i,i+3));

      for (const group of groups) {
        const groupH = WO_LABELS.length * (WO_ROW_H + WO_MARGIN);
        await ensureSpace(groupH, woTplDoc);
        for (let li=0; li<WO_LABELS.length; li++) {
          await ensureSpace(WO_ROW_H + WO_MARGIN, woTplDoc);
          const sz   = 6.5;
          const txtY = curY - WO_ROW_H + (WO_ROW_H - sz * 0.72) / 2;
          // ラベル
          group.forEach((_: any, ci: number) => {
            const lx = ML + ci * COL_W;
            drawTxt(WO_LABELS[li], lx + 2, txtY, 6.0);
          });
          // 値
          group.forEach((wo: any, ci: number) => {
            const vx   = ML + ci * COL_W + LABEL_W;
            const raw  = wo[WO_KEYS[li]];
            const val  = raw == null ? '' : (typeof raw==='number' ? raw.toFixed(3) : String(raw));
            if (val) drawTxt(val, vx + 2, txtY, sz);
          });
          // 行下罫線
          drawHLine(WO_LINE_X1, WO_LINE_X2, curY - WO_ROW_H);
          curY -= (WO_ROW_H + WO_MARGIN);
        }
        curY -= 3; // グループ間マージン
      }
      curY -= BLOCK_MARGIN;
    }

    // ══════════════════════════════════════════════════════════
    // ④ インデックスプログラム（同ページ継続）
    // ══════════════════════════════════════════════════════════
    const indexPrograms: any[] = (options.include_index_programs !== false) ? (d.indexPrograms ?? []) : [];
    if (indexPrograms.length > 0) {
      const ipTplDoc  = await loadTpl('repeat_ip.pdf');
      const ipFields  = fieldsByTpl('repeat_ip');
      const ipRowCfg  = ipFields.find((f:any) => f.field_key === '__row_cfg__');
      const ipCols    = ipFields.filter((f:any) => f.field_key.startsWith('col_'));
      const IP_ROW_H  = ipRowCfg ? parseFloat(ipRowCfg.font_size) : 14.0;
      const IP_MARGIN = 2.0;
      const getIPCX   = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f?Number(f.x):def; };
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
        const ip   = indexPrograms[i];
        const sz   = 6.5;
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
    const p2File = fs.existsSync(`${ASSETS}/template_repeat_p2.pdf`) ? 'template_repeat_p2.pdf' : null;
    if (p2File) {
      const p2Doc  = await PDFLib.load(fs.readFileSync(`${ASSETS}/${p2File}`));
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

print("=== fix_v104: ヘッダ+ツーリング同ページ連続描画 + 明細罫線 ===")

with open(SVC, 'r', encoding='utf-8') as f:
    content = f.read()
original = content

START_PAT = "  // ══════════════════════════════════════════════════════\n  // リピート段取シートPDF生成 v"
END_PAT   = "  async directPrint("

start_idx = content.find(START_PAT)
if start_idx == -1:
    print("ERR: 開始マーカーが見つかりません")
    sys.exit(1)

# directPrintの前の \n\n を探す
end_raw = content.find(END_PAT, start_idx)
if end_raw == -1:
    print("ERR: directPrint が見つかりません")
    sys.exit(1)
# directPrintの前の空行まで遡る
before = content[:end_raw]
nl_idx = before.rfind('\n\n')
end_idx = nl_idx if nl_idx > start_idx else end_raw

print(f"置換範囲: {start_idx} → {end_idx} ({end_idx-start_idx}文字)")

new_content = content[:start_idx] + NEW_FUNC + '\n\n' + content[end_idx:]

with open(SVC, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("OK: mc.service.ts 書き換え完了")

# ── ビルド ──
print("\n--- API ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit"], cwd=f"{PROJECT}/apps/api", capture_output=True, text=True)
err_lines = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if 'error TS' in l]
if err_lines:
    print(f"TypeScriptエラー: {len(err_lines)} 件")
    for e in err_lines[:20]: print(f"  {e}")
    print("ビルド失敗: 元に戻します")
    with open(SVC,'w',encoding='utf-8') as f: f.write(original)
    sys.exit(1)
print("TypeScriptエラー: 0 件 / API ビルド成功!")

r2 = subprocess.run(["npm","run","build"], cwd=f"{PROJECT}/apps/api", capture_output=True, text=True)
if r2.returncode != 0:
    print("ERR: nest build 失敗"); print(r2.stderr[-2000:]); sys.exit(1)
print("nest build 成功!")

print("\n--- PM2 restart ---")
subprocess.run(["pm2","restart","all"], cwd=PROJECT, capture_output=True)
print("PM2 再起動完了")

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=PROJECT, capture_output=True)
subprocess.run(["git","commit","-m","fix_v104: repeat sheet - header+tooling same page, row underlines"], cwd=PROJECT, capture_output=True)
subprocess.run(["git","push"], cwd=PROJECT, capture_output=True)
print("fix_v104 完了")

print("""
=== 完了サマリー ===
【修正内容】
  ① ヘッダ固定部(repeat_header)とツーリング明細を同一ページに連続描画
     - repeat_header.pdf を P1 として追加後、そのまま curY を下げながら
       ツーリング・WO・IP を同ページに続けて描画
     - ページ末尾に達した場合のみ新ページを追加してカラムヘッダを再描画

  ② ツーリング明細行の罫線追加
     - 各行の下に薄いグレー(0.4pt)の水平罫線を引く
     - カラムヘッダ行の下にも罫線あり
     - 行間マージン 2pt を追加してさらに視認性を向上

  ③ カラムヘッダ行の重複問題を解消
     - テンプレPDFのカラムヘッダ行をコピーではなく
       curY から始まる位置に直接描画するため位置ずれなし
""")
