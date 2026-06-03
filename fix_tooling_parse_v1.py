#!/usr/bin/env python3
"""
fix_tooling_parse_v1.py
ツーリングプログラム解析ロジック全面実装
- mc.service.ts: parseToolingProgram を旧VBA完全互換に刷新
  ① 括弧コメント抽出(同一行/次行両対応)
  ② 制御構文スキップ(GOTO/IF/WHILE/DO/END/ROUND/SQRT)
  ③ Oナンバー/コロン記法/Nシーケンス番号 → tool_no
  ④ T番号 → t_no
  ⑤ H番号 → length_offset_no
  ⑥ D番号 → dia_offset_no
  ⑦ D値テキスト → d_value_content (4.1D, 2-3D 等)
  ⑧ M98P/G65P/G66P → sub_pg_no
  ⑨ T番号循環シフト
  ⑩ sort_order 10刻み採番
- edit/page.tsx: applyParseResult のマッピングを全フィールド対応に更新
"""
import subprocess, sys, os, shutil

BASE = "/home/karkyon/projects/machcore"
SERVICE = f"{BASE}/apps/api/src/mc/mc.service.ts"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

# ── バックアップ ─────────────────────────────
for f in [SERVICE, EDIT_PAGE]:
    bak = f + ".bak"
    if os.path.exists(bak):
        os.remove(bak)
    shutil.copy2(f, bak)
print("=== [0] バックアップ完了 ===")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [1] mc.service.ts: parseToolingProgram 全面刷新
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with open(SERVICE, "r") as f:
    src = f.read()

OLD_PARSE = '''  /** ツーリングプログラムテキスト解析（プレビュー用）*/
  parseToolingProgram(text: string) {
    const lines = text.split(/\\r?\\n/);
    const tools: any[] = [];
    const tLineRe = /T(\\d+)/i;
    const hRe = /H(\\d+)/i;
    const dRe = /D(\\d+)/i;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith('%') || line.startsWith('(')) continue;
      const tMatch = line.match(tLineRe);
      if (!tMatch) continue;
      const toolNo = `T${tMatch[1].padStart(2, '0')}`;
      const hMatch = line.match(hRe);
      const dMatch = line.match(dRe);
      // 次行にコメントがあれば工具名として使用
      const nextLine = (lines[i + 1] ?? '').trim();
      const toolName = nextLine.startsWith('(') ? nextLine.replace(/[()]/g, '').trim() : undefined;

      tools.push({
        sort_order:       tools.length,
        tool_no:          toolNo,
        tool_name:        toolName,
        length_offset_no: hMatch ? `H${hMatch[1]}` : null,
        dia_offset_no:    dMatch ? `D${dMatch[1]}` : null,
        raw_program_line: line,
      });
    }
    return { count: tools.length, items: tools };
  }'''

