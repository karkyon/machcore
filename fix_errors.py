#!/usr/bin/env python3
"""
エラー修正スクリプト
1. mc.controller.ts: Put 重複 import 修正
2. page.tsx: State 定義が挿入されていない問題を修正
"""
import os, subprocess, sys, re

ROOT = os.path.expanduser("~/projects/machcore")
API  = os.path.join(ROOT, "apps/api")
WEB  = os.path.join(ROOT, "apps/web")

def run(cmd, cwd=None, check=True):
    print(f"  $ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd or ROOT, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip(), file=sys.stderr)
    if check and r.returncode != 0:
        print(f"ERROR: exit {r.returncode}")
        sys.exit(1)
    return r

# ─────────────────────────────────────────
# Fix 1: mc.controller.ts の Put 重複 import 修正
# ─────────────────────────────────────────
print("\n[Fix 1] mc.controller.ts Put 重複 import 修正...")
ctrl = os.path.join(API, "src/mc/mc.controller.ts")
with open(ctrl) as f:
    content = f.read()

# Put, Put → Put に修正
if "Put, Put" in content:
    content = content.replace("Put, Put", "Put", 1)
    with open(ctrl, "w") as f:
        f.write(content)
    print("  OK: Put 重複を修正しました")
else:
    print("  INFO: Put 重複なし（確認のみ）")
    # import行を表示
    for line in content.split('\n')[:5]:
        print(f"    {line}")

# ─────────────────────────────────────────
# Fix 2: page.tsx の State 定義挿入確認・修正
# ─────────────────────────────────────────
print("\n[Fix 2] page.tsx State 定義確認・修正...")
page = os.path.join(WEB, "app/page.tsx")
with open(page) as f:
    content = f.read()

needs_fix = False

# setCollectingId が定義されているか確認
if "setCollectingId" in content and "useState<{system" not in content and "collectingId" not in content.split("useState")[0]:
    needs_fix = True
    print("  INFO: collectingId state が未定義 → 追加します")

# State が追加されているか確認
if "collectingId" not in content:
    needs_fix = True

if needs_fix or "useState<{system" not in content:
    # lastAt state の直後に追加
    # 既存のパターンを探す
    patterns = [
        'const [lastAt,   setLastAt]   = useState<Date | null>(null);',
        'const [lastAt,  setLastAt]  = useState<Date | null>(null);',
        'const [lastAt, setLastAt] = useState<Date | null>(null);',
    ]
    found_pattern = None
    for p in patterns:
        if p in content:
            found_pattern = p
            break

    if found_pattern:
        state_additions = '''
  const [collectingId,  setCollectingId]  = useState<{system:"NC"|"MC"; id:number; programId:number} | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [collectErr,    setCollectErr]    = useState<string | null>(null);
  const [users,         setUsers]         = useState<any[]>([]);'''
        if "collectingId" not in content:
            content = content.replace(found_pattern, found_pattern + state_additions, 1)
            with open(page, "w") as f:
                f.write(content)
            print("  OK: State 定義を追加しました")
        else:
            print("  INFO: State 定義は既に存在します")
    else:
        print("  ERROR: lastAt state パターンが見つかりません")
        # デバッグ: useState の行を表示
        for i, line in enumerate(content.split('\n')):
            if 'useState' in line and 'lastAt' in line.lower():
                print(f"    line {i}: {line}")
        sys.exit(1)
else:
    print("  INFO: State 定義は既に存在します")

# ─────────────────────────────────────────
# Fix 3: users fetch useEffect 確認
# ─────────────────────────────────────────
print("\n[Fix 3] users fetch useEffect 確認...")
with open(page) as f:
    content = f.read()

if "/users" in content and "setUsers" in content:
    print("  INFO: users fetch は既に存在します")
else:
    # load useEffect の後に追加
    old_effect = '''  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);'''
    new_effect = '''  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
    fetch(`${API_URL}/users`).then(r => r.json()).then(d => setUsers(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);'''
    if old_effect in content:
        content = content.replace(old_effect, new_effect, 1)
        with open(page, "w") as f:
            f.write(content)
        print("  OK: users fetch useEffect 追加")
    else:
        print("  INFO: useEffect パターンが見つかりません（スキップ）")

# ─────────────────────────────────────────
# Fix 4: AuthModal import 確認
# ─────────────────────────────────────────
print("\n[Fix 4] AuthModal import 確認...")
with open(page) as f:
    content = f.read()

if 'AuthModal' not in content:
    # import 追加
    first_import = content.find('"use client"')
    insert_pos = content.find('\n', first_import) + 1
    # 最初のimport行の後に追加
    next_import = content.find('import ', insert_pos)
    if next_import != -1:
        content = content[:next_import] + 'import AuthModal from "@/components/auth/AuthModal";\n' + content[next_import:]
        with open(page, "w") as f:
            f.write(content)
        print("  OK: AuthModal import 追加")
elif 'import AuthModal' in content:
    print("  INFO: AuthModal import 既に存在")

print("\n✅ 修正完了")
print("\n次の手順:")
print("1. cd ~/projects/machcore/apps/api && npx tsc")
print("2. pm2 restart machcore-api && sleep 8")
print("3. cd ~/projects/machcore/apps/web && npm run build")
print("4. cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
