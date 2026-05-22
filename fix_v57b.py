import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch(path, old, new, label):
    content = read(path)
    if old not in content:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, content.replace(old, new, 1))
    print(f"OK: {label}")
    return True

# ── 1. api.ts Machine型にsortOrder追加 ──────────────────────────────
API_TS = f"{ROOT}/apps/web/lib/api.ts"

OLD_MACHINE_TYPE = '''export type Machine = {
  id: number;
  machineCode: string;
  machineName: string;
  isActive: boolean;
};'''

NEW_MACHINE_TYPE = '''export type Machine = {
  id: number;
  machineCode: string;
  machineName: string;
  isActive: boolean;
  sortOrder: number;
};'''

patch(API_TS, OLD_MACHINE_TYPE, NEW_MACHINE_TYPE, "api.ts Machine型にsortOrder追加")

# ── 2. ビルド & デプロイ ───────────────────────────────────────────────
def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
rc_api = run("npx nest build", cwd=f"{ROOT}/apps/api")
rc_web = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc_web != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("pm2 restart machcore-api machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: Machine型にsortOrder追加 v57b" && git push')
print("DONE")
