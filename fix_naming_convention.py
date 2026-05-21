#!/usr/bin/env python3
"""
命名規則違反 全修正
1. mc.service.ts: setupSheetLogs / changeHistory に snake_case map 追加
2. api.ts: McChangeHistory / McSetupSheetLog 型を snake_case に統一
3. mc/[mc_id]/page.tsx: McChangeHistory/McSetupSheetLog 参照箇所を snake_case に修正
4. mc/[mc_id]/record/page.tsx: McSetupSheetLog 参照箇所を snake_case に修正
"""
import os, sys

ROOT = os.path.expanduser("~/projects/machcore")
API  = os.path.join(ROOT, "apps/api")
WEB  = os.path.join(ROOT, "apps/web")

# ─────────────────────────────────────────
# 1. mc.service.ts: setupSheetLogs / changeHistory に map 追加
# ─────────────────────────────────────────
print("[1/4] mc.service.ts 修正...")
svc = os.path.join(API, "src/mc/mc.service.ts")
with open(svc) as f:
    content = f.read()

# setupSheetLogs: Prismaそのままreturn → mapして snake_case で返す
OLD_SETUP = """  async setupSheetLogs(mcId: number) {
    return this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
  }"""
NEW_SETUP = """  async setupSheetLogs(mcId: number) {
    const rows = await this.prisma.mcSetupSheetLog.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { printedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      printed_at:     r.printedAt,
      version:        r.version ?? null,
      operator_name:  r.operator?.name ?? null,
      work_collected: r.workCollected,
    }));
  }"""
if OLD_SETUP in content:
    content = content.replace(OLD_SETUP, NEW_SETUP, 1)
    print("  OK: setupSheetLogs map 追加")
else:
    print("  WARN: setupSheetLogs アンカーなし")

# changeHistory: Prismaそのままreturn → mapして snake_case で返す
OLD_CHANGE = """  async changeHistory(mcId: number) {
    return this.prisma.mcChangeHistory.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { changedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
  }"""
NEW_CHANGE = """  async changeHistory(mcId: number) {
    const rows = await this.prisma.mcChangeHistory.findMany({
      where:   { mcProgramId: mcId },
      orderBy: { changedAt: 'desc' },
      include: { operator: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      changed_at:     r.changedAt,
      change_type:    r.changeType,
      operator_name:  r.operator?.name ?? null,
      ver_before:     r.versionBefore ?? null,
      ver_after:      r.versionAfter  ?? null,
      change_detail:  r.content       ?? null,
    }));
  }"""
if OLD_CHANGE in content:
    content = content.replace(OLD_CHANGE, NEW_CHANGE, 1)
    print("  OK: changeHistory map 追加")
else:
    print("  WARN: changeHistory アンカーなし")

with open(svc, "w") as f:
    f.write(content)

# ─────────────────────────────────────────
# 2. api.ts: McChangeHistory / McSetupSheetLog 型を snake_case に統一
# ─────────────────────────────────────────
print("[2/4] api.ts 型修正...")
api_ts = os.path.join(WEB, "lib/api.ts")
with open(api_ts) as f:
    content = f.read()

# McChangeHistory: camelCase → snake_case
OLD_CHANGE_TYPE = """export type McChangeHistory = {
  id:            number;
  changedAt:     string;
  changeType:    string;
  operatorId:    number;
  versionBefore: string | null;
  versionAfter:  string | null;
  content:       string | null;
  operator:      { name: string } | null;
};"""
NEW_CHANGE_TYPE = """export type McChangeHistory = {
  id:            number;
  changed_at:    string;
  change_type:   string;
  operator_name: string | null;
  ver_before:    string | null;
  ver_after:     string | null;
  change_detail: string | null;
};"""
if OLD_CHANGE_TYPE in content:
    content = content.replace(OLD_CHANGE_TYPE, NEW_CHANGE_TYPE, 1)
    print("  OK: McChangeHistory 型修正")
else:
    print("  WARN: McChangeHistory 型アンカーなし")

# McSetupSheetLog: camelCase → snake_case
OLD_LOG_TYPE = """export type McSetupSheetLog = {
  id:          number;
  printedAt:   string;
  version:     string | null;
  operator:    { name: string } | null;
};"""
NEW_LOG_TYPE = """export type McSetupSheetLog = {
  id:             number;
  printed_at:     string;
  version:        string | null;
  operator_name:  string | null;
  work_collected: boolean;
};"""
if OLD_LOG_TYPE in content:
    content = content.replace(OLD_LOG_TYPE, NEW_LOG_TYPE, 1)
    print("  OK: McSetupSheetLog 型修正")
else:
    print("  WARN: McSetupSheetLog 型アンカーなし")

with open(api_ts, "w") as f:
    f.write(content)

# ─────────────────────────────────────────
# 3. mc/[mc_id]/page.tsx: 変更履歴/印刷履歴の参照箇所を snake_case に修正
# ─────────────────────────────────────────
print("[3/4] mc/[mc_id]/page.tsx 修正...")
mc_page = os.path.join(WEB, "app/mc/[mc_id]/page.tsx")
with open(mc_page) as f:
    content = f.read()

# McChangeHistory の参照: changedAt → changed_at, changeType → change_type 等
replacements = [
    # 変更履歴表示
    ("new Date(c.changedAt).toLocaleString",    "new Date(c.changed_at).toLocaleString"),
    ("new Date(c.changedAt).toLocaleDateString","new Date(c.changed_at).toLocaleDateString"),
    ("{c.changeType}",   "{c.change_type}"),
    ("{c.operatorId}",   "{c.operator_name ?? '—'}"),
    ("{c.versionBefore}", "{c.ver_before}"),
    ("{c.versionAfter}",  "{c.ver_after}"),
    ("{c.content}",       "{c.change_detail}"),
    # 印刷履歴表示
    ("new Date(p.printedAt).toLocaleString",    "new Date(p.printed_at).toLocaleString"),
    ("new Date(p.printedAt).toLocaleDateString","new Date(p.printed_at).toLocaleDateString"),
    ("new Date(p.printedAt).toLocaleTimeString","new Date(p.printed_at).toLocaleTimeString"),
    ("p.operator?.name",  "p.operator_name"),
    # 作業記録表示
    ("new Date(w.printedAt)", "new Date(w.printed_at)"),
]
count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1
print(f"  OK: {count}箇所修正")

with open(mc_page, "w") as f:
    f.write(content)

# ─────────────────────────────────────────
# 4. mc/[mc_id]/record/page.tsx: McSetupSheetLog 参照を snake_case に修正
# ─────────────────────────────────────────
print("[4/4] mc/[mc_id]/record/page.tsx 修正...")
rec_page = os.path.join(WEB, "app/mc/[mc_id]/record/page.tsx")
with open(rec_page) as f:
    content = f.read()

replacements = [
    ("s.printedAt",           "s.printed_at"),
    ("new Date(s.printedAt)", "new Date(s.printed_at)"),
    ("s.operator?.name",      "s.operator_name"),
]
count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        count += 1
print(f"  OK: {count}箇所修正")

with open(rec_page, "w") as f:
    f.write(content)

print("\n✅ 全修正完了")
print("cd ~/projects/machcore/apps/api && npx tsc && pm2 restart machcore-api && sleep 8")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
