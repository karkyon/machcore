#!/usr/bin/env python3
"""
fix_tooling_parse_v1b.py
TSC エラー修正: ToolEntry / ParsedLine をメソッド内ローカル interface → ファイルスコープ type に移動
"""
import subprocess, sys, os, shutil

BASE    = "/home/karkyon/projects/machcore"
SERVICE = f"{BASE}/apps/api/src/mc/mc.service.ts"

shutil.copy2(SERVICE, SERVICE + ".bak")
with open(SERVICE, "r") as f:
    src = f.read()

# ── [1] メソッド内の interface 定義を削除 ──────────────────────────
OLD_PARSED_INTERFACE = '''    interface ParsedLine {
      raw:      string;
      body:     string | null;  // 括弧除去後の本体
      comment:  string | null;  // 括弧内コメント
      skip:     boolean;        // 制御構文フラグ
    }

    '''

NEW_PARSED_INTERFACE = '''    '''  # 削除するだけ

OLD_TOOL_INTERFACE = '''    interface ToolEntry {
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

    '''

NEW_TOOL_INTERFACE = '''    '''  # 削除するだけ

# ── [2] ファイルスコープに type を追加（import 行の直後）──────────────
INSERT_AFTER = "import { PrintMcDto } from './dto/print-mc.dto';"

NEW_TYPES = """import { PrintMcDto } from './dto/print-mc.dto';

/** ツーリング解析: 行パース中間型 */
type McParsedLine = {
  raw:      string;
  body:     string | null;
  comment:  string | null;
  skip:     boolean;
};

/** ツーリング解析: 工具エントリ型 */
export type McToolEntry = {
  raw_program_line: string;
  tool_no:          string | null;
  t_no:             string | null;
  tool_name:        string | null;
  length_offset_no: string | null;
  dia_offset_no:    string | null;
  d_value_content:  string | null;
  sub_pg_no:        string | null;
  note:             string | null;
  sort_order:       number;
};"""

# ── 適用 ───────────────────────────────────────────────────────────
ok = True

if OLD_PARSED_INTERFACE in src:
    src = src.replace(OLD_PARSED_INTERFACE, NEW_PARSED_INTERFACE)
    print("  OK: ParsedLine interface 削除")
else:
    print("  SKIP: ParsedLine interface (既に削除済みか不一致)")

if OLD_TOOL_INTERFACE in src:
    src = src.replace(OLD_TOOL_INTERFACE, NEW_TOOL_INTERFACE)
    print("  OK: ToolEntry interface 削除")
else:
    print("  SKIP: ToolEntry interface (既に削除済みか不一致)")

if INSERT_AFTER in src and "export type McToolEntry" not in src:
    src = src.replace(INSERT_AFTER, NEW_TYPES)
    print("  OK: ファイルスコープ type 追加")
elif "export type McToolEntry" in src:
    print("  SKIP: ファイルスコープ type 既に存在")
else:
    print("  SKIP: import 行アンカー不一致")
    ok = False

# ── メソッド内の型アノテーション更新 ──────────────────────────────
# ParsedLine[] → McParsedLine[]
src = src.replace("const parsed: ParsedLine[] = ", "const parsed: McParsedLine[] = ")
# ToolEntry[] → McToolEntry[]
src = src.replace("const entries: ToolEntry[] = [];", "const entries: McToolEntry[] = [];")
print("  OK: メソッド内型アノテーション更新")

with open(SERVICE, "w") as f:
    f.write(src)

if not ok:
    sys.exit(1)

# ── [3] tsc チェック ────────────────────────────────────────────
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

# ── [4] nest build ───────────────────────────────────────────────
print("=== [4] nest build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/api && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npx nest build 2>&1"],
    capture_output=True, text=True
)
print(r.stdout[-2000:])
if r.returncode != 0:
    sys.exit(1)
print("  OK: nest build 完了")

# ── [5] Next.js build ────────────────────────────────────────────
print("=== [5] Next.js build ===")
r = subprocess.run(
    ["bash", "-c", f"cd {BASE}/apps/web && export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && npm run build 2>&1 | tail -20"],
    capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    sys.exit(1)
print("  OK: Next.js build 完了")

# ── [6] PM2 再起動 ───────────────────────────────────────────────
print("=== [6] PM2 再起動 ===")
subprocess.run(
    ["bash", "-c",
     "export NVM_DIR=\"$HOME/.nvm\" && . \"$NVM_DIR/nvm.sh\" && "
     "pm2 restart machcore-api --update-env && pm2 restart machcore-web"],
    capture_output=False
)

# ── [7] クリーンアップ & git push ────────────────────────────────
print("=== [7] クリーンアップ & git push ===")
for f in [SERVICE + ".bak"]:
    if os.path.exists(f): os.remove(f)

import glob
for s in glob.glob(f"{BASE}/fix_tooling_parse_v1.py"):
    try: os.remove(s)
    except: pass

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'fix: tooling parse v1b - McToolEntry exported type, tsc fix' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
