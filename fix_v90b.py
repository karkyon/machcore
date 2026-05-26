#!/usr/bin/env python3
"""fix_v90b: mc.service.ts の setupSheetLogs 残骸を除去してビルド通す"""
import subprocess, sys, os, re

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()

def write(p, content):
    with open(p, "w", encoding="utf-8") as f: f.write(content)

MC_SVC = f"{ROOT}/apps/api/src/mc/mc.service.ts"
svc = read(MC_SVC)

# 壊れたブロック全体を正規表現で特定して差し替え
# パターン: 新しいsetupSheetLogs本体 + 残骸の古いmap + 次のコメントまで
OLD_BROKEN = r"""  async setupSheetLogs\(mcId: number\) \{
    const rows = await this\.prisma\.mcSetupSheetLog\.findMany\(\{
      where:   \{ mcProgramId: mcId \},
      orderBy: \{ printedAt: 'desc' \},
      include: \{ operator: \{ select: \{ name: true \} \} \},
    \}\);
    const logsAsc = \[\.\.\.rows\]\.sort\(\(a, b\) => a\.id - b\.id\);
    return rows\.map\(r => \{
      const rank = logsAsc\.findIndex\(x => x\.id === r\.id\) \+ 1;
      return \{
        id:             r\.id,
        printed_at:     r\.printedAt,
        version:        r\.version \?\? null,
        operator_name:  r\.operator\?\.name \?\? null,
        work_collected: r\.workCollected,
        is_reference:   \(r as any\)\.isReference \?\? false,
        sheet_type:     rank === 1 \? 'NEW' : 'REPEAT',
      \};
    \}\);
  \} \},
    \}\);
    return rows\.map\(r => \(\{
      id:             r\.id,
      printed_at:     r\.printedAt,
      version:        r\.version \?\? null,
      operator_name:  r\.operator\?\.name \?\? null,
      work_collected: r\.workCollected,
      is_reference:   \(r as any\)\.isReference \?\? false,
    \}\)\);
  \}"""

NEW_CORRECT = """  async setupSheetLogs(mcId: number) {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    const logsAsc = [...rows].sort((a, b) => a.id - b.id);
    return rows.map(r => {
      const rank = logsAsc.findIndex(x => x.id === r.id) + 1;
      return {
        id:             r.id,
        printed_at:     r.printedAt,
        version:        r.version ?? null,
        operator_name:  r.operator?.name ?? null,
        work_collected: r.workCollected,
        is_reference:   (r as any).isReference ?? false,
        sheet_type:     rank === 1 ? 'NEW' : 'REPEAT',
      };
    });
  }"""

result = re.sub(OLD_BROKEN, NEW_CORRECT, svc, count=1)
if result == svc:
    print("WARN: 正規表現不一致 — 文字列マッチで試行")
    # 文字列で直接除去
    BAD_TAIL = """  } },
    });
    return rows.map(r => ({
      id:             r.id,
      printed_at:     r.printedAt,
      version:        r.version ?? null,
      operator_name:  r.operator?.name ?? null,
      work_collected: r.workCollected,
      is_reference:   (r as any).isReference ?? false,
    }));
  }

  /** 段取シートバック"""
    GOOD_TAIL = """  }

  /** 段取シートバック"""
    if BAD_TAIL in svc:
        result = svc.replace(BAD_TAIL, GOOD_TAIL, 1)
        print("OK: 残骸除去（文字列マッチ）")
    else:
        print("ERROR: パターンが見つかりません。手動確認が必要")
        sys.exit(1)
else:
    print("OK: setupSheetLogs 残骸除去（正規表現）")

write(MC_SVC, result)

# build api
print("\n--- build api ---")
r = subprocess.run(["pnpm","--filter","api","build"], cwd=ROOT, capture_output=True, text=True)
print(r.stdout[-4000:] if len(r.stdout)>4000 else r.stdout)
if r.stderr: print("STDERR:", r.stderr[-2000:] if len(r.stderr)>2000 else r.stderr)
if r.returncode != 0:
    print("BUILD FAILED (api) — abort"); sys.exit(1)

print("\n--- pm2 restart ---")
subprocess.run(["pm2","restart","machcore-api","machcore-web"], cwd=ROOT)
subprocess.run(["pm2","ls"], cwd=ROOT)

print("\n--- git push ---")
subprocess.run(["git","add","-A"], cwd=ROOT)
subprocess.run(["git","commit","-m","fix(v90b): setupSheetLogs残骸除去 ビルド修正"], cwd=ROOT)
subprocess.run(["git","push"], cwd=ROOT)
print("\nDONE v90b")
