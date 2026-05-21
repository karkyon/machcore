#!/usr/bin/env python3
"""
page.tsx の AuthModal 呼び出し方法を修正
- onSuccess は () => void （token引数なし）
- useAuth から token を取得して API 呼び出し
"""
import os, sys

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = os.path.join(ROOT, "apps/web")
page = os.path.join(WEB, "app/page.tsx")

with open(page) as f:
    content = f.read()

# 1. useAuth import 追加
OLD_IMPORT = 'import { useState, useEffect, useCallback } from "react";'
NEW_IMPORT = 'import { useState, useEffect, useCallback } from "react";\nimport { useAuth } from "@/contexts/AuthContext";'
if 'useAuth' not in content:
    content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("OK: useAuth import 追加")
else:
    print("INFO: useAuth import 既に存在")

# 2. コンポーネント内に useAuth 追加（router の直後）
OLD_ROUTER = '  const router = useRouter();'
NEW_ROUTER = '  const router = useRouter();\n  const { token: authToken, login } = useAuth();'
if 'authToken' not in content:
    content = content.replace(OLD_ROUTER, NEW_ROUTER, 1)
    print("OK: useAuth() 呼び出し追加")
else:
    print("INFO: authToken 既に存在")

# 3. handleAuthSuccess を onSuccess: () => void に対応した形に書き換え
OLD_HANDLER = '''  const handleAuthSuccess = async (token: string) => {
    if (!collectingId) return;
    setShowAuthModal(false);
    try {
      const { system, id, programId } = collectingId;
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
      const res = await fetch(`${API_URL}/${system.toLowerCase()}/${programId}/setup-sheet-logs/${id}/collect`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("回収処理に失敗しました");
      await load();
    } catch (e: any) {
      setCollectErr(e.message ?? "エラーが発生しました");
    } finally {
      setCollectingId(null);
    }
  };'''
NEW_HANDLER = '''  const handleAuthSuccess = async () => {
    if (!collectingId) return;
    setShowAuthModal(false);
    // useAuth の login() が呼ばれた直後なので token は次の tick で取れる
    // setTimeout で 1tick 待ってから取得
    setTimeout(async () => {
      const tok = authToken ?? (typeof window !== "undefined" ? localStorage.getItem("work_token") : null);
      if (!tok) { setCollectErr("認証トークンが取得できませんでした"); setCollectingId(null); return; }
      try {
        const { system, id, programId } = collectingId!;
        const _API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";
        const res = await fetch(`${_API}/${system.toLowerCase()}/${programId}/setup-sheet-logs/${id}/collect`, {
          method: "PUT",
          headers: { "Authorization": `Bearer ${tok}` },
        });
        if (!res.ok) throw new Error("回収処理に失敗しました");
        await load();
      } catch (e: any) {
        setCollectErr(e.message ?? "エラーが発生しました");
      } finally {
        setCollectingId(null);
      }
    }, 100);
  };'''

if OLD_HANDLER in content:
    content = content.replace(OLD_HANDLER, NEW_HANDLER, 1)
    print("OK: handleAuthSuccess を引数なし版に書き換え")
