#!/usr/bin/env python3
# coding: utf-8
"""
fix_v41.py
  問題1: 別PCでダッシュボード0件
    → API_URL = "http://localhost:3011/api" がビルド時埋め込みされ
      別PCブラウザからlocalhost:3011に接続しようとして失敗
    → page.tsx / nc/page.tsx の fetch(API_URL + ...) を fetch("/api/...") に変更
      (Next.js rewrite: /api/* → localhost:3011/api/* はサーバーサイドで動くので問題なし)
    → print/page.tsx の fetch(apiUrl + ...) も同様に /api/... に変更

  問題2: 段取シート印刷で is_reference should not exist
    → PrintMcDto に @IsOptional() @IsBoolean() is_reference?: boolean; を追加
    → API 再ビルド + pm2 restart
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    s = p.read_text(encoding="utf-8")
    if old in s:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {label}")
        return True
    print(f"WARN: {label} — パターン不一致")
    return False

# ── 1. page.tsx (MCダッシュボード) API_URLをrelativeパスに変更 ──
apply(
    ROOT + "/apps/web/app/page.tsx",
    'const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";',
    'const API_URL = "/api";  // Next.js rewrite経由 → サーバー側でlocalhost:3011にproxy',
    "page.tsx API_URL → /api (relative)"
)

# ── 2. nc/page.tsx (NCダッシュボード) 同様 ──
apply(
    ROOT + "/apps/web/app/nc/page.tsx",
    'const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";',
    'const API_URL = "/api";  // Next.js rewrite経由',
    "nc/page.tsx API_URL → /api (relative)"
)

# ── 3. mc/print/page.tsx の fetch(apiUrl + ...) を /api/... に変更 ──
apply(
    ROOT + "/apps/web/app/mc/[mc_id]/print/page.tsx",
    """    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiUrl}/mc/${mcId}/print`, {""",
    """    try {
      const res = await fetch(`/api/mc/${mcId}/print`, {""",
    "print/page.tsx handlePrint apiUrl → /api (relative)"
)

apply(
    ROOT + "/apps/web/app/mc/[mc_id]/print/page.tsx",
    """    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3011/api";
      const res = await fetch(`${apiUrl}/mc/${mcId}/direct-print`, {""",
    """    try {
      const res = await fetch(`/api/mc/${mcId}/direct-print`, {""",
    "print/page.tsx handleDirectPrint apiUrl → /api (relative)"
)

# ── 4. PrintMcDto に is_reference 追加 ──
apply(
    ROOT + "/apps/api/src/mc/dto/print-mc.dto.ts",
    "  @IsOptional() @IsBoolean() include_index_programs?: boolean;\n}",
    "  @IsOptional() @IsBoolean() include_index_programs?: boolean;\n  @IsOptional() @IsBoolean() is_reference?: boolean;\n}",
    "PrintMcDto is_reference 追加"
)

# ── 5. API 再ビルド ──
print("\n--- API npx tsc --noEmit ---")
r0 = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/api && npx tsc --noEmit",
    shell=True, capture_output=True, text=True
)
print(r0.stdout or "(no output)")
if r0.returncode != 0:
    print("STDERR:", r0.stderr[-1000:])
    print("API TSC FAILED — abort")
    sys.exit(1)

print("--- API pm2 restart ---")
r0b = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && pm2 restart machcore-api',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r0b.stdout[-400:])

# ── 6. Web ビルド ──
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
out = r.stdout
print(out[-4000:] if len(out) > 4000 else out)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart web ---")
r2 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout[-600:])

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && git add -A && "
    "git commit -m 'fix: API_URLをrelative(/api)に変更→別PC0件解消 PrintMcDto is_reference追加 v41' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])
print("\nDONE")
