#!/usr/bin/env python3
"""
fix_offset_index_v1c.py
page.tsx WOブロック・IPブロックの余分な閉じタグを修正
"""
import subprocess, sys

BASE     = "/home/karkyon/projects/machcore"
REF_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/page.tsx"

with open(REF_PAGE, "r") as f:
    src = f.read()

# doc6で確認した現在のWOブロック末尾（余分なdivが1つある）
OLD_WO = '''                </div>
              )}
                </div>
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''

NEW_WO = '''                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── インデックスプログラム ─── */}'''

if OLD_WO in src:
    src = src.replace(OLD_WO, NEW_WO, 1)
    print("  OK: WO 余分div除去")
else:
    print("  WARN: WO パターン不一致 — 手動確認:")
    idx = src.find('─── インデックスプログラム')
    if idx != -1:
        print(repr(src[max(0,idx-250):idx+80]))
    sys.exit(1)

# IPブロックも同様に確認・修正
OLD_IP = '''                </div>
              )}
                </div>
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}'''

NEW_IP = '''                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── 履歴 ─── */}'''

if OLD_IP in src:
    src = src.replace(OLD_IP, NEW_IP, 1)
    print("  OK: IP 余分div除去")
else:
    print("  INFO: IP余分divなし（正常）")

with open(REF_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", REF_PAGE)

print("=== ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -20",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr[-500:])
    sys.exit(1)

print("=== PM2 再起動 ===")
r = subprocess.run("pm2 restart machcore-web && pm2 ls", shell=True, capture_output=True, text=True)
print(r.stdout)

print("=== git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: offset/index v1c - fix closing tags WO/IP" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
