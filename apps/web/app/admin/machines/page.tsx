"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { machinesApi, Machine } from "@/lib/api";

const adminFetch = (path: string, opts?: RequestInit) =>
  fetch(`/api${path}`, { ...opts, headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) } });

type DialogMode = "create" | "edit" | null;
type SortKey = "id" | "machineName" | "machineType" | "maker" | "sortOrder" | "isActive";
type SortDir = "asc" | "desc";

export default function AdminMachinesPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [toast,    setToast]    = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [editTarget, setEditTarget] = useState<Machine | null>(null);
  const [fCode,  setFCode]  = useState("");
  const [fName,  setFName]  = useState("");
  const [fType,  setFType]  = useState("MC");
  const [fMaker, setFMaker] = useState("");
  const [fSort,  setFSort]  = useState("0");
  const [fError, setFError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [fltName,   setFltName]   = useState("");
  const [fltType,   setFltType]   = useState("");
  const [fltMaker,  setFltMaker]  = useState("");
  const [fltStatus, setFltStatus] = useState("");
  const [sortKey,   setSortKey]   = useState<SortKey>("sortOrder");
  const [sortDir,   setSortDir]   = useState<SortDir>("asc");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const showToast = (msg: string, ok: boolean) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };
  const handleLogout = () => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); };

  const fetchMachines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/admin/machines", { headers: { Authorization: `Bearer ${getToken()}` } });
      const d = await res.json();
      setMachines(Array.isArray(d) ? d : []);
    } catch { showToast("機械一覧の取得に失敗しました", false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    fetchMachines();
  }, [router, fetchMachines]);

  const filtered = machines.filter(m => {
    if (fltName   && !m.machineName?.includes(fltName))                  return false;
    // 種別は部分一致（NC旋盤, MCなど）+ NCだけ入力してもNC旋盤にヒット
    if (fltType   && !(m as any).machineType?.includes(fltType))          return false;
    if (fltMaker  && !(m as any).maker?.includes(fltMaker))              return false;
    if (fltStatus === "active"   && !m.isActive)                         return false;
    if (fltStatus === "inactive" &&  m.isActive)                         return false;
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

  const openCreate = () => { setFCode(""); setFName(""); setFType("MC"); setFMaker(""); setFSort("0"); setFError(null); setEditTarget(null); setDialogMode("create"); };
  const openEdit   = (m: Machine) => { setFCode(m.machineCode); setFName(m.machineName ?? ""); setFType((m as any).machineType ?? "MC"); setFMaker((m as any).maker ?? ""); setFSort(String(m.sortOrder ?? 0)); setFError(null); setEditTarget(m); setDialogMode("edit"); };

  const handleSave = async () => {
    if (!fCode || !fName) { setFError("機械コードと機械名は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      if (dialogMode === "create") {
        await adminFetch("/admin/machines", {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: JSON.stringify({ machine_code: fCode, machine_name: fName, machine_type: fType, maker: fMaker, sort_order: parseInt(fSort)||0, is_active: true }),
        });
      } else if (editTarget) {
        await adminFetch(`/admin/machines/${editTarget.id}`, {
          method: "PUT",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: JSON.stringify({ machine_code: fCode, machine_name: fName, machine_type: fType, maker: fMaker, sort_order: parseInt(fSort)||0 }),
        });
      }
      showToast(dialogMode === "edit" ? "更新しました" : "登録しました", true);
      setDialogMode(null); fetchMachines();
    } catch { setFError("通信エラー"); }
    finally { setSaving(false); }
  };

  const handleToggle = async (m: Machine) => {
    try {
      await adminFetch(`/admin/machines/${m.id}`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ is_active: !m.isActive }),
      });
      showToast(m.isActive ? "無効化しました" : "有効化しました", true); fetchMachines();
    } catch { showToast("変更失敗", false); }
  };

  return (
    <AdminLayout pathname={pathname}>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">機械一覧</h1>
            <button onClick={openCreate} className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg">＋ 新規機械追加</button>
          </div>
          <div className="flex flex-wrap gap-2 bg-white p-3 rounded-xl border border-slate-200 shrink-0">
            <input type="text" value={fltName} onChange={e => setFltName(e.target.value)} placeholder="機械名でフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltType} onChange={e => setFltType(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">種別: すべて</option>
              <option value="NC">NC</option>
              <option value="MC">MC</option>
            </select>
            <input type="text" value={fltMaker} onChange={e => setFltMaker(e.target.value)} placeholder="メーカーでフィルタ"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-36" />
            <select value={fltStatus} onChange={e => setFltStatus(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-sky-400 focus:outline-none">
              <option value="">状態: すべて</option><option value="active">有効のみ</option><option value="inactive">無効のみ</option>
            </select>
            <span className="text-xs text-slate-400 self-center">{filtered.length}/{machines.length}件</span>
          </div>

          {loading ? <div className="text-center py-20 text-slate-400">読み込み中…</div> : (
            <div className="flex-1 overflow-hidden bg-white rounded-xl border border-slate-200 flex flex-col">
              <div className="shrink-0 border-b border-slate-200">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-40"/><col className="w-24"/><col className="w-28"/>
                    <col className="w-16"/><col className="w-16"/><col className="w-40"/>
                  </colgroup>
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 text-xs uppercase">
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("id")}>ID<SortIcon k="id"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("machineName")}>機械名<SortIcon k="machineName"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("machineType")}>種別<SortIcon k="machineType"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("maker")}>メーカー<SortIcon k="maker"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("sortOrder")}>順序<SortIcon k="sortOrder"/></th>
                      <th className="px-3 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort("isActive")}>状態<SortIcon k="isActive"/></th>
                      <th className="px-3 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                </table>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm table-fixed">
                  <colgroup>
                    <col className="w-12"/><col className="w-40"/><col className="w-24"/><col className="w-28"/>
                    <col className="w-16"/><col className="w-16"/><col className="w-40"/>
                  </colgroup>
                  <tbody className="divide-y divide-slate-100">
                    {filtered.map((m, i) => (
                      <tr key={m.id} className={`${!m.isActive ? "opacity-40" : ""} ${i%2===0?"bg-white":"bg-slate-50/40"}`}>
                        <td className="px-3 py-2.5 text-slate-400 text-xs">{m.id}</td>
                        <td className="px-3 py-2.5 font-bold text-slate-800 text-xs truncate">{m.machineName}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs">{(m as any).machineType ?? "—"}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs truncate">{(m as any).maker ?? "—"}</td>
                        <td className="px-3 py-2.5 text-slate-500 text-xs">{m.sortOrder ?? 0}</td>
                        <td className="px-3 py-2.5">
                          <span className={`text-xs font-bold ${m.isActive ? "text-green-600" : "text-slate-400"}`}>{m.isActive ? "有効" : "無効"}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-1 flex-nowrap">
                            <button onClick={() => openEdit(m)} className="px-2 py-1 text-xs bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 rounded font-bold whitespace-nowrap">編集</button>
                            <button onClick={() => handleToggle(m)} className={`px-2 py-1 text-xs border rounded font-bold whitespace-nowrap ${m.isActive ? "bg-red-50 hover:bg-red-100 text-red-600 border-red-200" : "bg-green-50 hover:bg-green-100 text-green-600 border-green-200"}`}>
                              {m.isActive ? "無効化" : "有効化"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filtered.length === 0 && <tr><td colSpan={7} className="text-center py-12 text-slate-400">該当する機械がありません</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">{dialogMode === "create" ? "新規機械追加" : "機械編集"}</h2>
            {fError && <div className="text-red-500 text-xs mb-3">{fError}</div>}
            <div className="space-y-3">
              <div><label className="text-xs font-bold text-slate-500 block mb-1">機械コード *</label>
                <input type="text" value={fCode} onChange={e => setFCode(e.target.value)} disabled={dialogMode === "edit"}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none disabled:bg-slate-50" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">機械名 *</label>
                <input type="text" value={fName} onChange={e => setFName(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">種別</label>
                <input type="text" value={fType} onChange={e => setFType(e.target.value)} placeholder="例: NC旋盤, MC"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">メーカー</label>
                <input type="text" value={fMaker} onChange={e => setFMaker(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
              <div><label className="text-xs font-bold text-slate-500 block mb-1">順序</label>
                <input type="number" value={fSort} onChange={e => setFSort(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none" /></div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogMode(null)} className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50">キャンセル</button>
              <button onClick={handleSave} disabled={saving} className="px-4 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-lg font-bold disabled:opacity-50">
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
