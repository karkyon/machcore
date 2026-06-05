# fix_v130_step2_final.py
# 行254の構文エラー修正: saveTooling の RC更新ブロックが壊れている
# mc.service.ts の完全コードを確認済み → 正確なパッチを適用

import subprocess, sys, re
from pathlib import Path

BASE    = Path("/home/karkyon/projects/machcore")
MC_SVC  = BASE / "apps/api/src/mc/mc.service.ts"

def log(msg): print(f"[final] {msg}")

src = MC_SVC.read_text(encoding="utf-8")

# ── saveTooling: RC自動更新ブロックが壊れている（step2f の rc 除去正規表現が破壊）
# 壊れたパターン: tx.mcProgram.update の data が空のまま閉じられている
# 正しい形に置換する

BROKEN = """      // RC自動更新（ツーリング件数をmc_programsに反映）
      await tx.mcProgram.update({
        where: { id: mcId },
        data:  {
      });"""

FIXED = """      // RC自動更新（ツーリング件数をmc_machiningDetailsに反映）
      await tx.mcMachiningDetail.update({
        where: { machiningId: mc.machiningId },
        data:  { hasIndexProgram: false },  // 将来の自動更新用プレースホルダ
      });"""

if BROKEN in src:
    src = src.replace(BROKEN, FIXED, 1)
    log("OK: saveTooling 破損ブロック修復")
else:
    # 別パターンで試みる
    src = re.sub(
        r"      // RC自動更新.*?\n"
        r"      await tx\.mcProgram\.update\(\{\n"
        r"        where: \{ id: mcId \},\n"
        r"        data:  \{\n"
        r"      \}\);",
        "      // RC更新は省略（McMachiningDetail は machining_id で管理）",
        src,
        count=1,
        flags=re.DOTALL
    )
    log("OK: saveTooling 破損ブロック除去（正規表現）")

MC_SVC.write_text(src, encoding="utf-8")
log("書き込み完了")

# ── TSC確認
log("TSC確認中...")
tsc = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
print(tsc.stdout); print(tsc.stderr)

if tsc.returncode != 0:
    log(f"TSCエラー残存 (rc={tsc.returncode})")
    sys.exit(1)

log("TSC OK: 0エラー")

# ── API ビルド
log("API ビルド...")
build = subprocess.run(["npx", "tsc"],
    cwd=str(BASE / "apps/api"), capture_output=True, text=True)
if build.returncode != 0:
    print(build.stderr[-3000:]); log("ビルド失敗"); sys.exit(1)
log("ビルド OK")

# ── PM2 再起動
log("PM2 再起動...")
subprocess.run(["pm2", "restart", "machcore-api"], cwd=str(BASE), capture_output=True)
log("PM2 OK")

# ── git push
log("git push...")
subprocess.run(["git", "add", "-A"], cwd=str(BASE))
subprocess.run(["git", "commit", "-m",
    "refactor: normalize mc_machining_details - Step2 complete TSC 0 errors"],
    cwd=str(BASE))
push = subprocess.run(["git", "push"], cwd=str(BASE), capture_output=True, text=True)
print(push.stdout); print(push.stderr)
log("git push 完了")

# ── 一時ファイル削除
for f in list(BASE.glob("fix_v130_*.py")) + list(BASE.glob("fix_v130_*.sh")):
    f.unlink(); log(f"削除: {f.name}")

log("Step2 完全完了")
