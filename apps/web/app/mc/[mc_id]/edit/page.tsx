"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { mcApi, mcFilesApi, machinesApi, usersApi, McDetail, Machine, UserInfo } from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

const STATUS_LABEL: Record<string, string> = {
  NEW: "新規", PENDING_APPROVAL: "未承認", APPROVED: "承認済", CHANGING: "変更中",
};

export default function McEditPage() {
  const { mc_id } = useParams<{ mc_id: string }>();
  const mcId  = parseInt(mc_id);
  const router = useRouter();
  const [sbMode, setSbMode] = React.useState(false);
  const [sbRepeatMode, setSbRepeatMode] = React.useState(false);
  // 終了確認モーダル（リピートフロー）
  const [showKanryoModal, setShowKanryoModal] = React.useState(false);
  const [kanryoType,   setKanryoType]   = React.useState("小変更");
  const [kanryoDetail, setKanryoDetail] = React.useState("");
  const [pendingBody,  setPendingBody]  = React.useState<any>(null);
  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === parseInt(mc_id)) setSbMode(true);
      const r = sessionStorage.getItem("sb_repeat_edit");
      if (r && parseInt(r) === parseInt(mc_id)) setSbRepeatMode(true);
    }
  }, [mc_id]);

  const [detail, setDetail]   = useState<McDetail | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const { operator, isAuthenticated, token, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  // ── 離脱警告（useAuth後に配置必須）────────────────────────────
  React.useEffect(() => {
    if (!isAuthenticated) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "作業が完了していません。このページを離れますか？";
      return e.returnValue;
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isAuthenticated]);

  // sbMode=true かつ未認証の場合は自動で認証モーダルを開く（useAuth後に配置必須）
  React.useEffect(() => {
    if ((sbMode || sbRepeatMode) && !isAuthenticated) {
      console.log("[EDIT] sbMode/sbRepeatMode=true 未認証 → 認証モーダルを自動表示");
      setAuthOpen(true);
    }
  }, [sbMode, sbRepeatMode, isAuthenticated]);
  const [elapsed, setElapsed]  = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // 編集フィールド
  const [machineId,    setMachineId]    = useState<string>("");
  const [oNumber,      setONumber]      = useState("");
  const [clampNote,    setClampNote]    = useState("");
  const [cycleH,       setCycleH]       = useState(0);
  const [cycleM,       setCycleM]       = useState(0);
  const [cycleS,       setCycleS]       = useState(0);
  const [machiningQty, setMachiningQty] = useState(1);
  const [note,         setNote]         = useState("");
  const [creatorId,    setCreatorId]    = useState<string>("");
  const [sheetCreatedAt, setSheetCreatedAt] = useState<string>("");
  const [users,        setUsers]        = useState<UserInfo[]>([]);

  // ツーリング
  const [toolingRows, setToolingRows] = useState<any[]>([]);
  const [toolingText, setToolingText] = useState("");
  const [parseResult, setParseResult] = useState<any[] | null>(null);
  const [activeSection, setActiveSection] = useState<"basic"|"tooling"|"offset"|"index"|"files">("basic");

  // ワークオフセット
  const [offsetRows, setOffsetRows] = useState<any[]>([]);
  // インデックス
  const [indexRows, setIndexRows] = useState<any[]>([]);

  // ファイル（写真・図）
  const [files,          setFiles]          = useState<any[]>([]);
  const [fileUploading,  setFileUploading]  = useState(false);
  const [fileUploadMsg,  setFileUploadMsg]  = useState<string | null>(null);
  const photoInputRef = React.useRef<HTMLInputElement>(null);
  const scanInputRef  = React.useRef<HTMLInputElement>(null);

  const [saving, setSaving]   = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [toast, setToast]     = useState<string | null>(null);
  const showToast = useCallback((msg: string) => {
    setToast(msg); setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => {
    mcApi.findOne(mcId).then(r => {
      const d = (r as any).data ?? r;
      console.log("[EDIT] detail取得", { id: d.id, version: d.version, status: d.status, machine: d.machine });
      setDetail(d);
      // McDetail.machine は { machineCode, machineName } のみ — id は machines リストから取得
      // machines がまだ空の可能性があるので machineCode を一時保存してから後で解決
      if (d.machine?.machineCode) {
        // machinesが既に取得済みなら id を解決、なければ machineCode をそのまま保持
        setMachineId(d.machine.machineCode); // 一旦machineCodeをセット
      } else {
        setMachineId("");
      }
      setONumber(d.oNumber ?? "");
      setClampNote(d.clampNote ?? "");
      setNote(d.note ?? "");
      setMachiningQty(d.machiningQty ?? 1);
      if (d.cycleTimeSec != null) {
        setCycleH(Math.floor(d.cycleTimeSec / 3600));
        setCycleM(Math.floor((d.cycleTimeSec % 3600) / 60));
        setCycleS(d.cycleTimeSec % 60);
      }
      setCreatorId(d.creatorId ? String(d.creatorId) : "");
      setSheetCreatedAt(d.sheetCreatedAt ? d.sheetCreatedAt.slice(0, 10) : "");
      setToolingRows((d.tooling ?? []).map((t: any) => ({
        sort_order:       t.sortOrder       ?? t.sort_order       ?? 0,
        tool_no:          t.toolNo          ?? t.tool_no          ?? "",
        t_no:             t.tNo             ?? t.t_no             ?? "",
        tool_name:        t.toolName        ?? t.tool_name        ?? "",
        length_offset_no: t.lengthOffsetNo  ?? t.length_offset_no ?? "",
        dia_offset_no:    t.diaOffsetNo     ?? t.dia_offset_no    ?? "",
        diameter:         t.diameter        != null ? Number(t.diameter) : null,
        d_value_content:  t.dValueContent   ?? t.d_value_content  ?? "",
        sub_pg_no:        t.subPgNo         ?? t.sub_pg_no        ?? "",
        tool_type:        t.toolType        ?? t.tool_type        ?? "",
        note:             t.note            ?? "",
        raw_program_line: t.rawProgramLine  ?? t.raw_program_line ?? "",
      })));
      setOffsetRows(d.workOffsets ?? []);
      setIndexRows(d.indexPrograms ?? []);
    }).catch(() => {});
    machinesApi.list().then(r => setMachines((r as any).data ?? [])).catch(() => {});
    usersApi.list().then(r => setUsers((r as any).data ?? [])).catch(() => {});
    mcApi.listFiles(mcId).then(r => setFiles((r as any).data ?? [])).catch(() => {});
  }, [mcId]);

  const handleFileUpload = async (file: File, fileType?: 'PHOTO' | 'DRAWING') => {
    if (!token) return;
    setFileUploading(true);
    setFileUploadMsg(null);
    try {
      await mcFilesApi.upload(mcId, file, token, fileType);
      const r = await mcApi.listFiles(mcId);
      setFiles((r as any).data ?? []);
      setFileUploadMsg("✅ アップロード完了");
    } catch {
      setFileUploadMsg("❌ アップロード失敗");
    } finally {
      setFileUploading(false);
      setTimeout(() => setFileUploadMsg(null), 3000);
    }
  };

  // machines 取得後に machineId を machineCode → id に解決
  useEffect(() => {
    if (machines.length > 0 && machineId) {
      // machineId が数字でない（machineCode）場合に id に変換
      if (isNaN(parseInt(machineId))) {
        const m = machines.find(m => m.machineCode === machineId);
        if (m) setMachineId(String(m.id));
        else setMachineId("");
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machines]);

  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);

  const fmtElapsed = (s: number) =>
    `${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;

  const handleSave = async () => {
    console.log("[EDIT] handleSave開始", { sbMode, sbRepeatMode, token: token ? "あり" : "なし", mcId,
      data: { machineId, oNumber, clampNote, cycleH, cycleM, cycleS, machiningQty, note, creatorId, sheetCreatedAt,
              toolingRows: toolingRows.length, offsetRows: offsetRows.length, indexRows: indexRows.length } });
    if (!token) { setSaveError("認証が必要です"); return; }
    setSaving(true); setSaveError(null);
    try {
      const cycleTimeSec = cycleH * 3600 + cycleM * 60 + cycleS;
      await mcApi.update(mcId, {
        machine_id:     (machineId && !isNaN(parseInt(machineId))) ? parseInt(machineId) : undefined,
        o_number:       oNumber   || undefined,
        clamp_note:     clampNote || undefined,
        cycle_time_sec: cycleTimeSec > 0 ? cycleTimeSec : undefined,
        machining_qty:  machiningQty,
        note:           note || undefined,
        creator_id:     (creatorId && !isNaN(parseInt(creatorId))) ? parseInt(creatorId) : null,
        sheet_created_at: sheetCreatedAt || null,
      }, token);
      // ツーリング保存（DBのcamelCase → DTOのsnake_caseに変換）
      await mcApi.saveTooling(mcId, toolingRows.map((t: any, i: number) => ({
        sort_order:       i,
        tool_no:          t.tool_no   ?? t.toolNo   ?? "",
        tool_name:        t.tool_name ?? t.toolName ?? undefined,
        diameter:         t.diameter  ?? undefined,
        length_offset_no: t.length_offset_no ?? t.lengthOffsetNo ?? undefined,
        dia_offset_no:    t.dia_offset_no    ?? t.diaOffsetNo    ?? undefined,
        tool_type:        t.tool_type        ?? t.toolType       ?? undefined,
        note:             t.note             ?? undefined,
        raw_program_line: t.raw_program_line ?? t.rawProgramLine ?? undefined,
      })), token);
      // ワークオフセット保存（DBのcamelCase → DTOのsnake_caseに変換）
      if (offsetRows.length > 0) {
        await mcApi.saveWorkOffsets(mcId, offsetRows.map((o: any) => ({
          g_code:   o.g_code   ?? o.gCode   ?? "",
          x_offset: o.x_offset ?? (o.xOffset != null ? Number(o.xOffset) : undefined),
          y_offset: o.y_offset ?? (o.yOffset != null ? Number(o.yOffset) : undefined),
          z_offset: o.z_offset ?? (o.zOffset != null ? Number(o.zOffset) : undefined),
          a_offset: o.a_offset ?? (o.aOffset != null ? Number(o.aOffset) : undefined),
          r_offset: o.r_offset ?? (o.rOffset != null ? Number(o.rOffset) : undefined),
          note:     o.note     ?? undefined,
        })), token);
      }
      // インデックス保存（DBのcamelCase → DTOのsnake_caseに変換）
      if (indexRows.length > 0) {
        await mcApi.saveIndexPrograms(mcId, indexRows.map((r: any, i: number) => ({
          sort_order: i,
          axis_0: r.axis_0 ?? r.axis0 ?? undefined,
          axis_1: r.axis_1 ?? r.axis1 ?? undefined,
          axis_2: r.axis_2 ?? r.axis2 ?? undefined,
          note:   r.note   ?? undefined,
        })), token);
      }
      showToast("✅ 保存しました");
      // 新規(sbMode)/リピート(sbRepeatMode)/通常: いずれも終了確認モーダルを表示
      // 新規は変更内容を「新規登録」に固定
      if (sbMode) setKanryoType("新規登録");
      setPendingBody({ savedMcId: mcId, isSbMode: sbMode });
      setShowKanryoModal(true);
    } catch (e: any) {
      const errMsg = e?.response?.data?.message ?? e?.message ?? "保存に失敗しました";
      console.error("[STEP1] handleSave error:", e?.response?.status, errMsg, e?.response?.data);
      setSaveError(errMsg);
    } finally {
      setSaving(false);
    }
  };

  // ── 終了確認OK: change_type/detail を付けて再updateしバージョンインクリ → recordへ ──
  const handleKanryoOk = async () => {
    console.log("[EDIT] handleKanryoOk", { kanryoType, kanryoDetail, pendingBody, token: token ? "あり" : "なし" });
    if (!token || !pendingBody) return;
    try {
      await mcApi.finalize(pendingBody.savedMcId, kanryoType, kanryoDetail || undefined, token);
      setShowKanryoModal(false);
      const savedId = pendingBody.savedMcId;
      const wasSbMode = pendingBody.isSbMode;
      setPendingBody(null);
      showToast(`✅ ${kanryoType}として登録しました`);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("sb_repeat_edit");
        // 新規(sbMode)の場合はsb_next_recordが既にセット済み
        // リピート(sbRepeatMode)の場合はここでセット
        if (!wasSbMode) {
          sessionStorage.setItem("sb_next_record", String(savedId));
        }
      }
      setTimeout(() => router.push(`/mc/${savedId}/record`), 800);
    } catch (e: any) {
      const errMsg = e?.response?.data?.message ?? e?.message ?? "バージョン更新に失敗";
      setSaveError(errMsg);
      setShowKanryoModal(false);
    }
  };

  const handleParseTooling = async () => {
    if (!token || !toolingText.trim()) return;
    try {
      const res = await mcApi.parseTooling(mcId, toolingText, token);
      const items = ((res as any).data ?? res).items ?? [];
      setParseResult(items);
    } catch { alert("解析に失敗しました"); }
  };

  const applyParseResult = () => {
    if (!parseResult) return;
    setToolingRows(parseResult.map((item, i) => ({
      sort_order: i, tool_no: item.tool_no, tool_name: item.tool_name ?? "",
      length_offset_no: item.length_offset_no ?? "", dia_offset_no: item.dia_offset_no ?? "",
      raw_program_line: item.raw_program_line ?? "",
    })));
    setParseResult(null);
    setToolingText("");
    showToast("ツーリングデータを取り込みました");
  };

  if (!detail) return (
    <div className="h-screen flex items-center justify-center text-slate-400">読み込み中…</div>
  );

  const d = detail;

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {/* ヘッダー */}
      <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
        <button
          onClick={() => router.push(`/mc/${mcId}`)}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
        >
          <span className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          </span>
          MC詳細
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-teal-400 font-bold text-base">MachCore</span>
        <span className="text-sm font-medium flex items-center gap-1.5">変更・登録</span>
        <span className="ml-auto">
          {isAuthenticated && operator && (
            <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
              作業中: {operator.name} {fmtElapsed(elapsed)}
            </span>
          )}
          {!isAuthenticated && (
            <span className="text-[11px] bg-slate-600 text-white px-2 py-0.5 rounded">🔒 認証待ち</span>
          )}
        </span>
      </header>

      {/* 部品情報エリア */}
      {d && (
        <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-teal-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
            <span className="text-slate-300 text-xl font-light">/</span>
            <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
            {d.part.mainModel && <>
              <span className="text-slate-300 text-xl font-light">/</span>
              <span className="text-slate-500 text-lg font-medium leading-none">{d.part.mainModel}</span>
            </>}
            <div className="flex items-center gap-2 ml-2">
              {d.machine && <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-700">{d.machine.machineCode}</span>}
              <StatusBadge status={d.status} />
              <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
            {(detail as any)?.mcProcessNo != null && <span className="font-bold text-teal-700 text-sm">工程No: {(detail as any).mcProcessNo}</span>}
            <span className="text-slate-400">|</span>
            <span>MCID: <span className="text-slate-700">{d.legacyMcid ?? d.id}</span></span>
            <span className="text-slate-400">|</span>
            <span>加工ID: <span className="text-slate-700">{d.machiningId}</span></span>
            {d.part.partId && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
          </div>
        </div>
      )}

      {/* タブナビ */}
      <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
        <button onClick={() => !(sbMode || sbRepeatMode) && router.push(`/mc/${mcId}`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 rounded-t-md transition-colors " + ((sbMode || sbRepeatMode) ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>MC詳細
        </button>
        <button onClick={() => !(sbMode || sbRepeatMode) && router.push(`/mc/${mcId}/edit`)}
          className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t-md border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white transition-colors">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>変更・登録
        </button>
        <button onClick={() => !(sbMode || sbRepeatMode) && router.push(`/mc/${mcId}/print`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + ((sbMode || sbRepeatMode) ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>段取シート
        </button>
        <button onClick={() => !(sbMode || sbRepeatMode) && router.push(`/mc/${mcId}/record`)}
          className={"px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t-md border border-b-0 transition-colors " + ((sbMode || sbRepeatMode) ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-40" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]")}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>作業記録
        </button>
      </nav>

      {/* セッションバナー */}
      {isAuthenticated && operator && (sbMode || sbRepeatMode) && (
        <div className={`${sbRepeatMode ? "bg-amber-700" : "bg-blue-700"} text-white px-5 py-2 flex items-center justify-between text-xs shrink-0`}>
          <div className="flex items-center gap-3">
            <span className="bg-blue-500 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold shrink-0">1</span>
            <span className="font-bold">{sbRepeatMode ? "段取シートバック リピート: マシニング情報を確認・編集してください" : "段取シートバック STEP1: 基本情報・ツーリング・図写真などを登録してください"}</span>
            <span className={sbRepeatMode ? "text-amber-300" : "text-blue-300"}>→ {sbRepeatMode ? "更新後、変更内容を登録してSTEP2(作業記録)へ遷移します" : "登録完了後 STEP2(作業記録)へ自動遷移します"}</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => {
                logout();
                if (typeof window !== "undefined") {
                  sessionStorage.removeItem("sb_next_record");
                  sessionStorage.removeItem("sb_sheet_log_id");
                  sessionStorage.removeItem("sb_repeat_edit");
                }
                router.push("/");
              }}
              className="text-blue-200 hover:text-white text-xs px-3 py-1 rounded border border-blue-400 hover:border-white transition-colors">
              キャンセル（中断）
            </button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-blue-700 px-4 py-1 rounded font-bold hover:bg-blue-50 disabled:opacity-50 text-sm">
              {saving ? "保存中..." : (sbRepeatMode ? "更新完了 → 変更登録・STEP2へ" : "STEP1完了 → STEP2(作業記録)へ")}
            </button>
          </div>
        </div>
      )}
      {isAuthenticated && operator && !sbMode && !sbRepeatMode && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => {
                logout();
                router.push(`/mc/${mcId}`);
              }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : sbMode ? "STEP1完了 → STEP2(作業記録)へ" : "作業完了（登録）"}
            </button>
          </div>
        </div>
      )}

            {/* ロック状態 */}
      {!isAuthenticated && detail && (
        <div className="flex-1 flex items-center justify-center bg-slate-100">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-md w-full text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-red-50 border-2 border-red-200 flex items-center justify-center mx-auto">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            <div>
              <h2 className="text-slate-700 font-bold text-lg mb-1">変更・登録 — 作業開始前</h2>
              <p className="text-slate-400 text-sm">現在のデータを確認しています。変更・登録を行うには担当者の確認（パスワード）が必要です。</p>
            </div>
            <div className="border border-slate-200 rounded-xl overflow-hidden text-sm">
              <div className="grid grid-cols-3 divide-x divide-slate-200">
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">機械</div><div className="font-bold">{detail.machine?.machineCode ?? "—"}</div></div>
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">主Oナンバ</div><div className="font-mono font-bold">{detail.oNumber ?? "—"}</div></div>
                <div className="p-2.5 text-center"><div className="text-slate-400 text-xs mb-1">サイクルタイム</div><div className="font-bold">{detail.cycleTimeSec != null ? `${Math.floor(detail.cycleTimeSec/60)} 分` : "—"}</div></div>
              </div>
              {detail.clampNote && (
                <div className="p-2.5 border-t border-slate-200 text-left"><div className="text-slate-400 text-xs mb-1">備考</div><div className="text-slate-600 text-xs">{detail.clampNote.slice(0,60)}{detail.clampNote.length > 60 ? "…" : ""}</div></div>
              )}
            </div>
            <button
              onClick={() => setAuthOpen(true)}
              className="flex items-center gap-2 px-6 py-3 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-sm transition-colors mx-auto"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              この作業を開始する（担当者確認）
            </button>
            <div className="text-xs text-slate-400">担当者の選択とパスワード確認後に編集できます</div>
          </div>
        </div>
      )}

      {/* 編集フォーム */}
      {isAuthenticated && (
        <div className="flex flex-1 overflow-hidden">
          {/* セクションタブ */}
          <div className="w-36 shrink-0 bg-white border-r border-slate-200 flex flex-col pt-2">
            {[
              ["basic",   "基本情報"],
              ["tooling", "ツーリング"],
              ["offset",  "ワークオフセット"],
              ["index",   "インデックスPG"],
              ["files",   "図・写真"],
            ].map(([k, l]) => (
              <button key={k} onClick={() => { console.log('[EDIT] セクション切替', k); setActiveSection(k as any); }}
                className={`text-left px-4 py-3 text-xs font-medium border-l-2 transition-colors ${
                  activeSection === k ? "border-teal-500 text-teal-700 bg-teal-50" : "border-transparent text-slate-500 hover:bg-slate-50"}`}>
                {l}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {saveError && (
              <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">⚠️ {saveError}</div>
            )}

            {/* 基本情報 */}
            {activeSection === "basic" && (
              <div className="max-w-2xl space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">機械</label>
                    <select value={machineId} onChange={e => { console.log("[EDIT] 機械変更", e.target.value); setMachineId(e.target.value); }}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {machines.filter(m => m.isActive).map(m => (
                        <option key={m.id} value={String(m.id)}>{m.machineCode}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">主Oナンバ</label>
                    <input value={oNumber} onChange={e => { console.log("[EDIT] 主Oナンバ変更", e.target.value); setONumber(e.target.value); }}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">クランプ</label>
                  <textarea value={clampNote} onChange={e => setClampNote(e.target.value)} rows={3}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-2">サイクルタイム/1P</label>
                  <div className="flex items-center gap-2">
                    <input type="number" min={0} value={cycleH} onChange={e => setCycleH(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">H</span>
                    <input type="number" min={0} max={59} value={cycleM} onChange={e => setCycleM(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">M</span>
                    <input type="number" min={0} max={59} value={cycleS} onChange={e => setCycleS(Number(e.target.value))}
                      className="w-16 border border-slate-300 rounded-lg px-2 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-teal-400" />
                    <span className="text-xs text-slate-400">S</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">加工個数/1サイクル</label>
                  <input type="number" min={1} value={machiningQty} onChange={e => setMachiningQty(Number(e.target.value))}
                    className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-sm text-center focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-1">備考</label>
                  <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none resize-none" />
                </div>
                {/* 作成者・作成日 */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">作成者（段取シート作成者）</label>
                    <select value={creatorId} onChange={e => setCreatorId(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                      <option value="">— 選択 —</option>
                      {users.filter(u => u.isActive).map(u => (
                        <option key={u.id} value={String(u.id)}>{u.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 block mb-1">作成日（シート作成日）</label>
                    <input type="date" value={sheetCreatedAt} onChange={e => setSheetCreatedAt(e.target.value)}
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none" />
                  </div>
                </div>
              </div>
            )}

            {/* ツーリング */}
            {activeSection === "tooling" && (
              <div className="max-w-4xl space-y-4">
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <p className="text-xs font-bold text-amber-700 mb-3">ツーリングプログラム読取り（MC専用機能）</p>
                  <textarea value={toolingText} onChange={e => setToolingText(e.target.value)}
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-amber-500","bg-amber-100"); }}
                    onDragLeave={e => { e.currentTarget.classList.remove("border-amber-500","bg-amber-100"); }}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-amber-500","bg-amber-100");
                      const f = e.dataTransfer.files[0];
                      if (f) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(f); }
                    }}
                    placeholder="ツーリングプログラムをここに貼り付け、またはファイルをドラッグ＆ドロップ..."
                    rows={6}
                    className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono focus:ring-2 focus:ring-amber-400 focus:outline-none resize-none" />
                  <div className="flex items-center gap-2 mt-2 mb-2">
                    <label className="px-3 py-1.5 bg-white border border-amber-400 text-amber-700 text-xs font-bold rounded cursor-pointer hover:bg-amber-50 transition-colors">
                      ファイルを選択
                      <input type="file" className="hidden"
                        onChange={e => {
                          const f2 = e.target.files?.[0];
                          if (f2) { const reader = new FileReader(); reader.onload = ev => setToolingText(ev.target?.result as string ?? ""); reader.readAsText(f2); e.target.value = ""; }
                        }} />
                    </label>
                    <span className="text-[10px] text-amber-600">またはテキストを貼り付け / D&D</span>
                  </div>
                  <div className="flex gap-2">
                  <button onClick={handleParseTooling}
                      className="bg-amber-600 hover:bg-amber-700 text-white text-xs px-4 py-2 rounded-lg font-bold">解析・プレビュー</button>
                    {parseResult && (
                      <button onClick={applyParseResult}
                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs px-4 py-2 rounded-lg font-bold">
                        {parseResult.length}本を取り込む
                      </button>
                    )}
                  </div>
                  {parseResult && (
                    <div className="mt-3 text-xs text-amber-700">{parseResult.length}本の工具を検出しました。「取り込む」で確定します。</div>
                  )}
                </div>

                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ツーリングリスト ({toolingRows.length}レコード)</span>
                    <button onClick={() => setToolingRows(prev => [...prev, { sort_order: (prev.length + 1) * 10, tool_no: "", tool_name: "", length_offset_no: "", dia_offset_no: "" }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <div className="overflow-hidden">
                    <table className="w-full text-xs table-fixed">
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>{["","N","工具","T","H","D","D値","SUB","コメント","順番",""].map(h =>
                          <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                      </thead>
                    </table>
                    <div className="overflow-y-auto max-h-[55vh]">
                    <table className="w-full text-xs table-fixed">
                    <tbody>
                      {toolingRows.map((t, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-1 py-1 w-20">
                            <div className="flex gap-0.5">
                              <button onClick={() => {
                                if (i === 0) return;
                                setToolingRows(r => {
                                  const a = [...r];
                                  const so1 = a[i-1].sort_order; const so2 = a[i].sort_order;
                                  [a[i-1], a[i]] = [a[i], a[i-1]];
                                  a[i-1] = {...a[i-1], sort_order: so1}; a[i] = {...a[i], sort_order: so2};
                                  return a;
                                });
                              }} disabled={i===0} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↑</button>
                              <button onClick={() => {
                                if (i === toolingRows.length - 1) return;
                                setToolingRows(r => {
                                  const a = [...r];
                                  const so1 = a[i].sort_order; const so2 = a[i+1].sort_order;
                                  [a[i], a[i+1]] = [a[i+1], a[i]];
                                  a[i] = {...a[i], sort_order: so1}; a[i+1] = {...a[i+1], sort_order: so2};
                                  return a;
                                });
                              }} disabled={i===toolingRows.length-1} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↓</button>
                              <button onClick={() => {
                                setToolingRows(r => {
                                  const a = [...r];
                                  const newSo = a[i].sort_order;
                                  a.splice(i + 1, 0, { sort_order: newSo + 5, tool_no: "", tool_name: "", length_offset_no: "", dia_offset_no: "" });
                                  return a;
                                });
                              }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                            </div>
                          </td>
                          <td className="px-2 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}
                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}
                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.t_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_no: e.target.value} : x))}
                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}
                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}
                            className="w-12 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.diameter != null ? String(t.diameter) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, diameter: e.target.value === "" ? null : Number(e.target.value)} : x))}
                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" step="0.001" /></td>
                          <td className="px-2 py-1"><input value={t.sub_pg_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sub_pg_no: e.target.value} : x))}
                            className="w-16 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.note ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><input value={t.sort_order != null ? String(t.sort_order) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sort_order: e.target.value === "" ? 0 : Number(e.target.value)} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" /></td>
                          <td className="px-2 py-1"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                    </table>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ワークオフセット */}
            {activeSection === "offset" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ワークオフセット ({offsetRows.length}件)</span>
                    <button onClick={() => setOffsetRows(prev => [...prev, { g_code: `G${54 + prev.length}` }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["G座標","X","Y","Z","A","R",""].map(h =>
                        <th key={h} className="px-2 py-2 text-center font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {offsetRows.map((o, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1"><input value={o.g_code ?? o.gCode ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, g_code: e.target.value} : x))}
                            className="w-14 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          {["x_offset","y_offset","z_offset","a_offset","r_offset"].map(k => (
                            <td key={k} className="px-2 py-1"><input type="number" step="0.001"
                              value={o[k] ?? o[k.replace("_offset", "Offset")] ?? ""}
                              onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                              className="w-20 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                          ))}
                          <td className="px-2 py-1"><button onClick={() => setOffsetRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* インデックスプログラム */}
            {activeSection === "index" && (
              <div className="max-w-3xl">
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">インデックスプログラム ({indexRows.length}件)</span>
                    <button onClick={() => setIndexRows(prev => [...prev, { sort_order: prev.length, axis_0: "", axis_1: "", axis_2: "" }])}
                      className="text-xs text-teal-600 font-bold">+ 追加</button>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-teal-50">
                      <tr>{["No.","第0軸","第1軸","第2軸","備考",""].map(h =>
                        <th key={h} className="px-2 py-2 text-left font-bold text-teal-700 border-b border-teal-100">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {indexRows.map((p, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-2 py-1 text-center text-slate-400">{i+1}</td>
                          {["axis_0","axis_1","axis_2"].map(k => (
                            <td key={k} className="px-2 py-1"><input value={p[k] ?? p[k.replace("_","").replace("axis",k==="axis_0"?"axis0":k==="axis_1"?"axis1":"axis2")] ?? ""}
                              onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                              className="w-40 border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          ))}
                          <td className="px-2 py-1"><input value={p.note ?? ""}
                            onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                            className="w-32 border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-2 py-1"><button onClick={() => setIndexRows(r => r.filter((_,j) => j !== i))}
                            className="text-red-400 hover:text-red-600 text-xs">削除</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 図・写真 */}
            {activeSection === "files" && (
              <div className="max-w-3xl space-y-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <p className="text-xs font-bold text-slate-600 mb-3">写真・図のアップロード</p>
                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-teal-400 transition-colors"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-teal-400","bg-teal-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-teal-400","bg-teal-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const f = e.dataTransfer.files[0];
                      if (f) handleFileUpload(f, "PHOTO");
                    }}>
                    <p className="text-slate-400 text-sm mb-3">ファイルをここにドラッグ＆ドロップ</p>
                    <div className="flex items-center justify-center gap-3">
                      <label className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        写真を選択
                        <input ref={photoInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "PHOTO"); e.target.value = ""; } }} />
                      </label>
                      <label className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-lg cursor-pointer transition-colors">
                        図を選択
                        <input ref={scanInputRef} type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "DRAWING"); e.target.value = ""; } }} />
                      </label>
                    </div>
                    {fileUploading && <p className="text-xs text-teal-600 mt-2 animate-pulse">アップロード中...</p>}
                    {fileUploadMsg && <p className="text-xs mt-2 font-bold text-slate-600">{fileUploadMsg}</p>}
                    <p className="text-[10px] text-slate-400 mt-2">すべてのファイル形式に対応（写真・図・PDF等）</p>
                  </div>
                </div>
                {/* 📷 写真セクション */}
                  {files.filter((f: any) => f.file_type === "PHOTO").length > 0 && (
                    <div className="mb-5">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold text-white bg-teal-600 px-2.5 py-0.5 rounded-full">📷 写真</span>
                        <span className="text-xs text-slate-400">{files.filter((f: any) => f.file_type === "PHOTO").length}枚</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {files.filter((f: any) => f.file_type === "PHOTO").map((f: any) => (
                          <div key={f.id} className="bg-white rounded-xl border-2 border-teal-300 overflow-hidden shadow-sm">
                            <div className="aspect-square bg-teal-50 flex items-center justify-center overflow-hidden">
                              <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                                alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                                onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                            </div>
                            <div className="px-2 py-1.5 flex items-center justify-between bg-teal-50 border-t border-teal-200">
                              <p className="text-[11px] text-teal-800 font-bold truncate flex-1">{f.stored_name ?? f.original_name}</p>
                              <button onClick={async () => {
                                  if (!token || !window.confirm("削除しますか？")) return;
                                  await mcFilesApi.delete(mcId, f.id, token);
                                  const r = await mcApi.listFiles(mcId);
                                  setFiles((r as any).data ?? []);
                                }}
                                className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0 font-bold">✕</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* 📐 図セクション */}
                  {files.filter((f: any) => f.file_type === "DRAWING").length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold text-white bg-purple-600 px-2.5 py-0.5 rounded-full">📐 図</span>
                        <span className="text-xs text-slate-400">{files.filter((f: any) => f.file_type === "DRAWING").length}枚</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {files.filter((f: any) => f.file_type === "DRAWING").map((f: any) => (
                          <div key={f.id} className="bg-white rounded-xl border-2 border-purple-300 overflow-hidden shadow-sm">
                            <div className="aspect-square bg-purple-50 flex items-center justify-center overflow-hidden">
                              <img src={`/api/mc/${mcId}/files/${f.id}/thumb`}
                                alt={f.original_name} className="w-full h-full object-contain" loading="lazy"
                                onError={e2 => { (e2.target as HTMLImageElement).style.display = "none"; }} />
                            </div>
                            <div className="px-2 py-1.5 flex items-center justify-between bg-purple-50 border-t border-purple-200">
                              <p className="text-[11px] text-purple-800 font-bold truncate flex-1">{f.stored_name ?? f.original_name}</p>
                              <button onClick={async () => {
                                  if (!token || !window.confirm("削除しますか？")) return;
                                  await mcFilesApi.delete(mcId, f.id, token);
                                  const r = await mcApi.listFiles(mcId);
                                  setFiles((r as any).data ?? []);
                                }}
                                className="text-[10px] text-red-400 hover:text-red-600 ml-1 shrink-0 font-bold">✕</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {files.filter((f: any) => f.file_type === "PHOTO" || f.file_type === "DRAWING").length === 0 && (
                    <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">ファイルがありません</div>
                  )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 終了確認モーダル（リピートフロー: 変更種別選択 + バージョンインクリ）*/}
      {showKanryoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="bg-slate-800 px-5 py-3">
              <h2 className="text-base font-bold text-white">終了確認 — 変更内容を記録</h2>
              <p className="text-xs text-slate-400 mt-0.5">この変更をどの種類として登録しますか？バージョンが更新されます。</p>
            </div>
            <div className="p-5 space-y-4">
              {/* 新規登録の場合は固定表示 */}
              {pendingBody?.isSbMode ? (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                  <p className="text-sm font-bold text-blue-700 mb-1">変更種別: 新規登録</p>
                  <p className="text-xs text-blue-600">バージョン 0.0001 → 1.0001（整数部+1）</p>
                </div>
              ) : (
                <div>
                  <label className="text-xs font-bold text-slate-500 block mb-2">作業種別 *</label>
                  <div className="grid grid-cols-3 gap-2">
                    {["大変更","小変更","追加","修正","削除","訂正"].map(t => (
                      <button key={t} type="button"
                        onClick={() => setKanryoType(t)}
                        className={`py-2 rounded-lg text-sm font-bold border transition-colors ${
                          kanryoType === t
                            ? t === "大変更" ? "bg-red-600 text-white border-red-600"
                              : "bg-teal-600 text-white border-teal-600"
                            : "bg-white text-slate-600 border-slate-300 hover:border-teal-400"
                        }`}>
                        {t}
                      </button>
                    ))}
                  </div>
                  {kanryoType === "大変更" && (
                    <p className="text-xs text-red-600 mt-1.5 font-bold">⚠️ 大変更: バージョンの整数部が+1（例: 1.0001 → 2.0001）</p>
                  )}
                  {kanryoType !== "大変更" && (
                    <p className="text-xs text-teal-600 mt-1.5">小変更系: 100分の1位が+0.01（例: 1.0001 → 1.0101）</p>
                  )}
                </div>
              )}
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1.5">内容（任意）</label>
                <textarea value={kanryoDetail} onChange={e => setKanryoDetail(e.target.value)}
                  rows={2} placeholder={pendingBody?.isSbMode ? "登録内容の補足（任意）" : "変更の詳細内容を入力..."}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none" />
              </div>
            </div>
            <div className="px-5 pb-5 flex gap-3">
              <button onClick={handleKanryoOk}
                className="flex-1 bg-teal-600 hover:bg-teal-700 text-white font-bold py-3 rounded-xl text-sm transition-colors">
                OK — 作業記録へ
              </button>
              <button onClick={() => {
                  setShowKanryoModal(false);
                  if (pendingBody?.isSbMode) {
                    // 新規: sessionStorageをクリアしてダッシュボードへ
                    if (typeof window !== "undefined") {
                      sessionStorage.removeItem("sb_next_record");
                      sessionStorage.removeItem("sb_sheet_log_id");
                    }
                    logout();
                  } else {
                    logout();
                  }
                  router.push("/");
                }}
                className="px-5 py-3 border border-slate-300 rounded-xl text-sm text-slate-600 hover:bg-slate-50">
                スキップ（作業記録なし）
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 認証モーダル */}
      {authOpen && (
        <AuthModal isOpen={true} ncProgramId={mcId} mcProgramId={mcId} sessionType="edit" onSuccess={() => setAuthOpen(false)} onCancel={() => setAuthOpen(false)} />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}
