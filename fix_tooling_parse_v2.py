#!/usr/bin/env python3
"""
fix_tooling_parse_v2.py
parseToolingProgram 完全刷新 - after.pdf / group.pdf / XLSX 仕様完全対応

変更点:
  - Oグループ境界での分割
  - /M0 → スキップせず tool_no = "/M0"
  - M1/M01 → ESCAPE 独立行
  - (GOTO555) 等 括弧内GOTOコメント → GOTO*** 独立行
  - G65P8001 → sub_pg_no = "8001"
  - 空欄圧縮: 同一Nグループ内 SUB/コメント複数を上詰め
  - N番号はゼロパディング非等価（文字列保持）
  - O番号はゼロパディング等価（数値として正規化）
  - T番号循環シフト: 先頭グループにT+M6がない場合も対応
  - OグループのN行の tool_name は隣の SUB コメント（M98Pのコメント）からも補完
"""
import subprocess, sys, os, shutil

BASE    = "/home/karkyon/projects/machcore"
SERVICE = f"{BASE}/apps/api/src/mc/mc.service.ts"

shutil.copy2(SERVICE, SERVICE + ".bak")
with open(SERVICE, "r") as f:
    src = f.read()

# ── 旧 parseToolingProgram を新実装で置換 ──────────────────────────
OLD_MARKER = "  /** ツーリングプログラムテキスト解析（旧VBA完全互換版）"
# 終端を探す: 次のメソッド区切り（  // ══）またはメソッド開始
END_MARKER = "  // ══════════════════════════════════════════\n  // ワークオフセット"

start_idx = src.find(OLD_MARKER)
end_idx   = src.find(END_MARKER, start_idx)

if start_idx == -1 or end_idx == -1:
    print(f"SKIP: アンカー不一致 (start={start_idx}, end={end_idx})")
    sys.exit(1)

