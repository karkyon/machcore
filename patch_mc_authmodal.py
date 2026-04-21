#!/usr/bin/env python3
"""patch_mc_authmodal.py — MC フロントエンド 3ファイルの AuthModal Props を修正"""
import re

WEB = '/home/karkyon/projects/machcore/apps/web/app/mc'

files = {
    f'{WEB}/[mc_id]/page.tsx':   'mc/[mc_id]/page.tsx',
    f'{WEB}/[mc_id]/edit/page.tsx':   'mc/[mc_id]/edit/page.tsx',
    f'{WEB}/[mc_id]/print/page.tsx':  'mc/[mc_id]/print/page.tsx',
    f'{WEB}/[mc_id]/record/page.tsx': 'mc/[mc_id]/record/page.tsx',
}

for path, label in files.items():
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    original = src

    # <AuthModal ncId={...} sessionType="..." onSuccess=... onCancel=... />
    # → <AuthModal isOpen={true} ncProgramId={...} sessionType="..." onSuccess=... onCancel=... />
    src = re.sub(
        r'<AuthModal\s+ncId=\{(\w+)\}\s+sessionType="([^"]+)"\s+onSuccess=\{([^}]+)\}\s+onCancel=\{([^}]+)\}\s*/>',
        r'<AuthModal isOpen={true} ncProgramId={\1} sessionType="\2" onSuccess={\3} onCancel={\4} />',
        src
    )

    if src != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f'OK: {label}')
    else:
        print(f'SKIP: {label} (変更なし)')

print('\n✅ AuthModal Props 修正完了')