else:
    print("WARN: handleAuthSuccess のアンカーが見つかりません")
    # 別パターンで探す
    if 'handleAuthSuccess = async (token: string)' in content:
        # 行単位で置換
        lines = content.split('\n')
        new_lines = []
        skip = False
        brace_depth = 0
        for line in lines:
            if 'handleAuthSuccess = async (token: string)' in line:
                skip = True
                brace_depth = 0
                new_lines.append('  const handleAuthSuccess = async () => {')
                new_lines.append('    if (!collectingId) return;')
                new_lines.append('    setShowAuthModal(false);')
                new_lines.append('    setTimeout(async () => {')
                new_lines.append('      const tok = authToken ?? (typeof window !== "undefined" ? localStorage.getItem("work_token") : null);')
                new_lines.append('      if (!tok) { setCollectErr("認証トークンが取得できませんでした"); setCollectingId(null); return; }')
                new_lines.append('      try {')
                new_lines.append('        const { system, id, programId } = collectingId!;')
                new_lines.append('        const _API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011/api";')
                new_lines.append('        const res = await fetch(`${_API}/${system.toLowerCase()}/${programId}/setup-sheet-logs/${id}/collect`, {')
                new_lines.append('          method: "PUT",')
                new_lines.append('          headers: { "Authorization": `Bearer ${tok}` },')
                new_lines.append('        });')
                new_lines.append('        if (!res.ok) throw new Error("回収処理に失敗しました");')
                new_lines.append('        await load();')
                new_lines.append('      } catch (e: any) {')
                new_lines.append('        setCollectErr(e.message ?? "エラーが発生しました");')
                new_lines.append('      } finally {')
                new_lines.append('        setCollectingId(null);')
                new_lines.append('      }')
                new_lines.append('    }, 100);')
                new_lines.append('  };')
                continue
            if skip:
                brace_depth += line.count('{') - line.count('}')
                if brace_depth <= 0 and '};' in line:
                    skip = False
                continue
            new_lines.append(line)
        content = '\n'.join(new_lines)
        print("OK: handleAuthSuccess を行単位で書き換え")

# 4. AuthModal の呼び出し部分を修正
# users prop と programId prop を正しく設定
# AuthModal の Props: isOpen, sessionType, ncProgramId?, mcProgramId?, onSuccess, onCancel
OLD_MODAL = '''      {showAuthModal && (
        <AuthModal
          users={users}
          sessionType="WORK_RECORD"
          programId={collectingId?.programId ?? 0}
          onSuccess={handleAuthSuccess}
          onCancel={() => { setShowAuthModal(false); setCollectingId(null); }}
        />
      )}'''
NEW_MODAL = '''      {showAuthModal && (
        <AuthModal
          isOpen={true}
          sessionType="MC_WORK_RECORD"
          mcProgramId={collectingId?.system === "MC" ? collectingId?.programId : undefined}
          ncProgramId={collectingId?.system === "NC" ? collectingId?.programId : undefined}
          onSuccess={handleAuthSuccess}
          onCancel={() => { setShowAuthModal(false); setCollectingId(null); }}
        />
      )}'''

if OLD_MODAL in content:
    content = content.replace(OLD_MODAL, NEW_MODAL, 1)
    print("OK: AuthModal 呼び出しを修正")
else:
    print("WARN: AuthModal 呼び出しアンカーが見つかりません。別パターンで試みます")
    # isOpen なしのパターンを isOpen ありに
    if 'sessionType="WORK_RECORD"' in content:
        content = content.replace('sessionType="WORK_RECORD"', 'sessionType="MC_WORK_RECORD"', 1)
    if 'users={users}' in content and '<AuthModal' in content:
        content = content.replace('          users={users}\n', '', 1)
    if 'programId={collectingId?.programId ?? 0}' in content:
        content = content.replace(
            'programId={collectingId?.programId ?? 0}',
            'mcProgramId={collectingId?.system === "MC" ? collectingId?.programId : undefined}\n          ncProgramId={collectingId?.system === "NC" ? collectingId?.programId : undefined}',
            1
        )
    if '<AuthModal\n' in content and 'isOpen' not in content:
        content = content.replace('<AuthModal\n', '<AuthModal\n          isOpen={true}\n', 1)
    print("OK: AuthModal 呼び出しを別パターンで修正")

# 5. users state / users fetch は不要になった（AuthModal 内部で usersApi を呼ぶ）
# ただし useState 宣言は残したまま（型エラー回避）

with open(page, 'w') as f:
    f.write(content)

print("\n✅ 完了")
print("\n次の手順:")
print("cd ~/projects/machcore/apps/web && npm run build")
print("cd ~/projects/machcore && pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web")