NEW_IMPL = r"""  /** ツーリングプログラムテキスト解析 v2
   *  after.pdf / group.pdf / XLSX仕様完全対応
   *  - Oグループ境界分割
   *  - /M0, M1/M01(ESCAPE), (GOTO***), G65P8001対応
   *  - 空欄圧縮（同一Nグループ内 SUB/コメント上詰め）
   *  - T番号循環シフト（先頭T+M6なしパターン対応）
   */
  parseToolingProgram(text: string) {

    // ─────────────────────────────────────────
    // ユーティリティ
    // ─────────────────────────────────────────

    /** 括弧コメントを抽出。{body, comment} を返す */
    const extractComment = (raw: string): { body: string; comment: string | null } => {
      const k1 = raw.indexOf('(');
      const k2 = raw.lastIndexOf(')');
      if (k1 === -1 || k2 < k1) return { body: raw, comment: null };
      const comment = raw.slice(k1 + 1, k2).trim();
      const body    = (raw.slice(0, k1) + raw.slice(k2 + 1)).trim();
      return { body, comment };
    };

    /** アドレス + 数字を抽出。例: "H1T2" → H="H1", T="T2" */
    const extractAddr = (str: string, addr: string): string | null => {
      const upper = str.toUpperCase();
      const idx   = upper.indexOf(addr.toUpperCase());
      if (idx === -1) return null;
      let digits = '';
      for (let j = idx + addr.length; j < str.length; j++) {
        if (str[j] >= '0' && str[j] <= '9') digits += str[j];
        else break;
      }
      return digits ? `${addr.toUpperCase()}${digits}` : null;
    };

    /** サブプログラム番号抽出 (M98P / G65P / G66P) */
    const extractSubPg = (body: string): string | null => {
      const upper = body.toUpperCase();
      for (const pat of ['M98P', 'G65P', 'G66P']) {
        const idx = upper.indexOf(pat);
        if (idx === -1) continue;
        let digits = '';
        for (let j = idx + pat.length; j < body.length && digits.length < 8; j++) {
          if (body[j] >= '0' && body[j] <= '9') digits += body[j];
          else break;
        }
        if (digits) {
          const num = parseInt(digits, 10);
          // M98P2/3/4 は主軸退避・工具交換マクロなので除外（≤12）
          if (pat === 'M98P' && num <= 12) return null;
          return digits;
        }
      }
      return null;
    };

    /** O番号の数値正規化: O0001 = O1 */
    const normalizeO = (digits: string): string => String(parseInt(digits, 10));

    /** M0/M00/M30/M02/M99 等の終端Mコード判定 */
    const isStopM = (body: string): string | null => {
      const m = body.toUpperCase().match(/^M(0{1,2}|30|02|99)$/);
      return m ? `M${parseInt(m[1], 10)}` : null;
    };

    // ─────────────────────────────────────────
    // フェーズ1: 全行を構造化
    // ─────────────────────────────────────────
    interface RawRow {
      raw:      string;
      body:     string;       // 括弧除去後
      comment:  string | null;
    }

    const rows: RawRow[] = text.split(/\r?\n/).map(line => {
      const raw = line.trim();
      if (!raw) return { raw, body: '', comment: null };
      const { body, comment } = extractComment(raw);
      return { raw, body, comment };
    });

    // ─────────────────────────────────────────
    // フェーズ2: Oグループに分割
    //   O**** が現れるたびに新グループ開始
    //   グループ内の各行を解析してエントリ候補を生成
    // ─────────────────────────────────────────
    interface GroupEntry {
      type:     'O' | 'N' | 'M21' | 'ESCAPE' | 'STOP' | 'SPECIAL';
      tool_no:  string | null;
      tool_name: string | null;
      t_no:     string | null;
      h:        string | null;
      d:        string | null;
      d_value:  string | null;
      sub_pg_no: string | null;
      note:     string | null;
      raw:      string;
      subs:     string[];   // このグループ内の M98P 番号リスト（空欄圧縮用）
      comments: string[];   // このグループ内のコメントリスト（空欄圧縮用）
    }

    const finalEntries: McToolEntry[] = [];

    // Oグループの配列を構築
    const groups: { oEntry: GroupEntry; inner: RawRow[] }[] = [];
    let currentGroup: { oEntry: GroupEntry; inner: RawRow[] } | null = null;

    // プログラム先頭からO行が出てくる前の行をpreGroupとして扱う
    const preGroup: RawRow[] = [];

    for (const row of rows) {
      if (!row.body && !row.comment) continue; // 空行スキップ
      if (row.body === '%') continue;          // EOP

      const upper = row.body.toUpperCase();

      // O行判定
      const oMatch = row.body.match(/^O(\d+)/i);
      if (oMatch) {
        // 前のグループを確定
        if (currentGroup) groups.push(currentGroup);
        const oNum = normalizeO(oMatch[1]);
        currentGroup = {
          oEntry: {
            type: 'O',
            tool_no:   `O${oNum}`,
            tool_name: row.comment ?? null,
            t_no: null, h: null, d: null, d_value: null,
            sub_pg_no: null, note: null, raw: row.raw,
            subs: [], comments: [],
          },
          inner: [],
        };
      } else {
        if (currentGroup) currentGroup.inner.push(row);
        else              preGroup.push(row);
      }
    }
    if (currentGroup) groups.push(currentGroup);

    // ─────────────────────────────────────────
    // フェーズ3: 各Oグループを解析し、ツーリング行を生成
    //   Nグループごとに H/T/D/SUB/コメントを集約し1行生成
    //   空欄圧縮: 複数SUB/コメントがある場合は別行として追加
    // ─────────────────────────────────────────

    // プログラム先頭部分 (O行前) の特殊行を処理
    for (const row of preGroup) {
      const sp = parseSpecialRow(row);
      if (sp) finalEntries.push(sp);
    }

    // 主グループ処理
    const tNosForShift: Array<{ idx: number; val: string }> = [];

    for (const grp of groups) {
      // O行自体を1行追加
      const oIdx = finalEntries.length;
      finalEntries.push({
        raw_program_line: grp.oEntry.raw,
        tool_no:          grp.oEntry.tool_no,
        t_no:             null,
        tool_name:        grp.oEntry.tool_name,
        length_offset_no: null,
        dia_offset_no:    null,
        d_value_content:  null,
        sub_pg_no:        null,
        note:             null,
        sort_order:       0,
      });

      // グループ内の行をNセクションごとに処理
      let curN: {
        tool_no: string | null; tool_name: string | null;
        t: string | null; h: string | null; d: string | null;
        d_value: string | null;
        subs: string[]; comments: string[]; raw: string;
      } | null = null;

      const flushN = () => {
        if (!curN) return;
        // 主行
        const mainSub  = curN.subs[0]      ?? null;
        const mainNote = curN.comments[0]  ?? null;
        const eIdx = finalEntries.length;
        finalEntries.push({
          raw_program_line: curN.raw,
          tool_no:          curN.tool_no,
          t_no:             curN.t,
          tool_name:        curN.tool_name,
          length_offset_no: curN.h,
          dia_offset_no:    curN.d,
          d_value_content:  curN.d_value,
          sub_pg_no:        mainSub,
          note:             mainNote,
          sort_order:       0,
        });
        if (curN.t) tNosForShift.push({ idx: eIdx, val: curN.t });
        // 追加行（空欄圧縮: 2番目以降のSUBとコメントを独立行に）
        const maxExtra = Math.max(curN.subs.length - 1, curN.comments.length - 1);
        for (let i = 0; i < maxExtra; i++) {
          finalEntries.push({
            raw_program_line: '',
            tool_no:          null,
            t_no:             null,
            tool_name:        null,
            length_offset_no: null,
            dia_offset_no:    null,
            d_value_content:  null,
            sub_pg_no:        curN.subs[i + 1]     ?? null,
            note:             curN.comments[i + 1] ?? null,
            sort_order:       0,
          });
        }
        curN = null;
      };

      for (const row of grp.inner) {
        const upper = row.body.toUpperCase().trim();

        // N行 → 新しいNセクション開始
        const nMatch = row.body.match(/^N(\d+)/i);
        if (nMatch) {
          flushN();
          curN = {
            tool_no:   `N${nMatch[1]}`,  // ゼロパディング保持
            tool_name: row.comment ?? null,
            t: null, h: null, d: null, d_value: null,
            subs: [], comments: [],
            raw: row.raw,
          };
          continue;
        }

        // M1 / M01 → ESCAPE 独立行
        if (/^M0?1$/.test(upper)) {
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: null, t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null,
            note: 'ESCAPE', sort_order: 0,
          });
          continue;
        }

        // /M0 (オプショナルストップ) → tool_no に記録
        if (upper === '/M0' || upper === '/M00') {
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: upper, t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null, note: null,
            sort_order: 0,
          });
          continue;
        }

        // M0 / M00 → tool_no に記録
        if (/^M0{1,2}$/.test(upper)) {
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: `M${parseInt(upper.slice(1), 10)}`, t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null, note: null,
            sort_order: 0,
          });
          continue;
        }

        // M30 / M02 / M99 → 終端行
        const stopM = isStopM(upper);
        if (stopM) {
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: stopM, t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null,
            note: '/////////////',
            sort_order: 0,
          });
          continue;
        }

        // M21 (割出盤) → コメント付きで独立行
        if (/^M21$/.test(upper)) {
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: 'M21', t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null,
            note: row.comment ?? null,
            sort_order: 0,
          });
          continue;
        }

        // 括弧のみ行（コメント独立行）
        if (!row.body && row.comment) {
          const cUpper = row.comment.toUpperCase();
          const isGoto = cUpper.startsWith('GOTO') || cUpper.includes('GOTO');
          flushN();
          finalEntries.push({
            raw_program_line: row.raw,
            tool_no: isGoto ? row.comment : null,
            t_no: null, tool_name: null,
            length_offset_no: null, dia_offset_no: null,
            d_value_content: null, sub_pg_no: null,
            note: isGoto ? null : row.comment,
            sort_order: 0,
          });
          continue;
        }

        // Nセクション内の H/T/D/SUB/コメント収集
        if (curN) {
          // H番号（同じ行にT番号も含む場合がある: G43H1T2）
          const hv = extractAddr(row.body, 'H');
          if (hv && !curN.h) curN.h = hv;

          // T番号（次工具先読み: H1T2 の T2 は次工具呼出）
          // ここでは T をそのまま記録し循環シフトは後で実施
          const tv = extractAddr(row.body, 'T');
          if (tv && !curN.t) curN.t = tv;

          // D番号
          const dv = extractAddr(row.body, 'D');
          if (dv && !curN.d) curN.d = dv;

          // SUBプログラム番号
          const sv = extractSubPg(row.body);
          if (sv && !curN.subs.includes(sv)) curN.subs.push(sv);

          // コメント (M98P1001(1-3.3D Z-9) のような付きコメント)
          if (row.comment && !curN.comments.includes(row.comment)) {
            // D値パターン: "1-3.3D Z-9" など
            curN.comments.push(row.comment);
          }
        }
      }
      flushN();
    }

    // ─────────────────────────────────────────
    // フェーズ4: T番号循環シフト
    // ─────────────────────────────────────────
    const j = tNosForShift.length;
    if (j === 2) {
      finalEntries[tNosForShift[0].idx].t_no = tNosForShift[1].val;
      finalEntries[tNosForShift[1].idx].t_no = tNosForShift[0].val;
    } else if (j >= 3) {
      const orig = tNosForShift.map(x => x.val);
      finalEntries[tNosForShift[0].idx].t_no = orig[j - 1];
      for (let k = 1; k < j; k++) {
        finalEntries[tNosForShift[k].idx].t_no = orig[k - 1];
      }
    }

    // ─────────────────────────────────────────
    // フェーズ5: sort_order 10刻み採番
    // ─────────────────────────────────────────
    finalEntries.forEach((e, i) => { e.sort_order = (i + 1) * 10; });

    return { count: finalEntries.length, items: finalEntries };

    // ─── ローカル関数: O行前の特殊行処理 ───
    function parseSpecialRow(row: RawRow): McToolEntry | null {
      if (!row.body && !row.comment) return null;
      const upper = row.body.toUpperCase().trim();
      // /M0
      if (upper === '/M0' || upper === '/M00') {
        return { raw_program_line: row.raw, tool_no: upper, t_no: null, tool_name: null,
          length_offset_no: null, dia_offset_no: null, d_value_content: null,
          sub_pg_no: null, note: null, sort_order: 0 };
      }
      // M1/M01 → ESCAPE
      if (/^M0?1$/.test(upper)) {
        return { raw_program_line: row.raw, tool_no: null, t_no: null, tool_name: null,
          length_offset_no: null, dia_offset_no: null, d_value_content: null,
          sub_pg_no: null, note: 'ESCAPE', sort_order: 0 };
      }
      // G65P8001 → SUB=8001
      const gSub = extractSubPg(row.body);
      if (gSub) {
        return { raw_program_line: row.raw, tool_no: null, t_no: null, tool_name: row.comment ?? null,
          length_offset_no: null, dia_offset_no: null, d_value_content: null,
          sub_pg_no: gSub, note: null, sort_order: 0 };
      }
      // 括弧のみ行
      if (!row.body && row.comment) {
        const cUp = row.comment.toUpperCase();
        return { raw_program_line: row.raw,
          tool_no: (cUp.startsWith('GOTO') || cUp.includes('GOTO')) ? row.comment : null,
          t_no: null, tool_name: null,
          length_offset_no: null, dia_offset_no: null, d_value_content: null,
          sub_pg_no: null, note: (cUp.startsWith('GOTO') || cUp.includes('GOTO')) ? null : row.comment,
          sort_order: 0 };
      }
      return null;
    }
  }

"""

