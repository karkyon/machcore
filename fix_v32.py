#!/usr/bin/env python3
# coding: utf-8
"""
fix_v32.py — 旧システム段取ｼｰﾄ戻り2「プログラム行」対応
  1. work_records テーブルに prg_man / prg_time_min / prg_plas カラム追加（Docker psql）
  2. Prismaスキーマ WorkRecord に prgMan / prgTimeMin / prgPlas 追加
  3. create-mc-work-record.dto.ts に prg 系フィールド追加
  4. mc.service.ts workRecords レスポンス + createWorkRecord 保存に prg 系追加
  5. api.ts McWorkRecord / CreateMcWorkRecordBody に prg 系追加
  6. record/page.tsx に prgMan/prgTimeH/prgTimeM/prgPlas state + UIセクション追加
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    s = p.read_text(encoding="utf-8")
    if old in s:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {label}")
    else:
        print(f"WARN: {label} — パターン不一致")

# ─────────────────────────────────────────────────────────────
# 1. DB ALTER TABLE（Docker psql）
# ─────────────────────────────────────────────────────────────
print("--- DB ALTER TABLE ---")
sql = """
ALTER TABLE work_records
  ADD COLUMN IF NOT EXISTS prg_man       VARCHAR(100),
  ADD COLUMN IF NOT EXISTS prg_time_min  INTEGER,
  ADD COLUMN IF NOT EXISTS prg_plas      VARCHAR(50);
