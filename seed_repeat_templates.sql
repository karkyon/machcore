
DO $$
DECLARE
  tid_rh  INT;
  tid_rt  INT;
  tid_rwo INT;
  tid_rip INT;
BEGIN
  -- repeat_header
  INSERT INTO pdf_templates (name, description, file_path, page_number, is_active, created_at, updated_at)
  VALUES ('repeat_header', 'リピート段取シート: 基本情報ヘッダ固定部分',
          'assets/repeat_header.pdf', 1, true, NOW(), NOW())
  ON CONFLICT DO NOTHING;
  SELECT id INTO tid_rh FROM pdf_templates WHERE name='repeat_header';

  -- repeat_tooling
  INSERT INTO pdf_templates (name, description, file_path, page_number, is_active, created_at, updated_at)
  VALUES ('repeat_tooling', 'リピート段取シート: ツーリングリスト ヘッダ行',
          'assets/repeat_tooling.pdf', 1, true, NOW(), NOW())
  ON CONFLICT DO NOTHING;
  SELECT id INTO tid_rt FROM pdf_templates WHERE name='repeat_tooling';

  -- repeat_wo
  INSERT INTO pdf_templates (name, description, file_path, page_number, is_active, created_at, updated_at)
  VALUES ('repeat_wo', 'リピート段取シート: ワークオフセット枠',
          'assets/repeat_wo.pdf', 1, true, NOW(), NOW())
  ON CONFLICT DO NOTHING;
  SELECT id INTO tid_rwo FROM pdf_templates WHERE name='repeat_wo';

  -- repeat_ip
  INSERT INTO pdf_templates (name, description, file_path, page_number, is_active, created_at, updated_at)
  VALUES ('repeat_ip', 'リピート段取シート: インデックスプログラム ヘッダ行',
          'assets/repeat_ip.pdf', 1, true, NOW(), NOW())
  ON CONFLICT DO NOTHING;
  SELECT id INTO tid_rip FROM pdf_templates WHERE name='repeat_ip';

  -- ── repeat_header フィールド定義 ──────────────────────────────────────
  -- pdf-lib 座標系 (y=下からの距離, A4H=841.89)
  -- pdfkit y座標 → pdf-lib y座標 = 841.89 - pdfkitY - fontSize*0.72
  -- pdfkitY で各フィールドの上端y: タイトル行(h=21.3)後から各行
  -- タイトル行 y=25, h=21.3 → 次行開始 y=46.3
  -- 行1(納入先/図番) y=46.3, h=21.3
  -- 行2(名称)        y=67.6
  -- 行3(主機種/機械) y=88.9
  -- 行4(工程/ONo/VER)y=110.2
  -- 行5(CT/数量/承認/登録)y=131.5
  -- 備考起点         y=152.8
  -- クランプ起点     y=152.8 + NOTE_H/2 (可変)
  -- pdf-lib y = 841.89 - pdfkitY - (h-fs*0.72)/2 - fs*0.72
  --   ≈ 841.89 - pdfkitY - h/2 + fs*0.72/2 - fs*0.72
  --   ≈ 841.89 - pdfkitY - h/2 - fs*0.36
  -- 簡易: テキスト中央 pdf-lib y ≈ 841.89 - (pdfkitY + h/2) + fs*0.72/2

  DELETE FROM pdf_field_definitions WHERE template_id = tid_rh;
  INSERT INTO pdf_field_definitions
    (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
  VALUES
    -- 納入先 (行1左: x=ML+COL1=85.4, y=46.3, h=21.3, fs=7)
    (tid_rh, 'client_name',   '納入先',   86, 804, 7.0, 'part.clientName',    1,  1, true, NULL),
    -- 図面番号 (行1右: x=ML+COL1+150+COL1=290.4, h=21.3, fs=7)
    (tid_rh, 'drawing_no',    '図面番号', 291, 804, 7.0, 'part.drawingNo',     1,  2, true, NULL),
    -- 名称 (行2: x=85.4, y=67.6, h=21.3, fs=7)
    (tid_rh, 'part_name',     '名称',      86, 783, 7.0, 'part.name',          1,  3, true, NULL),
    -- 主機種型式 (行3: x=85.4, y=88.9, h=21.3, fs=7)
    (tid_rh, 'main_model',    '主機種型式', 86, 761, 7.0, 'part.mainModel',    1,  4, true, NULL),
    -- 機械 (行3右: x=ML+COL1+120+COL1=260.4, h=21.3, fs=7)
    (tid_rh, 'machine_code',  '機械',     261, 761, 7.0, 'machine.machineCode',1, 5, true, NULL),
    -- 工程No (行4: x=85.4, y=110.2, h=21.3, fs=7)
    (tid_rh, 'mc_process_no', '工程No',    86, 740, 7.0, 'mcProcessNo',        1,  6, true, NULL),
    -- ONo (行4: x=85.4+40+55=180.4+COL1=235.4 → ML+COL1+40+COL1=195.4)
    (tid_rh, 'o_number',      'ONo',      196, 740, 7.0, 'oNumber',            1,  7, true, NULL),
    -- VER (行4: x=ML+2*(COL1+100)=30.4+2*155=340.4 → x=ML+COL1+40+COL1+60+COL1=305.4)
    (tid_rh, 'version',       'VER',      306, 740, 7.0, 'version',            1,  8, true, NULL),
    -- CT (行5: x=85.4, y=131.5, h=21.3, fs=7)
    (tid_rh, 'cycle_time',    'CT',        86, 718, 7.0, 'cycleTimeSec',       1,  9, true, NULL),
    -- 数量 (行5: x=ML+COL1+60+COL1=195.4)
    (tid_rh, 'machining_qty', '数量',     196, 718, 7.0, 'machiningQty',       1, 10, true, NULL),
    -- 承認日 (行5)
    (tid_rh, 'approved_at',   '承認日',   261, 718, 7.0, 'approvedAt',         1, 11, true, NULL),
    -- 登録日 (行5右)
    (tid_rh, 'registered_at', '登録日',   361, 718, 7.0, 'registeredAt',       1, 12, true, NULL),
    -- ページ番号 (右下)
    (tid_rh, '__page_no__',   'ページ番号', 527, 15, 6.5, '__page_no__',       1, 99, true, NULL),
    -- 備考起点Y座標 (data_sourceではなく座標定義として使用)
    (tid_rh, '__note_start_y__',   '備考起点Y(pdfkit)', 0, 0, 0, '__note_start_y__',   1, 50, true, '152.8'),
    -- クランプ起点Y座標 (可変なのでコード側で計算、ここではfallback)
    (tid_rh, '__clamp_start_y__',  'クランプ起点Y(pdfkit)', 0, 0, 0, '__clamp_start_y__', 1, 51, true, '174.1');

  -- ── repeat_tooling フィールド定義 ──────────────────────────────────────
  -- ヘッダ行のX座標 + 明細行の row_y_start, row_height
  -- pdfkit: SEC_H=12 at y=25, header y=37, row y=51
  -- A4H=841.89, pdf-lib rowY = 841.89 - 51 - TH = 841.89 - 51 - 14 = 776.89
  DELETE FROM pdf_field_definitions WHERE template_id = tid_rt;
  INSERT INTO pdf_field_definitions
    (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
  VALUES
    (tid_rt, 'col_n',         'N列X',        30,  0, 6.5, 'toolNo',      1, 1, true, '20'),
    (tid_rt, 'col_tool_name', '工具名称X',   50,  0, 6.5, 'toolName',    1, 2, true, '105'),
    (tid_rt, 'col_t_no',      'T番号X',     155,  0, 6.5, 'tNumber',     1, 3, true, '25'),
    (tid_rt, 'col_h_val',     'H値X',       180,  0, 6.5, 'hValue',      1, 4, true, '25'),
    (tid_rt, 'col_d_reg',     'D登録X',     205,  0, 6.5, 'dRegister',   1, 5, true, '30'),
    (tid_rt, 'col_d_val',     'D値X',       235,  0, 6.5, 'dValue',      1, 6, true, '30'),
    (tid_rt, 'col_sub_pg',    'サブPGX',    265,  0, 6.5, 'subProgram',  1, 7, true, '55'),
    (tid_rt, 'col_note',      '備考X',      320,  0, 6.5, 'note',        1, 8, true, '236'),
    -- 明細行の設定 (note列に行高, y列に先頭明細Y=pdfkit)
    (tid_rt, '__row_cfg__',   '行設定', 30, 51, 14.0, '__row__', 1, 99, true, '14.0');

  -- ── repeat_wo フィールド定義 ──────────────────────────────────────────
  -- 3列横並び, 各列幅=PW/3≈175.4
  -- pdfkit: SEC_H=12 at y=25, WO rows start y=37
  DELETE FROM pdf_field_definitions WHERE template_id = tid_rwo;
  INSERT INTO pdf_field_definitions
    (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
  VALUES
    -- 構成定義: label_w / col_w / row_h / start_y(pdfkit)
    (tid_rwo, '__wo_cfg__', 'WO設定', 30, 37, 14.0, '__wo__', 1, 99, true, 'label_w=28,col_w=175.4,row_h=14.0,start_y=37');

  -- ── repeat_ip フィールド定義 ──────────────────────────────────────────
  -- pdfkit: SEC_H=12 at y=25, header y=37, row y=51
  DELETE FROM pdf_field_definitions WHERE template_id = tid_rip;
  INSERT INTO pdf_field_definitions
    (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
  VALUES
    (tid_rip, 'col_no',    'NoX',   30,  0, 6.5, 'sortOrder', 1, 1, true, '25'),
    (tid_rip, 'col_axis0', '軸0X',  55,  0, 6.5, 'axis0',     1, 2, true, '91'),
    (tid_rip, 'col_axis1', '軸1X', 146,  0, 6.5, 'axis1',     1, 3, true, '150'),
    (tid_rip, 'col_axis2', '軸2X', 296,  0, 6.5, 'axis2',     1, 4, true, '150'),
    (tid_rip, 'col_note',  '備考X',446,  0, 6.5, 'note',      1, 5, true, '110'),
    (tid_rip, '__row_cfg__', '行設定', 30, 51, 14.0, '__row__', 1, 99, true, '14.0');

END$$;
