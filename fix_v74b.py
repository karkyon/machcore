#!/usr/bin/env python3
"""fix_v74b.py — admin.controller.ts に Res を import追加してビルド"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
API  = f"{ROOT}/apps/api/src"

def read(path):
    with open(path, "r", encoding="utf-8") as f: return f.read()
def write(path, c):
    with open(path, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c: print(f"WARN: {label} — 不一致"); return False
    write(path, c.replace(old, new, 1)); print(f"OK: {label}"); return True
def run(cmd, cwd=ROOT):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# Res を import に追加
patch(
    f"{API}/admin/admin.controller.ts",
    "  Controller, Get, Post, Put, Delete, Body, UseGuards,\n  Param, ParseIntPipe, Query, BadRequestException,\n} from '@nestjs/common';",
    "  Controller, Get, Post, Put, Delete, Body, UseGuards,\n  Param, ParseIntPipe, Query, BadRequestException, Res,\n} from '@nestjs/common';",
    "admin.controller.ts Res import追加"
)

# FastifyReply の型も必要
patch(
    f"{API}/admin/admin.controller.ts",
    'import { execSync } from "child_process";',
    'import { execSync } from "child_process";\nimport type { FastifyReply } from \'fastify\';',
    "admin.controller.ts FastifyReply import追加"
)

print("--- build api ---")
rc = run("pnpm --filter api build", cwd=ROOT)
if rc != 0:
    rc = run("pnpm run build", cwd=f"{ROOT}/apps/api")
if rc != 0:
    print("BUILD FAILED (api) — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-api machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v74b): admin.controller.ts Res/FastifyReply import追加' && git push", cwd=ROOT)
print("DONE v74b")
