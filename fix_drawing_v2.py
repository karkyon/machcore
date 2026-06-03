#!/usr/bin/env python3
"""
fix_drawing_v2.py
RIDOC図面取得不可の完全修正:
1. ecosystem.config.js に RIDOC_API_URL 追加
2. apps/api を tsc ビルド（dist更新）
3. PM2 --update-env で再起動
4. 動作確認
"""
import subprocess, sys, time

BASE = "/home/karkyon/projects/machcore"
ECOSYSTEM = f"{BASE}/ecosystem.config.js"
NVM = "export NVM_DIR=$HOME/.nvm && . $NVM_DIR/nvm.sh && "

def sh(cmd, capture=True, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=capture, text=True, cwd=cwd)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

# ── 1. ecosystem.config.js に RIDOC_API_URL を追加 ──
print("=== [1] ecosystem.config.js 修正 ===")
eco = open(ECOSYSTEM, encoding="utf-8").read()

if "RIDOC_API_URL" in eco:
    print("  SKIP: 既に存在")
else:
    # machcore-api の env ブロックに追記
    OLD = "      env: { NODE_ENV: 'production', API_PORT: 3011 },"
    NEW = "      env: { NODE_ENV: 'production', API_PORT: 3011, RIDOC_API_URL: 'http://192.168.1.207:5087' },"
    if OLD not in eco:
        print(f"  ⚠️  アンカー見つからない: {repr(OLD[:60])}")
        # 内容表示してデバッグ
        idx = eco.find("NODE_ENV")
        print(f"  DEBUG: {repr(eco[max(0,idx-10):idx+80])}")
        sys.exit(1)
    eco = eco.replace(OLD, NEW)
    open(ECOSYSTEM, "w", encoding="utf-8").write(eco)
    print("  OK: RIDOC_API_URL=http://192.168.1.207:5087 を ecosystem.config.js に追加")

# ── 2. API TypeScript ビルド ──
print("\n=== [2] API tsc ビルド ===")
out, err, rc = sh(
    f"{NVM}cd {BASE}/apps/api && npx tsc --noEmit 2>&1 | tail -5",
    capture=True
)
if out: print(f"  tsc check: {out}")
if rc != 0 and "error" in (out+err).lower():
    print(f"  TypeScript エラー: {err[:500]}")
    sys.exit(1)
print("  OK: TypeCheck通過")

# APIビルド（NestJS dist生成）
print("  NestJS ビルド中...")
out, err, rc = sh(
    f"{NVM}cd {BASE}/apps/api && npx nest build 2>&1 | tail -10"
)
print(f"  {out[-500:] if out else ''}")
if rc != 0:
    print(f"  ビルドエラー: {err[:500]}")
    sys.exit(1)
print("  OK: dist ビルド完了")

# ── 3. PM2 ecosystem で再起動（--update-env）──
print("\n=== [3] PM2 再起動（ecosystem.config.js + --update-env）===")
subprocess.run(
    f"{NVM}cd {BASE} && pm2 restart ecosystem.config.js --only machcore-api --update-env",
    shell=True, capture_output=False
)
time.sleep(5)

# ── 4. 環境変数の反映確認 ──
print("\n=== [4] プロセス内環境変数確認 ===")
out, _, _ = sh(f"{NVM}pm2 env machcore-api 2>/dev/null | grep RIDOC")
print(f"  {out or '（見つからない - ecosystem再読込が必要かも）'}")

# ── 5. 動作テスト ──
print("\n=== [5] 動作テスト ===")
time.sleep(3)

# MC 87441 で直接テスト（drawingNo = T22044B10 が確認済み）
test_id = "87441"
out, _, rc = sh(
    f"curl -s -w '\\nHTTP:%{{http_code}} TYPE:%{{content_type}}' "
    f"--connect-timeout 10 "
    f"'http://localhost:3011/api/mc/{test_id}/drawing-image?imgType=TN' "
    f"-o /tmp/drawing_test.bin 2>&1"
)
print(f"  MC {test_id} TN テスト: {out}")

# ファイルサイズ確認
out2, _, _ = sh("wc -c /tmp/drawing_test.bin 2>/dev/null || echo '0 bytes'")
print(f"  レスポンスサイズ: {out2}")

# エラーの場合、本文表示
if "HTTP:404" in out or "HTTP:503" in out or "HTTP:502" in out:
    out3, _, _ = sh("cat /tmp/drawing_test.bin 2>/dev/null | head -c 300")
    print(f"  エラー本文: {out3}")

# ── 6. git push ──
print("\n=== [6] git push ===")
subprocess.run(
    f"cd {BASE} && git add -A && "
    "git commit -m 'fix: ecosystem.config.js RIDOC_API_URL + API rebuild' && "
    "git push",
    shell=True
)

print("\n=== 完了 ===")
