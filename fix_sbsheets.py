#!/usr/bin/env python3
import os

ROOT = os.path.expanduser("~/projects/machcore")
page = os.path.join(ROOT, "apps/web/app/page.tsx")

with open(page) as f:
    content = f.read()

# sbSheets 参照を削除（条件式を単純化）
OLD = "      {sbError && sbSheets !== null && ("
NEW = "      {sbError && sbResult !== null && ("
content = content.replace(OLD, NEW, 1)

with open(page, "w") as f:
    f.write(content)
print("OK")
