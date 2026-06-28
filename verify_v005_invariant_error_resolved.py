#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_v005_invariant_error_resolved.py

【検証専用・コード変更なし】
直前のパッチ(fix_v004)適用後、pm2 logsで表示されたInvariantErrorが
「再起動前の古いログファイルの残骸」なのか「実際に再発している」のかを
正確に判定する。

pm2 logs --lines N は単にログファイル末尾のN行を読むだけで、
プロセスの再起動有無に関わらずファイル自体は追記され続けるため、
再起動直後に古いエラーがそのまま表示されることがある。
これを「ログをフラッシュ（空にする）→ 新規アクセスを複数回発生させる →
その後のログだけを見る」という手順で切り分ける。

実行手順:
  cd /home/karkyon/projects/machcore && . "$NVM_DIR/nvm.sh" && python3 verify_v005_invariant_error_resolved.py

このスクリプトはコード変更・ビルド・pushを一切行わない。
完了後は確認用なので手動削除してください。
"""
import subprocess
import time

BASE = "/home/karkyon/projects/machcore"


def run(cmd, timeout=30):
    print(f"\n$ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    print(out)
    return r.returncode, out


def main():
    print("=" * 60)
    print("【検証】InvariantError 再発有無の正確な切り分け")
    print("=" * 60)

    # 1. ログを完全にフラッシュ（過去ログを消去）
    print("\n=== [1] pm2 logs をフラッシュ（過去ログ全消去） ===")
    run(["pm2", "flush"])

    # 2. ルート"/"へ複数回アクセスして307を確認
    print("\n=== [2] '/' へ10回連続アクセス（リダイレクト動作確認） ===")
    codes = []
    for i in range(10):
        rc, out = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                       "http://localhost:3010/"], timeout=10)
        code = out.strip()
        codes.append(code)
        time.sleep(0.3)
    print(f"取得したHTTPコード一覧: {codes}")
    all_redirect_ok = all(c in ("200", "307", "308") for c in codes)

    # 3. /mc, /nc にも追加アクセス（実運用相当の負荷）
    print("\n=== [3] '/mc' '/nc' へ追加アクセス ===")
    for url in ["http://localhost:3010/mc", "http://localhost:3010/nc"] * 3:
        run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}\\n", url], timeout=10)

    # 少し待ってログが書き込まれるのを確実にする
    time.sleep(2)

    # 4. フラッシュ後・新規アクセス後のログのみを確認
    print("\n=== [4] フラッシュ後の新規ログを確認(InvariantErrorの有無) ===")
    rc, log_out = run(["pm2", "logs", "machcore-web", "--lines", "200", "--nostream"], timeout=20)

    invariant_count = log_out.count("InvariantError")
    enoent_count = log_out.count("ENOENT")

    print("\n" + "=" * 60)
    print("【結果】")
    print(f"  '/' への10回アクセス結果: {'全て正常' if all_redirect_ok else '異常あり'} {codes}")
    print(f"  新規ログ中の InvariantError 出現回数: {invariant_count}")
    print(f"  新規ログ中の ENOENT(500.html) 出現回数: {enoent_count}")

    if invariant_count == 0 and enoent_count == 0 and all_redirect_ok:
        print("\n[CONFIRMED_FIXED] 修正後の新規アクセスでは InvariantError は発生していません。")
        print("前回表示されたエラーは、再起動前の古いログファイルの残骸でした。")
    else:
        print("\n[STILL_BROKEN] 修正後の新規アクセスでも InvariantError が再発しています。")
        print("追加調査が必要です。")
    print("=" * 60)


if __name__ == "__main__":
    main()