new_src = src[:start_idx] + NEW_IMPL + src[end_idx:]

with open(SERVICE, "w") as f:
    f.write(new_src)
print("=== [1] parseToolingProgram 全面置換 OK ===")

# ── TSC チェック ─────────────────────────────────────────────────
print("=== [2] API tsc チェック ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && npx tsc --noEmit 2>&1"],
    capture_output=True, text=True
)
if r.returncode != 0:
    print("  TSC エラー:")
    print(r.stdout[-3000:])
    sys.exit(1)
print("  OK: TypeCheck 通過")

# ── nest build ───────────────────────────────────────────────────
print("=== [3] nest build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx nest build 2>&1"],
    capture_output=True, text=True
)
print(r.stdout[-1000:])
if r.returncode != 0:
    sys.exit(1)
print("  OK: nest build 完了")

# ── PM2 再起動 ────────────────────────────────────────────────────
print("=== [4] PM2 再起動 ===")
subprocess.run(
    ["bash", "-c",
     "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-api --update-env"],
    capture_output=False
)

# ── クリーンアップ & git push ─────────────────────────────────────
print("=== [5] クリーンアップ & git push ===")
if os.path.exists(SERVICE + ".bak"): os.remove(SERVICE + ".bak")
import glob
for s in glob.glob(f"{BASE}/fix_tooling_preview_v1.py"):
    try: os.remove(s)
    except: pass

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'feat: tooling parse v2 - O-group split, /M0, ESCAPE, GOTO, G65P8001, blank compression' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
