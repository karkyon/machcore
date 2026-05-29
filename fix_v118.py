#!/usr/bin/env python3
"""fix_v118: IP列・WO枠をDBのfont_size/note幅から取得（ツーリングと同じ修正）"""
import subprocess, sys, os, shutil, re

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
src     = open(SVC, encoding="utf-8").read()
bak     = SVC + ".v118_pre.bak"
shutil.copy(SVC, bak)
print("バックアップ完了")

# ══════════════════════════════════════════════════════════════
# IP列修正: font_size/note幅をDBから取得、LINE_X2を565に制限
# ══════════════════════════════════════════════════════════════
OLD_IP = """      type IPCol = { dataKey: string; x: number; label: string };
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
      }"""

NEW_IP = """      const getIPCFS = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f?Number(f.font_size):def; };
      const getIPCW  = (key:string, def:number) => { const f=ipCols.find((c:any)=>c.field_key===key); return f&&f.note?parseFloat(f.note):def; };

      type IPCol = { dataKey: string; x: number; label: string; fs: number; w: number };
      const IP_COLS: IPCol[] = [
        { dataKey:'sortOrder', x: getIPCX('col_no',30),     label:'No',   fs: getIPCFS('col_no',8),    w: getIPCW('col_no',25)    },
        { dataKey:'axis0',     x: getIPCX('col_axis0',55),  label:'軸0',  fs: getIPCFS('col_axis0',8), w: getIPCW('col_axis0',91) },
        { dataKey:'axis1',     x: getIPCX('col_axis1',146), label:'軸1',  fs: getIPCFS('col_axis1',8), w: getIPCW('col_axis1',150)},
        { dataKey:'axis2',     x: getIPCX('col_axis2',296), label:'軸2',  fs: getIPCFS('col_axis2',8), w: getIPCW('col_axis2',150)},
        { dataKey:'note',      x: getIPCX('col_note',446),  label:'備考', fs: getIPCFS('col_note',8),  w: getIPCW('col_note',110) },
      ];
      const IP_LINE_X1 = IP_COLS[0].x;
      const ipLastCol  = IP_COLS[IP_COLS.length - 1];
      const IP_LINE_X2 = Math.min(ipLastCol.x + ipLastCol.w, 565);

      // カラムヘッダ
      await ensureSpace(IP_ROW_H * 2, ipTplDoc);
      IP_COLS.forEach(col => {
        const ipHdrY = curY - IP_ROW_H + (IP_ROW_H - col.fs * 0.72) / 2;
        drawTxt(col.label, col.x + 2, ipHdrY, col.fs);
      });
      drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_ROW_H);
      curY -= IP_ROW_H;

      for (let i=0; i<indexPrograms.length; i++) {
        await ensureSpace(IP_ROW_H + IP_MARGIN, ipTplDoc);
        const ip   = indexPrograms[i];
        IP_COLS.forEach(col => {
          const val = col.dataKey==='sortOrder' ? String(ip.sortOrder ?? i+1) : String((ip as any)[col.dataKey] ?? '');
          if (!val) return;
          const txtY = curY - IP_ROW_H + (IP_ROW_H - col.fs * 0.72) / 2;
          drawTxt(val, col.x + 2, txtY, col.fs);
        });
        drawHLine(IP_LINE_X1, IP_LINE_X2, curY - IP_ROW_H);
        curY -= (IP_ROW_H + IP_MARGIN);
      }"""

if OLD_IP in src:
    src = src.replace(OLD_IP, NEW_IP)
    print("OK: IP列 font_size/幅DB値化 + LINE_X2上限565")
else:
    print("ERROR: IP列パターン未検出"); sys.exit(1)

# ══════════════════════════════════════════════════════════════
# WO枠修正: font_size/sz を __wo_cfg__ の font_size から取得
# ══════════════════════════════════════════════════════════════
OLD_WO_SZ = """          const sz   = 6.5;
          const txtY = curY - WO_ROW_H + (WO_ROW_H - sz * 0.72) / 2;
          group.forEach((_: any, ci: number) => {
            drawTxt(WO_LABELS[li], ML + ci * COL_W + 2, txtY, 6.0);
          });
          group.forEach((wo: any, ci: number) => {
            const raw = wo[WO_KEYS[li]];
            const val = raw == null ? '' : (typeof raw==='number' ? raw.toFixed(3) : String(raw));
            if (val) drawTxt(val, ML + ci * COL_W + LABEL_W + 2, txtY, sz);
          });"""

NEW_WO_SZ = """          const woFs  = woCfg ? Number(woCfg.font_size) : 8;
          const txtY  = curY - WO_ROW_H + (WO_ROW_H - woFs * 0.72) / 2;
          group.forEach((_: any, ci: number) => {
            drawTxt(WO_LABELS[li], ML + ci * COL_W + 2, txtY, woFs);
          });
          group.forEach((wo: any, ci: number) => {
            const raw = wo[WO_KEYS[li]];
            const val = raw == null ? '' : (typeof raw==='number' ? raw.toFixed(3) : String(raw));
            if (val) drawTxt(val, ML + ci * COL_W + LABEL_W + 2, txtY, woFs);
          });"""

if OLD_WO_SZ in src:
    src = src.replace(OLD_WO_SZ, NEW_WO_SZ)
    print("OK: WO枠 font_sizeDB値化")
else:
    print("WARN: WO枠パターン未検出（スキップ）")

assert "async directPrint(" in src
assert "async generateRepeatSetupSheetPdf(" in src
open(SVC, "w", encoding="utf-8").write(src)
print("OK: mc.service.ts 書き換え完了")

print("--- TSC ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errs = [l for l in (r.stdout+r.stderr).splitlines() if "error TS" in l]
if errs:
    print(f"TSエラー {len(errs)}件"); [print(f"  {e}") for e in errs[:5]]
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
    "fix_v118: IP列・WO枠のFS/幅をDB値から取得"],
    capture_output=True, text=True, cwd=PROJECT)
print(r3.stdout.strip())
subprocess.run(["git","push"], capture_output=True, cwd=PROJECT)
print("git push完了")
