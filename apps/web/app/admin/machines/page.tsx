"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

type Machine = {
  id: number;
  machineCode: string;
  machineName: string;
  machineType: string | null;
  maker: string | null;
  sortOrder: number;
  isActive: boolean;
};

type DialogMode = "create" | "edit" | null;

export default function AdminMachinesPage() {
  const router = useRouter();
  const [machines,   setMachines]   = useState<Machine[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [toast,      setToast]      = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [editTarget, setEditTarget] = useState<Machine | null>(null);
  const [fCode,  setFCode]  = useState("");
  const [fName,  setFName]  = useState("");
  const [fType,  setFType]  = useState("NC旋盤");
  const [fMaker, setFMaker] = useState("");
  const [fOrder, setFOrder] = useState(0);
  const [saving, setSaving] = useState(false);
  const [fError, setFError] = useState<string | null>(null);

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const apiBase  = "/api";

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    fetchMachines();
  }, [router]);

  const fetchMachines = useCallback(async (tok?: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/admin/machines`, {
        headers: { Authorization: `Bearer ${tok ?? getToken()}` },
      });
      setMachines(await res.json());
    } catch { showToast("取得失敗", false); }
    finally { setLoading(false); }
  }, []);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const openCreate = () => {
    setFCode(""); setFName(""); setFType("NC旋盤"); setFMaker("");
    setFOrder((machines.length + 1) * 10);
    setFError(null); setEditTarget(null); setDialogMode("create");
  };

  const openEdit = (m: Machine) => {
    setFCode(m.machineCode); setFName(m.machineName);
    setFType(m.machineType ?? ""); setFMaker(m.maker ?? ""); setFOrder(m.sortOrder);
    setFError(null); setEditTarget(m); setDialogMode("edit");
  };

  const handleSave = async () => {
    if (!fCode.trim() || !fName.trim()) { setFError("機械コードと名称は必須です"); return; }
    setSaving(true); setFError(null);
    try {
      const url    = dialogMode === "edit" ? `${apiBase}/admin/machines/${editTarget!.id}` : `${apiBase}/admin/machines`;
      const method = dialogMode === "edit" ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ machine_code: fCode, machine_name: fName, machine_type: fType || null, maker: fMaker || null, sort_order: fOrder }),
      });
      if (!res.ok) { const d = await res.json(); setFError(d.message ?? "保存失敗"); return; }
      showToast(dialogMode === "edit" ? "更新しました" : "登録しました", true);
      setDialogMode(null); fetchMachines();
    } catch { setFError("通信エラー"); }
    finally { setSaving(false); }
  };

  const handleToggle = async (m: Machine) => {
    try {
      await fetch(`${apiBase}/admin/machines/${m.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ is_active: !m.isActive }),
      });
      showToast(m.isActive ? "無効化しました" : "有効化しました", true);
      fetchMachines();
    } catch { showToast("更新失敗", false); }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-slate-800 text-white px-6 py-3 flex items-center gap-3 shrink-0">
        <button onClick={() => router.push("/admin/users")}
          className="text-slate-400 hover:text-white text-sm transition-colors">
          ← ユーザ管理
        </button>
        <div className="h-4 w-px bg-slate-600" />
        <div className="flex items-center gap-2">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
          <span className="font-bold text-sm">機械マスタ管理</span>
        </div>
        <button onClick={() => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); }}
          className="ml-auto text-xs text-slate-400 hover:text-white transition-colors">
          ログアウト
        </button>
      </header>

      <main className="flex-1 p-6 max-w-5xl mx-auto w-full">
        <div className="flex justify-between items-center mb-4">
          <p className="text-sm text-slate-500">{machines.length} 件登録済み（無効含む）</p>
          <button onClick={openCreate}
            className="bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold px-4 py-2 rounded-lg transition-colors">
            ＋ 新規登録
          </button>
        </div>

        {loading ? (
          <p className="text-center py-12 text-slate-400">読み込み中...</p>
        ) : (
          <div className="bg-white rounded-xl shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {["ID","機械コード","機械名","種別","メーカー","順序","状態","操作"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {machines.map(m => (
                  <tr key={m.id} className={`hover:bg-slate-50 transition-colors ${!m.isActive ? "opacity-40" : ""}`}>
                    <td className="px-4 py-3 text-slate-400 text-xs">{m.id}</td>
                    <td className="px-4 py-3 font-mono font-bold text-slate-700">{m.machineCode}</td>
                    <td className="px-4 py-3 text-slate-800">{m.machineName}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{m.machineType ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{m.maker ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500 text-center text-xs">{m.sortOrder}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-bold ${m.isActive ? "text-green-600" : "text-slate-400"}`}>
                        {m.isActive ? "有効" : "無効"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right space-x-3">
                      <button onClick={() => openEdit(m)} className="text-xs text-sky-600 hover:underline">編集</button>
                      <button onClick={() => handleToggle(m)}
                        className={`text-xs hover:underline ${m.isActive ? "text-red-500" : "text-green-600"}`}>
                        {m.isActive ? "無効化" : "有効化"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {machines.length === 0 && (
              <p className="text-center py-12 text-slate-400">機械データがありません</p>
            )}
          </div>
        )}
      </main>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="bg-slate-800 px-6 py-4">
              <h2 className="text-white font-bold text-lg">
                {dialogMode === "create" ? "機械を新規登録" : "機械情報を編集"}
              </h2>
            </div>
            <div className="p-6 space-y-4">
              {fError && <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-2">{fError}</p>}
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">機械コード <span className="text-red-400">*</span></label>
                <input value={fCode} onChange={e => setFCode(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
                  placeholder="例: SL-25B/500-NC16" />
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">機械名 <span className="text-red-400">*</span></label>
                <input value={fName} onChange={e => setFName(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">種別</label>
                  <input value={fType} onChange={e => setFType(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                    placeholder="NC旋盤" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">メーカー</label>
                  <input value={fMaker} onChange={e => setFMaker(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                    placeholder="DMG森精機" />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1">表示順（小さいほど上位）</label>
                <input type="number" value={fOrder} onChange={e => setFOrder(Number(e.target.value))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={() => setDialogMode(null)}
                  className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors">
                  キャンセル
                </button>
                <button onClick={handleSave} disabled={saving}
                  className="flex-1 px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold hover:bg-sky-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-bold z-50
                         ${toast.ok ? "bg-green-600" : "bg-red-500"}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
