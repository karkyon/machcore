#!/usr/bin/env python3
"""
TypeScriptエラー3件を一括修正するスクリプト
実行: python3 fix_errors.py <プロジェクトルート>

修正内容:
  1. UserManagement.tsx:17  - 未使用の StatusBadge import を削除
  2. UserManagement.tsx:655 - variant="primary" → variant="info" に変更
  3. api.ts                 - userAPI に toggleUserStatus を追加
"""

import sys
import re
import os

PROJECT_ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/dump-tracker")

FILES = {
    "user_mgmt": os.path.join(PROJECT_ROOT, "frontend/cms/src/pages/UserManagement.tsx"),
    "api":       os.path.join(PROJECT_ROOT, "frontend/cms/src/utils/api.ts"),
}

def fix_file(path, fixes):
    """fixes: list of (old_str, new_str, description)"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    for old, new, desc in fixes:
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  ✅ {desc}")
        else:
            print(f"  ⚠️  対象文字列が見つかりません（既に修正済み？）: {desc}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ─────────────────────────────────────────────────────────────────────────────
# Fix 1 & 2: UserManagement.tsx
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[1/3] {FILES['user_mgmt']}")

um_fixes = [
    # Fix 1: StatusBadge は未使用なので import から除去
    (
        "import Table, { StatusBadge, ActionButtons } from '../components/common/Table';",
        "import Table, { ActionButtons } from '../components/common/Table';",
        "未使用の StatusBadge を import から削除"
    ),
    # Fix 2: 'primary' は ConfirmDialog の variant に存在しない → 'info' に変更
    (
        "variant={toggleTargetUser?.isActive ? 'danger' : 'primary'}",
        "variant={toggleTargetUser?.isActive ? 'danger' : 'info'}",
        "variant='primary' → 'info' に変更（Modal.tsx の型定義に合わせる）"
    ),
]

fix_file(FILES["user_mgmt"], um_fixes)

# ─────────────────────────────────────────────────────────────────────────────
# Fix 3: api.ts — userAPI に toggleUserStatus を追加
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[2/3] {FILES['api']}")

TOGGLE_METHOD = """
  /**
   * ユーザーステータス切替 (有効 ⇔ 無効)
   * バックエンド: PATCH /users/:id/toggle-status
   * 権限: ADMIN のみ
   */
  async toggleUserStatus(id: string): Promise<ApiResponse<User>> {
    console.log('[User API] toggleUserStatus attempt', { id });
    return apiClient.patch(`/users/${id}/toggle-status`);
  }"""

api_fixes = [
    (
        # deleteUser の直後に toggleUserStatus を挿入
        "  /**\n   * ユーザー削除\n   */\n  async deleteUser(id: string): Promise<ApiResponse<void>> {\n    return apiClient.delete(`/users/${id}`);\n  }\n};",
        "  /**\n   * ユーザー削除\n   */\n  async deleteUser(id: string): Promise<ApiResponse<void>> {\n    return apiClient.delete(`/users/${id}`);\n  },"
        + TOGGLE_METHOD + "\n};",
        "userAPI に toggleUserStatus を追加"
    ),
]

fix_file(FILES["api"], api_fixes)

# ─────────────────────────────────────────────────────────────────────────────
# 確認
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/3] 修正内容を確認中...")

with open(FILES["user_mgmt"], "r") as f:
    um = f.read()
assert "StatusBadge" not in um,         "❌ StatusBadge がまだ残っています"
assert "'info'" in um,                  "❌ variant='info' が見つかりません"
print("  ✅ UserManagement.tsx: 問題なし")

with open(FILES["api"], "r") as f:
    api = f.read()
assert "toggleUserStatus" in api,       "❌ toggleUserStatus が api.ts にありません"
print("  ✅ api.ts: 問題なし")

print("\n🎉 全修正完了！次のコマンドで確認してください:")
print("  cd frontend/cms && npx tsc --noEmit")
