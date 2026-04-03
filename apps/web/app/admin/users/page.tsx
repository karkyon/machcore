"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { adminUsersApi, AdminUserInfo } from "../../../lib/api";

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "管理者", OPERATOR: "作業者", VIEWER: "閲覧者",
};
const ROLE_COLOR: Record<string, string> = {
  ADMIN:    "bg-red-100 text-red-700",
  OPERATOR: "bg-sky-100 text-sky-700",
  VIEWER:   "bg-slate-100 text-slate-600",
};

type DialogMode = "create" | "edit" | "password" | null;
type AdminUser  = { id: number; name: string; role: string };

export default function AdminUsersPage() {
  const router = useRouter();
  const [adminUser,   setAdminUser]   = useState<AdminUser | null>(null);
  const [users,       setUsers]       = useState<AdminUserInfo[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [toast,       setToast]       = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode,  setDialogMode]  = useState<DialogMode>(null);
  const [editTarget,  setEditTarget]  = useState<AdminUserInfo | null>(null);
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

  const fetchUsers = useCallback(async (token?: string) => {
    setLoading(true);
    try {
      const res = await adminUsersApi.list(token ?? getToken());
      setUsers(res.data);
    } catch {
      showToast("ユーザ一覧の取得に失敗しました", false);
    } finally {
      setLoading(false);
    }
  }, []);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const handleLogout = () => {
    sessionStorage.removeItem("admin_token");
    sessionStorage.removeItem("admin_user");
    router.push("/admin/login");
  };

  const openCreate = () => {
    setFCode(""); setFName(""); setFKana(""); setFPw(""); setFPw2("");
    setFRole("OPERATOR"); setFError(null);
    setEditTarget(null); setDialogMode("create");
  };
  const openEdit = (u: AdminUserInfo) => {
    setFName(u.name); setFKana(u.nameKana ?? ""); setFRole(u.role);
    setFError(null); setEditTarget(u); setDialogMode("edit");
  };
  const openPassword = (u: AdminUserInfo) => {
    setFPw(""); setFPw2(""); setFError(null);
    setEditTarget(u); setDialogMode("password");
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
      showToast("ユーザを作成しました", true);
      closeDialog(); fetchUsers();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "作成に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handleUpdate = async () => {
    if (!editTarget || !fName) { setFError("名前は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.update(
        editTarget.id,
        { name: fName, name_kana: fKana || undefined, role: fRole },
        getToken()
      );
      showToast("ユーザ情報を更新しました", true);
      closeDialog(); fetchUsers();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "更新に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handlePassword = async () => {
    if (!editTarget)      return;
    if (!fPw)             { setFError("パスワードを入力してください"); return; }
    if (fPw !== fPw2)     { setFError("パスワードが一致しません"); return; }
    if (fPw.length < 4)   { setFError("パスワードは4文字以上"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.resetPassword(editTarget.id, fPw, getToken());
      showToast("パスワードを変更しました", true);
      closeDialog();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? "変更に失敗しました";
      setFError(Array.isArray(msg) ? msg.join(", ") : msg);
    } finally { setSaving(false); }
  };

  const handleToggleActive = async (u: AdminUserInfo) => {
    const action = u.isActive ? "無効化" : "有効化";
    if (!confirm(`${u.name} を${action}しますか？`)) return;
    try {
      if (u.isActive) {
        await adminUsersApi.deactivate(u.id, getToken());
      } else {
        await adminUsersApi.update(u.id, { is_active: true }, getToken());
      }
      showToast(`${u.name} を${action}しました`, true);
      fetchUsers();
    } catch {
      showToast(`${action}に失敗しました`, false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shadow">
        <div className="flex items-center gap-3">
          <span className="font-bold text-lg">MachCore</span>
          <span className="text-slate-400 text-sm">/ 管理者ユーザ管理</span>
        </div>
        <div className="flex items-center gap-4">
          {adminUser && <span className="text-slate-300 text-sm">{adminUser.name}</span>}
          <button onClick={() => router.push("/admin/settings")}
            className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg transition-colors">
            ⚙ 設定
          </button>
          <button onClick={handleLogout}
            className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg transition-colors">
            ログアウト
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-slate-700">ユーザ一覧</h1>
          <button onClick={openCreate}
            className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors">
            ＋ 新規ユーザ追加
          </button>
        </div>

        {loading ? (
          <div className="text-center py-20 text-slate-400">読み込み中...</div>
        ) : (
          <div className="bg-white rounded-xl shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
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
                {users.map(u => (
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
            {users.length === 0 && (
              <p className="text-center py-12 text-slate-400">ユーザが存在しません</p>
            )}
          </div>
        )}
      </main>

      {toast && (
        <div className={`fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-bold
                         ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}

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
                <Field label="パスワード *"    value={fPw}  onChange={setFPw}  type="password" />
                <Field label="パスワード確認 *" value={fPw2} onChange={setFPw2} type="password" />
              </>)}
              {dialogMode === "edit" && (<>
                <Field label="氏名 *"       value={fName} onChange={setFName} />
                <Field label="氏名（カナ）" value={fKana} onChange={setFKana} />
                <SelectField label="ロール" value={fRole} onChange={v => setFRole(v as any)} />
              </>)}
              {dialogMode === "password" && (<>
                <Field label="新しいパスワード *"    value={fPw}  onChange={setFPw}  type="password" />
                <Field label="新しいパスワード確認 *" value={fPw2} onChange={setFPw2} type="password" />
              </>)}
              {fError && (
                <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-2">{fError}</p>
              )}
              <div className="flex gap-3 pt-2">
                <button onClick={closeDialog}
                  className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50">
                  キャンセル
                </button>
                <button
                  onClick={dialogMode === "create" ? handleCreate : dialogMode === "edit" ? handleUpdate : handlePassword}
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

function SelectField({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void;
}) {
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
