import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def run(cmd, cwd=ROOT):
    print(f"--- {cmd.split()[0]} ---")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout[-3000:])
    if r.stderr.strip(): print("STDERR:", r.stderr[-2000:])
    return r.returncode

# ═══════════════════════════════════════════
# 1. users/page.tsx を完全書き直し
# ═══════════════════════════════════════════
USERS_PAGE = f"{ROOT}/apps/web/app/admin/users/page.tsx"

USERS_CONTENT = '''"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminUsersApi, AdminUserInfo } from "../../../lib/api";

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "管理者", OPERATOR: "作業者", VIEWER: "閲覧者",
};
const ROLE_COLOR: Record<string, string> = {
  ADMIN:    "bg-red-100 text-red-700",
  OPERATOR: "bg-sky-100 text-sky-700",
  VIEWER:   "bg-slate-100 text-slate-600",
};

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];

type DialogMode = "create" | "edit" | "password" | null;
type AdminUser  = { id: number; name: string; role: string };

export default function AdminUsersPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [adminUser,  setAdminUser]  = useState<AdminUser | null>(null);
  const [users,      setUsers]      = useState<AdminUserInfo[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [editTarget, setEditTarget] = useState<AdminUserInfo | null>(null);
  // フィルタ
  const [fltCode,   setFltCode]   = useState("");
  const [fltName,   setFltName]   = useState("");
  const [fltRole,   setFltRole]   = useState("");
  const [fltStatus, setFltStatus] = useState("");
  // フォーム
  const [fCode,  setFCode]  = useState("");
  const [fName,  setFName]  = useState("");
  const [fKana,  setFKana]  = useState("");
  const [fPw,    setFPw]    = useState("");
  const [fPw2,   setFPw2]   = useState("");
  const [fRole,  setFRole]  = useState<"VIEWER"|"OPERATOR"|"ADMIN">("OPERATOR");
  const [saving, setSaving] = useState(false);
  const [fError, setFError] = useState<string | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token || !user) { router.replace("/admin/login"); return; }
    setAdminUser(JSON.parse(user));
    fetchUsers(token);
  }, [router]);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";

  const filteredUsers = users.filter(u => {
    if (fltCode   && !u.employeeCode?.includes(fltCode)) return false;
    if (fltName   && !u.name?.includes(fltName))          return false;
    if (fltRole   && u.role !== fltRole)                  return false;
    if (fltStatus === "active"   && !u.isActive)          return false;
    if (fltStatus === "inactive" &&  u.isActive)          return false;
    return true;
  });

  const fetchUsers = useCallback(async (token?: string) => {
    setLoading(true);
    try {
      const res = await adminUsersApi.list(token ?? getToken());
      setUsers(res.data);
    } catch { showToast("ユーザ一覧の取得に失敗しました", false); }
    finally { setLoading(false); }
  }, []);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok }); setTimeout(() => setToast(null), 3000);
  };

  const handleLogout = () => {
    sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user");
    router.push("/admin/login");
  };

  const openCreate = () => {
    setFCode(""); setFName(""); setFKana(""); setFPw(""); setFPw2("");
    setFRole("OPERATOR"); setFError(null); setEditTarget(null); setDialogMode("create");
  };
  const openEdit = (u: AdminUserInfo) => {
    setFName(u.name); setFKana(u.nameKana ?? ""); setFRole(u.role);
    setFError(null); setEditTarget(u); setDialogMode("edit");
  };
  const openPassword = (u: AdminUserInfo) => {
    setFPw(""); setFPw2(""); setFError(null); setEditTarget(u); setDialogMode("password");
  };
  const closeDialog = () => { setDialogMode(null); setEditTarget(null); };

  const handleCreate = async () => {
    if (!fCode || !fName || !fPw) { setFError("必須項目を入力してください"); return; }
    if (fPw !== fPw2)             { setFError("パスワードが一致しません"); return; }
    if (fPw.length < 4)           { setFError("パスワードは4文字以上"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.create(
        { employee_code: fCode, name: fName, name_kana: fKana || undefined, password: fPw, role: fRole },
        getToken()
      );
      showToast("ユーザを作成しました", true); closeDialog(); fetchUsers();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "作成に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handleUpdate = async () => {
    if (!editTarget || !fName) { setFError("名前は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.update(editTarget.id, { name: fName, name_kana: fKana || undefined, role: fRole }, getToken());
      showToast("ユーザ情報を更新しました", true); closeDialog(); fetchUsers();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "更新に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handlePassword = async () => {
    if (!editTarget) return;
    if (!fPw)           { setFError("パスワードを入力してください"); return; }
    if (fPw !== fPw2)   { setFError("パスワードが一致しません"); return; }
    if (fPw.length < 4) { setFError("パスワードは4文字以上"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.resetPassword(editTarget.id, fPw, getToken());
      showToast("パスワードを変更しました", true); closeDialog();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "変更に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handleToggleActive = async (u: AdminUserInfo) => {
    const action = u.isActive ? "無効化" : "有効化";
    if (!confirm(`${u.name} を${action}しますか？`)) return;
    try {
      if (u.isActive) { await adminUsersApi.deactivate(u.id, getToken()); }
      else { await adminUsersApi.update(u.id, { is_active: true }, getToken()); }
      showToast(`${u.name} を${action}しました`, true); fetchUsers();
    } catch { showToast(`${action}に失敗しました`, false); }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-slate-400">{adminUser?.name}（管理者）</span>
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && <div className={`fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-bold z-50 ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="flex flex-1 min-h-0">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-slate-800">ユーザ一覧</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors">＋ 新規ユーザ追加</button>
          </div>

          {/* フィルタ */}
          <div className="flex flex-wrap gap-2 mb-4 bg-white p-3 rounded-xl border border-slate-200">
            <input type="text" value={fltCode} onChange={e => setFltCode(e.target.value)} placeholder="社員コードでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-44" />
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder="氏名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-44" />
            <select value={fltRole} onChange={e => setFltRole(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">ロール: すべて</option>
              <option value="ADMIN">管理者</option>
              <option value="OPERATOR">作業者</option>
              <option value="VIEWER">閲覧者</option>
            </select>
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option>
              <option value="active">有効のみ</option>
              <option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filteredUsers.length}/{users.length}件</span>
          </div>

          {loading ? <div className="text-center py-20 text-slate-400">読み込み中...</div> : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3 text-left">ID</th>
                    <th className="px-5 py-3 text-left">社員コード</th>
                    <th className="px-5 py-3 text-left">氏名</th>
                    <th className="px-5 py-3 text-left">カナ</th>
                    <th className="px-5 py-3 text-left">ロール</th>
                    <th className="px-5 py-3 text-left">状態</th>
                    <th className="px-5 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredUsers.map(u => (
                    <tr key={u.id} className={`hover:bg-slate-50 ${!u.isActive ? "opacity-40" : ""}`}>
                      <td className="px-5 py-3 text-slate-400">{u.id}</td>
                      <td className="px-5 py-3 font-mono text-slate-700">{u.employeeCode}</td>
                      <td className="px-5 py-3 font-medium text-slate-800">{u.name}</td>
                      <td className="px-5 py-3 text-slate-500">{u.nameKana ?? "—"}</td>
                      <td className="px-5 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${ROLE_COLOR[u.role]}`}>
                          {ROLE_LABEL[u.role] ?? u.role}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className={`text-xs font-bold ${u.isActive ? "text-green-600" : "text-slate-400"}`}>
                          {u.isActive ? "有効" : "無効"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right space-x-2">
                        <button onClick={() => openEdit(u)} className="text-xs text-sky-600 hover:underline">編集</button>
                        <button onClick={() => openPassword(u)} className="text-xs text-amber-600 hover:underline">PW変更</button>
                        <button onClick={() => handleToggleActive(u)}
                          className={`text-xs hover:underline ${u.isActive ? "text-red-500" : "text-green-600"}`}>
                          {u.isActive ? "無効化" : "有効化"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredUsers.length === 0 && <p className="text-center py-12 text-slate-400">該当するユーザがありません</p>}
            </div>
          )}
        </main>
      </div>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
            <div className="bg-slate-800 px-6 py-4 rounded-t-2xl">
              <h2 className="text-white font-bold text-base">
                {dialogMode === "create"   && "新規ユーザ追加"}
                {dialogMode === "edit"     && `ユーザ編集: ${editTarget?.name}`}
                {dialogMode === "password" && `PW変更: ${editTarget?.name}`}
              </h2>
            </div>
            <div className="p-6 space-y-4">
              {dialogMode === "create" && (<>
                <Field label="社員コード *" value={fCode} onChange={setFCode} placeholder="例: EMP001" />
                <Field label="氏名 *"       value={fName} onChange={setFName} placeholder="山田 太郎" />
                <Field label="氏名（カナ）" value={fKana} onChange={setFKana} placeholder="ヤマダ タロウ" />
                <SelectField label="ロール" value={fRole} onChange={v => setFRole(v as any)} />
                <Field label="パスワード *"     value={fPw}  onChange={setFPw}  type="password" />
                <Field label="パスワード確認 *" value={fPw2} onChange={setFPw2} type="password" />
              </>)}
              {dialogMode === "edit" && (<>
                <Field label="氏名 *"       value={fName} onChange={setFName} />
                <Field label="氏名（カナ）" value={fKana} onChange={setFKana} />
                <SelectField label="ロール" value={fRole} onChange={v => setFRole(v as any)} />
              </>)}
              {dialogMode === "password" && (<>
                <Field label="新しいパスワード *"     value={fPw}  onChange={setFPw}  type="password" />
                <Field label="新しいパスワード確認 *" value={fPw2} onChange={setFPw2} type="password" />
              </>)}
              {fError && <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-2">{fError}</p>}
              <div className="flex gap-3 pt-2">
                <button onClick={closeDialog} className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50">キャンセル</button>
                <button onClick={dialogMode === "create" ? handleCreate : dialogMode === "edit" ? handleUpdate : handlePassword}
                  disabled={saving}
                  className="flex-1 px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold hover:bg-sky-700 disabled:opacity-40">
                  {saving ? "処理中..." : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-bold text-slate-500 mb-1">{label}</label>
      <input type={type} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
    </div>
  );
}

function SelectField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void; }) {
  return (
    <div>
      <label className="block text-xs font-bold text-slate-500 mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 bg-white">
        <option value="OPERATOR">作業者</option>
        <option value="VIEWER">閲覧者</option>
        <option value="ADMIN">管理者</option>
      </select>
    </div>
  );
}
'''

