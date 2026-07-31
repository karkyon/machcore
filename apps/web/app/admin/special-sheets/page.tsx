"use client";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useLanguage } from "@/lib/i18n/LanguageContext";

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
  const { t } = useLanguage();
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
    } catch (e: any) { showToast(t("adminSpecialSheets.fetchFailed","取得失敗: {msg}").replace("{msg}", e.message), false); }
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
    if (!fSheetName.trim()) { showToast(t("adminSpecialSheets.sheetNameRequired", "シート名は必須です"), false); return; }
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
        if (!res.ok) throw new Error(t("adminSpecialSheets.pdfUploadFailed","PDFアップロード失敗: HTTP {code}").replace("{code}", String(res.status)));
        showToast(t("adminSpecialSheets.savedAndUploaded", "保存・PDFアップロード完了"));
      } else {
        showToast(editTarget ? t("adminSpecialSheets.updated","更新しました") : t("adminSpecialSheets.created","登録しました"));
      }
      setFPdfFile(null);
      setDialogOpen(false);
      fetchData();
    } catch (e: any) { showToast(t("adminSpecialSheets.saveFailed","保存失敗: {msg}").replace("{msg}", e.message), false); }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiFetch(`/admin/special-sheets/${id}`, { method: "DELETE" });
      showToast(t("adminSpecialSheets.deleted", "削除しました"));
      setDelConfirm(null);
      fetchData();
    } catch (e: any) { showToast(t("adminSpecialSheets.deleteFailed","削除失敗: {msg}").replace("{msg}", e.message), false); }
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
      showToast(t("adminSpecialSheets.pdfUploaded", "PDFをアップロードしました"));
      fetchData();
    } catch (e: any) { showToast(t("adminSpecialSheets.uploadFailed","アップロード失敗: {msg}").replace("{msg}", e.message), false); }
    finally { setUploadingId(null); }
  };

  const filtered = sheets.filter(s => {
    if (filterClient && String(s.clientId ?? "") !== filterClient) return false;
    if (filterKw && !(s.keyword ?? "").toLowerCase().includes(filterKw.toLowerCase()) && !s.sheetName.toLowerCase().includes(filterKw.toLowerCase())) return false;
    return true;
  });

  return (
    <AdminLayout pathname={pathname}>

      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-white text-sm font-bold shadow-lg ${toast.ok ? "bg-green-600" : "bg-red-600"}`}>
          {toast.msg}
        </div>
      )}

        <main className="flex-1 overflow-y-auto flex flex-col p-5 gap-3">
          <div className="flex items-center justify-between shrink-0">
            <h1 className="text-xl font-bold text-slate-800">{t("adminSpecialSheets.title", "SPシート管理")}</h1>
            <button onClick={openCreate}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg">
              {t("adminSpecialSheets.addNew", "+ 新規登録")}
            </button>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <strong>{t("adminSpecialSheets.infoBox1", "SPシート（スペシャル段取シート）")}</strong>{t("adminSpecialSheets.infoBox2", ": クレームやトラブル実績のある部品の特別な注意事項を管理します。")}<br/>
            {t("adminSpecialSheets.infoBox3", "段取シート印刷時に部品の図面番号・名称・主機種型式にキーワードがHITした場合、自動で警告が表示されます。")}
          </div>

          {/* フィルター */}
          <div className="flex gap-3 flex-wrap">
            <select value={filterClient} onChange={e => setFilterClient(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400">
              <option value="">{t("adminSpecialSheets.allClients", "全納入先")}</option>
              {clients.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
            </select>
            <input value={filterKw} onChange={e => setFilterKw(e.target.value)}
              placeholder={t("adminSpecialSheets.filterKwPlaceholder", "キーワード/シート名で絞り込み")}
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-sky-400 w-56" />
          </div>

          {loading ? (
            <div className="text-slate-400 text-sm text-center py-10">{t("adminSpecialSheets.loading", "読み込み中...")}</div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <th className="px-3 py-2 text-left w-8">{t("adminSpecialSheets.colId", "ID")}</th>
                    <th className="px-3 py-2 text-left w-36">{t("adminSpecialSheets.colClient", "納入先")}</th>
                    <th className="px-3 py-2 text-left w-28">{t("adminSpecialSheets.colKeyword", "キーワード")}</th>
                    <th className="px-3 py-2 text-left w-48">{t("adminSpecialSheets.colSheetName", "シート名")}</th>
                    <th className="px-3 py-2 text-left">{t("adminSpecialSheets.colContent", "内容（概要）")}</th>
                    <th className="px-3 py-2 text-center w-16">{t("adminSpecialSheets.colVer", "Ver")}</th>
                    <th className="px-3 py-2 text-center w-24">{t("adminSpecialSheets.colPdf", "PDF")}</th>
                    <th className="px-3 py-2 text-center w-28">{t("adminSpecialSheets.colAction", "操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr><td colSpan={8} className="text-center py-8 text-slate-400 text-sm">{t("adminSpecialSheets.noData", "データなし")}</td></tr>
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
                            className="text-xs text-teal-600 hover:underline font-bold">{t("adminSpecialSheets.viewPdf", "📄 表示")}</a>
                        ) : (
                          <label className="cursor-pointer text-xs text-slate-400 hover:text-teal-600">
                            {uploadingId === s.id ? "⏳" : t("adminSpecialSheets.uploadPdf", "📤 PDF")}
                            <input type="file" accept=".pdf" className="hidden"
                              onChange={e => { if (e.target.files?.[0]) handlePdfUpload(s.id, e.target.files[0]); e.target.value = ""; }} />
                          </label>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex gap-1 justify-center">
                          <button onClick={() => openEdit(s)}
                            className="px-2 py-1 text-xs bg-sky-100 text-sky-700 rounded hover:bg-sky-200 font-bold">{t("adminSpecialSheets.edit", "編集")}</button>
                          {delConfirm === s.id ? (
                            <>
                              <button onClick={() => handleDelete(s.id)}
                                className="px-2 py-1 text-xs bg-red-600 text-white rounded font-bold">{t("adminSpecialSheets.confirm", "確認")}</button>
                              <button onClick={() => setDelConfirm(null)}
                                className="px-2 py-1 text-xs bg-slate-200 text-slate-600 rounded">{t("adminSpecialSheets.cancelShort", "取消")}</button>
                            </>
                          ) : (
                            <button onClick={() => setDelConfirm(s.id)}
                              className="px-2 py-1 text-xs bg-red-100 text-red-600 rounded hover:bg-red-200 font-bold">{t("adminSpecialSheets.delete", "削除")}</button>
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

      {/* 編集/作成ダイアログ */}
      {dialogOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-base font-bold text-slate-800 mb-4">
              {editTarget ? t("adminSpecialSheets.editTitle","SPシート編集 (ID: {id})").replace("{id}", String(editTarget.id)) : t("adminSpecialSheets.createTitle","SPシート新規登録")}
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">{t("adminSpecialSheets.clientLabel", "納入先")}</label>
                <select value={fClientId} onChange={e => setFClientId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400">
                  <option value="">{t("adminSpecialSheets.unsetOption", "（未設定）")}</option>
                  {clients.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">{t("adminSpecialSheets.keywordLabel", "キーワード")} <span className="text-slate-400 font-normal">{t("adminSpecialSheets.keywordHint", "（図面番号/名称/主機種型式に部分一致チェック）")}</span></label>
                <input value={fKeyword} onChange={e => setFKeyword(e.target.value)}
                  placeholder={t("adminSpecialSheets.keywordPlaceholder", "例: ライナ  F57137  ドライブリング")}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">{t("adminSpecialSheets.sheetNameLabel", "シート名")} <span className="text-red-500">*</span></label>
                <input value={fSheetName} onChange={e => setFSheetName(e.target.value)}
                  placeholder={t("adminSpecialSheets.sheetNamePlaceholder", "例: YOKOTA_ライナ  MORI_注意事項")}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">{t("adminSpecialSheets.contentLabel", "内容・注意事項")}</label>
                <textarea value={fContent} onChange={e => setFContent(e.target.value)}
                  rows={4} placeholder={t("adminSpecialSheets.contentPlaceholder", "段取時の注意事項を記入...")}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 resize-none" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">{t("adminSpecialSheets.versionLabel", "バージョン")}</label>
                <input type="number" value={fVersion} onChange={e => setFVersion(e.target.value)}
                  className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
              </div>
              {/* PDFファイル D&D */}
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">
                  {t("adminSpecialSheets.pdfLabel", "PDFファイル")} <span className="text-slate-400 font-normal">{t("adminSpecialSheets.pdfHint", "（任意・D&Dまたはクリックで選択）")}</span>
                </label>
                <div
                  onDragOver={e => { e.preventDefault(); setPdfDragOver(true); }}
                  onDragLeave={() => setPdfDragOver(false)}
                  onDrop={e => {
                    e.preventDefault(); setPdfDragOver(false);
                    const file = e.dataTransfer.files[0];
                    if (file && file.type === "application/pdf") setFPdfFile(file);
                    else if (file) alert(t("adminSpecialSheets.pdfOnlyAlert", "PDFファイルのみ対応しています"));
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
                        className="ml-2 text-xs text-red-500 hover:text-red-700 font-bold">{t("adminSpecialSheets.removeFile", "✕ 削除")}</button>
                    </div>
                  ) : (
                    <div>
                      <div className="text-2xl mb-1">📤</div>
                      <p className="text-xs text-slate-500">{t("adminSpecialSheets.dropHint", "PDFをここにドラッグ＆ドロップ")}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{t("adminSpecialSheets.clickHint", "またはクリックしてファイルを選択")}</p>
                    </div>
                  )}
                </div>
                {editTarget?.pdfPath && !fPdfFile && (
                  <p className="text-[11px] text-teal-600 mt-1">
                    {t("adminSpecialSheets.existingPdfPrefix", "✅ 既存PDF登録済み —")}
                    <a href={`/api/admin/special-sheets/${editTarget.id}/pdf`} target="_blank"
                      className="underline ml-1 hover:text-teal-800">{t("adminSpecialSheets.viewCurrentPdf", "現在のPDFを表示")}</a>
                    {t("adminSpecialSheets.overwriteNote", "（新しいファイルを選択すると上書きされます）")}
                  </p>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setDialogOpen(false)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50">{t("adminSpecialSheets.cancel", "キャンセル")}</button>
              <button onClick={handleSave} disabled={saving}
                className="px-5 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-bold rounded-lg text-sm">
                {saving ? t("adminSpecialSheets.saving","保存中...") : t("adminSpecialSheets.save","保存")}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
