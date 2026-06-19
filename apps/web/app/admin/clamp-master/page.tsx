"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const CATEGORIES = [
  { key: "vise",  label: "バイス",     cols: ["name","model","maker"] },
  { key: "chuck", label: "チャック",   cols: ["name","size","maker"] },
  { key: "tsume", label: "爪",         cols: ["name"] },
  { key: "shiki", label: "敷板",       cols: ["name"] },
  { key: "index", label: "インデックス", cols: ["name","machine","model"] },
];
const COL_LABEL: Record<string,string> = { name:"名称", model:"型式", maker:"メーカー", size:"サイズ", machine:"搭載機" };

type Item = { id: number; name: string; model?: string|null; maker?: string|null; size?: string|null; machine?: string|null; sortOrder: number; isActive: boolean };

const getToken = () => sessionStorage.getItem("admin_token") ?? "";
const apiFetch = async (path: string, opts?: RequestInit) => {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type":"application/json", Authorization:`Bearer ${getToken()}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.message ?? `HTTP ${res.status}`); }
  return res.json();
};

export default function ClampMasterPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [catKey, setCatKey] = useState("vise");
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [editId, setEditId] = useState<number|null>(null);
  const [editForm, setEditForm] = useState<Record<string,string>>({});
  const [newForm, setNewForm] = useState<Record<string,string>>({});
  const [showNew, setShowNew] = useState(false);
  const [toast, setToast] = useState<{msg:string;ok:boolean}|null>(null);

  const showToast = (msg: string, ok=true) => { setToast({msg,ok}); setTimeout(()=>setToast(null),3000); };
  const cat = CATEGORIES.find(c => c.key === catKey)!;

  useEffect(() => {
    const t = sessionStorage.getItem("admin_token");
    if (!t) { router.replace("/admin/login"); return; }
  }, [router]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/admin/clamp-master/${catKey}`);
      setItems(data);
    } catch (e: any) { showToast(e.message, false); }
    finally { setLoading(false); }
  }, [catKey]);

  useEffect(() => { fetchItems(); setEditId(null); setShowNew(false); setNewForm({}); }, [fetchItems]);

  const handleSave = async (id: number) => {
    try {
      await apiFetch(`/admin/clamp-master/${catKey}/${id}`, { method:"PUT", body: JSON.stringify({
        ...editForm,
        sort_order: editForm.sortOrder ? parseInt(editForm.sortOrder) : undefined,
        is_active: editForm.isActive !== undefined ? editForm.isActive === "true" : undefined,
      })});
      showToast("保存しました");
      setEditId(null);
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const handleCreate = async () => {
    if (!newForm.name?.trim()) { showToast("名称を入力してください", false); return; }
    try {
      await apiFetch(`/admin/clamp-master/${catKey}`, { method:"POST", body: JSON.stringify({
        name: newForm.name,
        ...(cat.cols.includes("model") ? { model: newForm.model||"" } : {}),
        ...(cat.cols.includes("maker") ? { maker: newForm.maker||"" } : {}),
        ...(cat.cols.includes("size")  ? { size:  newForm.size||""  } : {}),
        ...(cat.cols.includes("machine") ? { machine: newForm.machine||"" } : {}),
        sort_order: items.length * 10 + 10,
        is_active: true,
      })});
      showToast("追加しました");
      setShowNew(false);
      setNewForm({});
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`「${name}」を削除しますか？`)) return;
    try {
      await apiFetch(`/admin/clamp-master/${catKey}/${id}`, { method:"DELETE" });
      showToast("削除しました");
      fetchItems();
    } catch (e: any) { showToast(e.message, false); }
  };

  const inputCls = "border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm focus:ring-2 focus:ring-sky-400 focus:outline-none w-full";

  return (
    <AdminLayout pathname={pathname}>

      {toast && <div className={`fixed top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg text-white text-sm font-bold ${toast.ok?"bg-green-600":"bg-red-600"}`}>{toast.msg}</div>}

        <main className="flex-1 overflow-hidden flex flex-col p-5 gap-4">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">クランプ マスタ管理</h1>
            <button onClick={() => { setShowNew(true); setNewForm({}); }}
              className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>
              新規追加
            </button>
          </div>

          {/* カテゴリタブ */}
          <div className="flex gap-1.5 shrink-0">
            {CATEGORIES.map(c => (
              <button key={c.key} onClick={() => setCatKey(c.key)}
                className={`px-4 py-1.5 text-sm font-bold rounded-lg border transition-colors ${catKey===c.key ? "bg-sky-600 text-white border-sky-600" : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"}`}>
                {c.label}
              </button>
            ))}
          </div>

          {/* 新規追加フォーム */}
          {showNew && (
            <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 shrink-0">
              <div className="text-sm font-bold text-sky-700 mb-3">新規 {cat.label} 追加</div>
              <div className="flex gap-3 flex-wrap">
                {cat.cols.map(col => (
                  <div key={col} className="flex-1 min-w-[120px]">
                    <label className="text-xs font-bold text-slate-500 block mb-1">{COL_LABEL[col] ?? col}</label>
                    <input value={newForm[col]??""} onChange={e => setNewForm(p=>({...p,[col]:e.target.value}))}
                      className={inputCls} placeholder={COL_LABEL[col]} />
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
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
                    {cat.cols.map(col => (
                      <th key={col} className="px-3 py-2.5 text-left font-bold text-slate-600 border-b border-slate-200">{COL_LABEL[col]??col}</th>
                    ))}
                    <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-16">順番</th>
                    <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-16">有効</th>
                    <th className="px-3 py-2.5 text-center font-bold text-slate-600 border-b border-slate-200 w-24">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, i) => (
                    <tr key={item.id} className={i%2===0?"bg-white":"bg-slate-50"}>
                      {editId === item.id ? (
                        <>
                          <td className="px-3 py-1.5 text-slate-400 font-mono text-xs">{item.id}</td>
                          {cat.cols.map(col => (
                            <td key={col} className="px-3 py-1.5">
                              <input value={editForm[col]??""} onChange={e => setEditForm(p=>({...p,[col]:e.target.value}))}
                                className={inputCls} />
                            </td>
                          ))}
                          <td className="px-3 py-1.5 text-center">
                            <input type="number" value={editForm.sortOrder??""} onChange={e => setEditForm(p=>({...p,sortOrder:e.target.value}))}
                              className="border border-slate-300 rounded px-2 py-1 text-sm w-16 text-center" />
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <select value={editForm.isActive??"true"} onChange={e => setEditForm(p=>({...p,isActive:e.target.value}))}
                              className="border border-slate-300 rounded px-2 py-1 text-sm">
                              <option value="true">有効</option>
                              <option value="false">無効</option>
                            </select>
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <div className="flex gap-1 justify-center">
                              <button onClick={() => handleSave(item.id)}
                                className="px-2.5 py-1 bg-teal-600 text-white text-xs font-bold rounded hover:bg-teal-700">保存</button>
                              <button onClick={() => setEditId(null)}
                                className="px-2.5 py-1 border border-slate-300 text-slate-600 text-xs rounded hover:bg-slate-50">取消</button>
                            </div>
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="px-3 py-2 text-slate-400 font-mono text-xs">{item.id}</td>
                          {cat.cols.map(col => (
                            <td key={col} className="px-3 py-2">{(item as any)[col] ?? "—"}</td>
                          ))}
                          <td className="px-3 py-2 text-center font-mono text-slate-400">{item.sortOrder}</td>
                          <td className="px-3 py-2 text-center">
                            <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${item.isActive?"bg-green-100 text-green-700":"bg-slate-100 text-slate-500"}`}>
                              {item.isActive?"有効":"無効"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center">
                            <div className="flex gap-1 justify-center">
                              <button onClick={() => { setEditId(item.id); setEditForm({
                                ...cat.cols.reduce((a,c)=>({...a,[c]:(item as any)[c]??""})  ,{}),
                                sortOrder: String(item.sortOrder),
                                isActive: String(item.isActive),
                              }); }}
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
                    <tr><td colSpan={cat.cols.length + 4} className="px-3 py-8 text-center text-slate-400">データがありません</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </main>
    </AdminLayout>
  );
}
