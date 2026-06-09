#!/usr/bin/env python3
"""
check_paths.py: MachCore 設計パス存在確認スクリプト
全パスの存在・書き込み可否・マウント状況を確認する
"""
import os, subprocess, json

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def check_dir(path, label, write_test=False):
    exists = os.path.isdir(path)
    writable = ""
    if exists and write_test:
        try:
            testfile = os.path.join(path, ".write_test")
            with open(testfile, "w") as f: f.write("ok")
            os.remove(testfile)
            writable = " ✅書込OK"
        except Exception as e:
            writable = f" ❌書込NG({e})"
    status = "✅ 存在" if exists else "❌ 不在"
    print(f"  {status}{writable}  {path}  [{label}]")
    return exists

print("=" * 70)
print("MachCore パス存在確認")
print("=" * 70)

# ─── /etc/fstab SMBエントリ確認 ───
print("\n【1】/etc/fstab SMBエントリ")
rc, out, _ = run("grep -E 'cifs|smb|ncfiles|mcfiles' /etc/fstab")
if out:
    for line in out.split("\n"):
        print(f"  {line}")
else:
    print("  ❌ SMB/CIFSエントリなし")

# ─── 現在のマウント状況 ───
print("\n【2】現在のCIFS/SMBマウント")
rc, out, _ = run("mount | grep -E 'cifs|smb'")
if out:
    for line in out.split("\n"):
        print(f"  ✅ {line}")
else:
    print("  ❌ CIFSマウントなし")

# ─── /mnt 直下確認 ───
print("\n【3】/mnt 直下")
rc, out, _ = run("ls -la /mnt/")
for line in out.split("\n"):
    print(f"  {line}")

# ─── 設計上の必須パス確認 ───
print("\n【4】MCファイル設計パス (SMBマウント先: \\\\192.168.1.9\\mc\\files → /mnt/ncfiles/mc_files)")
REQUIRED_MC = [
    ("/mnt/ncfiles/mc_files",                     "MCベースパス"),
    ("/mnt/ncfiles/mc_files/pg",                   "MCプログラム"),
    ("/mnt/ncfiles/mc_files/photos",               "MC写真"),
    ("/mnt/ncfiles/mc_files/drawings",             "MC図"),
    ("/mnt/ncfiles/mc_files/setupsheet",           "MC段取シートPDF"),
    ("/mnt/ncfiles/mc_files/thumbnails",           "MCサムネイル"),
]
for path, label in REQUIRED_MC:
    check_dir(path, label, write_test=True)

print("\n【5】NCファイル設計パス (SMBマウント先: \\\\192.168.1.9\\nc\\files → /mnt/ncfiles)")
REQUIRED_NC = [
    ("/mnt/ncfiles",                               "NCベースパス"),
    ("/mnt/ncfiles/nc_files",                      "NC用ファイル"),
]
for path, label in REQUIRED_NC:
    check_dir(path, label, write_test=True)

print("\n【6】旧移行ファイルパス確認")
LEGACY = [
    ("/mnt/mcfiles",                               "旧SMBマウント(mcfiles)"),
    ("/mnt/mcfiles/MC",                            "旧MC移行元"),
    ("/mnt/mcfiles/MC/files",                      "旧MC移行先"),
    ("/mnt/mcfiles/MC/files/Drawings",             "旧図"),
    ("/mnt/mcfiles/MC/files/Pictures",             "旧写真"),
    ("/mnt/mcfiles/MC/files/Programs",             "旧プログラム"),
]
for path, label in LEGACY:
    check_dir(path, label)

# ─── DB設定確認 ───
print("\n【7】DB companySetting 確認")
rc, out, _ = run("docker exec -i machcore-postgres psql -U machcore -d machcore_dev -c \"SELECT id, mc_storage_path, nc_storage_path, upload_base_path, mc_printer, nc_printer FROM company_settings WHERE id=1;\"")
print(f"  {out}")

# ─── 既存mc_filesのDBレコード件数確認 ───
print("\n【8】mc_files ファイルパス分布確認（上位10パターン）")
rc, out, _ = run("""docker exec -i machcore-postgres psql -U machcore -d machcore_dev -c "
SELECT
  SUBSTRING(file_path FROM 1 FOR 50) as path_prefix,
  file_type,
  COUNT(*) as cnt
FROM mc_files
WHERE is_deleted = false
GROUP BY path_prefix, file_type
ORDER BY cnt DESC
LIMIT 10;
" """)
print(f"  {out}")

# ─── 段取シートログ確認 ───
print("\n【9】mc_setup_sheet_logs pdf_path 保存状況（直近10件）")
rc, out, _ = run("""docker exec -i machcore-postgres psql -U machcore -d machcore_dev -c "
SELECT id, mc_program_id, printed_at, version, pdf_path
FROM mc_setup_sheet_logs
ORDER BY id DESC
LIMIT 10;
" """)
print(f"  {out}")

print("\n" + "=" * 70)
print("確認完了")
print("=" * 70)
