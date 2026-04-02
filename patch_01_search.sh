#!/bin/bash
# SCR-01: search/page.tsx への管理者エリア追加パッチ
# 適用先: ~/projects/machcore/apps/web/app/nc/search/page.tsx

TARGET=~/projects/machcore/apps/web/app/nc/search/page.tsx

# バックアップ
cp "$TARGET" "${TARGET}.bak_$(date +%Y%m%d_%H%M%S)"

python3 << 'PYEOF'
import re

target = '/home/karkyon/projects/machcore/apps/web/app/nc/search/page.tsx'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. import に useEffect追加（すでにあれば不要） ───
# useCallback はある。useState,useEffect,useCallback があることを確認済み
# 追加のimportは不要（既存のimportに含まれている）

# ─── 2. useRouter の後に isAdmin / company state 追加 ───
old_state = '''  const [selected, setSelected] = useState<number | null>(null);'''
new_state = '''  const [selected, setSelected]   = useState<number | null>(null);
  const [isAdmin,  setIsAdmin]    = useState(false);
  const [adminInfo, setAdminInfo] = useState<{ companyName?: string; logoPath?: string } | null>(null);'''

content = content.replace(old_state, new_state, 1)

# ─── 3. 最近のアクセス取得の useEffect の直後に admin判定 useEffect を追加 ───
old_recent_effect = '''  // 最近のアクセス取得
  useEffect(() => {
    ncApi.recent().then(r => setRecent(r.data)).catch(() => {});
  }, []);'''

new_recent_effect = '''  // 最近のアクセス取得
  useEffect(() => {
    ncApi.recent().then(r => setRecent(r.data)).catch(() => {});
  }, []);

  // 管理者ログイン状態チェック
  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    if (!token) return;
    setIsAdmin(true);
    fetch("/api/admin/company", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setAdminInfo(data); })
      .catch(() => {});
  }, []);'''

content = content.replace(old_recent_effect, new_recent_effect, 1)

# ─── 4. 右カラム section の閉じタグの直前に管理者エリアを挿入 ───
# </section> の直前（右カラム末尾）に管理者エリアを追加
# 右カラム最後の </section> を探して挿入
old_section_end = '''        </section>
      </div>
    </div>
  );
}'''

new_section_end = '''          {/* ── 管理者エリア（ADMIN限定） ── */}
          <div className="border-t border-slate-100 px-4 py-3 shrink-0">
            {isAdmin ? (
              <div className="space-y-2">
                {adminInfo?.logoPath && (
                  <img
                    src={`/api/${adminInfo.logoPath}`}
                    alt="company logo"
                    className="h-8 object-contain"
                  />
                )}
                <p className="text-[11px] font-bold text-slate-500 truncate">
                  {adminInfo?.companyName ?? "管理者メニュー"}
                </p>
                <div className="flex flex-col gap-1">
                  <a
                    href="/admin/users"
                    className="text-[11px] text-sky-600 hover:text-sky-700 flex items-center gap-1"
                  >
                    👥 ユーザ管理
                  </a>
                  <a
                    href="/admin/login"
                    className="text-[11px] text-slate-400 hover:text-slate-600 flex items-center gap-1"
                  >
                    ↩ 管理者ログアウト
                  </a>
                </div>
              </div>
            ) : (
              <a
                href="/admin/login"
                className="text-[10px] text-slate-300 hover:text-slate-500 transition-colors"
              >
                ⚙ 管理者
              </a>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}'''

content = content.replace(old_section_end, new_section_end, 1)

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ search/page.tsx パッチ適用完了")
PYEOF