NEW_PARSE = '''  /** ツーリングプログラムテキスト解析（旧VBA完全互換版）
   *  フェーズ1: 全行を構造化（括弧コメント・制御構文スキップ）
   *  フェーズ2: 各行からN/T/H/D/D値/SUB/コメント抽出
   *  フェーズ3: T番号循環シフト（MCの先読み慣習を補正）
   *  フェーズ4: sort_order 10刻み採番
   */
  parseToolingProgram(text: string) {
    // 制御構文キーワード（これらを含む行はスキップ）
    const SKIP_KEYWORDS = ['GOTO', 'IF', 'ROUND', 'SQRT', 'WHILE', 'WEND', 'DO', 'END'];

    // ─────────────────────────────────────────
    // フェーズ1: 全行を構造化
    // ─────────────────────────────────────────
    interface ParsedLine {
      raw:      string;
      body:     string | null;  // 括弧除去後の本体
      comment:  string | null;  // 括弧内コメント
      skip:     boolean;        // 制御構文フラグ
    }

    const rawLines = text.split(/\\r?\\n/);
    const parsed: ParsedLine[] = rawLines.map(raw => {
      const line = raw.trim();
      if (!line || line.startsWith('%')) return { raw: line, body: null, comment: null, skip: false };

      // 括弧コメント抽出
      let body = line;
      let comment: string | null = null;
      const k1 = line.indexOf('(');
      const k2 = line.indexOf(')');
      if (k1 !== -1 && k2 > k1) {
        comment = line.slice(k1 + 1, k2).trim();
        if (k1 === 0 && k2 === line.length - 1) {
          // 行全体が括弧: bodyはnull
          body = '';
        } else {
          body = (line.slice(0, k1) + line.slice(k2 + 1)).trim();
        }
      }

      // 制御構文スキップ判定
      const upper = body ? body.toUpperCase() : '';
      const skip = SKIP_KEYWORDS.some(kw => upper.includes(kw));

      return { raw: line, body: skip ? null : (body || null), comment, skip };
    });

    // ─────────────────────────────────────────
    // フェーズ2: フィールド抽出
    // ─────────────────────────────────────────
    interface ToolEntry {
      raw_program_line: string;
      tool_no:          string | null;  // N列: O番号 or Nシーケンス
      t_no:             string | null;  // T列: 工具番号
      tool_name:        string | null;  // 工具名（括弧コメント）
      length_offset_no: string | null;  // H列
      dia_offset_no:    string | null;  // D列
      d_value_content:  string | null;  // D値テキスト（4.1D, 2-3D 等）
      sub_pg_no:        string | null;  // M98P/G65P/G66P
      note:             string | null;  // コメント（工具名以外）
      sort_order:       number;
    }

    const entries: ToolEntry[] = [];

    const extractNum = (str: string, prefix: string, maxDigits: number): string | null => {
      const idx = str.toUpperCase().indexOf(prefix.toUpperCase());
      if (idx === -1) return null;
      let digits = '';
      for (let j = idx + prefix.length; j < str.length && digits.length < maxDigits; j++) {
        if (str[j] >= '0' && str[j] <= '9') digits += str[j];
        else break;
      }
      return digits ? `${prefix.toUpperCase()}${digits}` : null;
    };

    const extractSubPg = (str: string): string | null => {
      const patterns = ['M98P', 'G65P', 'G66P'];
      const upper = str.toUpperCase();
      for (const pat of patterns) {
        const idx = upper.indexOf(pat);
        if (idx === -1) continue;
        let digits = '';
        for (let j = idx + pat.length; j < str.length && digits.length < 8; j++) {
          if (str[j] >= '0' && str[j] <= '9') digits += str[j];
          else break;
        }
        if (digits) {
          const num = parseInt(digits, 10);
          // 1〜12は内部マクロ番号のため除外（旧VBAと同じ）
          if (num > 12) return digits;
        }
      }
      return null;
    };

    // D値テキスト抽出（例: 4.1D, 2-3D, 8-5.5D）
    const extractDValueText = (comment: string | null): string | null => {
      if (!comment) return null;
      // 数字・小数点・ハイフンの後に D が来るパターン
      const m = comment.match(/([\\d.\\-]+\\s*D)/i);
      return m ? m[1].trim() : null;
    };

    // Oナンバー or コロン記法抽出 → tool_no
    const extractONo = (body: string | null): string | null => {
      if (!body) return null;
      const upper = body.toUpperCase();
      // "O" + 数字
      let m = upper.match(/^O(\\d{1,4})/);
      if (m) return `O${m[1]}`;
      // ":数字"（ファナック系）
      m = upper.match(/:(\\d{1,4})/);
      if (m) return `O${m[1]}`;
      return null;
    };

    // Nシーケンス番号抽出
    const extractNNo = (body: string | null): string | null => {
      if (!body) return null;
      const m = body.toUpperCase().match(/N(\\d{1,7})/);
      return m ? `N${m[1]}` : null;
    };

    // M0/M30抽出
    const extractMStop = (body: string | null): string | null => {
      if (!body) return null;
      const m = body.toUpperCase().match(/M(0|30)(?:\\D|$)/);
      return m ? `M${m[1]}` : null;
    };

    let prevSubPg: string | null = null;

    for (let i = 0; i < parsed.length; i++) {
      const p = parsed[i];
      if (!p.body && !p.comment) continue;

      // tool_no の決定（O番号 > Nシーケンス > M0/M30）
      let tool_no = extractONo(p.body)
                 ?? extractNNo(p.body)
                 ?? extractMStop(p.body);

      // T番号
      const t_no = extractNum(p.body ?? '', 'T', 4);

      // H番号
      const length_offset_no = extractNum(p.body ?? '', 'H', 4);

      // D番号
      const dia_offset_no = extractNum(p.body ?? '', 'D', 4);

      // D値テキスト（コメントから）
      const d_value_content = extractDValueText(p.comment);

      // SUBプログラム番号（重複除外）
      const subRaw = extractSubPg(p.body ?? '');
      const sub_pg_no = (subRaw && subRaw !== prevSubPg) ? subRaw : null;
      if (subRaw) prevSubPg = subRaw;

      // 工具名: 同一行の括弧コメント（D値でない場合）or 次行の括弧コメント
      let tool_name: string | null = null;
      let note: string | null = null;
      if (p.comment) {
        if (d_value_content && p.comment.toUpperCase().replace(/\\s/g,'').includes(d_value_content.toUpperCase().replace(/\\s/g,''))) {
          // D値コメントはnoteへ
          note = p.comment;
        } else {
          tool_name = p.comment;
        }
      } else {
        // 次行が括弧コメントのみなら工具名として使用
        const next = parsed[i + 1];
        if (next && !next.body && next.comment) {
          tool_name = next.comment;
        }
      }

      // T番号または意味のある情報がある行のみエントリ追加
      if (t_no || tool_no || tool_name || length_offset_no || sub_pg_no) {
        entries.push({
          raw_program_line: p.raw,
          tool_no,
          t_no,
          tool_name,
          length_offset_no,
          dia_offset_no,
          d_value_content,
          sub_pg_no,
          note,
          sort_order: 0, // フェーズ4で設定
        });
      }
    }

    // ─────────────────────────────────────────
    // フェーズ3: T番号循環シフト（旧VBA toolingcopy と同一ロジック）
    // MCプログラムはT番号を「次に使う工具」として1つ先を指定する慣習があるため
    // 収集したT番号を1つ後ろにずらし、最後を先頭へ移動する
    // ─────────────────────────────────────────
    const tNos: Array<{ idx: number; val: string }> = [];
    for (let i = 0; i < entries.length; i++) {
      if (entries[i].t_no) tNos.push({ idx: i, val: entries[i].t_no! });
    }
    const j = tNos.length;
    if (j === 2) {
      // 2本: 前後入れ替え
      entries[tNos[0].idx].t_no = tNos[1].val;
      entries[tNos[1].idx].t_no = tNos[0].val;
    } else if (j >= 3) {
      // 3本以上: 先頭←最後, 2番目以降←1つ前
      const orig = tNos.map(x => x.val);
      entries[tNos[0].idx].t_no = orig[j - 1];
      for (let k = 1; k < j; k++) {
        entries[tNos[k].idx].t_no = orig[k - 1];
      }
    }
    // 1本の場合はそのまま

    // ─────────────────────────────────────────
    // フェーズ4: sort_order 10刻み採番
    // ─────────────────────────────────────────
    entries.forEach((e, i) => { e.sort_order = (i + 1) * 10; });

    return { count: entries.length, items: entries };
  }'''

