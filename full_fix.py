#!/usr/bin/env python3
"""
full_fix.py
① DBのdata_source確認・修正（タイム/加工ID/ファイル名/MCID）
② nest build
③ pm2 restart
④ git push
"""
import subprocess, sys
from pathlib import Path

DB_URL = "postgresql://machcore:machcore_pass_change_me@localhost:5440/machcore_dev"
API_DIR = Path("/home/karkyon/projects/machcore/apps/api")
GIT_DIR = Path("/home/karkyon/projects/machcore")

def psql(sql, verbose=False):
    r = subprocess.run(['psql', DB_URL, '-c', sql, '--no-align', '-t'],
                       capture_output=True, text=True)
    if verbose:
        print(r.stdout.strip())
    return r.stdout.strip()

# ──────────────────────────────────────────────────────
# ① DB確認
# ──────────────────────────────────────────────────────
print("=" * 60)
print("① repeat_header フィールド定義 確認")
print("=" * 60)
psql("""
SELECT f.field_key, f.label, f.data_source
FROM pdf_field_definitions f
JOIN pdf_templates t ON f.template_id = t.id
WHERE t.name = 'repeat_header' AND f.is_active=true
ORDER BY f.sort_order;
""", verbose=True)

# ──────────────────────────────────────────────────────
# ② data_source 修正
# ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("② data_source 修正")
print("=" * 60)

# MCIDフィールド: data_source='id' → 'legacyMcid'
r = psql("""
UPDATE pdf_field_definitions SET data_source='legacyMcid'
WHERE template_id = (SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (field_key ILIKE '%mcid%' OR label ILIKE '%mcid%')
  AND data_source='id';
""")
print(f"MCID(id→legacyMcid): {r}")

# 加工IDフィールド: data_source → 'machiningId'
r = psql("""
UPDATE pdf_field_definitions SET data_source='machiningId'
WHERE template_id = (SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (field_key ILIKE '%machining%' OR label ILIKE '%加工%id%' OR label ILIKE '%加工 id%')
  AND data_source <> 'machiningId';
""")
print(f"加工ID(→machiningId): {r}")

# タイムフィールド: data_source → 'cycleTimeSec'
# (cycleTimeSecは既に修正済みのはずだが確実にする)
r = psql("""
UPDATE pdf_field_definitions SET data_source='cycleTimeSec'
WHERE template_id = (SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (label ILIKE '%タイム%' OR label='CT' OR field_key='cycleTimeSec'
       OR field_key ILIKE '%cycle%time%' OR field_key ILIKE '%time%sec%')
  AND data_source <> 'cycleTimeSec';
""")
print(f"タイム(→cycleTimeSec): {r}")

# ファイル名フィールド
r = psql("""
UPDATE pdf_field_definitions SET data_source='fileName'
WHERE template_id = (SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (label ILIKE '%ファイル%名%' OR field_key ILIKE '%file%name%' OR field_key='fileName')
  AND data_source <> 'fileName';
""")
print(f"ファイル名(→fileName): {r}")

# 部品IDフィールド: data_source → 'part.partId'
r = psql("""
UPDATE pdf_field_definitions SET data_source='part.partId'
WHERE template_id = (SELECT id FROM pdf_templates WHERE name='repeat_header')
  AND (label ILIKE '%部品%id%' OR label ILIKE '%部品 id%' OR field_key ILIKE '%part%id%')
  AND data_source <> 'part.partId';
""")
print(f"部品ID(→part.partId): {r}")

# ──────────────────────────────────────────────────────
# 修正後の状態確認
# ──────────────────────────────────────────────────────
print("\n=== 修正後 data_source ===")
psql("""
SELECT field_key, label, data_source
FROM pdf_field_definitions f
JOIN pdf_templates t ON f.template_id = t.id
WHERE t.name = 'repeat_header' AND f.is_active=true
ORDER BY f.sort_order;
""", verbose=True)

# ──────────────────────────────────────────────────────
# ③ nest build
# ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("③ nest build")
print("=" * 60)
r = subprocess.run(['npx', 'nest', 'build'], cwd=API_DIR,
                   capture_output=True, text=True, timeout=300)
if r.returncode != 0:
    print(f"❌ build失敗:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    sys.exit(1)
print("✅ nest build 完了")

# ──────────────────────────────────────────────────────
# ④ pm2 restart
# ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("④ pm2 restart")
print("=" * 60)
r2 = subprocess.run(['pm2', 'list'], capture_output=True, text=True)
if r2.returncode == 0:
    print(r2.stdout)
    r3 = subprocess.run(['pm2', 'restart', 'all'], capture_output=True, text=True)
    print(r3.stdout)
    print("✅ pm2 restart 完了")
else:
    print("INFO: pm2未使用")

# ──────────────────────────────────────────────────────
# ⑤ git push（mc.service.tsは既にpush済み、DB変更はpush不要）
# ──────────────────────────────────────────────────────
print("\n✅ 全工程完了")
print("プレビューを再確認してください。")
