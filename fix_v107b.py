#!/usr/bin/env python3
"""
fix_v107b.py - バックアップから復元 + 正確なツーリングのみ置換
"""
import subprocess, sys, os, glob

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"

# ── Step1: 最新バックアップから復元 ──────────────────
print("--- バックアップ確認 ---")
baks = sorted(
    glob.glob(f"{PROJECT}/apps/api/src/mc/mc.service.ts.v*.bak"),
    key=os.path.getmtime, reverse=True
)
print("利用可能なbak:", [os.path.basename(b) for b in baks])

# v105b.bak2 が最後の正常版（fix_v106系適用前）
good_bak = None
for b in baks:
    content = open(b, encoding="utf-8").read()
    if "async directPrint(" in content and "await drawColHeader();" in content:
        good_bak = b
        print(f"正常版バックアップ: {os.path.basename(b)}")
        break

if not good_bak:
    print("ERROR: 正常なバックアップが見つかりません")
    # git から復元
    r = subprocess.run(["git","show","HEAD~3:apps/api/src/mc/mc.service.ts"],
        capture_output=True, text=True, cwd=PROJECT)
    if r.returncode == 0 and "async directPrint(" in r.stdout:
        content = r.stdout
        print("git HEAD~3 から復元")
    else:
        for i in range(1, 10):
            r = subprocess.run(["git","show",f"HEAD~{i}:apps/api/src/mc/mc.service.ts"],
                capture_output=True, text=True, cwd=PROJECT)
            if r.returncode == 0 and "async directPrint(" in r.stdout:
                content = r.stdout
                print(f"git HEAD~{i} から復元")
                break
        else:
            print("ERROR: gitからも復元できません")
            sys.exit(1)
    open(SVC, "w", encoding="utf-8").write(content)
else:
    import shutil
    shutil.copy(good_bak, SVC)
    content = open(SVC, encoding="utf-8").read()
    print(f"バックアップから復元完了: {os.path.basename(good_bak)}")

src = open(SVC, encoding="utf-8").read()
print(f"復元後確認: directPrint={'async directPrint(' in src}, drawColHeader={'await drawColHeader();' in src}")

# ── Step2: ツーリングループのみ正確に置換 ──────────────
# 開始: "      await drawColHeader();\n\n      let needsColHdr = false;"
# 終了: "      curY -= BLOCK_MARGIN;\n    }\n\n    // ══"
# (WO枠のコメント行の手前まで)

START = "      await drawColHeader();\n\n      let needsColHdr = false;"
# WO枠の直前まで（③ のコメント行）
import re
# ツーリングブロック終端を正確に特定
# "curY -= BLOCK_MARGIN;\n    }\n\n    // ══" で WO枠のコメントの手前
end_pattern = r"      curY -= BLOCK_MARGIN;\n    \}\n\n    // ══[═]+"

si = src.find(START)
m = re.search(end_pattern, src[si:])
if si < 0 or not m:
    print(f"ERROR: パターン未検出 si={si} m={m}")
    sys.exit(1)

ei = si + m.start() + len(m.group(0))
print(f"置換範囲: {si} → {ei}, length={ei-si}")
print("終端:", repr(src[ei-50:ei+50]))

NEW_LOOP = """      await drawColHeader();

      // カラム幅を計算（次カラムX - 自カラムX、最後は固定80pt）
      const colWidths: number[] = T_COLS.map((col, i) =>
        i < T_COLS.length - 1 ? T_COLS[i+1].x - col.x - 2 : 80
      );

      // テキスト折り返し（全角考慮）
      const wrapTxt = (text: string, maxW: number, fs: number): string[] => {
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
        return result.length ? result : [''];
      };

      let needsColHdr = false;
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
      }
      curY -= BLOCK_MARGIN;
    }

"""

# src[ei:] は "// ══════..." から始まっているのでそのまま連結
new_src = src[:si] + NEW_LOOP + src[ei:]
open(SVC, "w", encoding="utf-8").write(new_src)
print("OK: ツーリングループ書き換え完了")
print(f"directPrint確認: {'async directPrint(' in new_src}")

# ── Step3: ビルド ──────────────────────────────
print("--- ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errors = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TSエラー: {len(errors)}件"); [print(f"  {e}") for e in errors[:10]]
    open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
print("TypeScriptエラー: 0件")

nest_candidates = [f"{PROJECT}/node_modules/.bin/nest", f"{PROJECT}/apps/api/node_modules/.bin/nest"]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    found = subprocess.run(["find",PROJECT,"-path","*/node_modules/.bin/nest",
        "-not","-path","*/node_modules/*/node_modules/*"],
        capture_output=True,text=True).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)
if nest_bin:
    r2 = subprocess.run([nest_bin,"build","api"],capture_output=True,text=True,cwd=f"{PROJECT}/apps/api")
    if r2.returncode != 0:
        print(f"nest build 失敗: {(r2.stdout+r2.stderr)[:300]}")
        open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
    print("nest build 成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")
subprocess.run(["git","add","-A"], cwd=PROJECT)
subprocess.run(["git","commit","-m","fix_v107b: ツーリング折り返し+縮小修正（バックアップ復元版）"], cwd=PROJECT)
r3 = subprocess.run(["git","push"],capture_output=True,text=True,cwd=PROJECT)
print("fix_v107b 完了" if r3.returncode==0 else f"push警告: {r3.stderr[:100]}")