if OLD_PARSE in src:
    src = src.replace(OLD_PARSE, NEW_PARSE)
    with open(SERVICE, "w") as f:
        f.write(src)
    print("=== [1] mc.service.ts parseToolingProgram 更新 OK ===")
else:
    print("=== [1] SKIP: mc.service.ts アンカー不一致 ===")
    # 部分一致確認
    if "parseToolingProgram" in src:
        print("  ※ parseToolingProgram は存在するが前後のコードが変わっている可能性")
    sys.exit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [2] edit/page.tsx: applyParseResult マッピング更新
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with open(EDIT_PAGE, "r") as f:
    esrc = f.read()

OLD_APPLY = '''  const applyParseResult = () => {
    if (!parseResult) return;
    setToolingRows(parseResult.map((item, i) => ({
      sort_order: i, tool_no: item.tool_no, tool_name: item.tool_name ?? "",
      length_offset_no: item.length_offset_no ?? "", dia_offset_no: item.dia_offset_no ?? "",
      raw_program_line: item.raw_program_line ?? "",
    })));
    setParseResult(null);
    setToolingText("");
    showToast("ツーリングデータを取り込みました");
  };'''

NEW_APPLY = '''  const applyParseResult = () => {
    if (!parseResult) return;
    setToolingRows(parseResult.map((item, i) => ({
      sort_order:       item.sort_order       ?? (i + 1) * 10,
      tool_no:          item.tool_no          ?? "",
      t_no:             item.t_no             ?? "",
      tool_name:        item.tool_name        ?? "",
      length_offset_no: item.length_offset_no ?? "",
      dia_offset_no:    item.dia_offset_no    ?? "",
      diameter:         item.diameter         ?? null,
      d_value_content:  item.d_value_content  ?? "",
      sub_pg_no:        item.sub_pg_no        ?? "",
      tool_type:        item.tool_type        ?? "",
      note:             item.note             ?? "",
      raw_program_line: item.raw_program_line ?? "",
    })));
    setParseResult(null);
    setToolingText("");
    showToast("ツーリングデータを取り込みました");
  };'''

