"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useState, useCallback, useRef } from "react";
import { ncApi, machinesApi, filesApi, usersApi, NcDetail, Machine, UpdateNcBody, UserInfo } from "@/lib/api";
import { toJstDateString } from "@/lib/dateUtils";
import { isAgentOnline, agentPickAndUpload, agentCheckUsbTarget, agentAutoUpload, translateAgentError } from "@/lib/upload-agent";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";
import { NcPartHeader } from "@/components/nc/NcPartHeader";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";
import ApprovalModal from "@/components/shared/ApprovalModal";
import ProgramFileViewer from "@/components/shared/ProgramFileViewer";
import { useLanguage } from "@/lib/i18n/LanguageContext";

const KANRYO_TYPE_KEYS: Record<string, string> = {
  "大変更": "ncEditUi.typeMajorChange", "小変更": "ncEditUi.typeMinorChange", "追加": "ncEditUi.typeAdd",
  "修正": "ncEditUi.typeFix", "削除": "ncEditUi.typeDelete", "訂正": "ncEditUi.typeCorrection",
};

export default function NcEditPage() {
  const { t: tr } = useLanguage();
  const { nc_id } = useParams();
  const router    = useRouter();
  const ncId      = Number(nc_id);

  // ── 段取シートバック(sbMode=新規STEP1 / sbRepeatMode=リピート編集) — MC側と同一仕様 ──
  const [sbMode, setSbMode] = useState(false);
  const [sbRepeatMode, setSbRepeatMode] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === parseInt(String(nc_id))) setSbMode(true);
      const r = sessionStorage.getItem("sb_repeat_edit");
      if (r && parseInt(r) === parseInt(String(nc_id))) setSbRepeatMode(true);
    }
  }, [nc_id]);
  // [v068] 段取シートバックが正規にSTEP2(作業記録)へ引き継がれたかを追跡する。
  const sbFlowCompletedRef = useRef(false);

  const [detail,    setDetail]    = useState<NcDetail | null>(null);
  const [approvalModalOpen, setApprovalModalOpen] = useState(false); // [v095]
  const [machines,  setMachines]  = useState<Machine[]>([]);
  const [users,     setUsers]     = useState<UserInfo[]>([]); // [v096]
  const [creatorId, setCreatorId] = useState<string>(""); // [v096]
  const [sheetCreatedAt, setSheetCreatedAt] = useState<string>(""); // [v096]
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
  // [v101] 掴代(専用フィールド)
  const [clampAllowance, setClampAllowance] = useState("");
  // 加工リスト(MC側ツーリングと同等)
  const [toolingRows, setToolingRows] = useState<any[]>([]);
  const [toolingSaveMsg, setToolingSaveMsg] = useState<string | null>(null);
  // [加工リストマスタ選択化] 旧Access(t_d_Shave1/Shave2/Chip/Holder)相当の
  // 候補一覧を取得し、加工(加/工)・形状（チップ）・ホルダーをドロップダウン選択にする。
  const [toolMasters, setToolMasters] = useState<{ shave1: string[]; shave2: string[]; chip: string[]; holder: string[] }>({ shave1: [], shave2: [], chip: [], holder: [] });
  useEffect(() => {
    Promise.all(
      (["shave1", "shave2", "chip", "holder"] as const).map(cat =>
        fetch(`/api/admin/nc-tool-master/${cat}`).then(r => r.json()).catch(() => [])
      )
    ).then(([shave1, shave2, chip, holder]) => {
      setToolMasters({
        shave1: (shave1 ?? []).filter((x: any) => x.isActive).map((x: any) => x.name),
        shave2: (shave2 ?? []).filter((x: any) => x.isActive).map((x: any) => x.name),
        chip:   (chip   ?? []).filter((x: any) => x.isActive).map((x: any) => x.name),
        holder: (holder ?? []).filter((x: any) => x.isActive).map((x: any) => x.name),
      });
    }).catch(() => {});
  }, []);
  // 既存データに現在の値が候補一覧に無い場合でも消えないよう、常に候補+現在値の和集合を選択肢にする。
  const withCurrent = (master: string[], current: string) =>
    current && !master.includes(current) ? [...master, current] : master;

  // 変更検知（オレンジ枠用）
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const markDirty = (field: string) => setDirty(prev => new Set(prev).add(field));

  // [v112] 終了確認モーダル(変更種別選択 + 一時保存) — MC側と同一仕様
  const [showKanryoModal, setShowKanryoModal] = useState(false);
  const [kanryoType,   setKanryoType]   = useState("小変更");
  const [kanryoDetail, setKanryoDetail] = useState("");

  // ── [離脱時未保存警告] 既存のdirty(Set)をそのまま「未保存変更あり」判定に利用する。
  //    タブ切替・ダッシュボードへ等のSPA内遷移で、保存前に離脱しようとした場合に
  //    確認ダイアログを出し、キャンセルされたら遷移を中止する。
  const guardedNavigate = (path: string) => {
    if (dirty.size > 0 && !window.confirm(tr("ncEdit.unsavedChangesConfirm", "保存されていない変更があります。このまま移動すると変更内容は失われます。よろしいですか？"))) return;
    router.push(path);
  };

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

  // ── [仮登録破棄] アンマウント/離脱時クリーンアップから常に最新のdetailを
  //    参照できるようrefで追従させる。registrationCompletedRefは「作業完了（登録）」
  //    (finalize)が正規に完了したことを示し、trueの間は離脱時破棄処理をスキップする。
  const detailRef = useRef(detail);
  useEffect(() => { detailRef.current = detail; }, [detail]);
  const registrationCompletedRef = useRef(false);

  // ── [v115] 終了確認モーダル(showKanryoModal)が開いたまま=OK/一時保存/キャンセル
  //    いずれも押さずに離脱した場合、DBのstatusがCHANGINGのまま固着してしまうため、
  //    change_type="不明"で自動finalizeし、変更理由未入力のまま離脱したことを記録に残す
  //    (MC側 mc/[mc_id]/edit/page.tsx と同一仕様)。
  const showKanryoModalRef = useRef(false);
  useEffect(() => { showKanryoModalRef.current = showKanryoModal; }, [showKanryoModal]);
  const tokenRef = useRef(token);
  useEffect(() => { tokenRef.current = token; }, [token]);
  // sbMode/sbRepeatMode(段取シートバック)の最新値もrefで追従させる — MC側と同一仕様。
  const sbModeRef = useRef(sbMode);
  const sbRepeatModeRef = useRef(sbRepeatMode);
  useEffect(() => { sbModeRef.current = sbMode; }, [sbMode]);
  useEffect(() => { sbRepeatModeRef.current = sbRepeatMode; }, [sbRepeatMode]);

  // ── このページ自体がアンマウントされる(=他画面へ遷移する)際に、
  //    認証セッションが残っていれば必ず終了させる。タブ切り替えなど、明示的な
  //    「キャンセル」ボタンを経由しない遷移であっても、次の画面へ認証状態を持ち越さない。
  useLayoutEffect(() => {
    return () => {
      // [段取シートバック] STEP1(新規)/リピート編集フローの途中で離脱した場合は、
      // sessionStorageのsb_*フラグをクリアしてlogout()する(MC側と同一仕様)。
      // 正規にSTEP2(作業記録)へ引き継がれた場合(sbFlowCompletedRef)はスキップする。
      if (sbModeRef.current || sbRepeatModeRef.current) {
        if (sbFlowCompletedRef.current) {
          return;
        }
        console.warn("[NC-EDIT] 段取シートバックが未完了のまま離脱 — sessionStorageをクリアしlogoutします", { ncId });
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("sb_next_record");
          sessionStorage.removeItem("sb_sheet_log_id");
          sessionStorage.removeItem("sb_repeat_edit");
        }
        logout();
        return;
      }
      // [仮登録破棄] 新規登録(仮登録=PROVISIONAL)のまま「作業完了（登録）」
      // (finalize)を経由せずこの画面を離れた場合は、登録内容を破棄し
      // 採番したK_idを解放する。既に確定済み(PROVISIONAL以外)なら何もしない。
      // [FIX] 「変更・登録」タブ自体の認証(token)をまだ行っていない状態で離脱した
      // 場合でも必ず破棄されるよう、token有無は条件にしない
      // (abandon-provisionalエンドポイントは認証不要。PROVISIONAL状態のみ削除可能なため安全)。
      if (detailRef.current?.status === "PROVISIONAL" && !registrationCompletedRef.current) {
        console.warn("[NC-EDIT] 仮登録が未確定のまま離脱 — 仮登録を破棄しK_idを解放します", { ncId });
        fetch(`/api/nc/${ncId}/abandon-provisional`, {
          method:  "DELETE",
          keepalive: true,
        }).catch(() => {});
      }
      // [v115] 終了確認モーダルが未完了のまま離脱 — 変更理由不明として自動finalizeします
      if (showKanryoModalRef.current && tokenRef.current) {
        console.warn("[NC-EDIT] 終了確認モーダルが未完了のまま離脱 — 変更理由不明として自動finalizeします", { ncId });
        fetch(`/api/nc/${ncId}/finalize`, {
          method:  "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenRef.current}` },
          body:    JSON.stringify({ change_type: "不明", change_detail: tr("ncEdit.unspecifiedReasonDetail", "変更理由未入力（モーダル入力途中で離脱）") }),
          keepalive: true,
        }).catch(() => {});
      }
      if (isAuthenticatedRef.current) {
        console.warn("[NC-EDIT] ページ離脱を検知 — 認証セッションを終了します");
        logout();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── [仮登録破棄] ブラウザを閉じる/リロードする場合はSPA遷移によるアンマウントが
  //    発生しないため、beforeunloadでも同じ破棄処理を発火させる(keepalive:trueで
  //    ページ離脱後もリクエストを継続させる)。
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (detailRef.current?.status === "PROVISIONAL" && !registrationCompletedRef.current) {
        fetch(`/api/nc/${ncId}/abandon-provisional`, {
          method:  "DELETE",
          keepalive: true,
        }).catch(() => {});
      }
      // [離脱時未保存警告] 未保存の変更(dirty)があればブラウザ標準の確認ダイアログを出す
      if (dirty.size > 0) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [ncId, dirty]);

  // ── ファイルアップロード（UploadAgent経由、MC側と同方式）──
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const issueNcUploadTicket = async (fileType: "PHOTO" | "DRAWING") => {
    if (!token) throw new Error(tr("ncEdit.authRequired", "認証が必要です"));
    const res = await fetch(`/api/nc/${ncId}/files/upload-ticket`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ file_type: fileType }),
    });
    if (!res.ok) throw new Error(tr("ncEdit.ticketIssueFailed","チケット発行失敗: HTTP {code}").replace("{code}", String(res.status)));
    const json = await res.json();
    return { ticket: json.ticket as string, uploadPath: json.upload_path as string | undefined };
  };

  const requestNcUpload = useCallback(async (fileType: "PHOTO" | "DRAWING") => {
    if (!token || uploading) return;
    setUploading(true);
    setUploadMsg(tr("ncEdit.connectingAgent", "⏳ UploadAgentに接続中..."));

    const agentOnline = await isAgentOnline();
    if (!agentOnline) {
      const msg = tr("ncEdit.agentNotRunning", "❌ UploadAgentが起動していません。タスクトレイを確認し、UploadAgent を起動してください。");
      setUploadMsg(msg);
      setUploading(false);
      window.alert(msg);
      return;
    }

    const ok = window.confirm(
      tr("ncEdit.deleteConfirmUpload", "【アップロード元ファイルの削除確認】\n選択したファイルをアップロードします。アップロード完了後、元ファイルはゴミ箱フォルダへ自動移動されます。\n続行しますか？")
    );
    if (!ok) { setUploading(false); setUploadMsg(null); return; }

    setUploadMsg(tr("ncEdit.openingFileDialog", "⏳ UploadAgentでファイル選択ダイアログを開いています..."));
    try {
      const { ticket, uploadPath } = await issueNcUploadTicket(fileType);
      const result = await agentPickAndUpload(ticket, fileType, uploadPath);

      if (result.cancelled) { setUploadMsg(null); return; }
      if (!result.success) {
        const fallback1 = result.error ?? tr("ncEdit.uploadFailedGeneric", "アップロードに失敗しました");
        setUploadMsg(`❌ ${translateAgentError(tr, result.errorCode, result.errorParams, fallback1) ?? fallback1}`);
        return;
      }

      const res = await ncApi.findOne(ncId);
      setDetail(res.data);
      setUploadMsg(tr("ncEdit.uploadCompleteCount","✅ {n}件アップロード完了").replace("{n}", String(result.files.length)));
    } catch (e: any) {
      setUploadMsg(tr("ncEdit.uploadFailedPrefix","❌ アップロード失敗: {msg}").replace("{msg}", e.message ?? tr("ncEdit.unknownError","不明なエラー")));
    } finally {
      setUploading(false);
      setTimeout(() => setUploadMsg(null), 5000);
    }
  }, [token, ncId, uploading]);

  // ── PGファイル(PROGRAM)をUSBから登録(MC側 handlePgUploadFromUSB と同方式) ──
  // 選択ダイアログは一切表示しない。機械マスタ(Machine.pgIsFolder)に基づき
  // サーバー側で解決した権威的なファイル名/フォルダ名がUSB取込元フォルダ内に
  // 実在するかを確認し、存在すれば確認メッセージの後、無条件にアップロードする。
  const [pgUploading, setPgUploading] = useState(false);

  const handlePgUploadFromUSB = useCallback(async () => {
    if (!token) { setAuthOpen(true); return; }
    if (pgUploading) return;

    setPgUploading(true);
    setUploadMsg(tr("ncEdit.connectingAgent", "⏳ UploadAgentに接続中..."));

    const agentOnline = await isAgentOnline();
    if (!agentOnline) {
      const msg = tr("ncEdit.agentNotRunningPg", "❌ UploadAgentが起動していません。PGファイルのアップロードには UploadAgent の起動が必要です。");
      setUploadMsg(msg);
      setPgUploading(false);
      window.alert(msg);
      return;
    }

    try {
      const res = await fetch(`/api/nc/${ncId}/files/upload-ticket`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ file_type: "PROGRAM" }),
      });
      if (!res.ok) throw new Error(tr("ncEdit.ticketIssueFailed","チケット発行失敗: HTTP {code}").replace("{code}", String(res.status)));
      const ticketJson = await res.json();
      const ticket = ticketJson.ticket as string;
      const uploadPath = ticketJson.upload_path as string | undefined;
      const isFolderMode = !!ticketJson.is_folder;
      const expectedName: string | null = isFolderMode ? ticketJson.expected_folder_name : ticketJson.expected_file_name;

      if (!expectedName) {
        setUploadMsg(tr("ncEdit.resolveFileNameFailed", "❌ 対象ファイル名/フォルダ名の解決に失敗しました"));
        setPgUploading(false);
        return;
      }

      setUploadMsg(tr("ncEdit.checkingUsbFile", "⏳ USB内のファイルを確認しています..."));
      const check = await agentCheckUsbTarget(expectedName, isFolderMode);
      if (!check.success || !check.exists) {
        const fallback2 = tr("ncEdit.usbFolderNotFound","USBフォルダ内に「{name}」が見つかりません").replace("{name}", expectedName);
        const msg = translateAgentError(tr, check.errorCode, check.errorParams, check.error) ?? fallback2;
        setUploadMsg(`❌ ${msg}`);
        setPgUploading(false);
        return;
      }

      const ok = window.confirm(
        tr("ncEdit.pgUploadDeleteConfirmTitle", "【PGファイルアップロード - 元ファイル削除確認】\n") +
        tr("ncEdit.pgUploadDetected", "USB内に{unit}「{name}」を検出しました。\n").replace("{unit}", isFolderMode ? tr("ncEdit.folderUnit","フォルダ") : tr("ncEdit.fileUnit","ファイル")).replace("{name}", expectedName) +
        tr("ncEdit.pgUploadNamingRule", "この機械({mode})の命名規則に従い、そのままアップロードします。\n").replace("{mode}", isFolderMode ? tr("ncEdit.folderModeLabel","📁 フォルダ単位") : tr("ncEdit.fileModeLabel","📄 単体ファイル")) +
        tr("ncEdit.pgUploadAutoMove", "アップロード完了後、元ファイルはゴミ箱(.machcore_trash)へ自動移動されます。\n続行しますか？")
      );
      if (!ok) { setPgUploading(false); setUploadMsg(null); return; }

      setUploadMsg(tr("ncEdit.uploadingInProgress", "⏳ アップロード中..."));
      const result = await agentAutoUpload(ticket, "PROGRAM", expectedName, isFolderMode, uploadPath);

      if (result.cancelled) { setUploadMsg(null); return; }
      if (!result.success) {
        const fallback3 = result.error ?? tr("ncEdit.uploadFailedGeneric", "アップロードに失敗しました");
        setUploadMsg(`❌ ${translateAgentError(tr, result.errorCode, result.errorParams, fallback3) ?? fallback3}`);
        return;
      }

      const res2 = await ncApi.findOne(ncId);
      setDetail(res2.data);

      const n2 = result.files.length;
      const delFailCount = result.files.filter((f: any) => !f.localDeleted).length;
      let msg = tr("ncEdit.registerCompleteCount","✅ {n}件登録完了").replace("{n}", String(n2));
      if (delFailCount > 0) msg += tr("ncEdit.delFailWarning"," ⚠️ {n}件は元ファイルの削除に失敗 - 手動削除してください").replace("{n}", String(delFailCount));
      else msg += tr("ncEdit.movedToTrashSuffix", "。元ファイルをゴミ箱に移動しました");
      setUploadMsg(msg);
    } catch (e: any) {
      console.error("[NC_PG_UPLOAD] エラー:", e);
      setUploadMsg(tr("ncEdit.uploadFailedPrefix","❌ アップロード失敗: {msg}").replace("{msg}", e.message ?? tr("ncEdit.unknownError","不明なエラー")));
    } finally {
      setPgUploading(false);
      setTimeout(() => setUploadMsg(null), 6000);
    }
  }, [token, ncId, pgUploading]);

  // PG エディタ
  // [v084] 単一ファイルのみ対応の旧実装を廃止。MC側と同じ共通コンポーネント(ProgramFileViewer)に一本化。
  //   フォルダ単位(メインPG+サブPG)の複数ファイルにも対応する。
  const [newPgViewerOpen, setNewPgViewerOpen] = useState(false);

  const [authOpen, setAuthOpen] = useState(false);

  // sbMode/sbRepeatMode=true かつ未認証の場合は自動で認証モーダルを開く — MC側と同一仕様。
  useEffect(() => {
    if ((sbMode || sbRepeatMode) && !isAuthenticated) {
      setAuthOpen(true);
    }
  }, [sbMode, sbRepeatMode, isAuthenticated]);

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
      usersApi.list("NC"),
    ]).then(([ncRes, machRes, userRes]) => {
      const d = ncRes.data;
      setDetail(d);
      setMachines(machRes.data.filter(m => m.isActive));
      setUsers((userRes as any).data ?? userRes);
      setMachineId(d.machine?.id ?? "");
      setMachiningTime(String(d.machiningTime ?? ""));
      // [FIX] 単体ファイル機械のfolder_nameは旧システム互換のための無意味な固定値
      // "USB"(nc.service.ts resolveNewRegistrationNaming参照、実運用では不使用)が
      // 入っているだけなので、画面上は空欄で表示する(未編集のままならDB値は変わらない)。
      setFolderName(d.folderName === "USB" ? "" : (d.folderName ?? ""));
      setFileName(d.fileName ?? "");
      setVersion(d.version ?? "A");
      setClampNote(d.clampNote ?? "");
      setClampAllowance(d.clampAllowance ?? "");
      setCreatorId(d.creatorId ? String(d.creatorId) : ""); // [v096]
      setSheetCreatedAt(d.sheetCreatedAt ? d.sheetCreatedAt.slice(0, 10) : ""); // [v096]
      setToolingRows((d.tools ?? []).map((t: any) => ({
        sort_order:   t.sortOrder    ?? 0,
        process_type: t.processType  ?? "",
        chip_model:   t.chipModel    ?? "",
        holder_model: t.holderModel  ?? "",
        nose_r:       t.noseR        ?? "",
        t_number:     t.tNumber      ?? "",
        note:         t.note         ?? "",
      })));
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
    // [仮登録確定] まだ未確定(PROVISIONAL)の新規登録は、項目を何も変更していなくても
    // 「✓ 作業完了（登録）」で確定できるようにする(MC側の新規登録フローと同様)。
    const isProvisionalCompletion = detail?.status === "PROVISIONAL";
    try {
      const body: UpdateNcBody = {};
      if (dirty.has("machineId"))     body.machine_id     = machineId === "" ? undefined : Number(machineId);
      if (dirty.has("machiningTime")) body.machining_time = machiningTime === "" ? undefined : Number(machiningTime);
      if (dirty.has("folderName"))    body.folder_name    = folderName;
      if (dirty.has("fileName"))      body.file_name      = fileName;
      if (dirty.has("version"))       body.version        = version;
      if (dirty.has("clampNote"))     body.clamp_note     = clampNote;
      if (dirty.has("clampAllowance")) body.clamp_allowance = clampAllowance;
      if (dirty.has("creatorId"))     body.creator_id     = creatorId === "" ? null : Number(creatorId);
      if (dirty.has("sheetCreatedAt")) body.sheet_created_at = sheetCreatedAt === "" ? null : sheetCreatedAt;

      if (Object.keys(body).length === 0 && !isProvisionalCompletion) {
        setSaveError(tr("ncEdit.noChangeItems", "変更項目がありません"));
        return;
      }

      const { default: axios } = await import("axios");
      if (Object.keys(body).length > 0) {
        await axios.put(`/api/nc/${ncId}`, body, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }

      if (isProvisionalCompletion) {
        // [仮登録確定] finalize()でPENDING_APPROVALへ遷移させ、登録を確定する。
        // これ以降、離脱時の仮登録破棄(abandon-provisional)は発火しない。
        // 新規登録の確定は変更種別が一意("新規登録")のため、MC側sbModeと同様に
        // モーダルを経由せず直接finalizeする。
        await ncApi.finalize(ncId, tr("ncEdit.newRegistrationType", "新規登録"), undefined, token);
        registrationCompletedRef.current = true;
        // [段取シートバック] STEP1(新規)フロー中の確定完了 → STEP2(作業記録)へ引き継ぐ。
        if (sbMode) {
          if (typeof window !== "undefined") {
            sessionStorage.setItem("sb_next_record", String(ncId));
          }
          sbFlowCompletedRef.current = true;
          router.push(`/nc/${ncId}/record`);
          return;
        }
        logout();
        router.push(`/nc/${ncId}`);
        return;
      }

      // 新規(sbMode)の場合は変更内容を「新規登録」に固定する — MC側と同一仕様。
      if (sbMode) setKanryoType(tr("ncEdit.newRegistrationType", "新規登録"));
      // [v112] 通常編集(確定済みレコードの変更): MC側と同一仕様で、保存後に
      // 「終了確認モーダル」(変更種別選択 + バージョンインクリ、または一時保存)を表示する。
      setShowKanryoModal(true);
    } catch (e: any) {
      setSaveError(e?.response?.data?.message ?? tr("ncEdit.saveFailedGeneric", "保存に失敗しました"));
    } finally {
      setSaving(false);
    }
  }, [isAuthenticated, token, dirty, machineId, machiningTime, folderName, fileName, version, clampNote, creatorId, sheetCreatedAt, ncId, logout, router, detail]);

  // ── 終了確認OK: change_type/detailを付けてfinalize()しバージョンインクリ ──
  const handleKanryoOk = async () => {
    if (!token) return;
    const isSb = sbMode || sbRepeatMode;
    try {
      await ncApi.finalize(ncId, kanryoType, kanryoDetail || undefined, token);
      setShowKanryoModal(false);
      if (isSb) {
        // [段取シートバック] STEP1(新規)/リピート編集の完了 → STEP2(作業記録)へ引き継ぐ。
        if (typeof window !== "undefined") {
          sessionStorage.removeItem("sb_repeat_edit");
          // 新規(sbMode)の場合はsb_next_recordがダッシュボード側で既にセット済み。
          if (!sbMode) {
            sessionStorage.setItem("sb_next_record", String(ncId));
          }
        }
        sbFlowCompletedRef.current = true;
        setTimeout(() => router.push(`/nc/${ncId}/record`), 400);
        return;
      }
      logout();
      setTimeout(() => router.push(`/nc/${ncId}`), 400);
    } catch (e: any) {
      setSaveError(e?.response?.data?.message ?? tr("ncEdit.versionUpdateFailed", "バージョン更新に失敗"));
      setShowKanryoModal(false);
    }
  };

  // ── [一時保存] finalize()を呼ばず(=バージョン変更なし)、既に保存済みの内容を
  //    そのままCHANGINGステータスで残して離脱する。
  const handleKanryoTempSave = () => {
    setShowKanryoModal(false);
    logout();
    setTimeout(() => router.push(`/nc/${ncId}`), 400);
  };

  // ── モーダルの「キャンセル（変更を取り消す）」: 保存済みのCHANGING状態を
  //    revert()で元のステータスへ戻してから離脱する。
  const handleKanryoCancel = async () => {
    if (sbMode || sbRepeatMode) {
      // [段取シートバック] 新規/リピートフロー: 既存通り「スキップ」(作業記録なしでダッシュボードへ)
      setShowKanryoModal(false);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("sb_next_record");
        sessionStorage.removeItem("sb_sheet_log_id");
        sessionStorage.removeItem("sb_repeat_edit");
      }
      logout();
      router.push("/nc");
      return;
    }
    if (token) {
      try { await ncApi.revert(ncId, token); }
      catch (e) { console.warn("[NC-EDIT] キャンセル時revert失敗", e); }
    }
    setShowKanryoModal(false);
    logout();
    router.push(`/nc/${ncId}`);
  };

  const handleCancel = useCallback(() => {
    if (isAuthenticated) {
      if (!confirm(tr("ncEdit.discardChangesConfirm", "変更を破棄して戻りますか？"))) return;
      logout();
    }
    // [段取シートバック] 新規STEP1/リピート編集フロー中のキャンセルは
    // sessionStorageのsb_*フラグをクリアしてダッシュボードへ戻す。
    if (sbMode || sbRepeatMode) {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("sb_next_record");
        sessionStorage.removeItem("sb_sheet_log_id");
        sessionStorage.removeItem("sb_repeat_edit");
      }
      router.push("/nc");
      return;
    }
    // [仮登録] 確定前(PROVISIONAL)はNC詳細画面自体がブロックされるため、
    // キャンセル時はダッシュボードへ戻す(離脱により仮登録は自動破棄される)。
    if (detail?.status === "PROVISIONAL") {
      router.push("/nc");
    } else {
      router.push(`/nc/${ncId}`);
    }
  }, [isAuthenticated, logout, ncId, router, detail, sbMode, sbRepeatMode]);

  if (loadError) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-red-500 text-sm">{tr("ncEdit.loadErrorPrefix", "読み込みエラー: {msg}").replace("{msg}", String(loadError))}</div>
    </div>
  );
  if (!detail) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-slate-400 text-sm">{tr("ncEdit.loadingScreen", "読み込み中...")}</div>
    </div>
  );

  const d = detail;
  // [仮登録] 「作業完了（登録）」で確定するまでは段取シート・作業記録タブを非活性にする。
  const isProvisionalLocked = d.status === "PROVISIONAL";
  // [段取シートバック] STEP1(新規)/リピート編集フロー中もNC詳細・段取シート・
  // 作業記録タブを非活性にする(MC側と同一仕様)。
  const sbTabLocked = isProvisionalLocked || sbMode || sbRepeatMode;


  return (
    <>
      <div className="h-screen flex flex-col bg-slate-100">

        {/* ── グローバルヘッダー ── */}
        <header className="bg-slate-800 text-white px-5 py-2.5 flex items-center gap-3 shrink-0">
          {!isProvisionalLocked && (
            <>
              <button
                onClick={() => guardedNavigate(`/nc/${ncId}`)}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded-lg text-xs font-medium text-white transition-colors shrink-0"
              >
                <span className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center shrink-0">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
                </span>
                {tr("ncEditUi.ncDetail", "NC詳細")}
              </button>
              <span className="text-slate-600">|</span>
            </>
          )}
          <button onClick={() => guardedNavigate("/nc")} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-xs font-bold text-white transition-colors shrink-0">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>{tr("ncEditUi.toDashboard", "ダッシュボードへ")}
          </button>
          <span className="font-mono text-sky-400 font-bold text-base">MachCore</span>
          <span className="text-sm font-medium flex items-center gap-1.5">{tr("ncEditUi.editRegister", "変更・登録")}</span>
          <span className="ml-auto">
            {isAuthenticated && operator ? (
              <span className="text-[11px] bg-red-600 text-white px-3 py-1 rounded font-bold animate-pulse">
                {tr("ncEditUi.working", "作業中: {name}　{time}").replace("{name}", operator.name).replace("{time}", fmtElapsed(elapsed))}
              </span>
            ) : (
              <span className="text-[11px] text-slate-400 bg-slate-700 px-2 py-1 rounded">
                {tr("ncEditUi.waitingAuth", "🔒 認証待ち")}
              </span>
            )}
          </span>
        </header>

        {/* 部品情報エリア（共通コンポーネント） */}
        {d && <NcPartHeader data={d} showApprove onApproveClick={() => setApprovalModalOpen(true)} />}

        {/* [段取シートバック] STEP1(新規)/リピート編集フローの案内バナー — MC側と同一仕様 */}
        {isAuthenticated && (sbMode || sbRepeatMode) && (
          <div className={`${sbRepeatMode ? "bg-amber-600" : "bg-blue-600"} text-white px-5 py-2 flex items-center justify-between text-xs shrink-0`}>
            <div className="flex items-center gap-3">
              <span className="bg-white/20 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold shrink-0">1</span>
              <span className="font-bold">{sbRepeatMode ? tr("ncEditUi.sbRepeatBannerText","段取シートバック リピート: 旋盤情報を確認・編集してください") : tr("ncEditUi.sbNewBannerText","段取シートバック STEP1: 旋盤情報・ツーリングなどを登録してください")}</span>
              <span className="opacity-80">{sbRepeatMode ? tr("ncEditUi.sbRepeatNextText","→ 更新後、変更内容を登録してSTEP2(作業記録)へ遷移します") : tr("ncEditUi.sbNewNextText","→ 登録完了後 STEP2(作業記録)へ自動遷移します")}</span>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => {
                  if (typeof window !== "undefined") {
                    sessionStorage.removeItem("sb_next_record");
                    sessionStorage.removeItem("sb_sheet_log_id");
                    sessionStorage.removeItem("sb_repeat_edit");
                  }
                  logout();
                  router.push("/nc");
                }}
                className="text-white/80 hover:text-white text-xs px-3 py-1 rounded border border-white/40 hover:border-white transition-colors">
                {tr("ncEditUi.cancelInterrupt", "キャンセル（中断）")}
              </button>
              <button onClick={handleSave} disabled={saving}
                className="bg-white text-slate-800 px-4 py-1 rounded font-bold hover:bg-slate-100 disabled:opacity-50 text-sm">
                {saving ? tr("ncEditUi.saving","保存中...") : (sbRepeatMode ? tr("ncEditUi.sbRepeatCompleteButton","更新完了 → 変更登録・STEP2へ") : tr("ncEditUi.sbStep1CompleteButton","STEP1完了 → STEP2(作業記録)へ"))}
              </button>
            </div>
          </div>
        )}
        {/* [仮登録] 未確定状態の案内バナー */}
        {isProvisionalLocked && (
          <div className="bg-slate-100 border-b border-slate-200 px-4 py-2 text-xs text-slate-500 flex items-center gap-2 shrink-0">
            <span className="font-bold text-slate-600">{tr("ncEditUi.provisionalLockedLabel", "🔒 仮登録（未確定）")}</span>
            {tr("ncEditUi.provisionalLockedDesc")}
          </div>
        )}

        {/* タブナビ（MC側準拠: ブラウザタブ風） */}
        <nav className="bg-white border-b border-[#d0d8e4] px-4 flex gap-1.5 items-end shrink-0 pt-1.5">
          <button onClick={() => { if (!sbTabLocked) guardedNavigate(`/nc/${ncId}`); }}
            disabled={sbTabLocked}
            title={sbTabLocked ? tr("ncEditUi.availableAfterConfirm", "登録確定後に利用できます") : undefined}
            className={`px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 transition-colors ${sbTabLocked ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-50" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]"}`}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>{tr("ncEditUi.ncDetail", "NC詳細")}
          </button>
          <button onClick={() => router.push(`/nc/${ncId}/edit`)}
            className="px-4 py-1.5 text-[12px] font-bold flex items-center gap-1.5 rounded-t border border-b-0 border-[#1b2a41] bg-[#1b2a41] text-white">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>{tr("ncEditUi.editRegister", "変更・登録")}
            {isAuthenticated && <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse ml-0.5" />}
          </button>
          <button onClick={() => { if (!sbTabLocked) guardedNavigate(`/nc/${ncId}/print`); }}
            disabled={sbTabLocked}
            title={sbTabLocked ? tr("ncEditUi.availableAfterConfirm", "登録確定後に利用できます") : undefined}
            className={`px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 transition-colors ${sbTabLocked ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-50" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]"}`}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>{tr("ncEditUi.setupSheetTab", "段取シート")}
          </button>
          <button onClick={() => { if (!sbTabLocked) guardedNavigate(`/nc/${ncId}/record`); }}
            disabled={sbTabLocked}
            title={sbTabLocked ? tr("ncEditUi.availableAfterConfirm", "登録確定後に利用できます") : undefined}
            className={`px-4 py-1.5 text-[12px] font-semibold flex items-center gap-1.5 rounded-t border border-b-0 transition-colors ${sbTabLocked ? "border-slate-200 bg-slate-100 text-slate-300 cursor-not-allowed pointer-events-none opacity-50" : "border-[#c4cfdb] bg-white text-[#4a5568] hover:bg-[#eef3f8] hover:text-[#1b2a41]"}`}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>{tr("ncEditUi.workRecordTab", "作業記録")}
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
                <div className="font-bold text-slate-700 text-base">{tr("ncEditUi.lockedTitle", "変更・登録 — 作業開始前")}</div>
                <div className="text-slate-500 text-sm max-w-sm">
                  {tr("ncEditUi.lockedDesc")}
                </div>
                {/* データサマリー 50%透過 */}
                <div className="w-full max-w-md rounded-xl border border-slate-200 overflow-hidden opacity-50 pointer-events-none text-xs">
                  <div className="grid grid-cols-3 divide-x divide-slate-200 border-b border-slate-200">
                    <div className="p-2.5"><div className="text-slate-400">{tr("ncEditUi.machineLabel", "機械")}</div><div className="font-bold">{d.machine?.machineCode ?? "—"}</div></div>
                    <div className="p-2.5"><div className="text-slate-400">{tr("ncEditUi.fileNameLabel", "ファイル名")}</div><div className="font-mono font-bold">{d.fileName ?? "—"}</div></div>
                    <div className="p-2.5"><div className="text-slate-400">{tr("ncEditUi.machiningTimeLabel", "加工時間")}</div><div className="font-mono font-bold">{d.machiningTime != null ? tr("ncEditUi.minutesUnit","{n} 分").replace("{n}", String(d.machiningTime)) : "—"}</div></div>
                  </div>
                  <div className="p-2.5"><div className="text-slate-400">{tr("ncEditUi.noteLabel", "備考")}</div><div className="text-slate-600">{d.clampNote ? d.clampNote.slice(0,40)+"…" : "—"}</div></div>
                </div>
                <button
                  onClick={() => setAuthOpen(true)}
                  className="flex items-center gap-2 px-6 py-3 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-sm transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  {tr("ncEditUi.startWorkButton", "この作業を開始する（担当者確認）")}
                </button>
                <div className="text-xs text-slate-400">{tr("ncEditUi.startWorkHint", "担当者の選択とパスワード確認後に編集できます")}</div>
              </div>
            </div>
          )}

          {/* === ACTIVE STATE === */}
          {isAuthenticated && d && (
            <div className="max-w-6xl mx-auto space-y-4">

              {/* セッションバナー（赤） */}
              <div className="bg-red-600 rounded-xl px-5 py-3 flex items-center gap-3">
                <div className="w-2.5 h-2.5 bg-white rounded-full animate-pulse shrink-0"></div>
                <div className="flex-1">
                  <div className="text-white font-bold text-sm">{tr("ncEditUi.workingSessionTitle", "変更・登録 作業中")}</div>
                  <div className="text-red-200 text-xs">{tr("ncEditUi.workingSince","{name}（{role}）— 作業開始から {time}").replace("{name}", operator?.name ?? "").replace("{role}", operator?.role ?? "").replace("{time}", fmtElapsed(elapsed))}</div>
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
                  {tr("ncEditUi.editModeLabel", "編集モード — 変更した項目はオレンジ枠で表示")}
                </div>

                <div className="grid grid-cols-3 gap-5">

                  {/* 左カラム（col-span-2）: フォームフィールド */}
                  <div className="col-span-2 space-y-4">

                    {/* 行1: 工程L | 機械 | 加工時間 | フォルダ名 */}
                    <div className="grid grid-cols-4 gap-3">
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.processLLabel", "工程 L")} <span className="text-red-400 text-[10px]">{tr("ncEditUi.notChangeable", "変更不可")}</span></label>
                        <input
                          value={`L${d.processL}`} readOnly
                          className="border border-slate-200 rounded px-3 py-2 text-sm w-full bg-slate-50 text-slate-400 cursor-not-allowed"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.machineLabel", "機械")} <span className="text-red-400">*</span></label>
                        <select
                          value={machineId}
                          onChange={e => { setMachineId(e.target.value === "" ? "" : Number(e.target.value)); markDirty("machineId"); }}
                          className={fieldCls("machineId")}
                        >
                          <option value="">{tr("ncEditUi.selectOption", "— 選択 —")}</option>
                          {machines.map(m => (
                            <option key={m.id} value={m.id}>{m.machineCode}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.machiningTimeMinLabel", "加工時間（分）")}</label>
                        <input
                          type="number" min={0}
                          value={machiningTime}
                          onChange={e => { setMachiningTime(e.target.value); markDirty("machiningTime"); }}
                          className={fieldCls("machiningTime")}
                          placeholder="0"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.folderNameLabel", "フォルダ名")} <span className="text-red-400">*</span></label>
                        <input
                          type="text" maxLength={50}
                          value={folderName}
                          onChange={e => { setFolderName(e.target.value); markDirty("folderName"); }}
                          className={fieldCls("folderName", "font-mono")}
                          placeholder={tr("ncEditUi.folderNamePlaceholder", "例: 旭A")}
                        />
                      </div>
                    </div>

                    {/* 行2: ファイル名/O番号 | Ver */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">
                          {tr("ncEditUi.fileNameSlashONoLabel", "ファイル名 / O番号")} <span className="text-red-400">*</span>
                          {dirty.has("fileName") && <span className="text-orange-500 ml-1">●</span>}
                        </label>
                        <input
                          type="text" maxLength={50}
                          value={fileName}
                          onChange={e => { setFileName(e.target.value); markDirty("fileName"); }}
                          className={fieldCls("fileName", "font-mono")}
                          placeholder={tr("ncEditUi.fileNamePlaceholder", "例: 7065")}
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">
                          {tr("ncEditUi.verLabel", "Ver")} <span className="text-red-400">*</span>
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

                    {/* [v101] 掴代(専用フィールド。旧ACC_Lathe.Clamp) */}
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">
                        {tr("ncEditUi.clampAllowanceLabel", "掴代")} <span className="text-slate-400">(mm)</span>
                        {dirty.has("clampAllowance") && <span className="text-orange-500 ml-1">●</span>}
                      </label>
                      <input
                        value={clampAllowance}
                        onChange={e => { setClampAllowance(e.target.value); markDirty("clampAllowance"); }}
                        className={fieldCls("clampAllowance")}
                        placeholder={tr("ncEditUi.clampAllowancePlaceholder", "例: 専用 / 9~10")}
                      />
                    </div>

                    {/* クランプ / 備考 */}
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">
                        {tr("ncEditUi.clampNoteLabel", "クランプ / 備考")}
                        {dirty.has("clampNote") && <span className="text-orange-500 ml-1">●</span>}
                      </label>
                      <textarea
                        rows={4}
                        maxLength={2000}
                        value={clampNote}
                        onChange={e => { setClampNote(e.target.value); markDirty("clampNote"); }}
                        className={`${fieldCls("clampNote")} resize-y`}
                        placeholder={tr("ncEditUi.clampNotePlaceholder", "クランプ条件・注意事項など")}
                      />
                      <p className="text-[10px] text-slate-400 mt-0.5 text-right">{clampNote.length} / 2000</p>
                    </div>

                    {/* [v096] 作成者・作成日 + オペレーター/入力日 + 承認者/承認日 と、
                        その右隣にNCプログラム操作パネルを配置(MC側と同一構成+レイアウト改善) */}
                    <div className="grid grid-cols-[1fr_200px] gap-4">
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">
                              {tr("ncEditUi.creatorLabel", "作成者（段取シート作成者）")}
                              {dirty.has("creatorId") && <span className="text-orange-500 ml-1">●</span>}
                            </label>
                            <select
                              value={creatorId}
                              onChange={e => { setCreatorId(e.target.value); markDirty("creatorId"); }}
                              className={fieldCls("creatorId")}
                            >
                              <option value="">{tr("ncEditUi.selectOption", "— 選択 —")}</option>
                              {users
                                .filter(u => u.isActive || String(u.id) === creatorId)
                                .map(u => (
                                  <option key={u.id} value={String(u.id)}>{u.name}{u.isActive === false ? tr("ncEditUi.inactiveSuffix","（無効）") : ""}</option>
                                ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">
                              {tr("ncEditUi.createdDateLabel", "作成日（シート作成日）")}
                              {dirty.has("sheetCreatedAt") && <span className="text-orange-500 ml-1">●</span>}
                            </label>
                            <input
                              type="date"
                              value={sheetCreatedAt}
                              onChange={e => { setSheetCreatedAt(e.target.value); markDirty("sheetCreatedAt"); }}
                              className={fieldCls("sheetCreatedAt")}
                            />
                          </div>
                        </div>

                        {/* [v096] オペレーター・入力日・承認者・承認日(読み取り専用、MC側と同一構成) */}
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.operatorLabel", "オペレーター")}</label>
                            <div className="px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded">
                              {detail?.registrar?.name ?? "—"}
                            </div>
                          </div>
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.inputDateLabel", "入力日")}</label>
                            <div className="px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded font-mono">
                              {toJstDateString(detail?.registeredAt) ?? "—"}
                            </div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.approverLabel", "承認者")}</label>
                            <div className={`px-3 py-2 text-sm border rounded ${detail?.approver ? "bg-emerald-50 border-emerald-200 text-emerald-700 font-bold" : "bg-slate-50 border-slate-200 text-slate-400"}`}>
                              {detail?.approver?.name ?? tr("ncEditUi.notApproved", "未承認")}
                            </div>
                          </div>
                          <div>
                            <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.approvedDateLabel", "承認日")}</label>
                            <div className={`px-3 py-2 text-sm border rounded font-mono ${detail?.approvedAt ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-slate-50 border-slate-200 text-slate-400"}`}>
                              {toJstDateString(detail?.approvedAt) ?? tr("ncEditUi.notApproved", "未承認")}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* NCプログラム操作パネル [v084] MC側と同じ共通コンポーネント(ProgramFileViewer)に接続 */}
                      <div className="rounded-xl p-2.5 space-y-1.5 shrink-0" style={{background:"#0f172a", border:"1.5px solid #1e40af"}}>
                        <div className="text-[10px] text-sky-400 font-bold text-center tracking-wide mb-1">{tr("ncEditUi.ncProgramLabel", "NCプログラム")}</div>
                        <button
                          onClick={() => {
                            if (!token) { setAuthOpen(true); return; }
                            setNewPgViewerOpen(true);
                          }}
                          className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded-lg font-medium transition-colors"
                          style={{background:"#164e63", color:"#67e8f9"}}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                          {tr("ncEditUi.openPgEditor", "📄 PGエディタを開く")}
                        </button>
                        <button
                          onClick={handlePgUploadFromUSB}
                          disabled={pgUploading}
                          className="w-full flex items-center justify-center gap-1.5 text-xs py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
                          style={{background:"#065f46", color:"#6ee7b7"}}
                        >
                          {pgUploading && <span className="inline-block w-3 h-3 border-2 border-emerald-300 border-t-transparent rounded-full animate-spin" />}
                          {pgUploading ? tr("ncEditUi.registeringInProgress","⏳ 登録中...") : tr("ncEditUi.registerFromUsb","📥 USBから登録")}
                        </button>
                        <p className="text-[9px] text-slate-500 text-center">{tr("ncEditUi.editorSaveHint", "保存 / USBへ書き出し(UA経由)はエディタ内で行えます")}</p>
                      </div>
                    </div>
                  </div>

                  {/* 右カラム: ファイル操作 */}
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.drawingCountLabel", "図枚数")}</label>
                      <input type="number" readOnly value={d.drawingCount}
                        className="border border-slate-200 rounded px-3 py-2 text-sm w-full bg-slate-50 text-slate-500" />
                    </div>
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">{tr("ncEditUi.photoCountLabel", "写真枚数")}</label>
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
                        {tr("ncEditUi.importPhoto", "📷 写真を取り込む")}
                      </button>
                      <button
                        onClick={() => requestNcUpload("DRAWING")}
                        disabled={uploading}
                        className="w-full border border-purple-300 bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5 disabled:opacity-40"
                      >
                        {uploading && <span className="inline-block w-3 h-3 border-2 border-purple-700 border-t-transparent rounded-full animate-spin" />}
                        {tr("ncEditUi.importDrawing", "📄 図を取り込む")}
                      </button>
                      {uploadMsg && (
                        <p className={`text-[11px] text-center font-bold ${uploadMsg.startsWith("⏳") ? "text-amber-600 animate-pulse" : uploadMsg.startsWith("❌") ? "text-red-600" : "text-teal-600"}`}>
                          {uploadMsg}
                        </p>
                      )}
                      <p className="text-[10px] text-slate-400 text-center">{tr("ncEditUi.agentDialogHint", "UploadAgentでファイル選択ダイアログが開きます")}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* 加工リスト(MC側ツーリングタブと同等: 行追加・削除・上下移動)
                  幅いっぱいに使えるよう、上のフォームカードとは別の全幅カードとして配置 */}
                    {/* 加工リスト(MC側ツーリングタブと同等: 行追加・削除・上下移動) */}
                    <div className="bg-white rounded-xl border border-slate-200">
                      <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-600">{tr("ncEditUi.processListTitle","加工リスト ({n}レコード)").replace("{n}", String(toolingRows.length))}</span>
                        <div className="flex items-center gap-2">
                          {toolingSaveMsg && <span className="text-[11px] text-slate-500">{toolingSaveMsg}</span>}
                          <button
                            onClick={async () => {
                              if (!token) { setAuthOpen(true); return; }
                              try {
                                await ncApi.saveTooling(ncId, toolingRows.map((t, idx) => ({
                                  sort_order:   t.sort_order   ?? idx,
                                  process_type: t.process_type || undefined,
                                  chip_model:   t.chip_model   || undefined,
                                  holder_model: t.holder_model || undefined,
                                  nose_r:       t.nose_r       || undefined,
                                  t_number:     t.t_number     || undefined,
                                  note:         t.note         || undefined,
                                })), token);
                                setToolingSaveMsg(tr("ncEditUi.saveProcessListSuccess", "✅ 加工リストを保存しました"));
                                setTimeout(() => setToolingSaveMsg(null), 3000);
                              } catch { setToolingSaveMsg(tr("ncEditUi.saveFailedShort", "❌ 保存に失敗しました")); setTimeout(() => setToolingSaveMsg(null), 3000); }
                            }}
                            className="px-3 py-1 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-colors">
                            {tr("ncEditUi.saveProcessList", "✓ 加工リストを保存")}
                          </button>
                          <button onClick={() => setToolingRows(prev => [...prev, { sort_order: (prev.length + 1) * 10, process_type: "", chip_model: "", holder_model: "", nose_r: "", t_number: "", note: "" }])}
                            className="text-xs text-teal-600 font-bold">{tr("ncEditUi.addRow", "+ 追加")}</button>
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="text-xs w-full border-collapse">
                          <colgroup>
                            <col style={{width:"72px"}}/>
                            <col style={{width:"230px"}}/>
                            <col style={{width:"110px"}}/>
                            <col style={{width:"100px"}}/>
                            <col style={{width:"70px"}}/>
                            <col style={{width:"36px"}}/>
                            <col style={{width:"320px"}}/>
                            <col style={{width:"56px"}}/>
                            <col style={{width:"54px"}}/>
                          </colgroup>
                          <thead className="bg-teal-50">
                            <tr>
                              <th className="px-1 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">{tr("ncEditUi.colProcess", "加工")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">{tr("ncEditUi.colChipShape", "形状（チップ）")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">{tr("ncEditUi.colHolder", "ホルダー")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">{tr("ncEditUi.colNoseR", "ノーズR")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">{tr("ncEditUi.colTNo", "T NO")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-left text-[11px] whitespace-nowrap">{tr("ncEditUi.colNote", "備考")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap">{tr("ncEditUi.colOrder", "順番")}</th>
                              <th className="px-2 py-2 text-teal-700 font-bold border-b border-teal-100 text-center text-[11px] whitespace-nowrap"></th>
                            </tr>
                          </thead>
                          <tbody>
                          {toolingRows.map((t, i) => {
                            // process_type は "加/工" 結合済みの単一文字列(スキーマ変更なし)。
                            // 編集時のみ2つのドロップダウンに分解し、変更のたびに再結合する。
                            const ptParts = String(t.process_type ?? "").split("/");
                            const s1 = ptParts[0] ?? "";
                            const s2 = ptParts.slice(1).join("/") ?? "";
                            const combine = (a: string, b: string) => (a && b) ? `${a}/${b}` : (a || b || "");
                            return (
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
                                      a.splice(i + 1, 0, { sort_order: newSo + 5, process_type: "", chip_model: "", holder_model: "", nose_r: "", t_number: "", note: "" });
                                      return a;
                                    });
                                  }} className="text-[10px] px-1 py-0.5 bg-teal-100 hover:bg-teal-200 text-teal-700 rounded">+</button>
                                </div>
                              </td>
                              <td className="px-1 py-1">
                                <div className="flex gap-1">
                                  <select value={s1} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, process_type: combine(e.target.value, s2)} : x))}
                                    className="w-1/2 border border-slate-200 rounded px-1 py-1 text-xs bg-white">
                                    <option value="">{tr("ncEditUi.processS1Placeholder", "（加）")}</option>
                                    {withCurrent(toolMasters.shave1, s1).map(v => <option key={v} value={v}>{v}</option>)}
                                  </select>
                                  <select value={s2} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, process_type: combine(s1, e.target.value)} : x))}
                                    className="w-1/2 border border-slate-200 rounded px-1 py-1 text-xs bg-white">
                                    <option value="">{tr("ncEditUi.processS2Placeholder", "（工）")}</option>
                                    {withCurrent(toolMasters.shave2, s2).map(v => <option key={v} value={v}>{v}</option>)}
                                  </select>
                                </div>
                              </td>
                              <td className="px-1 py-1">
                                <select value={t.chip_model ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, chip_model: e.target.value} : x))}
                                  className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs bg-white">
                                  <option value=""></option>
                                  {withCurrent(toolMasters.chip, t.chip_model ?? "").map(v => <option key={v} value={v}>{v}</option>)}
                                </select>
                              </td>
                              <td className="px-1 py-1">
                                <select value={t.holder_model ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, holder_model: e.target.value} : x))}
                                  className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs bg-white">
                                  <option value=""></option>
                                  {withCurrent(toolMasters.holder, t.holder_model ?? "").map(v => <option key={v} value={v}>{v}</option>)}
                                </select>
                              </td>
                              <td className="px-1 py-1"><input value={t.nose_r ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, nose_r: e.target.value} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                              <td className="px-1 py-1"><input value={t.t_number ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, t_number: e.target.value} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-center" /></td>
                              <td className="px-1 py-1"><input value={t.note ?? ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, note: e.target.value} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 text-xs" /></td>
                              <td className="px-1 py-1"><input value={t.sort_order != null ? String(t.sort_order) : ""} onChange={e => setToolingRows(r => r.map((x,j) => j===i ? {...x, sort_order: e.target.value === "" ? 0 : Number(e.target.value)} : x))}
                                className="w-full border border-slate-200 rounded px-1.5 py-1 font-mono text-xs text-right" type="number" /></td>
                              <td className="px-1 py-1 text-center"><button onClick={() => setToolingRows(r => r.filter((_,j) => j !== i))}
                                className="px-2 py-1 text-[11px] font-bold bg-red-50 hover:bg-red-500 text-red-500 hover:text-white border border-red-300 hover:border-red-500 rounded transition-colors">{tr("ncEditUi.deleteRow", "削除")}</button></td>
                            </tr>
                            );
                          })}
                          </tbody>
                        </table>
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
                  disabled={saving || (dirty.size === 0 && !isProvisionalLocked)}
                  className="flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-bold text-sm rounded-lg transition-colors"
                >
                  {(sbMode || sbRepeatMode) ? tr("ncEditUi.step1CompleteButton","STEP1完了 → STEP2(作業記録)へ") : tr("ncEditUi.workCompleteButton","✓ 作業完了（登録）")}
                </button>
                <div className="text-xs text-amber-700">{tr("ncEditUi.historyRecordHint", "← 登録と同時に変更履歴に記録されます")}</div>
                <div className="flex-1"></div>
                <button
                  onClick={handleCancel}
                  className="flex items-center gap-2 px-4 py-2.5 bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 font-bold text-sm rounded-lg transition-colors"
                >
                  {tr("ncEditUi.cancelDiscard", "✗ キャンセル（変更を破棄）")}
                </button>
              </div>

            </div>
          )}

        </div>
      </div>

      {/* [v112] 終了確認モーダル(変更種別選択 + バージョンインクリ、または一時保存) — MC側と同一仕様 */}
      {showKanryoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="bg-slate-800 px-5 py-3">
              <h2 className="text-base font-bold text-white">{tr("ncEditUi.endConfirmTitle", "終了確認 — 変更内容を記録")}</h2>
              <p className="text-xs text-slate-400 mt-0.5">{tr("ncEditUi.endConfirmDesc")}</p>
            </div>
            <div className="p-5 space-y-4">
              {/* [防御的修正] 万一sbMode/sbRepeatModeが同時に真になっても
                  リピート(sbRepeatMode)を優先し、通常の種別選択UIを表示する。 */}
              {(sbMode && !sbRepeatMode) ? (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                  <p className="text-sm font-bold text-blue-700 mb-1">{tr("ncEditUi.changeTypeNewLabel", "変更種別: 新規登録")}</p>
                  <p className="text-xs text-blue-600">{tr("ncEditUi.versionUpdateStep2Note", "バージョン更新後、STEP2(作業記録)へ進みます")}</p>
                </div>
              ) : (
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-2">{tr("ncEditUi.workTypeLabel", "作業種別 *")}</label>
                <div className="grid grid-cols-3 gap-2">
                  {["大変更","小変更","追加","修正","削除","訂正"].map(t => (
                    <button key={t} type="button"
                      onClick={() => setKanryoType(t)}
                      className={`py-2 rounded-lg text-sm font-bold border transition-colors ${
                        kanryoType === t
                          ? t === "大変更" ? "bg-red-600 text-white border-red-600"
                            : "bg-sky-600 text-white border-sky-600"
                          : "bg-white text-slate-600 border-slate-300 hover:border-sky-400"
                      }`}>
                      {tr(KANRYO_TYPE_KEYS[t] ?? "", t)}
                    </button>
                  ))}
                </div>
                {kanryoType === "大変更" ? (
                  <p className="text-xs text-red-600 mt-1.5 font-bold">{tr("ncEditUi.majorChangeWarning", "⚠️ 大変更: バージョンの整数部が+1（例: 1.0001 → 2.0001）")}</p>
                ) : (
                  <p className="text-xs text-sky-600 mt-1.5">{tr("ncEditUi.minorChangeNote", "小変更系: 100分の1位が+0.01（例: 1.0001 → 1.0101）")}</p>
                )}
              </div>
              )}
              <div>
                <label className="text-xs font-bold text-slate-500 block mb-1.5">{tr("ncEditUi.contentOptionalLabel", "内容（任意）")}</label>
                <textarea value={kanryoDetail} onChange={e => setKanryoDetail(e.target.value)}
                  rows={2} placeholder={sbMode ? tr("ncEditUi.sbDetailPlaceholder", "登録内容の補足（任意）") : tr("ncEditUi.detailPlaceholder", "変更の詳細内容を入力...")}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400 resize-none" />
              </div>
            </div>
            <div className="px-5 pb-5 flex gap-3">
              <button onClick={handleKanryoOk}
                className="flex-1 bg-sky-600 hover:bg-sky-700 text-white font-bold py-3 rounded-xl text-sm transition-colors">
                {(sbMode || sbRepeatMode) ? tr("ncEditUi.okToWorkRecord","OK — 作業記録へ") : tr("ncEditUi.okRegister","OK — 登録する")}
              </button>
              {!(sbMode || sbRepeatMode) && (
              <button onClick={handleKanryoTempSave}
                title={tr("ncEditUi.tempSaveHint", "バージョンを変更せず、入力内容だけを保存します")}
                className="px-4 py-3 border border-sky-300 text-sky-700 bg-sky-50 hover:bg-sky-100 font-bold text-sm rounded-xl transition-colors whitespace-nowrap">
                {tr("ncEditUi.tempSave", "💾 一時保存")}
              </button>
              )}
              <button onClick={handleKanryoCancel}
                className="px-5 py-3 border border-slate-300 rounded-xl text-sm text-slate-600 hover:bg-slate-50">
                {(sbMode || sbRepeatMode) ? tr("ncEditUi.skipNoWorkRecord","スキップ（作業記録なし）") : tr("ncEditUi.cancelDiscardChange","キャンセル（変更を取り消す）")}
              </button>
            </div>
          </div>
        </div>
      )}

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

      {/* [v095] 承認モーダル */}
      <ApprovalModal
        isOpen={approvalModalOpen}
        system="NC"
        programId={ncId}
        onSuccess={() => {
          setApprovalModalOpen(false);
          ncApi.findOne(ncId).then(r => setDetail(r.data));
        }}
        onCancel={() => setApprovalModalOpen(false)}
      />

      {/* Toast */}
      {uploadMsg && (
        <div className="fixed bottom-6 right-6 bg-slate-800 text-white px-5 py-3 rounded-lg shadow-lg text-sm z-50">
          {uploadMsg}
        </div>
      )}
    </>
  );
}
