#!/bin/bash
# SCR-02: /nc/[nc_id]/page.tsx PG→USB書き出しボタン AUTH連携パッチ
# 適用先: ~/projects/machcore/apps/web/app/nc/[nc_id]/page.tsx

TARGET=~/projects/machcore/apps/web/app/nc/\[nc_id\]/page.tsx

cp "$TARGET" "${TARGET}.bak_$(date +%Y%m%d_%H%M%S)"

python3 << 'PYEOF'
target = '/home/karkyon/projects/machcore/apps/web/app/nc/[nc_id]/page.tsx'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. downloadApi import 確認・追加 ───
if 'downloadApi' not in content:
    content = content.replace(
        'import { ncApi,',
        'import { ncApi, downloadApi,'
    )

# ─── 2. selected state の後に pendingUsb state 追加 ───
# useAuth から token を取得していることを前提
# operator, token, openAuth, logout, isAuthenticated を useAuth から取得済みと仮定

old_auth_hook = '''  const { operator, token, openAuth, logout, isAuthenticated } = useAuth();'''
new_auth_hook = '''  const { operator, token, openAuth, logout, isAuthenticated } = useAuth();
  const [pendingUsb, setPendingUsb] = useState(false);'''

if old_auth_hook in content:
    content = content.replace(old_auth_hook, new_auth_hook, 1)
else:
    # fallback: 別のパターンを試す
    old_auth_hook2 = '''  const { operator, openAuth, logout, isAuthenticated, token } = useAuth();'''
    new_auth_hook2 = '''  const { operator, openAuth, logout, isAuthenticated, token } = useAuth();
  const [pendingUsb, setPendingUsb] = useState(false);'''
    content = content.replace(old_auth_hook2, new_auth_hook2, 1)

# ─── 3. useEffect を追加（pendingUsb 監視 → 自動ダウンロード） ───
# 最初の useEffect の前に挿入
old_useeffect_marker = '''  useEffect(() => {'''
usb_effect = '''  // USB pending: 認証成功後に自動ダウンロード
  useEffect(() => {
    if (isAuthenticated && pendingUsb && token) {
      setPendingUsb(false);
      downloadApi.pgFile(ncId, token).catch(() => alert("PGファイルのダウンロードに失敗しました"));
    }
  }, [isAuthenticated, pendingUsb, token, ncId]);

  useEffect(() => {'''

content = content.replace(old_useeffect_marker, usb_effect, 1)

# ─── 4. PG→USB ボタンに onClick を追加 ───
old_usb_btn = '''            <button className="text-[11px] bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded font-bold transition-colors">
              PG → USB 書き出し
            </button>'''
new_usb_btn = '''            <button
              onClick={() => { setPendingUsb(true); openAuth("usbdownload"); }}
              className="text-[11px] bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded font-bold transition-colors"
            >
              PG → USB 書き出し
            </button>'''

content = content.replace(old_usb_btn, new_usb_btn, 1)

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ [nc_id]/page.tsx パッチ適用完了")
PYEOF
