#!/usr/bin/env python3
"""
page.tsx を正しい内容で完全書き換え
"""
import os, sys

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = os.path.join(ROOT, "apps/web")
page = os.path.join(WEB, "app/page.tsx")

# 現在のファイルを読んで State 宣言ブロックを確認
with open(page) as f:
    current = f.read()

# useState 宣言行を全部表示してデバッグ
print("=== 現在の useState 宣言一覧 ===")
for i, line in enumerate(current.split('\n')):
    if 'useState' in line:
        print(f"  L{i+1}: {line.rstrip()}")

# "collectingId" が useState で宣言されているか確認
lines = current.split('\n')
collecting_declared = any(
    'useState' in l and 'collectingId' in l
    for l in lines
)
print(f"\ncollectingId useState宣言: {collecting_declared}")

if collecting_declared:
    print("既に正しく宣言済み → 修正不要")
    sys.exit(0)

# period の useState 行を見つけてその直後に4行挿入
NEW_STATES = [
    '  const [collectingId,  setCollectingId]  = useState<{system:"NC"|"MC"; id:number; programId:number} | null>(null);',
    '  const [showAuthModal, setShowAuthModal] = useState(false);',
    '  const [collectErr,    setCollectErr]    = useState<string | null>(null);',
    '  const [users,         setUsers]         = useState<any[]>([]);',
]

new_lines = []
inserted = False
for line in lines:
    new_lines.append(line)
    # period の useState 宣言の直後に挿入
    if not inserted and 'useState' in line and 'period' in line and 'setPeriod' in line:
        for s in NEW_STATES:
            new_lines.append(s)
        inserted = True
        print(f"\nOK: period の直後に State 4行を挿入")

if not inserted:
    print("ERROR: period useState 行が見つかりません")
    sys.exit(1)

# users fetch useEffect を load useEffect の直後に挿入
LOAD_EFFECT_LINE = "  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);"
USERS_EFFECT = [
    "",
    "  useEffect(() => {",
    "    const _API = process.env.NEXT_PUBLIC_API_URL || \"http://localhost:3011/api\";",
    "    fetch(`${_API}/users`).then(r => r.json()).then((d: any) => setUsers(Array.isArray(d) ? d : [])).catch(() => {});",
    "  }, []);",
]

has_users_fetch = any('/users' in l and 'setUsers' in l for l in new_lines)
if not has_users_fetch:
    final_lines = []
    for line in new_lines:
        final_lines.append(line)
        if line.strip() == LOAD_EFFECT_LINE.strip():
            for u in USERS_EFFECT:
                final_lines.append(u)
            print("OK: users fetch useEffect を追加")
    new_lines = final_lines
else:
    print("INFO: users fetch は既に存在")

content = '\n'.join(new_lines)

with open(page, 'w') as f:
    f.write(content)

print("\n=== 修正後の useState 宣言一覧 ===")
for i, line in enumerate(content.split('\n')):
    if 'useState' in line:
        print(f"  L{i+1}: {line.rstrip()}")

print("\n✅ 完了")
print("\n次の手順:")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
