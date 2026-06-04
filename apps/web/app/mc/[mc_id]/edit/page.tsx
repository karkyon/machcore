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

  // PGエディタ
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  const pgContentRef        = React.useRef<string>("");
  const pgMatchPositionsRef = React.useRef<number[]>([]);
  const pgMatchIndexRef     = React.useRef<number>(0);
  const pgMatchCountRef     = React.useRef<number>(0);
  const pgEditorSearchRef   = React.useRef<string>("");
  const pgEditorReplaceRef  = React.useRef<string>("");
  // Undo/Redo スタック
  const pgUndoStack      = React.useRef<string[]>([]);
  const pgRedoStack      = React.useRef<string[]>([]);
  const pgLastPush       = React.useRef<number>(0);
  const [pgEditorOpen,    setPgEditorOpen]    = useState(false);
  const [pgMatchCount,    setPgMatchCount]    = useState(0);
  const [pgMatchIndex,    setPgMatchIndex]    = useState(0);
  const [pgMatchPositions, setPgMatchPositions] = useState<number[]>([]);
  const [pgContent,       setPgContent]       = useState<string>("");
  const [pgOrigName,      setPgOrigName]      = useState<string>("");
  const [pgLoading,       setPgLoading]       = useState(false);
  const [pgSaving,        setPgSaving]        = useState(false);
  const [pgEditorSearch,  setPgEditorSearch]  = useState("");
  const [pgDarkMode,      setPgDarkMode]      = useState(false);
  const [pgEditorReplace, setPgEditorReplace] = useState("");
  const [pgCreatedBy,     setPgCreatedBy]     = useState<string>("");
  const [pgUpdatedAtDisp, setPgUpdatedAtDisp] = useState<string>("");
  const [pgUploadModalOpen, setPgUploadModalOpen] = useState(false);
  const [pgUploading, setPgUploading] = useState(false);

  // 写真/図 複数プレビュー選択
  const [photoPreviewFiles,   setPhotoPreviewFiles]   = useState<{file: File; url: string; selected: boolean}[]>([]);
  const [drawingPreviewFiles, setDrawingPreviewFiles] = useState<{file: File; url: string; selected: boolean}[]>([]);
  const [photoPreviewOpen,    setPhotoPreviewOpen]    = useState(false);
  const [drawingPreviewOpen,  setDrawingPreviewOpen]  = useState(false);
  const [bulkUploading,       setBulkUploading]       = useState(false);

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
      setOffsetRows((d.workOffsets ?? []).map((o: any) => ({
        g_code:   o.gCode   ?? o.g_code   ?? "",
        x_offset: o.xOffset != null ? String(o.xOffset) : (o.x_offset != null ? String(o.x_offset) : ""),
        y_offset: o.yOffset != null ? String(o.yOffset) : (o.y_offset != null ? String(o.y_offset) : ""),
        z_offset: o.zOffset != null ? String(o.zOffset) : (o.z_offset != null ? String(o.z_offset) : ""),
        a_offset: o.aOffset != null ? String(o.aOffset) : (o.a_offset != null ? String(o.a_offset) : ""),
        r_offset: o.rOffset != null ? String(o.rOffset) : (o.r_offset != null ? String(o.r_offset) : ""),
        note:     o.note    ?? "",
      })));
      // PG作成者・更新日時
      setPgCreatedBy(d.pgCreatedBy ? String(d.pgCreatedBy) : "");
      setPgUpdatedAtDisp(d.pgUpdatedAt ? new Date(d.pgUpdatedAt).toLocaleString("ja-JP") : "");
      setIndexRows((d.indexPrograms ?? []).map((p: any) => ({
        sort_order: p.sortOrder ?? p.sort_order ?? 0,
        axis_0:     p.axis0    ?? p.axis_0     ?? "",
        axis_1:     p.axis1    ?? p.axis_1     ?? "",
        axis_2:     p.axis2    ?? p.axis_2     ?? "",
        note:       p.note     ?? "",
      })));
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

  // ────────── PG検索ヘルパー ──────────
  const pgSetContent = (val: string) => {
    pgContentRef.current = val;
    setPgContent(val);
    console.log("[PGEditor] pgSetContent len="+val.length);
  };
  const pgSetMatch = (positions: number[], idx: number) => {
    pgMatchPositionsRef.current = positions;
    pgMatchIndexRef.current = idx;
    pgMatchCountRef.current = positions.length;
    setPgMatchPositions(positions);
    setPgMatchIndex(idx);
    setPgMatchCount(positions.length);
    console.log("[PGEditor] pgSetMatch count="+positions.length+" idx="+idx+" pos="+(positions[idx]??-1));
  };
  const pgClearMatch = () => {
    pgMatchPositionsRef.current = [];
    pgMatchIndexRef.current = 0;
    pgMatchCountRef.current = 0;
    setPgMatchPositions([]); setPgMatchIndex(0); setPgMatchCount(0);
  };
  const pgFullReset = (content: string, origName?: string) => {
    const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    pgContentRef.current = normalized;
    pgUndoStack.current = [];
    pgRedoStack.current = [];
    pgLastPush.current = 0;
    pgEditorSearchRef.current = "";
    pgEditorReplaceRef.current = "";
    pgMatchPositionsRef.current = [];
    pgMatchIndexRef.current = 0;
    pgMatchCountRef.current = 0;
    setPgContent(normalized);
    setPgMatchPositions([]); setPgMatchIndex(0); setPgMatchCount(0);
    setPgEditorSearch(""); setPgEditorReplace("");
    setPgDarkMode(false);
    if (origName !== undefined) setPgOrigName(origName);
    console.log("[PGEditor] pgFullReset len="+normalized.length+" origName="+(origName??""));
  };

  // textareaの指定文字オフセット位置へスクロール（中央表示）
  const scrollToMatch = (ta: HTMLTextAreaElement, pos: number) => {
    if (!pgContentRef.current) { console.warn("[PGEditor] scrollToMatch: empty ref skip"); return; }
    const text   = pgContentRef.current.slice(0, pos);
    const lines  = (text.match(/\n/g) || []).length;
    const style  = getComputedStyle(ta);
    const lh     = parseFloat(style.lineHeight) || 18;
    const pt     = parseFloat(style.paddingTop)  || 0;
    ta.scrollTop = Math.max(0, lines * lh + pt - ta.clientHeight / 2);
    console.log("[PGEditor] scrollToMatch pos="+pos+" line="+lines+" scrollTop="+ta.scrollTop);
  };

  const execSearchQuery = (q: string, fromIndex = 0) => {
    if (!q || !pgTextareaRef.current) return;
    const ta   = pgTextareaRef.current;
    const text = pgContentRef.current;
    try {
      const esc  = q.replace(new RegExp("[-.*+?^${}()|\\[\\]\\\\]", "g"), "\\$&");
      const regex = new RegExp(esc, "gi");
      const positions: number[] = [];
      let m: RegExpExecArray | null;
      while ((m = regex.exec(text)) !== null) positions.push(m.index);
      if (positions.length === 0) { pgClearMatch(); return; }
      // fromIndex を超える最初のマッチ（なければ先頭に折り返し）
      let idx = positions.findIndex(p => p >= fromIndex);
      if (idx === -1) idx = 0;
      pgSetMatch(positions, idx);
      // Reactのrender完了後にsetSelectionRangeを呼ぶ（controlled textareaはrender前はDOMが古い）
      const _pos = positions[idx];
      const _len = q.length;
      requestAnimationFrame(() => {
        const ta2 = pgTextareaRef.current;
        if (!ta2) return;
        ta2.focus();
        ta2.setSelectionRange(_pos, _pos + _len);
        scrollToMatch(ta2, _pos);
        console.log("[PGEditor] rAF setSelectionRange pos="+_pos+" end="+(_pos+_len)+" taValueLen="+ta2.value.length);
      });
    } catch {}
  };

  // 検索ボタン押下: 連続クリックで次のマッチへ
  const handleSearchBtn = () => {
    const q = pgEditorSearchRef.current;
    if (!q) return;
    const ta = pgTextareaRef.current;
    if (!ta) return;
    console.log("[PGEditor] handleSearchBtn q="+q+" contentLen="+pgContentRef.current.length+" matches="+pgMatchPositionsRef.current.length+" idx="+pgMatchIndexRef.current);
    if (pgMatchPositionsRef.current.length === 0) {
      execSearchQuery(q, 0);
    } else {
      const positions = pgMatchPositionsRef.current;
      const nextIdx = (pgMatchIndexRef.current + 1) % positions.length;
      pgMatchIndexRef.current = nextIdx;
      setPgMatchIndex(nextIdx);
      const _pos2 = positions[nextIdx];
      const _len2 = q.length;
      console.log("[PGEditor] next nextIdx="+nextIdx+" pos="+_pos2);
      requestAnimationFrame(() => {
        const ta2 = pgTextareaRef.current;
        if (!ta2) return;
        ta2.focus();
        ta2.setSelectionRange(_pos2, _pos2 + _len2);
        scrollToMatch(ta2, _pos2);
      });
    }
  };

  // Undo: スタックから1つ戻す
  const pgUndo = () => {
    console.log("[PGEditor] Undo undoStack="+pgUndoStack.current.length+" redoStack="+pgRedoStack.current.length);
    if (pgUndoStack.current.length === 0) { console.warn("[PGEditor] Undo stack empty"); return; }
    pgRedoStack.current.push(pgContentRef.current);
    const prev = pgUndoStack.current.pop()!;
    pgSetContent(prev);
    pgClearMatch();
    requestAnimationFrame(() => { pgTextareaRef.current?.focus(); });
  };

  // Redo: スタックから1つ進める
  const pgRedo = () => {
    console.log("[PGEditor] Redo undoStack="+pgUndoStack.current.length+" redoStack="+pgRedoStack.current.length);
    if (pgRedoStack.current.length === 0) { console.warn("[PGEditor] Redo stack empty"); return; }
    pgUndoStack.current.push(pgContentRef.current);
    const next = pgRedoStack.current.pop()!;
    pgSetContent(next);
    pgClearMatch();
    requestAnimationFrame(() => { pgTextareaRef.current?.focus(); });
  };

  // PGファイルをUSBから登録（単体 or フォルダ）
  const handlePgUploadFromUSB = async (mode: "file" | "folder") => {
    if (!token) { showToast("❌ 認証が必要です"); return; }
    setPgUploadModalOpen(false);
    setPgUploading(true);
    // machiningId を detail から取得
    const machId = String(detail?.machiningId ?? "");
    try {
      if (mode === "file") {
        // 単体ファイル: showOpenFilePicker
        const [fileHandle] = await (window as any).showOpenFilePicker({ multiple: false });
        const file: File = await fileHandle.getFile();
        // ファイル名を加工IDにリネーム（拡張子はそのまま）
        const ext = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")) : "";
        const newName = machId + ext;
        const renamedFile = new File([file], newName, { type: file.type });
        const fd = new FormData();
        fd.append("file", renamedFile);
        fd.append("is_folder_upload", "false");
        const res = await fetch(`/api/mc/${mcId}/files/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
        const refreshed = await mcApi.findOne(mcId);
        setDetail((refreshed as any).data ?? refreshed);
        showToast(`✅ PGファイルを登録しました（${newName}）`);
      } else {
        // フォルダ: showDirectoryPicker → 中のファイルを全アップロード
        const dirHandle = await (window as any).showDirectoryPicker({ mode: "read" });
        let count = 0;
        for await (const [, fh] of dirHandle.entries()) {
          if (fh.kind !== "file") continue;
          const file: File = await fh.getFile();
          const fd = new FormData();
          fd.append("file", file);
          fd.append("is_folder_upload", "true");
          const res = await fetch(`/api/mc/${mcId}/files/upload`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: fd,
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          count++;
        }
        if (count === 0) { showToast("⚠️ フォルダ内にファイルが見つかりません"); return; }
        setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
        const refreshed = await mcApi.findOne(mcId);
        setDetail((refreshed as any).data ?? refreshed);
        showToast(`✅ PGフォルダを登録しました（${count}ファイル、加工ID: ${machId}フォルダとして保存）`);
      }
    } catch (e: any) {
      if (e.name === "AbortError") { setPgUploading(false); return; }
      showToast("❌ アップロード失敗: " + (e.message || "不明なエラー"));
    } finally {
      setPgUploading(false);
    }
  };

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
        pg_created_by:  (pgCreatedBy && !isNaN(parseInt(pgCreatedBy))) ? parseInt(pgCreatedBy) : null,
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
      sort_order:       item.sort_order       ?? (i + 1) * 10,
      tool_no:          item.tool_no          ?? "",
      t_no:             item.t_no             ?? "",
      tool_name:        item.tool_name        ?? "",
      length_offset_no: item.length_offset_no ?? "",
      dia_offset_no:    item.dia_offset_no    ?? "",
      diameter:         item.diameter         ?? null,
      d_value_content:  item.d_value_content  ?? "",
      sub_pg_no:        item.sub_pg_no        ?? "",
      tool_type:        item.tool_type        ?? "",
      note:             item.note             ?? "",
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
      {isAuthenticated && (sbMode || sbRepeatMode) && (
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
      {isAuthenticated && !sbMode && !sbRepeatMode && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator?.name ?? "（作業中）"}</span>
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

                {/* PG情報 */}
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">プログラム情報</span>
                    <button onClick={async () => {
                      setPgLoading(true);
                      try {
                        const r = await mcApi.getPgFile(mcId);
                        const data = (r as any).data ?? r;
                        console.log("[PGEditor] PGファイル読込完了 raw="+(data.content?.length??0)+" name="+(data.originalName??""));
                        pgFullReset(data.content ?? "", data.originalName ?? "");
                        setPgEditorOpen(true);
                      } catch { showToast("PGファイルが見つかりません"); }
                      finally { setPgLoading(false); }
                    }} disabled={pgLoading}
                      className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                    </button>
                    <button onClick={() => {
                      if (!token) { showToast("❌ 認証が必要です"); return; }
                      if (!("showOpenFilePicker" in window)) { showToast("❌ Chrome/Edgeが必要です"); return; }
                      setPgUploadModalOpen(true);
                    }} disabled={pgUploading}
                      className="px-3 py-1 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgUploading ? "⏳ 登録中..." : "📥 USBから登録"}
                    </button>
                  </div>
                  <div className="px-4 py-3 grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">PG作成者</label>
                      <select value={pgCreatedBy} onChange={e => setPgCreatedBy(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 focus:outline-none">
                        <option value="">— 選択 —</option>
                        {users.filter(u => u.isActive).map(u => (
                          <option key={u.id} value={String(u.id)}>{u.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 block mb-1">PG更新日時</label>
                      <div className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-slate-50 text-slate-600 font-mono">
                        {pgUpdatedAtDisp || "—"}
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5">※ PGアップロード時に自動更新</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ツーリング */}
            {activeSection === "tooling" && (
              <div className="space-y-4 max-w-[1188px]">

                {/* ツーリングリスト */}
                <div className="bg-white rounded-xl border border-slate-200">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-600">ツーリングリスト ({toolingRows.length}レコード)</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={async () => {
                          if (!token) { alert("認証が必要です"); return; }
                          try {
                            await mcApi.saveTooling(mcId, toolingRows.map((t, idx) => ({
                              sort_order:       t.sort_order       ?? idx,
                              tool_no:          t.tool_no          ?? "",
                              t_no:             t.t_no             ?? undefined,
                              tool_name:        t.tool_name        ?? undefined,
                              length_offset_no: t.length_offset_no ?? undefined,
                              dia_offset_no:    t.dia_offset_no    ?? undefined,
                              diameter:         t.diameter         ?? undefined,
                              d_value_content:  t.d_value_content  ?? undefined,
                              sub_pg_no:        t.sub_pg_no        ?? undefined,
                              tool_type:        t.tool_type        ?? undefined,
                              note:             t.note             ?? undefined,
                              raw_program_line: t.raw_program_line ?? undefined,
                            })), token);
                            showToast("✅ ツーリングを保存しました");
                          } catch { showToast("❌ 保存に失敗しました"); }
                        }}
                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                        ✓ ツーリングを保存
                      </button>
                      <button onClick={() => setToolingRows(prev => [...prev, { sort_order: (prev.length + 1) * 10, tool_no: "", tool_name: "", length_offset_no: "", dia_offset_no: "" }])}
                        className="text-xs text-teal-600 font-bold">+ 追加</button>
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-[55vh]">
                    <table className="text-xs w-full border-collapse">
                      <colgroup>
                        <col style={{width:"72px"}}/>
                        <col style={{width:"90px"}}/>
                        <col style={{width:"210px"}}/>
                        <col style={{width:"54px"}}/>
                        <col style={{width:"54px"}}/>
                        <col style={{width:"54px"}}/>
                        <col style={{width:"60px"}}/>
                        <col style={{width:"60px"}}/>
                        <col style={{width:"420px"}}/>
                        <col style={{width:"60px"}}/>
                        <col style={{width:"54px"}}/>
                      </colgroup>
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>
                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">N</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">工具</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">T</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">H</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">D</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">D値</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">SUB</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">コメント</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">順番</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                        </tr>
                      </thead>
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
                          <td className="px-1 py-1"><input value={t.tool_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_no: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.tool_name ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, tool_name: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.t_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_no: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.length_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, length_offset_no: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.dia_offset_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, dia_offset_no: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.diameter != null ? String(t.diameter) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, diameter: e.target.value === "" ? null : Number(e.target.value)} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" step="0.001" /></td>
                          <td className="px-1 py-1"><input value={t.sub_pg_no ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sub_pg_no: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.note ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                          <td className="px-1 py-1"><input value={t.sort_order != null ? String(t.sort_order) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sort_order: e.target.value === "" ? 0 : Number(e.target.value)} : x))}
                            className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" /></td>
                          <td className="px-1 py-1 text-center"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}
                            className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">削除</button></td>
                        </tr>
                      ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* プログラム読取り（リストの下） */}
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
                    <div className="mt-3 text-xs text-amber-700 font-bold">{parseResult.length}本の工具を検出しました。内容を確認して「取り込む」で確定します。</div>
                  )}
                </div>

                {/* 解析結果プレビューテーブル */}
                {parseResult && parseResult.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden">
                    <div className="bg-amber-100 px-4 py-2 border-b border-amber-200 flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-800">📋 解析プレビュー（{parseResult.length}件）— 取り込み前に確認</span>
                      <button
                        onClick={() => setParseResult(null)}
                        className="text-xs text-amber-600 hover:text-amber-800 font-bold px-2 py-0.5 rounded hover:bg-amber-200">
                        ✕ 閉じる
                      </button>
                    </div>
                    <div className="overflow-y-auto max-h-[40vh]">
                      <table className="text-xs w-auto border-collapse">
                        <colgroup>
                          <col style={{width:"36px"}} />
                          <col style={{width:"70px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"180px"}} />
                          <col style={{width:"50px"}} />
                          <col style={{width:"50px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"60px"}} />
                          <col style={{width:"180px"}} />
                          <col style={{width:"60px"}} />
                        </colgroup>
                        <thead className="sticky top-0 z-10 bg-amber-200">
                          <tr>
                            <th className="px-2 py-1.5 text-center text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">#</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">N</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">T</th>
                            <th className="px-2 py-1.5 text-left text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">工具名</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">H</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">D</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">D値</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">SUB</th>
                            <th className="px-2 py-1.5 text-left text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">コメント</th>
                            <th className="px-2 py-1.5 text-amber-900 font-bold border-b border-amber-300 whitespace-nowrap">順番</th>
                          </tr>
                        </thead>
                        <tbody>
                          {parseResult.map((item, i) => (
                            <tr key={i} className={i % 2 === 0 ? "bg-white hover:bg-amber-50" : "bg-amber-50 hover:bg-amber-100"}>
                              <td className="px-2 py-1 text-center text-slate-400 font-mono">{i + 1}</td>
                              <td className="px-2 py-1 font-mono font-bold text-teal-700">{item.tool_no ?? "—"}</td>
                              <td className="px-2 py-1 font-mono text-slate-700">{item.t_no ?? "—"}</td>
                              <td className="px-2 py-1 text-slate-800 max-w-[180px] truncate" title={item.tool_name ?? ""}>{item.tool_name || "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-slate-600">{item.length_offset_no ?? "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-slate-600">{item.dia_offset_no ?? "—"}</td>
                              <td className="px-2 py-1 text-center text-slate-600">{item.d_value_content || "—"}</td>
                              <td className="px-2 py-1 font-mono text-center text-indigo-600">{item.sub_pg_no || "—"}</td>
                              <td className="px-2 py-1 text-slate-500 max-w-[180px] truncate" title={item.note ?? ""}>{item.note || "—"}</td>
                              <td className="px-2 py-1 text-center text-slate-400 font-mono">{item.sort_order}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="px-4 py-2 border-t border-amber-200 flex justify-end">
                      <button
                        onClick={() => {
                          if (!parseResult) return;
                          setToolingRows(parseResult.map((item, i) => ({
                            sort_order:       item.sort_order       ?? (i + 1) * 10,
                            tool_no:          item.tool_no          ?? "",
                            t_no:             item.t_no             ?? "",
                            tool_name:        item.tool_name        ?? "",
                            length_offset_no: item.length_offset_no ?? "",
                            dia_offset_no:    item.dia_offset_no    ?? "",
                            diameter:         item.diameter         ?? null,
                            d_value_content:  item.d_value_content  ?? "",
                            sub_pg_no:        item.sub_pg_no        ?? "",
                            tool_type:        item.tool_type        ?? "",
                            note:             item.note             ?? "",
                            raw_program_line: item.raw_program_line ?? "",
                          })));
                          setParseResult(null);
                          setToolingText("");
                          showToast("ツーリングデータを取り込みました");
                        }}
                        className="bg-teal-600 hover:bg-teal-700 text-white text-xs px-6 py-2 rounded-lg font-bold">
                        ✅ {parseResult.length}本を取り込む
                      </button>
                    </div>
                  </div>
                )}

              </div>
            )}

            {/* ワークオフセット */}
            {activeSection === "offset" && (
              <div className="max-w-[816px]">
                <div className="bg-white rounded-xl border border-slate-200">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between rounded-t-xl">
                    <span className="text-xs font-bold text-slate-600">ワークオフセット ({offsetRows.length}レコード)</span>
                    <div className="flex items-center gap-2">
                      <button onClick={async () => {
                        if (!token) { showToast("❌ 認証が必要です"); return; }
                        try {
                          await mcApi.saveWorkOffsets(mcId, offsetRows.map((o: any) => ({
                            g_code:   o.g_code   ?? o.gCode   ?? "",
                            x_offset: o.x_offset != null && o.x_offset !== "" ? Number(o.x_offset) : undefined,
                            y_offset: o.y_offset != null && o.y_offset !== "" ? Number(o.y_offset) : undefined,
                            z_offset: o.z_offset != null && o.z_offset !== "" ? Number(o.z_offset) : undefined,
                            a_offset: o.a_offset != null && o.a_offset !== "" ? Number(o.a_offset) : undefined,
                            r_offset: o.r_offset != null && o.r_offset !== "" ? Number(o.r_offset) : undefined,
                            note:     o.note     ?? undefined,
                          })), token);
                          showToast("✅ ワークオフセットを保存しました");
                        } catch { showToast("❌ 保存に失敗しました"); }
                      }}
                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                        ✓ ワークオフセットを保存
                      </button>
                      <button onClick={() => setOffsetRows(prev => [...prev, { g_code: `G${54 + prev.length}` }])}
                        className="text-xs text-teal-600 font-bold">+ 追加</button>
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-[55vh]">
                    <table className="text-xs w-full border-collapse">
                      <colgroup>
                        <col style={{width:"72px"}}/>
                        <col style={{width:"70px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"100px"}}/>
                        <col style={{width:"120px"}}/>
                        <col style={{width:"54px"}}/>
                      </colgroup>
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>
                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">G</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">X</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">Y</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">Z</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">A / C</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">R / B</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">備考</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {offsetRows.map((o, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-1 py-1">
                              <div className="flex gap-0.5">
                                <button onClick={() => {
                                  if (i === 0) return;
                                  setOffsetRows(r => {
                                    const a = [...r]; [a[i-1], a[i]] = [a[i], a[i-1]]; return a;
                                  });
                                }} disabled={i===0} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↑</button>
                                <button onClick={() => {
                                  if (i === offsetRows.length - 1) return;
                                  setOffsetRows(r => {
                                    const a = [...r]; [a[i], a[i+1]] = [a[i+1], a[i]]; return a;
                                  });
                                }} disabled={i===offsetRows.length-1} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↓</button>
                                <button onClick={() => {
                                  setOffsetRows(r => {
                                    const a = [...r];
                                    a.splice(i + 1, 0, { g_code: "" });
                                    return a;
                                  });
                                }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                              </div>
                            </td>
                            <td className="px-1 py-1"><input value={o.g_code ?? o.gCode ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, g_code: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                            {["x_offset","y_offset","z_offset","a_offset","r_offset"].map(k => (
                              <td key={k} className="px-1 py-1"><input type="number" step="0.001"
                                value={o[k] ?? ""}
                                onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, [k]: e.target.value} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                            ))}
                            <td className="px-1 py-1"><input value={o.note ?? ""} onChange={e => setOffsetRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                            <td className="px-1 py-1 text-center">
                              <button onClick={() => setOffsetRows(r => r.filter((_,j) => j !== i))}
                                className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">
                                削除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* インデックスプログラム */}
            {activeSection === "index" && (
              <div className="max-w-[1016px]">
                <div className="bg-white rounded-xl border border-slate-200">
                  <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between rounded-t-xl">
                    <span className="text-xs font-bold text-slate-600">インデックスプログラム ({indexRows.length}レコード)</span>
                    <div className="flex items-center gap-2">
                      <button onClick={async () => {
                        if (!token) { showToast("❌ 認証が必要です"); return; }
                        try {
                          await mcApi.saveIndexPrograms(mcId, indexRows.map((r: any, idx: number) => ({
                            sort_order: idx,
                            axis_0: r.axis_0 ?? r.axis0 ?? undefined,
                            axis_1: r.axis_1 ?? r.axis1 ?? undefined,
                            axis_2: r.axis_2 ?? r.axis2 ?? undefined,
                            note:   r.note   ?? undefined,
                          })), token);
                          showToast("✅ インデックスPGを保存しました");
                        } catch { showToast("❌ 保存に失敗しました"); }
                      }}
                        className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                        ✓ インデックスPGを保存
                      </button>
                      <button onClick={() => setIndexRows(prev => [...prev, { sort_order: prev.length, axis_0: "", axis_1: "", axis_2: "" }])}
                        className="text-xs text-teal-600 font-bold">+ 追加</button>
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-[55vh]">
                    <table className="text-xs w-full border-collapse">
                      <colgroup>
                        <col style={{width:"72px"}}/>
                        <col style={{width:"90px"}}/>
                        <col style={{width:"240px"}}/>
                        <col style={{width:"240px"}}/>
                        <col style={{width:"200px"}}/>
                        <col style={{width:"120px"}}/>
                        <col style={{width:"54px"}}/>
                      </colgroup>
                      <thead className="bg-teal-50 sticky top-0 z-10">
                        <tr>
                          <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">STEP/N</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第0軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第1軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">第2軸</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">備考</th>
                          <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {indexRows.map((p, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                            <td className="px-1 py-1">
                              <div className="flex gap-0.5">
                                <button onClick={() => {
                                  if (i === 0) return;
                                  setIndexRows(r => {
                                    const a = [...r]; [a[i-1], a[i]] = [a[i], a[i-1]]; return a;
                                  });
                                }} disabled={i===0} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↑</button>
                                <button onClick={() => {
                                  if (i === indexRows.length - 1) return;
                                  setIndexRows(r => {
                                    const a = [...r]; [a[i], a[i+1]] = [a[i+1], a[i]]; return a;
                                  });
                                }} disabled={i===indexRows.length-1} className="text-[10px] px-1 py-0.5 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-30">↓</button>
                                <button onClick={() => {
                                  setIndexRows(r => {
                                    const a = [...r];
                                    a.splice(i + 1, 0, { sort_order: i + 1, axis_0: "", axis_1: "", axis_2: "" });
                                    return a;
                                  });
                                }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                              </div>
                            </td>
                            <td className="px-1 py-1"><input value={p.axis_0 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_0: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_0 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_0: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_1 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_1: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.axis_2 ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, axis_2: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs" /></td>
                            <td className="px-1 py-1"><input value={p.note ?? ""} onChange={e => setIndexRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                              className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                            <td className="px-1 py-1 text-center">
                              <button onClick={() => setIndexRows(r => r.filter((_,j) => j !== i))}
                                className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">
                                削除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {activeSection === "files" && (
              <div className="max-w-3xl space-y-4">
                {/* 写真アップロード */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-slate-600">📷 写真のアップロード</p>
                    <div className="flex gap-2">
                      <label className="px-3 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors">
                        複数選択・フォルダ
                        <input type="file" accept="image/*" multiple className="hidden"
                          onChange={e => {
                            const files2 = Array.from(e.target.files ?? []);
                            if (!files2.length) return;
                            setPhotoPreviewFiles(files2.map(f => ({
                              file: f,
                              url: URL.createObjectURL(f),
                              selected: true,
                            })));
                            setPhotoPreviewOpen(true);
                            e.target.value = "";
                          }} />
                      </label>
                      <label className="px-3 py-1.5 bg-teal-100 hover:bg-teal-200 text-teal-700 text-xs font-bold rounded-lg cursor-pointer border border-teal-300 transition-colors">
                        1枚追加
                        <input type="file" accept="image/*" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "PHOTO"); e.target.value = ""; } }} />
                      </label>
                    </div>
                  </div>
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center text-xs text-slate-400"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-teal-400","bg-teal-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-teal-400","bg-teal-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-teal-400","bg-teal-50");
                      const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"));
                      if (droppedFiles.length === 1) { handleFileUpload(droppedFiles[0], "PHOTO"); return; }
                      if (droppedFiles.length > 1) {
                        setPhotoPreviewFiles(droppedFiles.map(f => ({ file: f, url: URL.createObjectURL(f), selected: true })));
                        setPhotoPreviewOpen(true);
                      }
                    }}>
                    D&Dでも追加できます（複数対応）
                  </div>
                  {fileUploading && <p className="text-xs text-teal-600 mt-2 animate-pulse">アップロード中...</p>}
                  {fileUploadMsg && <p className="text-xs mt-2 font-bold text-slate-600">{fileUploadMsg}</p>}
                </div>

                {/* 図アップロード */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-slate-600">📐 図のアップロード</p>
                    <div className="flex gap-2">
                      <label className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors">
                        複数選択・フォルダ
                        <input type="file" multiple className="hidden"
                          onChange={e => {
                            const files2 = Array.from(e.target.files ?? []);
                            if (!files2.length) return;
                            setDrawingPreviewFiles(files2.map(f => ({
                              file: f,
                              url: f.type.startsWith("image/") ? URL.createObjectURL(f) : "",
                              selected: true,
                            })));
                            setDrawingPreviewOpen(true);
                            e.target.value = "";
                          }} />
                      </label>
                      <label className="px-3 py-1.5 bg-purple-100 hover:bg-purple-200 text-purple-700 text-xs font-bold rounded-lg cursor-pointer border border-purple-300 transition-colors">
                        1枚追加
                        <input type="file" className="hidden"
                          onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileUpload(f, "DRAWING"); e.target.value = ""; } }} />
                      </label>
                    </div>
                  </div>
                  <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center text-xs text-slate-400"
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-purple-400","bg-purple-50"); }}
                    onDragLeave={e => e.currentTarget.classList.remove("border-purple-400","bg-purple-50")}
                    onDrop={e => {
                      e.preventDefault();
                      e.currentTarget.classList.remove("border-purple-400","bg-purple-50");
                      const droppedFiles = Array.from(e.dataTransfer.files);
                      if (droppedFiles.length === 1) { handleFileUpload(droppedFiles[0], "DRAWING"); return; }
                      if (droppedFiles.length > 1) {
                        setDrawingPreviewFiles(droppedFiles.map(f => ({
                          file: f,
                          url: f.type.startsWith("image/") ? URL.createObjectURL(f) : "",
                          selected: true,
                        })));
                        setDrawingPreviewOpen(true);
                      }
                    }}>
                    D&Dでも追加できます（複数対応）
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

      {/* PGアップロードモーダル（単体 or フォルダ） */}
      {pgUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-800 text-base">📥 PGファイル登録方法を選択</h3>
              <button onClick={() => setPgUploadModalOpen(false)} className="text-slate-400 hover:text-slate-600 text-xl font-bold">✕</button>
            </div>
            <p className="text-xs text-slate-500">
              加工ID: <span className="font-mono font-bold text-teal-700">{detail?.machiningId}</span> として登録します
            </p>
            <div className="space-y-3">
              <button onClick={() => handlePgUploadFromUSB("file")}
                className="w-full px-4 py-4 bg-teal-50 hover:bg-teal-100 border-2 border-teal-300 rounded-xl text-left transition-colors">
                <div className="font-bold text-teal-800 mb-1">📄 単体ファイル</div>
                <div className="text-xs text-teal-600">拡張子なしのプログラムファイル（テキスト形式）を1つ選択。ファイル名は加工IDに自動リネームされます。</div>
                <div className="text-[10px] text-teal-400 mt-1 font-mono">例: O6000 → {detail?.machiningId}</div>
              </button>
              <button onClick={() => handlePgUploadFromUSB("folder")}
                className="w-full px-4 py-4 bg-amber-50 hover:bg-amber-100 border-2 border-amber-300 rounded-xl text-left transition-colors">
                <div className="font-bold text-amber-800 mb-1">📁 フォルダ単位</div>
                <div className="text-xs text-amber-600">メインPG + サブPGを含むフォルダを選択。フォルダ内の全ファイルが加工IDフォルダとして保存されます。</div>
                <div className="text-[10px] text-amber-400 mt-1 font-mono">例: 1846.WPD/ → {detail?.machiningId}/</div>
              </button>
            </div>
            <p className="text-[10px] text-slate-400 text-center">Chrome / Edge のみ対応（HTTPS必須）</p>
          </div>
        </div>
      )}

      {/* PGエディタモーダル */}
      {pgEditorOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-2">
          <div style={{width:"90vw", height:"95vh", maxWidth:"1400px"}} className={`${pgDarkMode ? "bg-slate-900" : "bg-white"} rounded-2xl shadow-2xl flex flex-col`}>

            {/* ヘッダー */}
            <div className={`flex items-center justify-between px-5 py-3 border-b shrink-0 rounded-t-2xl ${pgDarkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-slate-50"}`}>
              <div className="flex items-center gap-3">
                <span className="text-slate-400 text-lg">📄</span>
                <span className={`font-bold ${pgDarkMode ? "text-slate-100" : "text-slate-800"}`}>PGエディタ</span>
                {pgOrigName && <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2.5 py-1 rounded-lg border">{pgOrigName}</span>}
                {detail?.machiningId && (
                  <span className="text-xs text-slate-400 font-mono">
                    📁 mc_files/pg/{detail.machiningId}/{pgOrigName || "—"}
                  </span>
                )}
                <span className="text-xs text-slate-400">{pgContent.split('\n').length}行 / {pgContent.length}文字</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={async () => {
                  try {
                    const [fileHandle] = await (window as any).showOpenFilePicker({ multiple: false });
                    const file = await fileHandle.getFile();
                    const text = await file.text();
                    pgFullReset(text, file.name);
                    showToast("✅ ファイルを読み込みました");
                  } catch (e: any) {
                    if (e.name !== 'AbortError') showToast("❌ 読み込み失敗: " + (e.message || "不明なエラー"));
                  }
                }} className="px-3 py-1.5 text-xs font-bold bg-slate-600 hover:bg-slate-700 text-white rounded-lg transition-colors">
                  📂 USB/ファイルから読み込み
                </button>
                <button onClick={async () => {
                  if (!('showSaveFilePicker' in window)) {
                    showToast("❌ 非対応ブラウザです。Chrome/Edgeをご使用ください");
                    return;
                  }
                  try {
                    const fileHandle = await (window as any).showSaveFilePicker({
                      suggestedName: pgOrigName || "program.min",
                      types: [{ description: 'NCプログラム', accept: { 'text/plain': ['.min','.spf','.mpf','.nc','.txt'] } }],
                    });
                    const writable = await fileHandle.createWritable();
                    await writable.write(pgContent);
                    await writable.close();
                    showToast("✅ USB/指定先に保存しました");
                  } catch (e: any) {
                    if (e.name === 'AbortError') return;
                    showToast("❌ 保存失敗: " + (e.message || "USBが接続されているか確認してください"));
                  }
                }} className="px-3 py-1.5 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors">
                  💾 USB/指定先に保存
                </button>
                <button onClick={async () => {
                  if (!token) { showToast("❌ 認証が必要です"); return; }
                  setPgSaving(true);
                  try {
                    const res = await fetch(`/api/mc/${mcId}/pg-content`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({ content: pgContentRef.current, original_name: pgOrigName }),
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                    showToast("✅ PGファイルをサーバに保存しました");
                  } catch (e: any) {
                    showToast("❌ サーバ保存に失敗: " + (e.message || ""));
                  } finally { setPgSaving(false); }
                }} disabled={pgSaving}
                  className="px-3 py-1.5 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors disabled:opacity-50">
                  {pgSaving ? "⏳ 保存中..." : "✓ サーバに保存"}
                </button>
                <button onClick={pgUndo} title="Undo (Ctrl+Z)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40"
                  disabled={pgUndoStack.current.length === 0}>
                  ↩
                </button>
                <button onClick={pgRedo} title="Redo (Ctrl+Y)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40"
                  disabled={pgRedoStack.current.length === 0}>
                  ↪
                </button>
                <button onClick={() => setPgDarkMode(m => !m)} title="表示切替"
                  className={`px-2.5 py-1.5 text-xs font-bold rounded-lg border transition-colors ${
                    pgDarkMode
                      ? "bg-slate-700 hover:bg-slate-600 text-slate-200 border-slate-600"
                      : "bg-white hover:bg-slate-50 text-slate-700 border-slate-300"
                  }`}>
                  {pgDarkMode ? "☀" : "🌙"}
                </button>
                <button onClick={() => {
                  setPgEditorOpen(false);
                  pgContentRef.current = "";
                  pgUndoStack.current = [];
                  pgRedoStack.current = [];
                  pgMatchPositionsRef.current = [];
                  pgMatchIndexRef.current = 0;
                  pgMatchCountRef.current = 0;
                  pgEditorSearchRef.current = "";
                  pgEditorReplaceRef.current = "";
                  console.log("[PGEditor] closed - all refs cleared");
                }}
                  className="px-2.5 py-1.5 text-sm font-bold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg" title="閉じる">
                  ✕
                </button>
              </div>
            </div>

            {/* 検索・置換バー */}
            <div className={`flex items-center gap-2 px-5 py-2 border-b shrink-0 ${pgDarkMode ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-slate-50"}`}>
              <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg px-2 py-1 shrink-0" style={{width:"220px"}}>
                <span className="text-slate-400 text-xs shrink-0">🔍</span>
                <input
                  value={pgEditorSearch}
                  onChange={e => {
                    const q = e.target.value;
                    pgEditorSearchRef.current = q;
                    setPgEditorSearch(q);
                    if (!q) { pgClearMatch(); }
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Escape') {
                      setPgEditorSearch('');
                      pgClearMatch();
                    }
                  }}
                  placeholder="キーワード入力"
                  className="text-xs font-mono w-full focus:outline-none min-w-0"
                />
                {pgMatchCount > 0 && (
                  <span className="text-[10px] text-teal-600 font-bold whitespace-nowrap shrink-0">{pgMatchIndex + 1}/{pgMatchCount}</span>
                )}
                {pgEditorSearch && pgMatchCount === 0 && (
                  <span className="text-[10px] text-red-500 font-bold whitespace-nowrap shrink-0">なし</span>
                )}
              </div>
              <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg px-2 py-1 shrink-0" style={{width:"180px"}}>
                <span className="text-slate-400 text-xs shrink-0">↩</span>
                <input value={pgEditorReplace} onChange={e => { pgEditorReplaceRef.current = e.target.value; setPgEditorReplace(e.target.value); }}
                  placeholder="置換後" className="text-xs font-mono w-full focus:outline-none min-w-0" />
              </div>
              <button onClick={handleSearchBtn}
                className="px-3 py-1.5 text-xs bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-bold shrink-0">🔍 検索</button>
                     <button onClick={() => {
                const sq = pgEditorSearchRef.current;
                const rq = pgEditorReplaceRef.current;
                if (!sq || pgMatchPositionsRef.current.length === 0) return;
                const cur = pgContentRef.current;
                const pos = pgMatchPositionsRef.current[pgMatchIndexRef.current];
                console.log("[PGEditor] 1件置換クリック sq="+sq+" rq="+rq+" pos="+pos+" matchCount="+pgMatchPositionsRef.current.length+" matchIdx="+pgMatchIndexRef.current);
                if (pos === undefined || pos < 0 || pos + sq.length > cur.length) {
                  console.error("[PGEditor] 1件置換 pos無効 pos="+pos+" curLen="+cur.length);
                  return;
                }
                const context = cur.slice(Math.max(0,pos-15), pos+sq.length+15);
                console.log("[PGEditor] 置換前コンテキスト: ["+context+"]");
                pgUndoStack.current.push(cur);
                pgRedoStack.current = [];
                const newContent = cur.slice(0, pos) + rq + cur.slice(pos + sq.length);
                pgSetContent(newContent);
                showToast("1件置換しました");
                console.log("[PGEditor] 置換後コンテキスト: ["+newContent.slice(Math.max(0,pos-15), pos+rq.length+15)+"]");
                execSearchQuery(sq, pos + rq.length);
              }} className="px-3 py-1.5 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg font-bold border border-blue-300 shrink-0">置換</button>
              <button onClick={() => {
                const sq = pgEditorSearchRef.current;
                const rq = pgEditorReplaceRef.current;
                if (!sq) return;
                const cur = pgContentRef.current;
                const count = cur.split(sq).length - 1;
                console.log("[PGEditor] 全置換クリック sq="+sq+" rq="+rq+" count="+count);
                if (count === 0) { showToast("見つかりません"); return; }
                pgUndoStack.current.push(cur);
                pgRedoStack.current = [];
                const newContent = cur.split(sq).join(rq);
                pgSetContent(newContent);
                showToast(count + "件を全置換しました");
                pgClearMatch();
              }} className="px-3 py-1.5 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-bold shrink-0">全置換</button>
              <div className="ml-auto text-[10px] text-slate-400 shrink-0">Ctrl+S: 保存 | Esc: 解除</div>
            </div>

            {/* エディタ本体 */}
            <div className="flex-1 overflow-hidden">
              <textarea
                ref={pgTextareaRef}
                value={pgContent}
                onChange={e => {
                  const newVal = e.target.value;
                  if (newVal === "" && pgContentRef.current.length > 10) {
                    console.warn("[PGEditor] onChange empty guard refLen="+pgContentRef.current.length);
                    return;
                  }
                  const now = Date.now();
                  // 500ms 以上経過したらスタックに積む（細かい入力は1エントリにまとめる）
                  if (now - pgLastPush.current > 500) {
                    pgUndoStack.current.push(pgContentRef.current);
                    if (pgUndoStack.current.length > 200) pgUndoStack.current.shift();
                    pgRedoStack.current = [];
                    pgLastPush.current = now;
                  }
                  pgSetContent(newVal);
                }}
                onKeyDown={e => {
                  // Ctrl+Z: Undo
                  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
                    e.preventDefault();
                    pgUndo();
                    return;
                  }
                  // Ctrl+Y / Ctrl+Shift+Z: Redo
                  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
                    e.preventDefault();
                    pgRedo();
                    return;
                  }
                  // Ctrl+S: サーバ保存
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    if (!token || pgSaving) return;
                    setPgSaving(true);
                    fetch(`/api/mc/${mcId}/pg-content`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({ content: pgContentRef.current, original_name: pgOrigName }),
                    }).then(r => {
                      if (!r.ok) throw new Error();
                      setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                      showToast("✅ Ctrl+S: 保存しました");
                    }).catch(() => showToast("❌ 保存失敗")).finally(() => setPgSaving(false));
                  }
                }}
                className={`w-full h-full p-5 font-mono text-sm resize-none focus:outline-none leading-relaxed ${
                  pgDarkMode
                    ? "text-green-300 bg-slate-900"
                    : "text-slate-800 bg-white border border-slate-200"
                }`}
                spellCheck={false}
              />
            </div>

            {/* フッター */}
            <div className={`px-5 py-2 border-t rounded-b-2xl shrink-0 flex items-center gap-4 text-[10px] ${pgDarkMode ? "border-slate-700 bg-slate-800 text-slate-400" : "border-slate-200 bg-slate-50 text-slate-400"}`}>
              <span>💡 Ctrl+S: サーバ保存</span>
              <span>|</span>
              <span>📂 USB/ファイルから読み込み → 確認後「サーバに保存」</span>
              <span>|</span>
              <span>💾 USB/指定先に保存: エディタ内容をUSBに直接書き出し</span>
            </div>
          </div>
        </div>
      )}

      {/* 写真 アルバムプレビュー選択モーダル */}
      {photoPreviewOpen && photoPreviewFiles.length > 0 && (() => {
        const selectedCount = photoPreviewFiles.filter(f => f.selected).length;
        const [expandedIdx, setExpandedIdx] = React.useState<number|null>(null);
        return (
          <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-3">
            <div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{width:"95vw",height:"95vh"}}>
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-slate-50 rounded-t-2xl shrink-0">
                <div className="flex items-center gap-3">
                  <span className="text-lg">📷</span>
                  <span className="font-bold text-slate-800">写真の選択・取り込み</span>
                  <span className="bg-teal-100 text-teal-700 text-xs font-bold px-2.5 py-1 rounded-full">{selectedCount}/{photoPreviewFiles.length}枚 選択中</span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setPhotoPreviewFiles(f => f.map(x => ({ ...x, selected: true })))}
                    className="text-xs text-teal-600 font-bold px-3 py-1.5 rounded-lg hover:bg-teal-50 border border-teal-300">全選択</button>
                  <button onClick={() => setPhotoPreviewFiles(f => f.map(x => ({ ...x, selected: false })))}
                    className="text-xs text-slate-500 font-bold px-3 py-1.5 rounded-lg hover:bg-slate-100 border border-slate-300">全解除</button>
                  <button onClick={async () => {
                    const selected = photoPreviewFiles.filter(f => f.selected);
                    if (!selected.length) { showToast("1枚以上選択してください"); return; }
                    setBulkUploading(true);
                    let ok = 0;
                    for (const item of selected) {
                      try { await handleFileUpload(item.file, "PHOTO"); ok++; } catch {}
                    }
                    setBulkUploading(false);
                    photoPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                    setPhotoPreviewOpen(false); setPhotoPreviewFiles([]);
                    showToast(`✅ ${ok}枚の写真を保存しました（加工ID連番で命名）`);
                  }} disabled={bulkUploading || !selectedCount}
                    className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-bold rounded-xl disabled:opacity-50 transition-colors">
                    {bulkUploading ? "⏳ 保存中..." : `📥 選択した${selectedCount}枚を取り込む`}
                  </button>
                  <button onClick={() => {
                    photoPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                    setPhotoPreviewOpen(false); setPhotoPreviewFiles([]);
                  }} className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">✕ キャンセル</button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-5 bg-slate-900">
                <div className="grid gap-4" style={{gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))"}}>
                  {photoPreviewFiles.map((item, i) => (
                    <div key={i} className={`relative rounded-xl overflow-hidden transition-all group
                      ${item.selected ? "ring-4 ring-teal-400 shadow-xl" : "ring-2 ring-slate-600 opacity-70 hover:opacity-100"}`}>
                      <div className="absolute top-2 left-2 z-10"
                        onClick={e => { e.stopPropagation(); setPhotoPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x)); }}>
                        <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center font-bold text-sm
                          ${item.selected ? "bg-teal-500 border-teal-500 text-white" : "bg-black/40 border-white/60 text-transparent"}`}>✓</div>
                      </div>
                      <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={e => { e.stopPropagation(); setExpandedIdx(i); }}
                          className="w-7 h-7 rounded-full bg-black/60 border border-white/40 text-white text-xs flex items-center justify-center">⛶</button>
                      </div>
                      <div className="aspect-square bg-slate-800 overflow-hidden cursor-pointer"
                        onClick={() => setPhotoPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x))}>
                        <img src={item.url} alt={item.file.name} className="w-full h-full object-cover hover:scale-105 transition-transform duration-200" />
                      </div>
                      <div className="px-3 py-2 bg-slate-800 border-t border-slate-700">
                        <p className="text-[11px] text-slate-200 font-medium truncate">{item.file.name}</p>
                        <p className="text-[10px] text-slate-400">{(item.file.size / 1024).toFixed(0)} KB</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {expandedIdx !== null && (
                <div className="absolute inset-0 z-20 bg-black/95 flex items-center justify-center rounded-2xl"
                  onClick={() => setExpandedIdx(null)}>
                  <button className="absolute top-4 right-4 text-white text-2xl bg-black/50 w-10 h-10 rounded-full flex items-center justify-center">✕</button>
                  <button disabled={expandedIdx === 0} className="absolute left-4 text-white text-3xl bg-black/50 w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-30"
                    onClick={e => { e.stopPropagation(); setExpandedIdx(i => i! > 0 ? i! - 1 : i); }}>‹</button>
                  <img src={photoPreviewFiles[expandedIdx].url} alt="" className="max-w-[85vw] max-h-[85vh] object-contain rounded-lg" onClick={e => e.stopPropagation()} />
                  <button disabled={expandedIdx === photoPreviewFiles.length - 1} className="absolute right-4 text-white text-3xl bg-black/50 w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-30"
                    onClick={e => { e.stopPropagation(); setExpandedIdx(i => i! < photoPreviewFiles.length - 1 ? i! + 1 : i); }}>›</button>
                  <div className="absolute bottom-4 text-slate-300 text-xs text-center">
                    <p>{photoPreviewFiles[expandedIdx].file.name}</p>
                    <p className="text-slate-500">{expandedIdx + 1} / {photoPreviewFiles.length}</p>
                  </div>
                </div>
              )}
              <div className="px-5 py-2 border-t border-slate-200 bg-slate-50 rounded-b-2xl shrink-0 text-[10px] text-slate-400">
                💡 クリックで選択/解除 | ⛶で拡大 | 保存ファイル名: 加工ID-連番（例: 5629-3.jpg）
              </div>
            </div>
          </div>
        );
      })()}

      {/* 図 アルバムプレビュー選択モーダル */}
      {drawingPreviewOpen && drawingPreviewFiles.length > 0 && (() => {
        const selectedCount2 = drawingPreviewFiles.filter(f => f.selected).length;
        const [expandedIdx2, setExpandedIdx2] = React.useState<number|null>(null);
        return (
          <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-3">
            <div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{width:"95vw",height:"95vh"}}>
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-slate-50 rounded-t-2xl shrink-0">
                <div className="flex items-center gap-3">
                  <span className="text-lg">📐</span>
                  <span className="font-bold text-slate-800">図の選択・取り込み</span>
                  <span className="bg-purple-100 text-purple-700 text-xs font-bold px-2.5 py-1 rounded-full">{selectedCount2}/{drawingPreviewFiles.length}件 選択中</span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setDrawingPreviewFiles(f => f.map(x => ({ ...x, selected: true })))}
                    className="text-xs text-purple-600 font-bold px-3 py-1.5 rounded-lg hover:bg-purple-50 border border-purple-300">全選択</button>
                  <button onClick={() => setDrawingPreviewFiles(f => f.map(x => ({ ...x, selected: false })))}
                    className="text-xs text-slate-500 font-bold px-3 py-1.5 rounded-lg hover:bg-slate-100 border border-slate-300">全解除</button>
                  <button onClick={async () => {
                    const selected = drawingPreviewFiles.filter(f => f.selected);
                    if (!selected.length) { showToast("1件以上選択してください"); return; }
                    setBulkUploading(true);
                    let ok = 0;
                    for (const item of selected) {
                      try { await handleFileUpload(item.file, "DRAWING"); ok++; } catch {}
                    }
                    setBulkUploading(false);
                    drawingPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                    setDrawingPreviewOpen(false); setDrawingPreviewFiles([]);
                    showToast(`✅ ${ok}件の図を保存しました（加工ID連番で命名）`);
                  }} disabled={bulkUploading || !selectedCount2}
                    className="px-5 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold rounded-xl disabled:opacity-50 transition-colors">
                    {bulkUploading ? "⏳ 保存中..." : `📥 選択した${selectedCount2}件を取り込む`}
                  </button>
                  <button onClick={() => {
                    drawingPreviewFiles.forEach(f => URL.revokeObjectURL(f.url));
                    setDrawingPreviewOpen(false); setDrawingPreviewFiles([]);
                  }} className="px-4 py-2 bg-slate-200 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-300">✕ キャンセル</button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-5 bg-slate-900">
                <div className="grid gap-4" style={{gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))"}}>
                  {drawingPreviewFiles.map((item, i) => (
                    <div key={i} className={`relative rounded-xl overflow-hidden transition-all group
                      ${item.selected ? "ring-4 ring-purple-400 shadow-xl" : "ring-2 ring-slate-600 opacity-70 hover:opacity-100"}`}>
                      <div className="absolute top-2 left-2 z-10"
                        onClick={e => { e.stopPropagation(); setDrawingPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x)); }}>
                        <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center font-bold text-sm
                          ${item.selected ? "bg-purple-500 border-purple-500 text-white" : "bg-black/40 border-white/60 text-transparent"}`}>✓</div>
                      </div>
                      {item.url && (
                        <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={e => { e.stopPropagation(); setExpandedIdx2(i); }}
                            className="w-7 h-7 rounded-full bg-black/60 border border-white/40 text-white text-xs flex items-center justify-center">⛶</button>
                        </div>
                      )}
                      <div className="aspect-square bg-slate-800 overflow-hidden flex items-center justify-center cursor-pointer"
                        onClick={() => setDrawingPreviewFiles(f => f.map((x,j) => j===i ? {...x, selected: !x.selected} : x))}>
                        {item.url
                          ? <img src={item.url} alt={item.file.name} className="w-full h-full object-cover hover:scale-105 transition-transform duration-200" />
                          : <div className="text-center"><div className="text-5xl mb-2">📄</div><div className="text-xs text-slate-300">{item.file.name.split('.').pop()?.toUpperCase()}</div></div>
                        }
                      </div>
                      <div className="px-3 py-2 bg-slate-800 border-t border-slate-700">
                        <p className="text-[11px] text-slate-200 font-medium truncate">{item.file.name}</p>
                        <p className="text-[10px] text-slate-400">{(item.file.size / 1024).toFixed(0)} KB</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {expandedIdx2 !== null && drawingPreviewFiles[expandedIdx2]?.url && (
                <div className="absolute inset-0 z-20 bg-black/95 flex items-center justify-center rounded-2xl"
                  onClick={() => setExpandedIdx2(null)}>
                  <button className="absolute top-4 right-4 text-white text-2xl bg-black/50 w-10 h-10 rounded-full flex items-center justify-center">✕</button>
                  <button disabled={expandedIdx2 === 0} className="absolute left-4 text-white text-3xl bg-black/50 w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-30"
                    onClick={e => { e.stopPropagation(); setExpandedIdx2(i => i! > 0 ? i! - 1 : i); }}>‹</button>
                  <img src={drawingPreviewFiles[expandedIdx2].url} alt="" className="max-w-[85vw] max-h-[85vh] object-contain rounded-lg" onClick={e => e.stopPropagation()} />
                  <button disabled={expandedIdx2 === drawingPreviewFiles.length - 1} className="absolute right-4 text-white text-3xl bg-black/50 w-12 h-12 rounded-full flex items-center justify-center disabled:opacity-30"
                    onClick={e => { e.stopPropagation(); setExpandedIdx2(i => i! < drawingPreviewFiles.length - 1 ? i! + 1 : i); }}>›</button>
                  <div className="absolute bottom-4 text-slate-300 text-xs text-center">
                    <p>{drawingPreviewFiles[expandedIdx2].file.name}</p>
                    <p className="text-slate-500">{expandedIdx2 + 1} / {drawingPreviewFiles.length}</p>
                  </div>
                </div>
              )}
              <div className="px-5 py-2 border-t border-slate-200 bg-slate-50 rounded-b-2xl shrink-0 text-[10px] text-slate-400">
                💡 クリックで選択/解除 | ⛶で拡大 | 保存ファイル名: 加工ID-連番（例: 5629-3.jpg）
              </div>
            </div>
          </div>
        );
      })()}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-50">{toast}</div>
      )}
    </div>
  );
}
