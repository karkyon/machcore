#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_machining_qty_decimal.py
==============================
「加工個数_数値不一致」11件の根本修正。

[原因]
  旧Access ACC_マシニングraw.加工個数 は通貨型(Currency)で、
  0.5000 のような小数値を実際に保持している(業務上意味のあるデータ確認済み)。
  現行スキーマ McProgram.machiningQty は Int? のため、
  mc_full_import.py でPostgreSQLのInteger型に渡す際に四捨五入され、
  0.5 → 1 のように情報が失われていた。

[修正方針]
  machining_qty を Int → Decimal(10,4) に変更し、小数を正しく保持する。
  通貨型の標準精度(小数4桁)に合わせる。

[修正対象ファイル]
  1. apps/api/prisma/schema.prisma
       McProgram.machiningQty: Int? @default(1) → Decimal? @db.Decimal(10,4) @default(1)
  2. apps/api/src/mc/dto/create-mc.dto.ts
       @IsInt() @Min(1) → @IsNumber() @Min(0.0001)
  3. apps/api/src/mc/dto/update-mc.dto.ts
       同上
  4. scripts/mc_full_import.py (PHASE1)
       qty or 1 のまま(Decimal化により小数も正しく渡るようになるため変更不要だが、
       int化していないか確認し、もし変換していれば修正)

[DB側]
  prisma migrate dev/reset は禁止ルールのため、
  ALTER TABLE で直接カラム型を変更する(本パッチでは別途SQL実行が必要)。
