"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

const SIDEBAR_ITEMS = [
  { href: "/admin/users",         label: "ユーザ管理",         icon: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 8 0 4 4 0 0 0-8 0" },
  { href: "/admin/machines",      label: "機械管理",           icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/mc/timecards",        label: "機械タイムカード",   icon: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" },
  { href: "/admin/settings",      label: "システム設定",       icon: "M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" },
  { href: "/admin/calendar",      label: "営業カレンダー",     icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" },
  { href: "/admin/raw",           label: "RAWデータ",          icon: "M4 6h16M4 10h16M4 14h16M4 18h16" },
  { href: "/admin/system-logs",   label: "システムログ",       icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2" },
  { href: "/admin/pdf-editor",    label: "段取りシートエディタ",        icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 1-2-2V5a2 2 0 1 2-2h5.586a1 1 0 1 .707.293l5.414 5.414a1 1 0 1 .293.707V19a2 2 0 1-2 2z" },
  { href: "/admin/special-sheets",label: "SPシート管理",       icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2M12 12h.01M12 16h.01" }
];

type SpecialSheet = {
  id: number;
  clientId: number | null;
  keyword: string | null;
  sheetName: string;
  content: string;
  pdfPath: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
};
type Client = { id: number; name: string };

const getToken = () => sessionStorage.getItem("admin_token") ?? "";
const apiFetch = async (path: string, opts?: RequestInit) => {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}`, ...(opts?.headers ?? {}) },
  });
  if (!res.ok) { const t = await res.text().catch(() => ""); throw new Error(`HTTP ${res.status}: ${t}`); }
  return res.json();
};

export default function SpecialSheetsPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [sheets,    setSheets]    = useState<SpecialSheet[]>([]);
  const [clients,   setClients]   = useState<Client[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [toast,     setToast]     = useState<{ msg: string; ok: boolean } | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<SpecialSheet | null>(null);
  const [fClientId,  setFClientId]  = useState<string>("");
  const [fKeyword,   setFKeyword]   = useState("");
  const [fSheetName, setFSheetName] = useState("");
  const [fContent,   setFContent]   = useState("");
  const [fVersion,   setFVersion]   = useState("0");
  const [saving,     setSaving]     = useState(false);
  const [delConfirm, setDelConfirm] = useState<number | null>(null);
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [filterClient, setFilterClient] = useState<string>("");
  const [filterKw,     setFilterKw]     = useState("");
  const [fPdfFile,     setFPdfFile]     = useState<File | null>(null);
  const [pdfDragOver,  setPdfDragOver]  = useState(false);

  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 3500); };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        apiFetch("/admin/special-sheets"),
        apiFetch("/admin/clients"),
      ]);
      setSheets(s);
      setClients(c);
    } catch (e: any) { showToast("取得失敗: " + e.message, false); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const clientName = (id: number | null) =>
    id ? (clients.find(c => c.id === id)?.name ?? `ID:${id}`) : "—";

  const openCreate = () => {
    setEditTarget(null);
    setFClientId(""); setFKeyword(""); setFSheetName(""); setFContent(""); setFVersion("0"); setFPdfFile(null);
    setDialogOpen(true);
  };
  const openEdit = (s: SpecialSheet) => {
    setEditTarget(s);
    setFClientId(s.clientId ? String(s.clientId) : "");
    setFKeyword(s.keyword ?? "");
    setFSheetName(s.sheetName);
    setFContent(s.content);
    setFVersion(String(s.version)); setFPdfFile(null);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!fSheetName.trim()) { showToast("シート名は必須です", false); return; }
    setSaving(true);
    try {
      const body = {
        client_id:  fClientId ? Number(fClientId) : null,
        keyword:    fKeyword.trim() || null,
        sheet_name: fSheetName.trim(),
        content:    fContent.trim(),
        version:    Number(fVersion) || 0,
      };
      let savedId: number | null = null;
      if (editTarget) {
        await apiFetch(`/admin/special-sheets/${editTarget.id}`, {
          method: "PUT", body: JSON.stringify(body),
        });
        savedId = editTarget.id;
      } else {
        const created = await apiFetch("/admin/special-sheets", {
          method: "POST", body: JSON.stringify(body),
        });
        savedId = created.id;
      }
      // PDFファイルが選択されていれば自動アップロード
      if (fPdfFile && savedId) {
        const fd = new FormData();
        fd.append("file", fPdfFile);
        const res = await fetch(`/api/admin/special-sheets/${savedId}/upload-pdf`, {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: fd,
        });
        if (!res.ok) throw new Error("PDFアップロード失敗: HTTP " + res.status);
        showToast("保存・PDFアップロード完了");
      } else {
        showToast(editTarget ? "更新しました" : "登録しました");
      }
      setFPdfFile(null);
      setDialogOpen(false);
      fetchData();
    } catch (e: any) { showToast("保存失敗: " + e.message, false); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiFetch(`/admin/special-sheets/${id}`, { method: "DELETE" });
      showToast("削除しました");
      setDelConfirm(null);
      fetchData();
    } catch (e: any) { showToast("削除失敗: " + e.message, false); }
  };

  const handlePdfUpload = async (id: number, file: File) => {
    setUploadingId(id);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/admin/special-sheets/${id}/upload-pdf`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: fd,
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      showToast("PDFをアップロードしました");
      fetchData();
    } catch (e: any) { showToast("アップロード失敗: " + e.message, false); }
    finally { setUploadingId(null); }
  };

  const filtered = sheets.filter(s => {
    if (filterClient && String(s.clientId ?? "") !== filterClient) return false;
    if (filterKw && !(s.keyword ?? "").toLowerCase().includes(filterKw.toLowerCase()) && !s.sheetName.toLowerCase().includes(filterKw.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-5 py-3 flex items-center gap-3 shrink-0">
        <span className="text-sm font-bold text-slate-800 tracking-wide">MachCore 管理パネル</span>
        <div className="ml-auto flex items-center gap-3">
          <a href="/" className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded">← ダッシュボード</a>
          <button onClick={() => { sessionStorage.removeItem("admin_token"); router.push("/admin/login"); }}
            className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded">ログアウト</button>
        </div>
      </header>

      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-white text-sm font-bold shadow-lg ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <aside className="w-52 shrink-0 bg-white border-r border-slate-200 flex flex-col py-4 gap-0.5 overflow-y-auto">
          <div className="px-4 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">メニュー</div>
          {SIDEBAR_ITEMS.filter(i => i.href !== "/admin/pdf-editor" && i.href !== "/admin/special-sheets").map(item => (
            <a key={item.href} href={item.href}
              className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
              {item.label}
            </a>
          ))}
          <div className="mx-3 my-1 border-t border-slate-200" />
          {["/admin/pdf-editor", "/admin/special-sheets"].map(href => {
            const item = SIDEBAR_ITEMS.find(i => i.href === href)!;
            return (
              <a key={item.href} href={item.href}
                className={"mx-2 px-3 py-2 rounded-lg flex items-center gap-2.5 text-sm transition-colors " + (pathname === item.href ? "bg-sky-50 text-sky-700 font-bold border border-sky-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900")}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={item.icon} /></svg>
                {item.label}
              </a>
            );
          })}
        </aside>

        <main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">SPシート管理</h1>
            <button onClick={openCreate}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg">
              + 新規登録
            </button>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <strong>SPシート（スペシャル段取シート）</strong>: クレームやトラブル実績のある部品の特別な注意事項を管理します。<br/>
            段取シート印刷時に部品の図面番号・名称・主機種型式にキーワードがHITした場合、自動で警告が表示されます。
          </div>

          {/* フィルター */}
          <div className="flex gap-3 flex-wrap">
            <select value={filterClient} onChange={e => setFilterClient(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400">
              <option value="">全納入先</option>
              {clients.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
            </select>
            <input value={filterKw} onChange={e => setFilterKw(e.target.value)}
              placeholder="キーワード/シート名で絞り込み"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400 w-56" />
          </div>

          {loading ? (
            <div className="text-slate-400 text-sm text-center py-10">読み込み中...</div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <th className="px-3 py-2 text-left w-8">ID</th>
                    <th className="px-3 py-2 text-left w-36">納入先</th>
                    <th className="px-3 py-2 text-left w-28">キーワード</th>
                    <th className="px-3 py-2 text-left w-48">シート名</th>
                    <th className="px-3 py-2 text-left">内容（概要）</th>
                    <th className="px-3 py-2 text-center w-16">Ver</th>
                    <th className="px-3 py-2 text-center w-24">PDF</th>
                    <th className="px-3 py-2 text-center w-28">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr><td colSpan={8} className="text-center py-8 text-slate-400 text-sm">データなし</td></tr>
                  )}
                  {filtered.map((s, i) => (
                    <tr key={s.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                      <td className="px-3 py-2 text-slate-500 font-mono text-xs">{s.id}</td>
                      <td className="px-3 py-2 font-bold text-slate-700 text-xs">{clientName(s.clientId)}</td>
                      <td className="px-3 py-2 font-mono text-teal-700 text-xs font-bold">{s.keyword ?? "—"}</td>
                      <td className="px-3 py-2 text-slate-700 text-xs">{s.sheetName}</td>
                      <td className="px-3 py-2 text-slate-500 text-xs max-w-xs truncate" title={s.content}>{s.content.slice(0, 60)}{s.content.length > 60 ? "…" : ""}</td>
                      <td className="px-3 py-2 text-center text-xs font-mono text-slate-500">{s.version}</td>
                      <td className="px-3 py-2 text-center">
                        {s.pdfPath ? (
                          <a href={`/api/admin/special-sheets/${s.id}/pdf`} target="_blank"
                            className="text-xs text-teal-600 hover:underline font-bold">📄 表示</a>
                        ) : (
                          <label className="cursor-pointer text-xs text-slate-400 hover:text-teal-600">
                            {uploadingId === s.id ? "⏳" : "📤 PDF"}
                            <input type="file" accept=".pdf" className="hidden"
                              onChange={e => { if (e.target.files?.[0]) handlePdfUpload(s.id, e.target.files[0]); e.target.value = ""; }} />
                          </label>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex gap-1 justify-center">
                          <button onClick={() => openEdit(s)}
                            className="px-2 py-1 text-xs bg-sky-100 text-sky-700 rounded hover:bg-sky-200 font-bold">編集</button>
                          {delConfirm === s.id ? (
                            <>
                              <button onClick={() => handleDelete(s.id)}
                                className="px-2 py-1 text-xs bg-red-600 text-white rounded font-bold">確認</button>
                              <button onClick={() => setDelConfirm(null)}
                                className="px-2 py-1 text-xs bg-slate-200 text-slate-600 rounded">取消</button>
                            </>
                          ) : (
                            <button onClick={() => setDelConfirm(s.id)}
                              className="px-2 py-1 text-xs bg-red-100 text-red-600 rounded hover:bg-red-200 font-bold">削除</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* 編集/作成ダイアログ */}
      {dialogOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-base font-bold text-slate-800 mb-4">
              {editTarget ? `SPシート編集 (ID: ${editTarget.id})` : "SPシート新規登録"}
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">納入先</label>
                <select value={fClientId} onChange={e => setFClientId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400">
                  <option value="">（未設定）</option>
                  {clients.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">キーワード <span className="text-slate-400 font-normal">（図面番号/名称/主機種型式に部分一致チェック）</span></label>
                <input value={fKeyword} onChange={e => setFKeyword(e.target.value)}
                  placeholder="例: ライナ  F57137  ドライブリング"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">シート名 <span className="text-red-500">*</span></label>
                <input value={fSheetName} onChange={e => setFSheetName(e.target.value)}
                  placeholder="例: YOKOTA_ライナ  MORI_注意事項"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">内容・注意事項</label>
                <textarea value={fContent} onChange={e => setFContent(e.target.value)}
                  rows={4} placeholder="段取時の注意事項を記入..."
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 resize-none" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">バージョン</label>
                <input type="number" value={fVersion} onChange={e => setFVersion(e.target.value)}
                  className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              {/* PDFファイル D&D */}
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">
                  PDFファイル <span className="text-slate-400 font-normal">（任意・D&Dまたはクリックで選択）</span>
                </label>
                <div
                  onDragOver={e => { e.preventDefault(); setPdfDragOver(true); }}
                  onDragLeave={() => setPdfDragOver(false)}
                  onDrop={e => {
                    e.preventDefault(); setPdfDragOver(false);
                    const file = e.dataTransfer.files[0];
                    if (file && file.type === "application/pdf") setFPdfFile(file);
                    else if (file) alert("PDFファイルのみ対応しています");
                  }}
                  onClick={() => document.getElementById("sp-pdf-input")?.click()}
                  className={`border-2 border-dashed rounded-xl px-4 py-5 text-center cursor-pointer transition-colors ${
                    pdfDragOver ? "border-sky-400 bg-sky-50" :
                    fPdfFile    ? "border-green-400 bg-green-50" :
                                  "border-slate-300 bg-slate-50 hover:border-sky-300 hover:bg-sky-50"
                  }`}
                >
                  <input id="sp-pdf-input" type="file" accept="application/pdf" className="hidden"
                    onChange={e => { if (e.target.files?.[0]) setFPdfFile(e.target.files[0]); e.target.value = ""; }} />
                  {fPdfFile ? (
                    <div className="flex items-center justify-center gap-2">
                      <span className="text-green-600 text-lg">📄</span>
                      <span className="text-sm font-bold text-green-700">{fPdfFile.name}</span>
                      <button onClick={e => { e.stopPropagation(); setFPdfFile(null); }}
                        className="ml-2 text-xs text-red-500 hover:text-red-700 font-bold">✕ 削除</button>
                    </div>
                  ) : (
                    <div>
                      <div className="text-2xl mb-1">📤</div>
                      <p className="text-xs text-slate-500">PDFをここにドラッグ＆ドロップ</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">またはクリックしてファイルを選択</p>
                    </div>
                  )}
                </div>
                {editTarget?.pdfPath && !fPdfFile && (
                  <p className="text-[11px] text-teal-600 mt-1">
                    ✅ 既存PDF登録済み —
                    <a href={`/api/admin/special-sheets/${editTarget.id}/pdf`} target="_blank"
                      className="underline ml-1 hover:text-teal-800">現在のPDFを表示</a>
                    （新しいファイルを選択すると上書きされます）
                  </p>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogOpen(false)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50">キャンセル</button>
              <button onClick={handleSave} disabled={saving}
                className="px-5 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-bold rounded-lg text-sm">
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
