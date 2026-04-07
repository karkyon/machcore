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
      <div className="h-screen flex flex-col bg-slate-100">

        {/* ── グローバルヘッダー ── */}
        <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
          <button
            onClick={() => router.push(`/nc/${ncId}`)}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
          >
            <span className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center shrink-0">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            </span>
            NC詳細
          </button>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
          <span className="text-slate-400 text-xs">|</span>
          <span className="text-sm font-medium">✏️ 変更・登録</span>
          <span className="ml-auto">
            {isAuthenticated && operator ? (
              <span className="text-[11px] bg-red-600 text-white px-3 py-1 rounded font-bold animate-pulse">
                作業中: {operator.name}　{fmtElapsed(elapsed)}
              </span>
            ) : (
              <span className="text-[11px] text-slate-400 bg-slate-700 px-2 py-1 rounded">
                🔒 認証待ち
              </span>
            )}
          </span>
        </header>

        {/* ── 部品ヘッダー（白カード） ── */}
        {d && (
          <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
            <div className="flex items-center gap-3 mb-1">
              <span className="font-mono text-sky-600 font-bold text-lg">{d.part.drawingNo}</span>
              <ProcessBadge level={d.processL} />
              <StatusBadge status={d.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver.{d.version}</span>
            </div>
            <div className="flex items-center gap-4 text-[11px] text-slate-500 font-mono">
              <span>{d.part.name}</span>
              <span className="text-slate-300">|</span>
              <span>NC_id: {d.id}</span>
              {d.part.clientName && <><span className="text-slate-300">|</span><span>{d.part.clientName}</span></>}
            </div>
          </div>
        )}

        {/* ── タブナビ ── */}
        <nav className="bg-slate-800 px-5 flex gap-0 shrink-0 border-t border-slate-700">
          {([
            { href: `/nc/${ncId}`,        label: "NC詳細",    icon: "📋", active: false },
            { href: `/nc/${ncId}/edit`,   label: "変更・登録", icon: "✏️",  active: true  },
            { href: `/nc/${ncId}/print`,  label: "段取シート", icon: "🖨",  active: false },
            { href: `/nc/${ncId}/record`, label: "作業記録",  icon: "⏱",  active: false },
          ] as {href:string;label:string;icon:string;active:boolean}[]).map(tab => (
            <button key={tab.href} onClick={() => router.push(tab.href)}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                tab.active ? "text-sky-400 border-sky-400" : "text-slate-400 hover:text-slate-200 border-transparent"
              }`}>
              {tab.icon} {tab.label}
              {tab.active && isAuthenticated && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse ml-1" />}
            </button>
          ))}
        </nav>

        {/* ── メインコンテンツ ── */}
        <div className="flex-1 overflow-y-auto p-5">

          {/* === LOCKED STATE === */}
          {!isAuthenticated && d && (
            <div className="max-w-2xl mx-auto">
              <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-white flex flex-col items-center justify-center py-12 px-8 gap-4 text-center">
                <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center text-2xl">🔒</div>
                <div className="font-bold text-slate-700 text-base">変更・登録 — 作業開始前</div>
                <div className="text-slate-500 text-sm max-w-sm">
                  現在のデータを確認しています。変更・登録を行うには担当者の確認（パスワード）が必要です。
                </div>
                {/* データサマリー 50%透過 */}
                <div className="w-full max-w-md rounded-xl border border-slate-200 overflow-hidden opacity-50 pointer-events-none text-xs">
                  <div className="grid grid-cols-3 divide-x divide-slate-200 border-b border-slate-200">
                    <div className="p-2.5"><div className="text-slate-400">機械</div><div className="font-bold">{d.machine?.machineCode ?? "—"}</div></div>
                    <div className="p-2.5"><div className="text-slate-400">ファイル名</div><div className="font-mono font-bold">{d.fileName ?? "—"}</div></div>
                    <div className="p-2.5"><div className="text-slate-400">加工時間</div><div className="font-mono font-bold">{d.machiningTime != null ? `${d.machiningTime} 分` : "—"}</div></div>
                  </div>
                  <div className="p-2.5"><div className="text-slate-400">備考</div><div className="text-slate-600">{d.clampNote ? d.clampNote.slice(0,40)+"…" : "—"}</div></div>
                </div>
                <button
                  onClick={() => setAuthOpen(true)}
                  className="flex items-center gap-2 px-6 py-3 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-sm transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  この作業を開始する（担当者確認）
                </button>
                <div className="text-xs text-slate-400">担当者の選択とパスワード確認後に編集できます</div>
              </div>
            </div>
          )}

          {/* === ACTIVE STATE === */}
          {isAuthenticated && d && (
            <div className="max-w-4xl mx-auto space-y-4">

              {/* セッションバナー（赤） */}
              <div className="bg-red-600 rounded-xl px-5 py-3 flex items-center gap-3">
                <div className="w-2.5 h-2.5 bg-white rounded-full animate-pulse shrink-0"></div>
                <div className="flex-1">
                  <div className="text-white font-bold text-sm">変更・登録 作業中</div>
                  <div className="text-red-200 text-xs">{operator?.name}（{operator?.role}）— 作業開始から {fmtElapsed(elapsed)}</div>
                </div>
                <div className="text-white font-mono text-sm font-bold">{fmtElapsed(elapsed)}</div>
              </div>

              {/* エラー表示 */}
              {saveError && (
                <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-red-600 text-sm">⚠️ {saveError}</div>
              )}

              {/* 編集フォームカード */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <div className="flex items-center gap-1.5 mb-4 text-xs font-bold text-amber-600">
                  <div className="w-2 h-2 bg-amber-400 rounded-full"></div>
                  編集モード — 変更した項目はオレンジ枠で表示
                </div>

                <div className="grid grid-cols-3 gap-5">

                  {/* 左カラム（col-span-2）: フォームフィールド */}
                  <div className="col-span-2 space-y-4">

                    {/* 行1: 工程L | 機械 | 加工時間 | フォルダ名 */}
                    <div className="grid grid-cols-4 gap-3">
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">工程 L <span className="text-red-400 text-[10px]">変更不可</span></label>
                        <input
                          value={`L${d.processL}`} readOnly
                          className="border border-slate-200 rounded px-3 py-2 text-sm w-full bg-slate-50 text-slate-400 cursor-not-allowed"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">機械 <span className="text-red-400">*</span></label>
                        <select
                          value={machineId}
                          onChange={e => { setMachineId(e.target.value === "" ? "" : Number(e.target.value)); markDirty("machineId"); }}
                          className={fieldCls("machineId")}
                        >
                          <option value="">— 選択 —</option>
                          {machines.map(m => (
                            <option key={m.id} value={m.id}>{m.machineCode}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">加工時間（分）</label>
                        <input
                          type="number" min={0}
                          value={machiningTime}
                          onChange={e => { setMachiningTime(e.target.value); markDirty("machiningTime"); }}
                          className={fieldCls("machiningTime")}
                          placeholder="0"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">フォルダ名 <span className="text-red-400">*</span></label>
                        <input
                          type="text" maxLength={50}
                          value={folderName}
                          onChange={e => { setFolderName(e.target.value); markDirty("folderName"); }}
                          className={fieldCls("folderName", "font-mono")}
                          placeholder="例: 旭A"
                        />
                      </div>
                    </div>

                    {/* 行2: ファイル名/O番号 | Ver */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">
                          ファイル名 / O番号 <span className="text-red-400">*</span>
                          {dirty.has("fileName") && <span className="text-orange-500 ml-1">●</span>}
                        </label>
                        <input
                          type="text" maxLength={50}
                          value={fileName}
                          onChange={e => { setFileName(e.target.value); markDirty("fileName"); }}
                          className={fieldCls("fileName", "font-mono")}
                          placeholder="例: 7065"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">
                          Ver <span className="text-red-400">*</span>
                          {dirty.has("version") && <span className="text-orange-500 ml-1">●</span>}
                        </label>
                        <input
                          type="text" maxLength={3}
                          value={version}
                          onChange={e => { setVersion(e.target.value.toUpperCase()); markDirty("version"); }}
                          className={fieldCls("version", "font-mono font-bold")}
                          placeholder="A"
                        />
                      </div>
                    </div>

                    {/* クランプ / 備考 */}
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">
                        クランプ / 備考
                        {dirty.has("clampNote") && <span className="text-orange-500 ml-1">●</span>}
                      </label>
                      <textarea
                        rows={4}
                        maxLength={2000}
                        value={clampNote}
                        onChange={e => { setClampNote(e.target.value); markDirty("clampNote"); }}
                        className={`${fieldCls("clampNote")} resize-y`}
                        placeholder="クランプ条件・注意事項など"
                      />
                      <p className="text-[10px] text-slate-400 mt-0.5 text-right">{clampNote.length} / 2000</p>
                    </div>
                  </div>

                  {/* 右カラム: ファイル操作 */}
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">図枚数</label>
                      <input type="number" readOnly value={d.drawingCount}
                        className="border border-slate-200 rounded px-3 py-2 text-sm w-full bg-slate-50 text-slate-500" />
                    </div>
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">写真枚数</label>
                      <input type="number" readOnly value={d.photoCount}
                        className="border border-slate-200 rounded px-3 py-2 text-sm w-full bg-slate-50 text-slate-500" />
                    </div>
                    <div className="pt-1 space-y-2">
                      <button
                        onClick={() => photoInputRef.current?.click()}
                        disabled={uploading}
                        className="w-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5"
                      >
                        📷 写真を取り込む
                      </button>
                      <button
                        onClick={() => scanInputRef.current?.click()}
                        disabled={uploading}
                        className="w-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5"
                      >
                        📄 図をスキャン
                      </button>
                    </div>
                    {/* NCプログラム操作パネル */}
                    <div className="rounded-xl p-2.5 space-y-1.5" style={{background:"#0f172a", border:"1.5px solid #1e40af"}}>
                      <div className="text-[10px] text-sky-400 font-bold text-center tracking-wide mb-1">NCプログラム</div>
                      <button
                        onClick={handleDownload}
                        className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded-lg font-medium transition-colors"
                        style={{background:"#1d4ed8", color:"#fff"}}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        USB へ書き出し
                      </button>
                      <button
                        onClick={() => handlePgOpen()}
                        className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded-lg font-medium transition-colors"
                        style={{background:"#164e63", color:"#67e8f9"}}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                        テキストエディタで編集
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* PGテキストエディタ */}
              {pgOpen && (
                <div className="rounded-xl overflow-hidden" style={{border:"2px solid #1e40af", background:"#0f172a"}}>
                  <div className="flex items-center gap-2 px-3 py-2" style={{background:"#1e3a5f"}}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#67e8f9" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                    <span className="text-sky-300 font-bold text-sm">NCプログラム テキストエディタ</span>
                    {pgDirty && <span className="text-amber-400 text-xs ml-1">● 未保存</span>}
                    <div className="flex-1"></div>
                    <button onClick={() => setPgOpen(false)} className="text-slate-500 hover:text-white text-xs px-2">✕ 閉じる</button>
                  </div>
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

              {/* ── 完了ボタンバー ── */}
              <div className="rounded-xl p-4 flex items-center gap-3 flex-wrap" style={{background:"#fff7ed", border:"1.5px solid #fed7aa"}}>
                <button
                  onClick={handleSave}
                  disabled={saving || dirty.size === 0}
                  className="flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-bold text-sm rounded-lg transition-colors"
                >
                  ✓ 作業完了（登録）
                </button>
                <div className="text-xs text-amber-700">← 登録と同時に変更履歴に記録されます</div>
                <div className="flex-1"></div>
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-2 px-4 py-2.5 bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 font-bold text-sm rounded-lg transition-colors"
                >
                  ✗ キャンセル（変更を破棄）
                </button>
              </div>

            </div>
          )}

          {/* ファイル入力（非表示） */}
          <input ref={photoInputRef} type="file" accept="image/*,.pdf,.tif,.tiff" multiple className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f); }} />
          <input ref={scanInputRef} type="file" accept="image/*,.pdf,.tif,.tiff" multiple className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f); }} />

        </div>
      </div>

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal
          isOpen={authOpen}
          sessionType="edit"
          ncProgramId={ncId}
          onSuccess={() => setAuthOpen(false)}
          onCancel={() => setAuthOpen(false)}
        />
      )}

      {/* Toast */}
      {uploadMsg && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">
          {uploadMsg}
        </div>
      )}
    </>
  );
}