write(USERS_PAGE, USERS_CONTENT)
print("OK: admin/users/page.tsx 完全書き直し")

# ═══════════════════════════════════════════
# 2. mc/timecards/page.tsx — 「←管理パネル」ボタン追加
# ═══════════════════════════════════════════
TC_PAGE = f"{ROOT}/apps/web/app/mc/timecards/page.tsx"

OLD_TC_HEADER = '''        <button onClick={() => router.push("/mc")}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium transition-colors">
          ← ダッシュボード
        </button>'''

NEW_TC_HEADER = '''        <button onClick={() => router.push("/mc")}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium transition-colors">
          ← ダッシュボード
        </button>
        <button onClick={() => router.push("/admin/machines")}
          className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 border border-slate-500 rounded-lg text-xs font-medium transition-colors">
          ⚙ 管理パネル
        </button>'''

c = read(TC_PAGE)
if OLD_TC_HEADER in c:
    write(TC_PAGE, c.replace(OLD_TC_HEADER, NEW_TC_HEADER, 1))
    print("OK: mc/timecards/page.tsx 管理パネルボタン追加")
else:
    print("WARN: mc/timecards/page.tsx 管理パネルボタン — パターン不一致")

# ═══════════════════════════════════════════
# ビルド & デプロイ
# ═══════════════════════════════════════════
rc = run("npm run build", cwd=f"{ROOT}/apps/web")
if rc != 0:
    print("BUILD FAILED — abort"); sys.exit(1)

run("npx tsc --noEmit", cwd=f"{ROOT}/apps/api")
run("pm2 restart machcore-web && pm2 save && pm2 list")
run('git add -A && git commit -m "fix: users/page.tsx完全書き直しライトモード+フィルタ+TC画面に管理パネルボタン v64" && git push')
print("DONE")
