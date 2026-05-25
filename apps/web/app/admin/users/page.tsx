"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminUsersApi, AdminUserInfo } from "@/lib/api";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",    label: "ユーザ管理",       icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines", label: "機械管理",         icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",   label: "機械タイムカード", icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings", label: "システム設定",     icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/raw",      label: "RAWデータ",        icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
];
const ROLE_COLOR: Record<string, string> = {
  ADMIN: "bg-red-100 text-red-700", OPERATOR: "bg-sky-100 text-sky-700", VIEWER: "bg-slate-100 text-slate-600",
};
const ROLE_LABEL: Record<string, string> = { ADMIN: "管理者", OPERATOR: "作業者", VIEWER: "閲覧者" };

type SortKey = "id" | "employeeCode" | "name" | "nameKana" | "role" | "isActive";
type SortDir = "asc" | "desc";

export default function AdminUsersPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [users,      setUsers]      = useState<AdminUserInfo[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<"create"|"edit"|"password"|null>(null);
  const [editTarget, setEditTarget] = useState<AdminUserInfo | null>(null);
  const [fName2,  setFName2]  = useState(""); const [fKana2, setFKana2] = useState("");
  const [fRole2,  setFRole2]  = useState(""); const [fActive2, setFActive2] = useState("");
  const [fPW,     setFPW]     = useState("");
  const [fError,  setFError]  = useState<string|null>(null);
  const [saving,  setSaving]  = useState(false);
  const [fltCode,   setFltCode]   = useState("");
  const [fltName,   setFltName]   = useState("");
  const [fltRole,   setFltRole]   = useState("");
  const [fltStatus, setFltStatus] = useState("");
  const [sortKey,   setSortKey]   = useState<SortKey>("id");
  const [sortDir,   setSortDir]   = useState<SortDir>("asc");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };
  const handleLogout = () => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); };

  const fetchUsers = useCallback(async () => {
    const token = getToken();
    if (!token) { router.replace("/admin/login"); return; }
    setLoading(true);
    try {
      const r = await adminUsersApi.list(token);
      setUsers((r as any).data ?? r);
    } catch { showToast("取得失敗", false); }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    const user  = sessionStorage.getItem("admin_user");
    if (!token || !user) { router.replace("/admin/login"); return; }
    fetchUsers();
  }, [router, fetchUsers]);

  const filteredUsers = users.filter(u => {
    if (fltCode   && !u.employeeCode.includes(fltCode)) return false;
    if (fltName   && !u.name.includes(fltName))          return false;
    if (fltRole   && u.role !== fltRole)                  return false;
    if (fltStatus === "active"   && !u.isActive)          return false;
    if (fltStatus === "inactive" &&  u.isActive)          return false;
    return true;
  }).sort((a, b) => {
    let va: any = a[sortKey], vb: any = b[sortKey];
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return sortDir === "asc" ? -1 : 1;
    if (va > vb) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };
  const SortIcon = ({ k }: { k: SortKey }) => (
    <span className="ml-1 opacity-50">{sortKey === k ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}</span>
  );

  const openCreate = () => { setFName2(""); setFKana2(""); setFRole2("OPERATOR"); setFActive2(""); setFPW(""); setFError(null); setEditTarget(null); setDialogMode("create"); };
  const openEdit   = (u: AdminUserInfo) => { setFName2(u.name); setFKana2(u.nameKana ?? ""); setFRole2(u.role); setFActive2(u.isActive ? "active" : "inactive"); setFPW(""); setFError(null); setEditTarget(u); setDialogMode("edit"); };
  const openPassword = (u: AdminUserInfo) => { setFPW(""); setFError(null); setEditTarget(u); setDialogMode("password"); };

  const handleSave = async () => {
    const token = getToken();
    if (!fName2) { setFError("氏名は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      if (dialogMode === "create") {
        if (!fPW) { setFError("パスワードは必須です"); setSaving(false); return; }
        await adminUsersApi.create({ employee_code: `STAFF${Date.now()}`, name: fName2, name_kana: fKana2 || undefined, password: fPW, role: fRole2 as any }, token);
        showToast("ユーザを登録しました", true);
      } else if (dialogMode === "edit" && editTarget) {
        await adminUsersApi.update(editTarget.id, { name: fName2, name_kana: fKana2 || undefined, role: fRole2 as any, is_active: fActive2 !== "inactive" }, token);
        showToast("更新しました", true);
      }
      setDialogMode(null); fetchUsers();
    } catch { setFError("通信エラー"); }
    finally { setSaving(false); }
  };

  const handlePW = async () => {
    if (!editTarget || !fPW) { setFError("パスワードを入力してください"); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.resetPassword(editTarget.id, fPW, getToken());
      showToast("パスワードを変更しました", true); setDialogMode(null);
    } catch { setFError("変更失敗"); }
    finally { setSaving(false); }
  };

  const handleToggleActive = async (u: AdminUserInfo) => {
    try {
      await adminUsersApi.update(u.id, { is_active: !u.isActive }, getToken());
      showToast(u.isActive ? "無効化しました" : "有効化しました", true); fetchUsers();
    } catch { showToast("変更失敗", false); }
  };

  // ユーザのシステム区分を推定（ADMIN001はADMIN、それ以外はemployeeCodeから）
  const getSystemBadge = (u: AdminUserInfo) => {
    if (u.role === "ADMIN") return null;
    // employeeCodeでMC/NCを判別 (実際はDBにないのでNCをデフォルト)
    return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-700">NC</span>;
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded transition-colors">← ダッシュボード</a>
          <button onClick={handleLogout} className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded transition-colors">ログアウト</button>
        </div>
      </header>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon}/></svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">ユーザ一覧</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg">＋ 新規ユーザ追加</button>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <input type="text" value={fltCode} onChange={e => setFltCode(e.target.value)} placeholder="社員コードでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-40" />
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder="氏名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltRole} onChange={e => setFltRole(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">ロール: すべて</option>
              <option value="ADMIN">管理者</option><option value="OPERATOR">作業者</option><option value="VIEWER">閲覧者</option>
            </select>
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option><option value="active">有効のみ</option><option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filteredUsers.length}/{users.length}件</span>
          </div>

          {loading ? (
            <div className="text-center py-20 text-slate-400">読み込み中...</div>
          ) : (
            <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
              <div className="shrink-0 border-b border-slate-200">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-28"/><col className="w-28"/><col className="w-24"/>
                    <col className="w-24"/><col className="w-14"/><col className="w-52"/>
                  </colgroup>
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("id")}>ID<SortIcon k="id"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("employeeCode")}>社員コード<SortIcon k="employeeCode"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("name")}>氏名<SortIcon k="name"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("nameKana")}>カナ<SortIcon k="nameKana"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("role")}>ロール<SortIcon k="role"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("isActive")}>状態<SortIcon k="isActive"/></th>
                      <th className="px-3 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-28"/><col className="w-28"/><col className="w-24"/>
                    <col className="w-24"/><col className="w-14"/><col className="w-52"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filteredUsers.map(u => (
                      <tr key={u.id} className={`hover:bg-slate-50 ${!u.isActive ? "opacity-40" : ""}`}>
                        <td className="px-3 py-2.5 text-slate-400 text-xs">{u.id}</td>
                        <td className="px-3 py-2.5 font-mono text-slate-700 text-xs">{u.employeeCode}</td>
                        <td className="px-3 py-2.5 text-slate-800 text-xs font-medium">
                          <div className="flex items-center gap-1">
                            <span className="truncate">{u.name}</span>
                            {getSystemBadge(u)}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs truncate">{u.nameKana ?? "—"}</td>
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold ${ROLE_COLOR[u.role]}`}>{ROLE_LABEL[u.role] ?? u.role}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`text-xs font-bold ${u.isActive ? "text-green-600" : "text-slate-400"}`}>{u.isActive ? "有効" : "無効"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-1 flex-nowrap">
                            <button onClick={() => openEdit(u)} className="px-2 py-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded font-bold whitespace-nowrap">編集</button>
                            <button onClick={() => openPassword(u)} className="px-2 py-1 text-xs bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded font-bold whitespace-nowrap">PW変更</button>
                            <button onClick={() => handleToggleActive(u)} className={`px-2 py-1 text-xs border rounded font-bold whitespace-nowrap ${u.isActive ? "bg-red-50 hover:bg-red-100 text-red-600 border-red-200" : "bg-green-50 hover:bg-green-100 text-green-600 border-green-200"}`}>
                              {u.isActive ? "無効化" : "有効化"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredUsers.length === 0 && <tr><td colSpan={7} className="text-center py-12 text-slate-400">該当するユーザがありません</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ダイアログ */}
      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">
              {dialogMode === "create" ? "新規ユーザ追加" : dialogMode === "edit" ? "ユーザ編集" : "パスワード変更"}
            </h2>
            {fError && <div className="text-red-500 text-xs mb-3">{fError}</div>}
            {dialogMode !== "password" ? (
              <div className="space-y-3">
                <div><label className="text-xs font-bold text-slate-500 block mb-1">氏名 *</label>
                  <input type="text" value={fName2} onChange={e => setFName2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">カナ</label>
                  <input type="text" value={fKana2} onChange={e => setFKana2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">ロール</label>
                  <select value={fRole2} onChange={e => setFRole2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                    <option value="OPERATOR">作業者</option><option value="VIEWER">閲覧者</option><option value="ADMIN">管理者</option>
                  </select></div>
                {dialogMode === "edit" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">状態</label>
                    <select value={fActive2} onChange={e => setFActive2(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                      <option value="active">有効</option><option value="inactive">無効</option>
                    </select></div>
                )}
                {dialogMode === "create" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">パスワード *</label>
                    <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                )}
              </div>
            ) : (
              <div><label className="text-xs font-bold text-slate-500 block mb-1">新しいパスワード</label>
                <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogMode(null)} className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">キャンセル</button>
              <button onClick={dialogMode === "password" ? handlePW : handleSave} disabled={saving}
                className="px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold disabled:opacity-50">
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
