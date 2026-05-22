#!/usr/bin/env python3
# coding: utf-8
"""
fix_v34b.py
  edit/page.tsx で isAuthenticated が useAuth() 宣言より前に参照されている
  → sbMode自動認証useEffectを useAuth()宣言の後に移動する
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"
EDIT = ROOT + "/apps/web/app/mc/[mc_id]/edit/page.tsx"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    s = p.read_text(encoding="utf-8")
    if old in s:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {label}")
        return True
    print(f"WARN: {label} — パターン不一致")
    return False

# Step1: sbMode自動認証useEffectを削除（useAuth前の位置から）
apply(
    EDIT,
    """
  // sbMode=true かつ未認証の場合は自動で認証モーダルを開く
  React.useEffect(() => {
    if (sbMode && !isAuthenticated) {
      console.log("[STEP1] sbMode=true 未認証 → 認証モーダルを自動表示");
      setAuthOpen(true);
    }
  }, [sbMode, isAuthenticated]);

  const [detail, setDetail]   = useState<McDetail | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);""",
    """
  const [detail, setDetail]   = useState<McDetail | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  // sbMode=true かつ未認証の場合は自動で認証モーダルを開く（useAuth後に配置必須）
  React.useEffect(() => {
    if (sbMode && !isAuthenticated) {
      console.log("[STEP1] sbMode=true 未認証 → 認証モーダルを自動表示");
      setAuthOpen(true);
    }
  }, [sbMode, isAuthenticated]);""",
    "edit/page.tsx sbMode自動認証useEffectをuseAuth宣言後に移動"
)

# Build
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

print("\n--- pm2 restart web ---")
r2 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout)

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'fix: edit sbMode自動認証useEffectをuseAuth宣言後に移動 v34b' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])

print("\nDONE")
