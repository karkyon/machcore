import subprocess, os

FILEPATH = "/home/karkyon/projects/machcore/apps/api/src/mc/mc.service.ts"
PROJ     = "/home/karkyon/projects/machcore"

for root, dirs, files in os.walk(f"{PROJ}/apps"):
    for f in files:
        if f.endswith('.bak'):
            os.remove(os.path.join(root, f))

code = open(FILEPATH, encoding='utf-8').read()

# 全3箇所 6.5 → 10.5
before = code.count('6.5')
code = code.replace(
    "size: 6.5, font: font2, color: rgb(0.4,0.4,0.4) }); // p2発行日時",
    "size: 10.5, font: font2, color: rgb(0.4,0.4,0.4) }); // p2発行日時"
)
# dtSz定義を全て10.5に
import re
code, n = re.subn(r'(const dtSz = )6\.5(;)', r'\g<1>10.5\2', code)
print(f"dtSz置換: {n}箇所")

# p2の発行日時size: 6.5も置換
code, n2 = re.subn(
    r"(p2Page\.drawText\(`発行: \$\{issuedAtNew\}`,.*?size: )6\.5",
    r"\g<1>10.5",
    code
)
print(f"p2発行日時size置換: {n2}箇所")

open(FILEPATH, 'w', encoding='utf-8').write(code)

# 確認
matches = [(i+1, l.rstrip()) for i,l in enumerate(code.splitlines()) if 'dtSz' in l or ('発行' in l and 'size' in l)]
for ln, l in matches:
    print(f"  L{ln}: {l}")

r = subprocess.run(["npx","tsc","--noEmit"], cwd=f"{PROJ}/apps/api", capture_output=True, text=True)
if r.returncode != 0:
    print("TSCエラー:", r.stdout[-2000:]); exit(1)
print("✅ tsc OK")

r = subprocess.run(["npx","nest","build"], cwd=f"{PROJ}/apps/api", capture_output=True, text=True, timeout=120)
if r.returncode != 0:
    print("BUILD ERROR:", r.stdout[-2000:]); exit(1)
print("✅ nest build OK")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True)
print("✅ pm2 restart")

subprocess.run(["git","add","apps/api/src/mc/mc.service.ts"], cwd=PROJ)
subprocess.run(["git","commit","-m","fix: issued datetime font size 10.5pt"], cwd=PROJ)
r = subprocess.run(["git","push"], cwd=PROJ, capture_output=True, text=True)
print("✅ git push\n", r.stdout, r.stderr)