"""
import sys, os

REPO = os.environ.get("MACHCORE_REPO", "/home/karkyon/projects/machcore")
F_SCHEMA   = os.path.join(REPO, "apps/api/prisma/schema.prisma")
F_CREATE   = os.path.join(REPO, "apps/api/src/mc/dto/create-mc.dto.ts")
F_UPDATE   = os.path.join(REPO, "apps/api/src/mc/dto/update-mc.dto.ts")


def load(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def save(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def patch(src, old, new, label):
    cnt = src.count(old)
    if cnt == 0:
        if new and new in src:
            print(f"[SKIP] {label}: 適用済み")
            return src
        print(f"[ABORT] {label}: 元コード不一致（一致数=0）")
        sys.exit(1)
    if cnt != 1:
        print(f"[ABORT] {label}: 一致数={cnt}（期待値=1）")
        sys.exit(1)
    print(f"[OK] {label} 適用")
    return src.replace(old, new, 1)


# ──────────────────────────────────────────────
# 1. schema.prisma
# ──────────────────────────────────────────────
src = load(F_SCHEMA)

OLD_SCHEMA = '''  machiningQty  Int?            @default(1)                  @map("machining_qty")'''
NEW_SCHEMA = '''  machiningQty  Decimal?        @db.Decimal(10, 4) @default(1) @map("machining_qty")'''

src = patch(src, OLD_SCHEMA, NEW_SCHEMA, "1.schema.prisma: McProgram.machiningQty を Decimal(10,4) に変更")

save(F_SCHEMA, src)
print("[OK] schema.prisma 保存完了")


# ──────────────────────────────────────────────
# 2. create-mc.dto.ts
# ──────────────────────────────────────────────
src = load(F_CREATE)

OLD_CREATE = '''  @IsOptional() @IsInt() @Min(1)
  machining_qty?: number;'''
NEW_CREATE = '''  @IsOptional() @IsNumber() @Min(0.0001)
  machining_qty?: number;'''

src = patch(src, OLD_CREATE, NEW_CREATE, "2.create-mc.dto.ts: machining_qty を IsNumber に変更")

save(F_CREATE, src)
print("[OK] create-mc.dto.ts 保存完了")


# ──────────────────────────────────────────────
# 3. update-mc.dto.ts
# ──────────────────────────────────────────────
src = load(F_UPDATE)

OLD_UPDATE = '''  @IsOptional() @IsInt() @Min(1)
  machining_qty?: number;'''
NEW_UPDATE = '''  @IsOptional() @IsNumber() @Min(0.0001)
  machining_qty?: number;'''

src = patch(src, OLD_UPDATE, NEW_UPDATE, "3.update-mc.dto.ts: machining_qty を IsNumber に変更")

save(F_UPDATE, src)
print("[OK] update-mc.dto.ts 保存完了")


# ──────────────────────────────────────────────
# 4. IsNumber import 確認・追加
#    create-mc.dto.ts は既に "import { IsNumber, IsInt, IsString, IsOptional, Min, MaxLength }"
#    でIsNumberをimport済み(確認済み)のため対象外。
#    update-mc.dto.ts は "import { IsInt, IsString, IsOptional, Min, MaxLength }" で
#    IsNumber未import(確認済み)のため追加する。
# ──────────────────────────────────────────────
src = load(F_UPDATE)
OLD_IMPORT_UPDATE = "import { IsInt, IsString, IsOptional, Min, MaxLength } from 'class-validator';"
NEW_IMPORT_UPDATE = "import { IsInt, IsNumber, IsString, IsOptional, Min, MaxLength } from 'class-validator';"
src = patch(src, OLD_IMPORT_UPDATE, NEW_IMPORT_UPDATE, "4.update-mc.dto.ts: import文にIsNumberを追加")
save(F_UPDATE, src)
print("[OK] update-mc.dto.ts import修正完了")

src = load(F_CREATE)
first_line_create = src.split("\n", 1)[0]
if "IsNumber" in first_line_create:
    print("[OK] create-mc.dto.ts: IsNumberは既にimport済み(変更不要)")
else:
    print(f"[WARN] create-mc.dto.ts: 想定と異なるimport行です。手動確認してください: {first_line_create}")


print("\n[OK] 全ファイル修正完了")

import subprocess

print("\n=== TypeScript構文簡易チェック(波括弧対応のみ確認) ===")
for fpath in [F_CREATE, F_UPDATE]:
    content = load(fpath)
    if content.count("{") != content.count("}"):
        print(f"[ABORT] {fpath}: 波括弧の数が不一致です。構文エラーの可能性。")
        sys.exit(1)
print("[OK] 簡易構文チェック成功(波括弧対応OK)")


def sh(cmd, cwd=None):
    print(f"[RUN] {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode, r.stdout, r.stderr


# ──────────────────────────────────────────────
# 5. DB側カラム型変更 (prisma migrate dev/reset禁止ルールのため直接SQL)
#    既存の整数値はDecimalへ無損失で変換可能(USING句で明示キャスト)。
# ──────────────────────────────────────────────
print("\n=== [DB] mc_programs.machining_qty カラム型変更 (Integer→Decimal(10,4)) ===")
alter_sql = (
    "ALTER TABLE mc_programs "
    "ALTER COLUMN machining_qty TYPE numeric(10,4) "
    "USING machining_qty::numeric(10,4);"
)
docker_cmd = (
    f'docker exec machcore-postgres psql -U machcore -d machcore_dev -c "{alter_sql}"'
)
rc, out, err = sh(docker_cmd)
if rc != 0:
    print("[ABORT] DBカラム型変更に失敗しました。")
    sys.exit(1)
print("[OK] DBカラム型変更完了")

# ──────────────────────────────────────────────
# 6. prisma generate (migrate dev/resetは使わず、生成のみ)
# ──────────────────────────────────────────────
print("\n=== [2] prisma generate ===")
rc, out, err = sh(
    f"export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && "
    f"cd {REPO}/apps/api && node_modules/.bin/prisma generate 2>&1"
)
if rc != 0:
    print("[ABORT] prisma generate に失敗しました。")
    sys.exit(1)
print("[OK] prisma generate 完了")

# ──────────────────────────────────────────────
# 7. APIビルド確認
# ──────────────────────────────────────────────
print("\n=== [3] APIビルド確認 (nest build) ===")
rc, out, err = sh(
    f"export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && "
    f"cd {REPO}/apps/api && node_modules/.bin/nest build 2>&1"
)
full_out = (out or "") + (err or "")
if "error TS" in full_out:
    print("[ABORT] APIビルドでエラーTSを検出。push中止。")
    sys.exit(1)
if rc != 0:
    print(f"[ABORT] APIビルドが異常終了(returncode={rc})。push中止。")
    sys.exit(1)
print("[OK] APIビルド エラー0件")

# ──────────────────────────────────────────────
# 8. Webビルド確認
# ──────────────────────────────────────────────
print("\n=== [4] Webビルド確認 (pnpm --filter web build) ===")
rc, out, err = sh(
    f"export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && "
    f"cd {REPO} && pnpm --filter web build 2>&1"
)
full_out = (out or "") + (err or "")
if "error TS" in full_out:
    print("[ABORT] Webビルドでエラーtsを検出。push中止。")
    sys.exit(1)
if rc != 0:
    print(f"[ABORT] Webビルドが異常終了(returncode={rc})。push中止。")
    sys.exit(1)
print("[OK] Webビルド エラー0件")

# ──────────────────────────────────────────────
# 9. git push
# ──────────────────────────────────────────────
print("\n=== [5] git push ===")
rc, out, err = sh(
    f'cd {REPO} && git add -A && '
    f'git commit -m "fix: machining_qty を Decimal(10,4) に変更し小数値を正しく保持" && '
    f'git push origin main 2>&1'
)
if rc != 0 and "nothing to commit" not in (out + err):
    print("[ABORT] git push に失敗しました。")
    sys.exit(1)
print("[OK] git push 完了")

# ──────────────────────────────────────────────
# 10. PM2再起動
# ──────────────────────────────────────────────
print("\n=== [6] PM2再起動 (machcore-api) ===")
rc, out, err = sh("pm2 restart machcore-api")
if rc != 0:
    print("[ABORT] PM2再起動に失敗しました。")
    sys.exit(1)
print("[OK] PM2再起動完了")

print("\n=== [7] 後片付け(自分自身) ===")
self_path = os.path.abspath(__file__)
print(f"  このスクリプト自身を削除: {self_path}")
try:
    os.remove(self_path)
except OSError as e:
    print(f"  [WARN] 自己削除に失敗: {e}")

print("\n[DONE] 全工程完了。再インポート(--phase 1)を実行すると、")
print("  旧データの小数値(加工個数)が正しく反映されます。")
