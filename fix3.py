#!/usr/bin/env python3
# coding: utf-8
import pathlib

PAGE = pathlib.Path("/home/karkyon/projects/machcore/apps/web/app/page.tsx")
src = PAGE.read_text(encoding="utf-8")

if "is_reference" not in src:
    src = src.replace(
        "  version: string | null; printed_at: string; operator_name: string;\n"
        "};",
        "  version: string | null; printed_at: string; operator_name: string;\n"
        "  sheet_type?: string | null;\n"
        "  is_reference?: boolean;\n"
        "};",
        1)
    PAGE.write_text(src, encoding="utf-8")
    print("OK: McSheet型に sheet_type/is_reference 追加")
else:
    print("INFO: 既に存在")

print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
