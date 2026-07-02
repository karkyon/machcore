"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useState, useCallback, useRef } from "react";
import { ncApi, machinesApi, filesApi, NcDetail, Machine, UpdateNcBody } from "@/lib/api";
import { isAgentOnline, agentPickAndUpload } from "@/lib/upload-agent";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";
import { NcPartHeader } from "@/components/nc/NcPartHeader";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";
import ProgramFileViewer from "@/components/shared/ProgramFileViewer";

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
  const { operator, isAuthenticated, logout, token, isSessionForNc } = useAuth();

  // ── 別のnc_id向け認証セッションが残っていないか検証（MC側 edit/print/page.tsx と同ロジック）──
  // 「変更・登録」等で認証した状態のまま別画面(段取シート/NC詳細等)へ遷移した場合に、
  // 再認証なしで作業ができてしまうことを防ぐため、不一致を検知したら即座にログアウトする。
  useLayoutEffect(() => {
    if (!ncId) return;
    if (isAuthenticated && !isSessionForNc(ncId)) {
      console.warn("[NC-EDIT] 認証セッションが別のnc_id向けのため強制ログアウト", { ncId });
      logout();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ncId, isAuthenticated]);

  // ── [FIX v060] stale closure対策: アンマウント時クリーンアップ内で常に
  //    最新のisAuthenticatedを参照できるようrefで追従させる。
  const isAuthenticatedRef = useRef(isAuthenticated);
  useEffect(() => { isAuthenticatedRef.current = isAuthenticated; }, [isAuthenticated]);

  // ── このページ自体がアンマウントされる(=他画面へ遷移する)際に、
  //    認証セッションが残っていれば必ず終了させる。タブ切り替えなど、明示的な
  //    「キャンセル」ボタンを経由しない遷移であっても、次の画面へ認証状態を持ち越さない。
  useLayoutEffect(() => {
    return () => {
      if (isAuthenticatedRef.current) {
        console.warn("[NC-EDIT] ページ離脱を検知 — 認証セッションを終了します");
        logout();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── ファイルアップロード（UploadAgent経由、MC側と同方式）──
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const issueNcUploadTicket = async (fileType: "PHOTO" | "DRAWING") => {
    if (!token) throw new Error("認証が必要です");
    const res = await fetch(`/api/nc/${ncId}/files/upload-ticket`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ file_type: fileType }),
    });
    if (!res.ok) throw new Error(`チケット発行失敗: HTTP ${res.status}`);
    const json = await res.json();
    return { ticket: json.ticket as string, uploadPath: json.upload_path as string | undefined };
  };

  const requestNcUpload = useCallback(async (fileType: "PHOTO" | "DRAWING") => {
    if (!token || uploading) return;
    setUploading(true);
    setUploadMsg("⏳ UploadAgentに接続中...");

    const agentOnline = await isAgentOnline();
    if (!agentOnline) {
      const msg = "❌ UploadAgentが起動していません。タスクトレイを確認し、UploadAgent を起動してください。";
      setUploadMsg(msg);
      setUploading(false);
      window.alert(msg);
      return;
    }

    const ok = window.confirm(
      "【アップロード元ファイルの削除確認】\n選択したファイルをアップロードします。アップロード完了後、元ファイルはゴミ箱フォルダへ自動移動されます。\n続行しますか？"
    );
    if (!ok) { setUploading(false); setUploadMsg(null); return; }

    setUploadMsg("⏳ UploadAgentでファイル選択ダイアログを開いています...");
    try {
      const { ticket, uploadPath } = await issueNcUploadTicket(fileType);
      const result = await agentPickAndUpload(ticket, fileType, uploadPath);

      if (result.cancelled) { setUploadMsg(null); return; }
      if (!result.success) { setUploadMsg(`❌ ${result.error ?? "アップロードに失敗しました"}`); return; }

      const res = await ncApi.findOne(ncId);
      setDetail(res.data);
      setUploadMsg(`✅ ${result.files.length}件アップロード完了`);
    } catch (e: any) {
      setUploadMsg("❌ アップロード失敗: " + (e.message ?? "不明なエラー"));
    } finally {
      setUploading(false);
      setTimeout(() => setUploadMsg(null), 5000);
    }
  }, [token, ncId, uploading]);

  // PG エディタ
  // [v084] 単一ファイルのみ対応の旧実装を廃止。MC側と同じ共通コンポーネント(ProgramFileViewer)に一本化。
  //   フォルダ単位(メインPG+サブPG)の複数ファイルにも対応する。
  const [newPgViewerOpen, setNewPgViewerOpen] = useState(false);

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
      machinesApi.list("NC"),
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
          <button onClick={() => router.push("/nc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>ダッシュボードへ
          </button>
          <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
          <span className="text-sm font-medium flex items-center gap-1.5">変更・登録</span>
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

        {/* 部品情報エリア（共通コンポーネント） */}
        {d && <NcPartHeader data={d} />}

        {/* タブナビ（MC側準拠: ブラウザタブ風） */}
        <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
          <button onClick={() => router.push(`/nc/${ncId}`)}
            className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>NC詳細
          </button>
          <button onClick={() => router.push(`/nc/${ncId}/edit`)}
            className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
            {isAuthenticated && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse ml-0.5" />}
          </button>
          <button onClick={() => router.push(`/nc/${ncId}/print`)}
            className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
          </button>
          <button onClick={() => router.push(`/nc/${ncId}/record`)}
            className="px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
          </button>
        </nav>

        {/* ── メインコンテンツ ── */}
        <div className="flex-1 overflow-y-auto p-5">

          {/* === LOCKED STATE === */}
          {!isAuthenticated && d && (
            <div className="max-w-lg mx-auto mt-8">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 flex flex-col items-center gap-4 text-center">
                <div className="w-14 h-14 rounded-full bg-red-50 border border-red-200 flex items-center justify-center">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#991b1b" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </div>
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
                        onClick={() => requestNcUpload("PHOTO")}
                        disabled={uploading}
                        className="w-full border border-teal-300 bg-teal-50 hover:bg-teal-100 text-teal-700 text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5 disabled:opacity-40"
                      >
                        {uploading && <span className="inline-block w-3 h-3 border-2 border-teal-700 border-t-transparent rounded-full animate-spin" />}
                        📷 写真を取り込む
                      </button>
                      <button
                        onClick={() => requestNcUpload("DRAWING")}
                        disabled={uploading}
                        className="w-full border border-purple-300 bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5 disabled:opacity-40"
                      >
                        {uploading && <span className="inline-block w-3 h-3 border-2 border-purple-700 border-t-transparent rounded-full animate-spin" />}
                        📄 図を取り込む
                      </button>
                      {uploadMsg && (
                        <p className={`text-[11px] text-center font-bold ${uploadMsg.startsWith("⏳") ? "text-amber-600 animate-pulse" : uploadMsg.startsWith("❌") ? "text-red-600" : "text-teal-600"}`}>
                          {uploadMsg}
                        </p>
                      )}
                      <p className="text-[10px] text-slate-400 text-center">UploadAgentでファイル選択ダイアログが開きます</p>
                    </div>
                    {/* NCプログラム操作パネル [v084] MC側と同じ共通コンポーネント(ProgramFileViewer)に接続 */}
                    <div className="rounded-xl p-2.5 space-y-1.5" style={{background:"#0f172a", border:"1.5px solid #1e40af"}}>
                      <div className="text-[10px] text-sky-400 font-bold text-center tracking-wide mb-1">NCプログラム</div>
                      <button
                        onClick={() => {
                          if (!token) { setAuthOpen(true); return; }
                          setNewPgViewerOpen(true);
                        }}
                        className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded-lg font-medium transition-colors"
                        style={{background:"#164e63", color:"#67e8f9"}}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                        📄 PGエディタを開く
                      </button>
                      <p className="text-[9px] text-slate-500 text-center">保存 / USBへ書き出し(UA経由)はエディタ内で行えます</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* [v084] 新共通コンポーネント(NC編集モード) — MC側 mc/[mc_id]/edit/page.tsx と同一 */}
              {newPgViewerOpen && (
                <ProgramFileViewer
                  system="nc"
                  programId={ncId}
                  mode="edit"
                  token={token}
                  onClose={() => setNewPgViewerOpen(false)}
                  onAuthRequired={() => setAuthOpen(true)}
                />
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
