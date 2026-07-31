"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { adminUsersApi, AdminUserInfo } from "@/lib/api";
import { useLanguage } from "@/lib/i18n/LanguageContext";

const ROLE_COLOR: Record<string, string> = {
  ADMIN: "bg-red-100 text-red-700", OPERATOR: "bg-sky-100 text-sky-700", VIEWER: "bg-slate-100 text-slate-600",
};
const ROLE_KEY: Record<string, string> = { ADMIN: "adminUsers.roleAdmin", OPERATOR: "adminUsers.roleOperator", VIEWER: "adminUsers.roleViewer" };
const SYS_COLOR: Record<string, string> = {
  NC: "bg-teal-100 text-teal-700", MC: "bg-purple-100 text-purple-700", BOTH: "bg-amber-100 text-amber-700",
};

type SortKey = "id" | "employeeCode" | "name" | "nameKana" | "role" | "isActive" | "systemType";
type SortDir = "asc" | "desc";

export default function AdminUsersPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const { t } = useLanguage();
  const [users,      setUsers]      = useState<AdminUserInfo[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<"create"|"edit"|"password"|null>(null);
  const [editTarget, setEditTarget] = useState<AdminUserInfo | null>(null);
  const [fName2,  setFName2]  = useState("");
  const [fKana2,  setFKana2]  = useState("");
  const [fRole2,  setFRole2]  = useState("");
  const [fActive2, setFActive2] = useState("");
  const [fSys2,   setFSys2]   = useState("NC");
  const [fCanApprove2, setFCanApprove2] = useState(false); // [v094] 承認資格
  const [fPW,     setFPW]     = useState("");
  const [fError,  setFError]  = useState<string|null>(null);
  const [saving,  setSaving]  = useState(false);
  const [fltCode,   setFltCode]   = useState("");
  const [fltName,   setFltName]   = useState("");
  const [fltRole,   setFltRole]   = useState("");
  const [fltStatus, setFltStatus] = useState("");
  const [fltSys,    setFltSys]    = useState("");
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
    } catch { showToast(t("adminUsers.fetchFailed", "取得失敗"), false); }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    if (!token) { router.replace("/admin/login"); return; }
    fetchUsers();
  }, [router, fetchUsers]);

  const filteredUsers = users.filter(u => {
    if (fltCode   && !u.employeeCode.includes(fltCode)) return false;
    if (fltName   && !u.name.includes(fltName))          return false;
    if (fltRole   && u.role !== fltRole)                  return false;
    if (fltStatus === "active"   && !u.isActive)          return false;
    if (fltStatus === "inactive" &&  u.isActive)          return false;
    if (fltSys    && u.systemType !== fltSys)             return false;
    return true;
  }).sort((a, b) => {
    let va: any = (a as any)[sortKey] ?? "";
    let vb: any = (b as any)[sortKey] ?? "";
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

  const openCreate = () => {
    setFName2(""); setFKana2(""); setFRole2("OPERATOR"); setFActive2(""); setFSys2("NC"); setFCanApprove2(false); setFPW(""); setFError(null); setEditTarget(null); setDialogMode("create");
  };
  const openEdit = (u: AdminUserInfo) => {
    setFName2(u.name); setFKana2(u.nameKana ?? ""); setFRole2(u.role);
    setFActive2(u.isActive ? "active" : "inactive"); setFSys2(u.systemType ?? "NC");
    setFCanApprove2(u.canApprove ?? false);
    setFPW(""); setFError(null); setEditTarget(u); setDialogMode("edit");
  };
  const openPassword = (u: AdminUserInfo) => { setFPW(""); setFError(null); setEditTarget(u); setDialogMode("password"); };

  const handleSave = async () => {
    const token = getToken();
    if (!fName2) { setFError(t("adminUsers.nameRequired", "氏名は必須です")); return; }
    setSaving(true); setFError(null);
    try {
      if (dialogMode === "create") {
        if (!fPW) { setFError(t("adminUsers.passwordRequired", "パスワードは必須です")); setSaving(false); return; }
        await adminUsersApi.create({ employee_code: `STAFF${Date.now()}`, name: fName2, name_kana: fKana2 || undefined, password: fPW, role: fRole2 as any, can_approve: fCanApprove2 }, token);
        showToast(t("adminUsers.userCreated", "ユーザを登録しました"), true);
      } else if (dialogMode === "edit" && editTarget) {
        await adminUsersApi.update(editTarget.id, { name: fName2, name_kana: fKana2 || undefined, role: fRole2 as any, is_active: fActive2 !== "inactive", system_type: fSys2 as any, can_approve: fCanApprove2 }, token);
        showToast(t("adminUsers.updated", "更新しました"), true);
      }
      setDialogMode(null); fetchUsers();
    } catch { setFError(t("adminUsers.communicationError", "通信エラー")); }
    finally { setSaving(false); }
  };

  const handlePW = async () => {
    if (!editTarget || !fPW) { setFError(t("adminUsers.enterPassword", "パスワードを入力してください")); return; }
    setSaving(true); setFError(null);
    try {
      await adminUsersApi.resetPassword(editTarget.id, fPW, getToken());
      showToast(t("adminUsers.passwordChanged", "パスワードを変更しました"), true); setDialogMode(null);
    } catch { setFError(t("adminUsers.changeFailed", "変更失敗")); }
    finally { setSaving(false); }
  };

  const handleToggleActive = async (u: AdminUserInfo) => {
    try {
      await adminUsersApi.update(u.id, { is_active: !u.isActive }, getToken());
      showToast(u.isActive ? t("adminUsers.deactivated","無効化しました") : t("adminUsers.activated","有効化しました"), true); fetchUsers();
    } catch { showToast(t("adminUsers.changeFailed", "変更失敗"), false); }
  };

  return (
    <AdminLayout pathname={pathname}>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">{t("adminUsers.title", "ユーザ一覧")}</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg">{t("adminUsers.addNew", "＋ 新規ユーザ追加")}</button>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <input type="text" value={fltCode} onChange={e => setFltCode(e.target.value)} placeholder={t("adminUsers.filterCode", "社員コードでフィルタ")}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-40" />
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder={t("adminUsers.filterName", "氏名でフィルタ")}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltSys} onChange={e => setFltSys(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">{t("adminUsers.sysAll", "区分: すべて")}</option>
              <option value="NC">NC</option>
              <option value="MC">MC</option>
              <option value="BOTH">{t("adminUsers.sysBoth", "NC+MC")}</option>
            </select>
            <select value={fltRole} onChange={e => setFltRole(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">{t("adminUsers.roleAll", "ロール: すべて")}</option>
              <option value="ADMIN">{t("adminUsers.roleAdmin","管理者")}</option><option value="OPERATOR">{t("adminUsers.roleOperator","作業者")}</option><option value="VIEWER">{t("adminUsers.roleViewer","閲覧者")}</option>
            </select>
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">{t("adminUsers.statusAll", "状態: すべて")}</option><option value="active">{t("adminUsers.activeOnly", "有効のみ")}</option><option value="inactive">{t("adminUsers.inactiveOnly", "無効のみ")}</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{t("adminUsers.countFraction","{a}/{b}件").replace("{a}",String(filteredUsers.length)).replace("{b}",String(users.length))}</span>
          </div>

          {loading ? (
            <div className="text-center py-20 text-slate-400">{t("adminUsers.loading", "読み込み中...")}</div>
          ) : (
            <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
              <div className="shrink-0 border-b border-slate-200">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-10"/><col className="w-28"/><col className="w-32"/><col className="w-24"/>
                    <col className="w-16"/><col className="w-24"/><col className="w-14"/><col className="w-16"/><col className="w-52"/>
                  </colgroup>
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("id")}>{t("adminUsers.colId","ID")}<SortIcon k="id"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("employeeCode")}>{t("adminUsers.colEmployeeCode","社員コード")}<SortIcon k="employeeCode"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("name")}>{t("adminUsers.colName","氏名")}<SortIcon k="name"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("nameKana")}>{t("adminUsers.colKana","カナ")}<SortIcon k="nameKana"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("systemType")}>{t("adminUsers.colSys","区分")}<SortIcon k="systemType"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("role")}>{t("adminUsers.colRole","ロール")}<SortIcon k="role"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("isActive")}>{t("adminUsers.colStatus","状態")}<SortIcon k="isActive"/></th>
                      <th className="px-3 py-3 text-left">{t("adminUsers.colApproval", "承認資格")}</th>
                      <th className="px-3 py-3 text-right">{t("adminUsers.colAction", "操作")}</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-10"/><col className="w-28"/><col className="w-32"/><col className="w-24"/>
                    <col className="w-16"/><col className="w-24"/><col className="w-14"/><col className="w-16"/><col className="w-52"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filteredUsers.map(u => (
                      <tr key={u.id} className={`hover:bg-slate-50 ${!u.isActive ? "opacity-40" : ""}`}>
                        <td className="px-3 py-2.5 text-slate-400 text-xs">{u.id}</td>
                        <td className="px-3 py-2.5 font-mono text-slate-700 text-xs">{u.employeeCode}</td>
                        <td className="px-3 py-2.5 text-slate-800 text-xs font-medium truncate">{u.name}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs truncate">{u.nameKana ?? "—"}</td>
                        <td className="px-3 py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SYS_COLOR[u.systemType] ?? "bg-slate-100 text-slate-500"}`}>{u.systemType ?? "NC"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold ${ROLE_COLOR[u.role]}`}>{ROLE_KEY[u.role] ? t(ROLE_KEY[u.role]) : u.role}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`text-xs font-bold ${u.isActive ? "text-green-600" : "text-slate-400"}`}>{u.isActive ? t("adminUsers.active","有効") : t("adminUsers.inactive","無効")}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          {u.canApprove
                            ? <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700">{t("adminUsers.approvable", "承認可")}</span>
                            : <span className="text-[10px] text-slate-300">—</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-1 flex-nowrap">
                            <button onClick={() => openEdit(u)} className="px-2 py-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded font-bold whitespace-nowrap">{t("adminUsers.edit", "編集")}</button>
                            <button onClick={() => openPassword(u)} className="px-2 py-1 text-xs bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded font-bold whitespace-nowrap">{t("adminUsers.changePassword", "PW変更")}</button>
                            <button onClick={() => handleToggleActive(u)} className={`px-2 py-1 text-xs border rounded font-bold whitespace-nowrap ${u.isActive ? "bg-red-50 hover:bg-red-100 text-red-600 border-red-200" : "bg-green-50 hover:bg-green-100 text-green-600 border-green-200"}`}>
                              {u.isActive ? t("adminUsers.deactivate","無効化") : t("adminUsers.activate","有効化")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredUsers.length === 0 && <tr><td colSpan={9} className="text-center py-12 text-slate-400">{t("adminUsers.noMatch", "該当するユーザがありません")}</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">
              {dialogMode === "create" ? t("adminUsers.createTitle","新規ユーザ追加") : dialogMode === "edit" ? t("adminUsers.editTitle","ユーザ編集") : t("adminUsers.passwordTitle","パスワード変更")}
            </h2>
            {fError && <div className="text-red-500 text-xs mb-3">{fError}</div>}
            {dialogMode !== "password" ? (
              <div className="space-y-3">
                <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.nameLabel", "氏名 *")}</label>
                  <input type="text" value={fName2} onChange={e => setFName2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.kanaLabel", "カナ")}</label>
                  <input type="text" value={fKana2} onChange={e => setFKana2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.sysTypeLabel", "システム区分")}</label>
                  <select value={fSys2} onChange={e => setFSys2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                    <option value="NC">NC</option>
                    <option value="MC">MC</option>
                    <option value="BOTH">{t("adminUsers.sysBothFull", "NC+MC（両方）")}</option>
                  </select></div>
                <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.roleLabel", "ロール")}</label>
                  <select value={fRole2} onChange={e => setFRole2(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                    <option value="OPERATOR">{t("adminUsers.roleOperator","作業者")}</option><option value="VIEWER">{t("adminUsers.roleViewer","閲覧者")}</option><option value="ADMIN">{t("adminUsers.roleAdmin","管理者")}</option>
                  </select></div>
                <div className="flex items-center gap-2">
                  <input id="fCanApprove2" type="checkbox" checked={fCanApprove2} onChange={e => setFCanApprove2(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-400" />
                  <label htmlFor="fCanApprove2" className="text-xs font-bold text-slate-600">
                    {t("adminUsers.approvalCheckbox", "承認資格（MC/NC情報の承認操作を許可する）")}
                  </label>
                </div>
                {dialogMode === "edit" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.statusLabel", "状態")}</label>
                    <select value={fActive2} onChange={e => setFActive2(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
                      <option value="active">{t("adminUsers.active","有効")}</option><option value="inactive">{t("adminUsers.inactive","無効")}</option>
                    </select></div>
                )}
                {dialogMode === "create" && (
                  <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.passwordLabel", "パスワード *")}</label>
                    <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
                )}
              </div>
            ) : (
              <div><label className="text-xs font-bold text-slate-500 block mb-1">{t("adminUsers.newPasswordLabel", "新しいパスワード")}</label>
                <input type="password" value={fPW} onChange={e => setFPW(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
            )}
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogMode(null)} className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">{t("adminUsers.cancel", "キャンセル")}</button>
              <button onClick={dialogMode === "password" ? handlePW : handleSave} disabled={saving}
                className="px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold disabled:opacity-50">
                {saving ? t("adminUsers.saving","保存中…") : t("adminUsers.save","保存")}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
