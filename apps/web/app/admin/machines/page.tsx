"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

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
  const pathname = usePathname();
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
      {/* トップヘッダー */}
      <header className="bg-slate-900 text-white px-5 py-2.5 flex items-center gap-3 shrink-0 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-sky-600 flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
          </div>
          <span className="text-sm font-bold tracking-wide">MachCore 管理パネル</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <a href="/nc/search"
            className="text-xs bg-slate-600 hover:bg-slate-500 text-slate-200 px-3 py-1.5 rounded transition-colors">
            ← NC画面
          </a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); sessionStorage.removeItem("admin_user"); router.push("/admin/login"); }}
            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded transition-colors">
            ログアウト
          </button>
        </div>
      </header>

      {/* サイドバー + メイン */}
      <div className="flex flex-1 min-h-0">
        <aside className="w-48 shrink-0 bg-slate-800 flex flex-col py-4 gap-1 border-r border-slate-700">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider">メニュー</div>
          {[
            { href: "/admin/users",    label: "ユーザ管理",   icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
            { href: "/admin/machines", label: "機械管理",     icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
            { href: "/admin/settings", label: "システム設定", icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
            { href: "/admin/raw",      label: "RAWデータ",    icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
          ].map(item => (
            <a key={item.href} href={item.href}
              className={`mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors ${
                pathname === item.href
                  ? "bg-sky-600 text-white font-bold"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={item.icon}/>
              </svg>
              {item.label}
            </a>
          ))}
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
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
      </div>

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