"""
r = subprocess.run(
    f'docker exec machcore-postgres psql -U machcore -d machcore_dev -c "{sql.strip()}"',
    shell=True, capture_output=True, text=True
)
print(r.stdout.strip() or r.stderr.strip())

# ─────────────────────────────────────────────────────────────
# 2. Prismaスキーマ WorkRecord に prg 系追加
# ─────────────────────────────────────────────────────────────
apply(
    ROOT + "/apps/api/prisma/schema.prisma",
    "  setupOperatorIds        Json?              @default(\"[]\") @map(\"setup_operator_ids\")\n  productionOperatorIds   Json?              @default(\"[]\") @map(\"production_operator_ids\")",
    "  setupOperatorIds        Json?              @default(\"[]\") @map(\"setup_operator_ids\")\n  productionOperatorIds   Json?              @default(\"[]\") @map(\"production_operator_ids\")\n  prgMan                  String?  @db.VarChar(100)  @map(\"prg_man\")\n  prgTimeMin              Int?                       @map(\"prg_time_min\")\n  prgPlas                 String?  @db.VarChar(50)   @map(\"prg_plas\")",
    "schema.prisma WorkRecord prg系追加"
)

# ─────────────────────────────────────────────────────────────
# 3. create-mc-work-record.dto.ts に prg 系追加
# ─────────────────────────────────────────────────────────────
apply(
    ROOT + "/apps/api/src/mc/dto/create-mc-work-record.dto.ts",
    "  @IsOptional()\n  production_operator_ids?: number[];\n}",
    "  @IsOptional()\n  production_operator_ids?: number[];\n\n  @IsOptional() @IsString() @MaxLength(100)\n  prg_man?: string;\n\n  @IsOptional() @IsInt() @Min(0)\n  prg_time_min?: number;\n\n  @IsOptional() @IsString() @MaxLength(50)\n  prg_plas?: string;\n}",
    "create-mc-work-record.dto.ts prg系追加"
)

# ─────────────────────────────────────────────────────────────
# 4. mc.service.ts workRecords レスポンス + createWorkRecord 保存
# ─────────────────────────────────────────────────────────────
# workRecords レスポンス
apply(
    ROOT + "/apps/api/src/mc/mc.service.ts",
    "      interrupt_setup_min: r.interruptSetupMin,\n      interrupt_work_min:  r.interruptWorkMin,\n      note:            r.note,\n    }));",
    "      interrupt_setup_min: r.interruptSetupMin,\n      interrupt_work_min:  r.interruptWorkMin,\n      note:            r.note,\n      setup_operator_ids:      r.setupOperatorIds,\n      production_operator_ids: r.productionOperatorIds,\n      prg_man:         (r as any).prgMan      ?? null,\n      prg_time_min:    (r as any).prgTimeMin  ?? null,\n      prg_plas:        (r as any).prgPlas     ?? null,\n    }));",
    "mc.service.ts workRecords レスポンス prg系追加"
)

# createWorkRecord prisma.create data
apply(
    ROOT + "/apps/api/src/mc/mc.service.ts",
    "        setupOperatorIds:      dto.setup_operator_ids      ?? [],\n        productionOperatorIds: dto.production_operator_ids ?? [],\n      },",
    "        setupOperatorIds:      dto.setup_operator_ids      ?? [],\n        productionOperatorIds: dto.production_operator_ids ?? [],\n        prgMan:            dto.prg_man       ?? null,\n        prgTimeMin:        dto.prg_time_min  ?? null,\n        prgPlas:           dto.prg_plas      ?? null,\n      },",
    "mc.service.ts createWorkRecord prg系保存"
)

# ─────────────────────────────────────────────────────────────
# 5. api.ts McWorkRecord / CreateMcWorkRecordBody prg 系追加
# ─────────────────────────────────────────────────────────────
apply(
    ROOT + "/apps/web/lib/api.ts",
    "  setup_operator_ids:      number[] | null;\n  production_operator_ids: number[] | null;\n};",
    "  setup_operator_ids:      number[] | null;\n  production_operator_ids: number[] | null;\n  prg_man:      string | null;\n  prg_time_min: number | null;\n  prg_plas:     string | null;\n};",
    "api.ts McWorkRecord prg系追加"
)

apply(
    ROOT + "/apps/web/lib/api.ts",
    "  setup_operator_ids?:      number[];\n  production_operator_ids?:",
    "  setup_operator_ids?:      number[];\n  production_operator_ids?:",
    "api.ts CreateMcWorkRecordBody (確認)"
)

# CreateMcWorkRecordBody に prg 系追加
apply(
    ROOT + "/apps/web/lib/api.ts",
    "  production_operator_ids?: number[];\n};\n\nexport type McPrintOptions",
    "  production_operator_ids?: number[];\n  prg_man?:      string;\n  prg_time_min?: number;\n  prg_plas?:     string;\n};\n\nexport type McPrintOptions",
    "api.ts CreateMcWorkRecordBody prg系追加"
)

# ─────────────────────────────────────────────────────────────
# 6. record/page.tsx にプログラム state + UI + handleSubmit 追加
# ─────────────────────────────────────────────────────────────
REC = ROOT + "/apps/web/app/mc/[mc_id]/record/page.tsx"

# state 追加: prgMan/prgTimeH/prgTimeM/prgPlas
apply(
    REC,
    "  const [note,         setNote]         = useState(\"\");",
    "  const [note,         setNote]         = useState(\"\");\n  // プログラム\n  const [prgMan,       setPrgMan]       = useState(\"\");\n  const [prgTimeH,     setPrgTimeH]     = useState(0);\n  const [prgTimeM,     setPrgTimeM]     = useState(0);\n  const [prgPlas,      setPrgPlas]      = useState(\"\");",
    "record/page.tsx prgMan state 追加"
)

# resetForm に prg 系追加
apply(
    REC,
    "    setNote(\"\"); setSaveError(null);",
    "    setNote(\"\"); setSaveError(null);\n    setPrgMan(\"\"); setPrgTimeH(0); setPrgTimeM(0); setPrgPlas(\"\");",
    "record/page.tsx resetForm prg系追加"
)

# loadRecord に prg 系追加
apply(
    REC,
    "    setNote(r.note ?? \"\");",
    "    setNote(r.note ?? \"\");\n    setPrgMan(r.prg_man ?? \"\"); \n    const pt = r.prg_time_min ?? 0;\n    setPrgTimeH(Math.floor(pt / 60)); setPrgTimeM(pt % 60);\n    setPrgPlas(r.prg_plas ?? \"\");",
    "record/page.tsx loadRecord prg系追加"
)

# handleSubmit body に prg 系追加
apply(
    REC,
    "        note:                note || undefined,\n        machine_id:          machineId ? parseInt(machineId) : undefined,",
    "        note:                note || undefined,\n        machine_id:          machineId ? parseInt(machineId) : undefined,\n        prg_man:             prgMan || undefined,\n        prg_time_min:        (prgTimeH * 60 + prgTimeM) || undefined,\n        prg_plas:            prgPlas || undefined,",
    "record/page.tsx handleSubmit prg系送信"
)

# UIセクション: 備考の前にプログラム行セクションを追加
PRG_SECTION = """
              {/* プログラム */}
              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 space-y-3">
                <h3 className="text-xs font-bold text-purple-700 border-b border-purple-200 pb-2">💾 プログラム</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">プログラム担当</label>
                    <input type="text" value={prgMan} onChange={e => setPrgMan(e.target.value)}
                      placeholder="担当者名"
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">PrgTime</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min="0" value={prgTimeH} onChange={e => setPrgTimeH(parseInt(e.target.value)||0)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                      <span className="text-xs text-slate-500">h</span>
                      <input type="number" min="0" max="59" value={prgTimeM} onChange={e => setPrgTimeM(parseInt(e.target.value)||0)}
                        className="w-14 border border-slate-200 rounded px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-1 focus:ring-teal-400" />
                      <span className="text-xs text-slate-500">m</span>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1.5">PrgPlas (ePL)</label>
                    <input type="text" value={prgPlas} onChange={e => setPrgPlas(e.target.value)}
                      placeholder="ePL"
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400" />
                  </div>
                </div>
              </div>

"""

apply(
    REC,
    "              {/* 備考 */}\n              <div className=\"bg-white rounded-xl border border-slate-200 p-4\">",
    PRG_SECTION + "              {/* 備考 */}\n              <div className=\"bg-white rounded-xl border border-slate-200 p-4\">",
    "record/page.tsx プログラムUIセクション追加"
)

# ─────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
out = r.stdout
print(out[-5000:] if len(out) > 5000 else out)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- API npx tsc ---")
r2 = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/api && npx tsc --noEmit",
    shell=True, capture_output=True, text=True
)
print(r2.stdout or "(no output)")
if r2.returncode != 0:
    print("STDERR:", r2.stderr[-2000:])
    print("API TSC FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart ---")
r3 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r3.stdout)

print("\n--- git commit & push ---")
r4 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'feat: work_records prg_man/prg_time_min/prg_plas追加 record/page.tsxプログラム行UI実装 v32' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r4.stdout)
if r4.returncode != 0:
    print("STDERR:", r4.stderr[-500:])

print("\nDONE")
