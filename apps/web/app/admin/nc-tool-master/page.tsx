"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const CATEGORIES = [
  { key: "shave1", label: "加（Sv1）" },
  { key: "shave2", label: "工（Sv2）" },
  { key: "chip",   label: "形状（チップ）" },
  { key: "holder", label: "ホルダー" },
];

type Item = { id: number; name: string; sortOrder: number; isActive: boolean };

const getToken = () => sessionStorage.getItem("admin_token") ?? "";
const apiFetch = async (path: string, opts?: RequestInit) => {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
  return res.json();
};

export default function NcToolMasterPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [catKey, setCatKey] = useState("shave1");
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [newName, setNewName] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3000); };
  const cat = CATEGORIES.find(c => c.key === catKey)!;

  useEffect(() => {
    const t = sessionStorage.getItem("admin_token");
    if (!t) { router.replace("/admin/login"); return; }
  }, [router]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/nc-tool-master/${catKey}`);
      setItems(data);
    } catch (e: any) { showToast(e.message, false); }
    finally { setLoading(false); }
  }, [catKey]);

  useEffect(() => { fetchItems(); setEditId(null); setShowNew(false); setNewName(""); }, [fetchItems]);

  const handleSave = async (id: number) => {
    try {
      await apiFetch(`/admin/nc-tool-master/${catKey}/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: editForm.name,
          sort_order: editForm.sortOrder ? parseInt(editForm.sortOrder) : undefined,
          is_active: editForm.isActive !== undefined ? editForm.isActive === "true" : undefined,
        }),
      });
      showToast("保存しました");
      setEditId(null);
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const handleCreate = async () => {
    if (!newName.trim()) { showToast("名称を入力してください", false); return; }
    try {
      await apiFetch(`/admin/nc-tool-master/${catKey}`, {
        method: "POST",
        body: JSON.stringify({ name: newName, sort_order: items.length * 10 + 10, is_active: true }),
      });
      showToast("追加しました");
      setShowNew(false);
      setNewName("");
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`「${name}」を削除しますか？\nこの値を使用中の加工リスト行には影響しません(表示上の選択肢から外れるのみ)。`)) return;
    try {
      await apiFetch(`/admin/nc-tool-master/${catKey}/${id}`, { method: "DELETE" });
      showToast("削除しました");
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const inputCls = "border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-full";

  return (
    <AdminLayout pathname={pathname}>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>{toast.msg}</div>}

      <main className="flex-1 overflow-hidden flex flex-col p-5 gap-4">
        <div className="flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-xl font-bold text-slate-800">NC 加工リスト マスタ管理</h1>
            <p className="text-xs text-slate-400 mt-1">NC旋盤「変更・登録」画面の加工リスト(ツーリング)で選択できる候補一覧です。旧システム(Access)の t_d_Shave1/Shave2/Chip/Holder に相当します。</p>
          </div>
          <button onClick={() => { setShowNew(true); setNewName(""); }}
            className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg shrink-0">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
            新規追加
          </button>
        </div>

        {/* カテゴリタブ */}
        <div className="flex gap-1.5 shrink-0">
          {CATEGORIES.map(c => (
            <button key={c.key} onClick={() => setCatKey(c.key)}
              className={`px-4 py-1.5 text-sm font-bold rounded-lg border transition-colors ${catKey === c.key ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
              {c.label}
            </button>
          ))}
        </div>

        {/* 新規追加フォーム */}
        {showNew && (
          <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 shrink-0">
            <div className="text-sm font-bold text-sky-700 mb-3">新規 {cat.label} 追加</div>
            <div className="flex gap-3 items-end">
              <div className="flex-1 max-w-xs">
                <label className="text-xs font-bold text-slate-500 block mb-1">名称</label>
                <input value={newName} onChange={e => setNewName(e.target.value)} className={inputCls} placeholder="例: 外径" />
              </div>
              <button onClick={handleCreate} className="px-4 py-1.5 bg-sky-600 text-white text-sm font-bold rounded-lg hover:bg-sky-700">追加</button>
              <button onClick={() => setShowNew(false)} className="px-4 py-1.5 border border-slate-300 text-slate-600 text-sm rounded-lg hover:bg-slate-50">キャンセル</button>
            </div>
          </div>
        )}

        {/* 一覧テーブル */}
        <div className="flex-1 overflow-auto bg-white rounded-xl border border-slate-200">
          {loading ? (
            <div className="p-8 text-center text-slate-400">読み込み中...</div>
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2.5 text-left font-bold text-slate-600 border-b border-slate-200 w-12">ID</th>
                  <th className="px-3 py-2.5 text-left font-bold text-slate-600 border-b border-slate-200">名称</th>
                  <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-16">順番</th>
                  <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-16">有効</th>
                  <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-24">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={item.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                    {editId === item.id ? (
                      <>
                        <td className="px-3 py-1.5 text-slate-400 font-mono text-xs">{item.id}</td>
                        <td className="px-3 py-1.5">
                          <input value={editForm.name ?? ""} onChange={e => setEditForm(p => ({ ...p, name: e.target.value }))} className={inputCls} />
                        </td>
                        <td className="px-3 py-1.5 text-center">
                          <input type="number" value={editForm.sortOrder ?? ""} onChange={e => setEditForm(p => ({ ...p, sortOrder: e.target.value }))}
                            className="border border-slate-300 rounded px-2 py-1 text-sm w-16 text-center" />
                        </td>
                        <td className="px-3 py-1.5 text-center">
                          <select value={editForm.isActive ?? "true"} onChange={e => setEditForm(p => ({ ...p, isActive: e.target.value }))}
                            className="border border-slate-300 rounded px-2 py-1 text-sm">
                            <option value="true">有効</option>
                            <option value="false">無効</option>
                          </select>
                        </td>
                        <td className="px-3 py-1.5 text-center">
                          <div className="flex gap-1 justify-center">
                            <button onClick={() => handleSave(item.id)} className="px-2.5 py-1 bg-teal-600 text-white text-xs font-bold rounded hover:bg-teal-700">保存</button>
                            <button onClick={() => setEditId(null)} className="px-2.5 py-1 border border-slate-300 text-slate-600 text-xs rounded hover:bg-slate-50">取消</button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-2 text-slate-400 font-mono text-xs">{item.id}</td>
                        <td className="px-3 py-2">{item.name}</td>
                        <td className="px-3 py-2 text-center font-mono text-slate-400">{item.sortOrder}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${item.isActive ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                            {item.isActive ? "有効" : "無効"}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <div className="flex gap-1 justify-center">
                            <button onClick={() => { setEditId(item.id); setEditForm({ name: item.name, sortOrder: String(item.sortOrder), isActive: String(item.isActive) }); }}
                              className="px-2.5 py-1 bg-slate-100 text-slate-600 text-xs font-bold rounded hover:bg-slate-200 border border-slate-300">編集</button>
                            <button onClick={() => handleDelete(item.id, item.name)}
                              className="px-2.5 py-1 bg-red-50 text-red-600 text-xs font-bold rounded hover:bg-red-100 border border-red-200">削除</button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-400">データがありません</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </AdminLayout>
  );
}
