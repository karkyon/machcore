"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ncApi, NcDetail, NcTool, ChangeHistory, WorkRecord, SetupSheetLog,
} from "@/lib/api";
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";
import { useAuth } from "@/contexts/AuthContext";
import AuthModal from "@/components/auth/AuthModal";

type MainTab = "lathe" | "tools" | "history" | "files";
type HistorySubTab = "change" | "work" | "print";

const CHANGE_TYPE_LABELS: Record<string, string> = {
  NEW_REGISTRATION: "新規登録",
  CHANGE:           "変更",
  APPROVAL:         "承認",
  MIGRATION:        "移行",
};

export default function NcDetailPage() {
  const { nc_id } = useParams();
  const router    = useRouter();
  const ncId      = Number(nc_id);

  const [detail,     setDetail]     = useState<NcDetail | null>(null);
  const [loadError,  setLoadError]  = useState<string | null>(null);

  const [mainTab,    setMainTab]    = useState<MainTab>("lathe");
  const [histTab,    setHistTab]    = useState<HistorySubTab>("change");

  const [changes,    setChanges]    = useState<ChangeHistory[] | null>(null);
  const [works,      setWorks]      = useState<WorkRecord[]    | null>(null);
  const [prints,     setPrints]     = useState<SetupSheetLog[] | null>(null);
  const [histLoading, setHistLoading] = useState(false);

  const { operator, isAuthenticated, logout } = useAuth();
  const [authModalOpen, setAuthModalOpen]     = useState(false);
  const [authSessionType, setAuthSessionType] = useState("edit");

  const openAuth = (sessionType: string) => {
    setAuthSessionType(sessionType);
    setAuthModalOpen(true);
  };

  // NC詳細ロード
  useEffect(() => {
    if (!ncId) return;
    ncApi.findOne(ncId)
      .then(r => setDetail(r.data))
      .catch(e => setLoadError(e.message));
  }, [ncId]);

  // 履歴タブ選択時にAPIコール（初回のみ）
  useEffect(() => {
    if (mainTab !== "history") return;
    if (histTab === "change"  && changes === null) {
      setHistLoading(true);
      ncApi.changeHistory(ncId).then(r => setChanges(r.data)).finally(() => setHistLoading(false));
    }
    if (histTab === "work"    && works === null) {
      setHistLoading(true);
      ncApi.workRecords(ncId).then(r => setWorks(r.data)).finally(() => setHistLoading(false));
    }
    if (histTab === "print"   && prints === null) {
      setHistLoading(true);
      ncApi.setupSheetLogs(ncId).then(r => setPrints(r.data)).finally(() => setHistLoading(false));
    }
  }, [mainTab, histTab, ncId, changes, works, prints]);

  const fmtDate = (s: string) =>
    new Date(s).toLocaleString("ja-JP", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-red-500 text-sm">読み込みエラー: {loadError}</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-400 text-sm">読み込み中...</div>
      </div>
    );
  }

  const d = detail;

  return (
    <>
    <div className="h-screen flex flex-col bg-slate-50">

      {/* ── ヘッダー ── */}
      <header className="bg-slate-800 text-white px-5 py-3 flex items-center gap-3 shrink-0">
        <button
          onClick={() => router.push("/nc/search")}
          className="text-slate-400 hover:text-white text-xs transition-colors"
        >
          ← 検索結果
        </button>
        <span className="text-slate-600">|</span>
        <span className="font-mono text-sky-400 font-bold text-sm">MachCore</span>
        <span className="text-slate-400 text-xs">|</span>
        <span className="text-sm font-medium">NC 詳細</span>
        <span className="ml-auto flex items-center gap-2">
          {isAuthenticated && operator ? (
            <>
              <span className="text-[11px] bg-red-600 text-white px-2 py-0.5 rounded font-bold animate-pulse">
                作業中: {operator.name}
              </span>
              <button
                onClick={logout}
                className="text-[11px] text-slate-400 hover:text-white transition-colors"
              >
                終了
              </button>
            </>
          ) : (
            <button
              onClick={() => openAuth("edit")}
              className="text-[11px] bg-sky-600 hover:bg-sky-700 text-white px-3 py-1 rounded font-bold transition-colors"
            >
              この作業を開始する
            </button>
          )}
          <button className="text-[11px] bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded font-bold transition-colors">
            PG → USB 書き出し
          </button>
        </span>
      </header>

      {/* ── 部品ヘッダーエリア ── */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-sky-600 font-bold text-lg">{d.part.drawingNo}</span>
          <ProcessBadge level={d.processL} />
          <StatusBadge status={d.status} />
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">
            Ver. {d.version}
          </span>
        </div>
        <div className="text-sm text-slate-700 font-medium mb-1">{d.part.name}</div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>NC_id: {d.id}</span>
          <span>部品ID: {d.part.partId}</span>
          {d.part.clientName && <span>納入先: {d.part.clientName}</span>}
          {d.processingId && <span>加工ID: {d.processingId}</span>}
        </div>
      </div>

      {/* ── メインタブバー ── */}
      <div className="bg-white border-b border-slate-200 px-5 shrink-0 flex gap-0">
        {([ 
          { key: "lathe",   label: "旋盤データ" },
          { key: "tools",   label: "工具リスト" },
          { key: "history", label: "📋 履歴" },
          { key: "files",   label: "写真・図" },
        ] as { key: MainTab; label: string }[]).map(t => (
          <button
            key={t.key}
            onClick={() => setMainTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              mainTab === t.key
                ? "border-sky-500 text-sky-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── タブコンテンツ ── */}
      <div className="flex-1 overflow-y-auto">

        {/* ─ 旋盤データ ─ */}
        {mainTab === "lathe" && (
          <div className="p-5 max-w-2xl space-y-4">
            <Section title="工程・機械">
              <Row label="工程"       value={`L${d.processL}`} />
              <Row label="機械"       value={d.machine?.machineName ?? d.machine?.machineCode ?? "—"} />
              <Row label="加工時間"   value={d.machiningTime != null ? `${d.machiningTime} 分` : "—"} />
              <Row label="段取参考"   value={d.setupTimeRef  != null ? `${d.setupTimeRef} 分`  : "—"} />
            </Section>
            <Section title="ファイル情報">
              <Row label="フォルダ名" value={d.folderName ?? "—"} />
              <Row label="ファイル名" value={d.fileName   ?? "—"} />
              <Row label="O番号"      value={d.oNumber    ?? "—"} />
            </Section>
            <Section title="付帯情報">
              <Row label="図枚数"   value={`${d.drawingCount} 枚`} />
              <Row label="写真枚数" value={`${d.photoCount} 枚`} />
            </Section>
            {d.clampNote && (
              <Section title="クランプ・備考">
                <pre className="text-xs text-slate-700 whitespace-pre-wrap font-sans">{d.clampNote}</pre>
              </Section>
            )}
            <Section title="登録・承認">
              <Row label="登録者" value={d.registrar.name} />
              <Row label="登録日" value={fmtDate(d.createdAt)} />
              <Row label="承認者" value={d.approver?.name ?? "未承認"} />
            </Section>
          </div>
        )}

        {/* ─ 工具リスト ─ */}
        {mainTab === "tools" && (
          <div className="p-5">
            {d.tools.length === 0 ? (
              <Empty label="工具データなし" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                  <thead className="bg-slate-100 text-slate-600">
                    <tr>
                      {["No", "加工種別", "チップ型番", "ホルダー型番", "ノーズR", "T番号", "備考"].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.tools.map((t: NcTool, i: number) => (
                      <tr key={t.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                        <td className="px-3 py-2 font-mono text-slate-500">{t.sortOrder}</td>
                        <td className="px-3 py-2">{t.processType ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{t.chipModel   ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{t.holderModel ?? "—"}</td>
                        <td className="px-3 py-2">{t.noseR   ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{t.tNumber ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-500">{t.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ─ 履歴 ─ */}
        {mainTab === "history" && (
          <div className="flex flex-col h-full">
            {/* サブタブ */}
            <div className="bg-slate-50 border-b border-slate-200 px-5 flex gap-0 shrink-0">
              {([
                { key: "change", label: "✏️ 変更履歴" },
                { key: "work",   label: "⏱ 作業記録" },
                { key: "print",  label: "🖨 印刷履歴" },
              ] as { key: HistorySubTab; label: string }[]).map(t => (
                <button
                  key={t.key}
                  onClick={() => setHistTab(t.key)}
                  className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
                    histTab === t.key
                      ? "border-sky-500 text-sky-600"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              {histLoading && <div className="text-slate-400 text-sm">読み込み中...</div>}

              {/* 変更履歴 */}
              {histTab === "change" && !histLoading && (
                changes === null ? null :
                changes.length === 0 ? <Empty label="変更履歴なし" /> : (
                  <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                    <thead className="bg-slate-100 text-slate-600">
                      <tr>
                        {["日時", "種別", "担当者", "Ver変化", "変更内容"].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {changes.map((c, i) => (
                        <tr key={c.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(c.changed_at)}</td>
                          <td className="px-3 py-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              c.change_type === "APPROVE" ? "bg-green-100 text-green-700" :
                              c.change_type === "NEW"     ? "bg-blue-100 text-blue-700" :
                              c.change_type === "MIGRATE" ? "bg-slate-100 text-slate-500" :
                              "bg-amber-100 text-amber-700"
                            }`}>
                              {CHANGE_TYPE_LABELS[c.change_type] ?? c.change_type}
                            </span>
                          </td>
                          <td className="px-3 py-2">{c.operator_name ?? "—"}</td>
                          <td className="px-3 py-2 font-mono text-slate-500">
                            {c.ver_before && c.ver_after ? `${c.ver_before} → ${c.ver_after}` : "—"}
                          </td>
                          <td className="px-3 py-2 text-slate-600">{c.change_detail ?? ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}

              {/* 作業記録 */}
              {histTab === "work" && !histLoading && (
                works === null ? null :
                works.length === 0 ? <Empty label="作業記録なし" /> : (
                  <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                    <thead className="bg-slate-100 text-slate-600">
                      <tr>
                        {["作業日", "担当者", "機械", "段取(分)", "加工(分)", "個数", "備考", ""].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {works.map((w, i) => (
                        <tr key={w.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(w.work_date)}</td>
                          <td className="px-3 py-2">{w.operator_name ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{w.machine_code ?? "—"}</td>
                          <td className="px-3 py-2 text-right">{w.setup_time    ?? "—"}</td>
                          <td className="px-3 py-2 text-right">{w.machining_time ?? "—"}</td>
                          <td className="px-3 py-2 text-right">{w.quantity ?? "—"}</td>
                          <td className="px-3 py-2 text-slate-500">{w.note ?? ""}</td>
                          <td className="px-3 py-2">
                            <button
                              onClick={() => router.push(`/nc/${ncId}/record?edit=${w.id}`)}
                              className="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-0.5 rounded transition-colors"
                            >
                              ✏️ 編集
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}

              {/* 印刷履歴 */}
              {histTab === "print" && !histLoading && (
                prints === null ? null :
                prints.length === 0 ? <Empty label="印刷履歴なし" /> : (
                  <table className="w-full text-xs border-collapse bg-white rounded-xl overflow-hidden shadow-sm">
                    <thead className="bg-slate-100 text-slate-600">
                      <tr>
                        {["印刷日時", "印刷者", "バージョン"].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-bold border-b border-slate-200">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {prints.map((p, i) => (
                        <tr key={p.id} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                          <td className="px-3 py-2 font-mono whitespace-nowrap text-slate-500">{fmtDate(p.printed_at)}</td>
                          <td className="px-3 py-2">{p.printer_name ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{p.version ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}
            </div>
          </div>
        )}

        {/* ─ 写真・図 ─ */}
        {mainTab === "files" && (
          <div className="p-5">
            <Empty label="写真・図（未実装）" />
          </div>
        )}

      </div>
    </div>

    <AuthModal
      isOpen={authModalOpen}
      sessionType={authSessionType}
      ncProgramId={ncId}
      onSuccess={() => setAuthModalOpen(false)}
      onCancel={() => setAuthModalOpen(false)}
    />
    </>
  );
}

// ── ヘルパーコンポーネント ──
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
      <div className="px-4 py-2 bg-slate-50 border-b border-slate-100">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">{title}</span>
      </div>
      <div className="divide-y divide-slate-50">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center px-4 py-2 gap-4">
      <span className="text-xs text-slate-400 w-24 shrink-0">{label}</span>
      <span className="text-sm text-slate-700 font-mono">{value}</span>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-300 gap-2">
      <div className="text-4xl">📂</div>
      <p className="text-sm">{label}</p>
    </div>
  );
}