if OLD_APPLY in esrc:
    esrc = esrc.replace(OLD_APPLY, NEW_APPLY)
    with open(EDIT_PAGE, "w") as f:
        f.write(esrc)
    print("=== [2] edit/page.tsx applyParseResult 更新 OK ===")
else:
    print("=== [2] SKIP: edit/page.tsx アンカー不一致 ===")
    sys.exit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [3] API tsc チェック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== [3] API tsc チェック ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && npx tsc --noEmit 2>&1"],
    capture_output=True, text=True
)
if r.returncode != 0:
    print("  TSC エラー:")
    print(r.stdout[-3000:])
    sys.exit(1)
print("  OK: TypeCheck 通過")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [4] API nest build
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== [4] API nest build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx nest build 2>&1"],
    capture_output=True, text=True
)
print(r.stdout[-2000:])
if r.returncode != 0:
    print("  nest build 失敗")
    sys.exit(1)
print("  OK: nest build 完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [5] Next.js build
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== [5] Next.js build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/web && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build 2>&1 | tail -20"],
    capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("  Next.js build 失敗")
    sys.exit(1)
print("  OK: Next.js build 完了")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [6] PM2 再起動
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== [6] PM2 再起動 ===")
subprocess.run(
    ["bash", "-c", f"export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && pm2 restart machcore-api --update-env && pm2 restart machcore-web 2>&1"],
    capture_output=False
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [7] クリーンアップ & git push
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("=== [7] クリーンアップ & git push ===")
for f in [SERVICE + ".bak", EDIT_PAGE + ".bak"]:
    if os.path.exists(f):
        os.remove(f)

# 古いfixスクリプト削除
import glob
old_scripts = glob.glob(f"{BASE}/fix_tooling_screen_v1*.py") + glob.glob(f"{BASE}/fix_tooling_screen_v1*.py")
for s in old_scripts:
    if os.path.basename(s) != "fix_tooling_parse_v1.py":
        try: os.remove(s)
        except: pass

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'fix: tooling parse v1 - full VBA-compatible logic (T-shift/sub/comment/Ono)' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
