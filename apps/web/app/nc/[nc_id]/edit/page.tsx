"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useRef } from "react";
import { ncApi, machinesApi, filesApi, NcDetail, Machine, UpdateNcBody, downloadApi } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";
import GCodeEditor from "@/components/nc/GCodeEditor";

export default function NcEditPage() {
  const { nc_id } = useParams();
  const router    = useRouter();
  const ncId      = Number(nc_id);

  const [detail,    setDetail]    = useState<NcDetail | null>(null);
  const [machines,  setMachines]  = useState<Machine[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // フォーム値
  const [machineId,     setMachineId]     = useState<number | "">("");
  const [machiningTime, setMachiningTime] = useState<string>("");
  const [folderName,    setFolderName]    = useState("");
  const [fileName,      setFileName]      = useState("");
  const [version,       setVersion]       = useState("");
  const [clampNote,     setClampNote]     = useState("");

  // 変更検知（オレンジ枠用）
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const markDirty = (field: string) => setDirty(prev => new Set(prev).add(field));

  // AUTH（必ずファイルアップロードより先に宣言）
  const { operator, isAuthenticated, logout, token } = useAuth();

  // ── ファイルアップロード（useAuth後に配置）──
  const photoInputRef = useRef<HTMLInputElement>(null);
  const scanInputRef  = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const handleFileUpload = useCallback(async (file: File) => {
    if (!token) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      await filesApi.upload(ncId, file, token);
      setUploadMsg(`✅ ${file.name} をアップロードしました`);
      const res = await ncApi.findOne(ncId);
      setDetail(res.data);
    } catch {
      setUploadMsg("❌ アップロードに失敗しました");
    } finally {
      setUploading(false);
      setTimeout(() => setUploadMsg(null), 3000);
    }
  }, [token, ncId]);

  // PG エディタ
  const [pgOpen,       setPgOpen]       = useState(false);
  const [pgLoading,    setPgLoading]    = useState(false);
  const [pgContent,    setPgContent]    = useState("");
  const [pgEncoding,   setPgEncoding]   = useState("UTF-8");
  const [pgLineEnding, setPgLineEnding] = useState("LF");
  const [pgDirty,      setPgDirty]      = useState(false);
  const [pgSaving,     setPgSaving]     = useState(false);
  const [pgError,      setPgError]      = useState<string | null>(null);

  const handlePgOpen = useCallback(async () => {
    if (!token) { setAuthOpen(true); return; }
    if (pgOpen) { setPgOpen(false); return; }
    setPgLoading(true);
    setPgError(null);
    try {
      const { default: axios } = await import("axios");
      const res = await axios.get(`/api/nc/${ncId}/pg-file`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPgContent(res.data.content);
      setPgEncoding(res.data.encoding);
      setPgLineEnding(res.data.lineEnding);
      setPgDirty(false);
      setPgOpen(true);
    } catch (e: any) {
      setPgError(e?.response?.data?.message ?? "PGファイルの読込に失敗しました");
    } finally {
      setPgLoading(false);
    }
  }, [token, ncId, pgOpen]);

  const handlePgSave = useCallback(async () => {
    if (!token) return;
    setPgSaving(true);
    setPgError(null);
    try {
      const { default: axios } = await import("axios");
      await axios.put(
        `/api/nc/${ncId}/pg-file`,
        { content: pgContent, encoding: pgEncoding, lineEnding: pgLineEnding },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setPgDirty(false);
    } catch (e: any) {
      setPgError(e?.response?.data?.message ?? "PGファイルの保存に失敗しました");
    } finally {
      setPgSaving(false);
    }
  }, [token, ncId, pgContent, pgEncoding, pgLineEnding]);

  const [authOpen, setAuthOpen] = useState(false);

  // 経過タイマー
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const fmtElapsed = (s: number) => {
    const h   = Math.floor(s / 3600);
    const m   = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  // データ取得
  useEffect(() => {
    if (!ncId) return;
    Promise.all([
      ncApi.findOne(ncId),
      machinesApi.list(),
    ]).then(([ncRes, machRes]) => {
      const d = ncRes.data;
      setDetail(d);
      setMachines(machRes.data.filter(m => m.isActive));
      setMachineId(d.machine?.id ?? "");
      setMachiningTime(String(d.machiningTime ?? ""));
      setFolderName(d.folderName ?? "");
      setFileName(d.fileName ?? "");
      setVersion(d.version ?? "A");
      setClampNote(d.clampNote ?? "");
    }).catch(e => setLoadError(e.message));
  }, [ncId]);

  // フィールドクラス（変更時オレンジ枠）
  const fieldCls = (field: string, base = "") =>
    `${base} border rounded px-3 py-2 text-sm w-full focus:outline-none ${
      dirty.has(field)
        ? "border-orange-400 bg-orange-50 focus:ring-1 focus:ring-orange-400"
        : "border-slate-300 bg-white focus:ring-1 focus:ring-sky-400"
    } ${!isAuthenticated ? "opacity-50 cursor-not-allowed" : ""}`;

  // 保存
  const handleSave = useCallback(async () => {
    if (!isAuthenticated || !token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const body: UpdateNcBody = {};
      if (dirty.has("machineId"))     body.machine_id     = machineId === "" ? undefined : Number(machineId);
      if (dirty.has("machiningTime")) body.machining_time = machiningTime === "" ? undefined : Number(machiningTime);
      if (dirty.has("folderName"))    body.folder_name    = folderName;
      if (dirty.has("fileName"))      body.file_name      = fileName;
      if (dirty.has("version"))       body.version        = version;
      if (dirty.has("clampNote"))     body.clamp_note     = clampNote;

      if (Object.keys(body).length === 0) {
        setSaveError("変更項目がありません");
        return;
      }

      const { default: axios } = await import("axios");
      await axios.put(`/api/nc/${ncId}`, body, {
        headers: { Authorization: `Bearer ${token}` },
      });

      logout();
      router.push(`/nc/${ncId}`);
    } catch (e: any) {
      setSaveError(e?.response?.data?.message ?? "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  }, [isAuthenticated, token, dirty, machineId, machiningTime, folderName, fileName, version, clampNote, ncId, logout, router]);

  const handleDownload = async () => {
    try {
      const t = localStorage.getItem("work_token");
      if (!t) { alert("先に作業を開始してください"); return; }
      await downloadApi.pgFile(ncId, t);
    } catch {
      alert("ダウンロードに失敗しました");
    }
  };

  const handleCancel = useCallback(() => {
    if (isAuthenticated) {
      if (!confirm("変更を破棄して戻りますか？")) return;
      logout();
    }
    router.push(`/nc/${ncId}`);
  }, [isAuthenticated, logout, ncId, router]);

  if (loadError) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-red-500 text-sm">読み込みエラー: {loadError}</div>
    </div>
  );
  if (!detail) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-slate-400 text-sm">読み込み中...</div>
    </div>
  );

  const d = detail;

  return (
    <>
      {/* ── 隠しファイルinput ── */}
      <input
        ref={photoInputRef}
        type="file"
        accept="image/jpeg,image/png,image/tiff,image/gif"
        multiple
        className="hidden"
        onChange={e => {
          if (e.target.files) Array.from(e.target.files).forEach(handleFileUpload);
          e.target.value = "";
        }}
      />
      <input
        ref={scanInputRef}
        type="file"
        accept="image/tiff,image/tif,application/pdf,image/jpeg,image/png"
        multiple
        className="hidden"
        onChange={e => {
          if (e.target.files) Array.from(e.target.files).forEach(handleFileUpload);
          e.target.value = "";
        }}
      />

      <div className="h-screen flex flex-col bg-slate-50">

        {/* ── ヘッダー ── */}
        <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
          <button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="text-slate-400 hover:text-white text-xs transition-colors"
          >
            ← NC詳細
          </button>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
          <span className="text-slate-400 text-xs">|</span>
          <span className="text-sm font-medium">✏️ 変更・登録</span>
          <span className="ml-auto flex items-center gap-2">
            {isAuthenticated && operator ? (
              <span className="text-[11px] bg-red-600 text-white px-3 py-1 rounded font-bold animate-pulse">
                作業中: {operator.name}　{fmtElapsed(elapsed)}
              </span>
            ) : (
              <span className="text-[11px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">
                🔒 認証待ち
              </span>
            )}
          </span>
        </header>

        {/* ── 部品ヘッダー ── */}
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-sky-600 font-bold text-lg">{d.part.drawingNo}</span>
            <ProcessBadge level={d.processL} />
            <StatusBadge status={d.status} />
            <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">
              Ver.{d.version}
            </span>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-slate-500">
            <span>{d.part.name}</span>
            <span className="text-slate-300">|</span>
            <span>NC_id: <span className="font-mono text-slate-700">{d.id}</span></span>
            {d.part.clientName && (
              <><span className="text-slate-300">|</span><span>{d.part.clientName}</span></>
            )}
          </div>
        </div>

        {/* ── メインコンテンツ ── */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="max-w-2xl mx-auto">

            {/* ロック状態バナー */}
            {!isAuthenticated && (
              <div className="mb-5 bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
                <div>
                  <p className="text-amber-800 font-bold text-sm">🔒 編集にはWork Session認証が必要です</p>
                  <p className="text-amber-600 text-xs mt-0.5">担当者を選択してパスワードを入力してください</p>
                </div>
                <button
                  onClick={() => setAuthOpen(true)}
                  className="bg-sky-600 hover:bg-sky-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
                >
                  この作業を開始する
                </button>
              </div>
            )}

            {/* エラー表示 */}
            {saveError && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-600 text-sm">
                ⚠️ {saveError}
              </div>
            )}

            {/* 編集フォーム */}
            <div className={`bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden ${!isAuthenticated ? "opacity-60" : ""}`}>
              <div className="bg-slate-50 border-b border-slate-200 px-5 py-3">
                <h2 className="text-sm font-bold text-slate-700">NCデータ編集</h2>
                {dirty.size > 0 && (
                  <span className="text-[11px] text-orange-600 font-medium">
                    ● {dirty.size}項目 変更済み
                  </span>
                )}
              </div>

              <div className="p-5 space-y-4">

                {/* 工程L（変更不可） + Ver */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">
                      工程 L <span className="text-slate-300 font-normal">（変更不可）</span>
                    </label>
                    <div className="border border-slate-200 rounded px-3 py-2 text-sm bg-slate-50 text-slate-400 font-mono">
                      L{d.processL}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">
                      Ver <span className="text-red-400">*</span>
                      {dirty.has("version") && <span className="text-orange-500 ml-1">●</span>}
                    </label>
                    <input
                      type="text"
                      maxLength={1}
                      value={version}
                      disabled={!isAuthenticated}
                      onChange={e => { setVersion(e.target.value.toUpperCase()); markDirty("version"); }}
                      className={fieldCls("version", "font-mono uppercase")}
                      placeholder="A"
                    />
                  </div>
                </div>

                {/* 機械 */}
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    機械 <span className="text-red-400">*</span>
                    {dirty.has("machineId") && <span className="text-orange-500 ml-1">●</span>}
                  </label>
                  <select
                    value={machineId}
                    disabled={!isAuthenticated}
                    onChange={e => { setMachineId(e.target.value === "" ? "" : Number(e.target.value)); markDirty("machineId"); }}
                    className={fieldCls("machineId")}
                  >
                    <option value="">-- 機械を選択 --</option>
                    {machines.map(m => (
                      <option key={m.id} value={m.id}>{m.machineCode} — {m.machineName}</option>
                    ))}
                  </select>
                </div>

                {/* 加工時間 */}
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    加工時間（分）
                    {dirty.has("machiningTime") && <span className="text-orange-500 ml-1">●</span>}
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={machiningTime}
                    disabled={!isAuthenticated}
                    onChange={e => { setMachiningTime(e.target.value); markDirty("machiningTime"); }}
                    className={fieldCls("machiningTime")}
                    placeholder="0"
                  />
                </div>

                {/* フォルダ名 */}
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    フォルダ名 <span className="text-red-400">*</span>
                    {dirty.has("folderName") && <span className="text-orange-500 ml-1">●</span>}
                  </label>
                  <input
                    type="text"
                    maxLength={50}
                    value={folderName}
                    disabled={!isAuthenticated}
                    onChange={e => { setFolderName(e.target.value); markDirty("folderName"); }}
                    className={fieldCls("folderName", "font-mono")}
                    placeholder="例: NC_PARTS_001"
                  />
                </div>

                {/* ファイル名 */}
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    ファイル名 / O番号 <span className="text-red-400">*</span>
                    {dirty.has("fileName") && <span className="text-orange-500 ml-1">●</span>}
                  </label>
                  <input
                    type="text"
                    maxLength={50}
                    value={fileName}
                    disabled={!isAuthenticated}
                    onChange={e => { setFileName(e.target.value); markDirty("fileName"); }}
                    className={fieldCls("fileName", "font-mono")}
                    placeholder="例: O1234"
                  />
                </div>

                {/* クランプ備考 */}
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1">
                    クランプ / 備考
                    {dirty.has("clampNote") && <span className="text-orange-500 ml-1">●</span>}
                  </label>
                  <textarea
                    rows={4}
                    maxLength={2000}
                    value={clampNote}
                    disabled={!isAuthenticated}
                    onChange={e => { setClampNote(e.target.value); markDirty("clampNote"); }}
                    className={fieldCls("clampNote")}
                    placeholder="クランプ条件・注意事項など"
                  />
                  <p className="text-[10px] text-slate-400 mt-0.5 text-right">{clampNote.length} / 2000</p>
                </div>

              </div>
            </div>

            {/* ── ファイル取込エリア ── */}
            {isAuthenticated && (
              <div className="mt-4 bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-3">
                  📎 ファイル取込
                </h3>
                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    onClick={() => photoInputRef.current?.click()}
                    disabled={uploading}
                    className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                  >
                    📷 写真を取り込む
                  </button>
                  <button
                    onClick={() => scanInputRef.current?.click()}
                    disabled={uploading}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-lg transition-colors"
                  >
                    🖼 図をスキャン（取込）
                  </button>
                  {uploading && (
                    <span className="text-xs text-slate-400 animate-pulse">⏳ アップロード中…</span>
                  )}
                  {uploadMsg && (
                    <span className="text-xs font-medium text-slate-600">{uploadMsg}</span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 mt-2">
                  写真: JPEG / PNG / TIFF対応 ／ 図: TIFF / PDF / PNG / JPEG対応（TIFF → PNG自動変換）
                </p>
              </div>
            )}

            {/* ── PG テキストエディタ ── */}
            <div className="mt-4">
              <div className="flex items-center gap-3 mb-2">
                <button
                  onClick={handlePgOpen}
                  disabled={!isAuthenticated || pgLoading}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                    pgOpen
                      ? "bg-slate-700 text-white border-slate-700"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                  } ${!isAuthenticated || pgLoading ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {pgLoading ? "読込中…" : pgOpen ? "✕ エディタを閉じる" : "📝 テキストエディタで編集"}
                </button>
                {pgDirty  && <span className="text-xs text-orange-500 font-bold">● 未保存</span>}
                {pgSaving && <span className="text-xs text-sky-500">保存中…</span>}
                {pgError  && <span className="text-xs text-red-500">{pgError}</span>}
              </div>
              {pgOpen && (
                <div className="h-[480px]">
                  <GCodeEditor
                    content={pgContent}
                    encoding={pgEncoding}
                    lineEnding={pgLineEnding}
                    readOnly={!isAuthenticated}
                    onChange={v => { setPgContent(v); setPgDirty(true); }}
                    onSave={handlePgSave}
                  />
                </div>
              )}
            </div>

            {/* ── アクションボタン ── */}
            <div className="mt-5 flex items-center justify-between">
              <button
                onClick={handleCancel}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-slate-600 bg-white border border-slate-300 hover:bg-slate-50 transition-colors"
              >
                ✗ キャンセル（変更を破棄）
              </button>
              <button
                onClick={handleDownload}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold transition-colors"
              >
                💾 USBへ書き出し
              </button>
              <button
                onClick={handleSave}
                disabled={!isAuthenticated || saving || dirty.size === 0}
                className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-colors ${
                  isAuthenticated && dirty.size > 0 && !saving
                    ? "bg-sky-600 hover:bg-sky-700 text-white"
                    : "bg-slate-200 text-slate-400 cursor-not-allowed"
                }`}
              >
                {saving ? "登録中..." : "✓ 作業完了（登録）"}
              </button>
            </div>

          </div>
        </div>
      </div>

      {/* AUTH モーダル */}
      <AuthModal
        isOpen={authOpen}
        sessionType="edit"
        ncProgramId={ncId}
        onSuccess={() => setAuthOpen(false)}
        onCancel={() => setAuthOpen(false)}
      />
    </>
  );
}