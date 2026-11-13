"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/**
 * 手動印刷(システム設定の出力方式=MANUAL)で発行した段取シートを画面に表示し、
 * 利用者がブラウザの印刷機能でプリンタを選んで印刷するためのモーダル。
 * 表示した時点で発行履歴には記録済み(print_method=MANUAL)。透かしのない正式な段取シート。
 */
export function ManualPrintModal({ pdfBase64, note, onClose }: {
  pdfBase64: string;
  note?: string | null;
  onClose: () => void;
}) {
  const { t } = useLanguage();
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [printed, setPrinted] = useState(false);

  const url = useMemo(() => {
    const bin = atob(pdfBase64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
  }, [pdfBase64]);
  // 別タブで開いた後に閉じても表示が消えないよう、解放は少し待つ
  useEffect(() => () => { setTimeout(() => URL.revokeObjectURL(url), 60000); }, [url]);

  const handlePrint = () => {
    setPrinted(true);
    try {
      const w = frameRef.current?.contentWindow;
      if (!w) throw new Error("no frame");
      w.focus();
      w.print();
    } catch {
      // ブラウザが埋め込みPDFの印刷を許さない場合は別タブで開いて印刷してもらう
      window.open(url, "_blank");
    }
  };
  const handleOpenTab = () => { setPrinted(true); window.open(url, "_blank"); };
  const handleClose = () => {
    if (!printed && !window.confirm(t("manualPrint.closeConfirm", "まだ印刷していません。閉じてもよろしいですか？"))) return;
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-3">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[94vh] flex flex-col overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-3 shrink-0 flex-wrap">
          <div className="flex-1 min-w-[240px]">
            <p className="font-bold text-slate-800 text-sm">{t("manualPrint.title", "🖥 段取シート（手動印刷）")}</p>
            <p className="text-xs text-slate-500">{t("manualPrint.recordedNote", "発行履歴に記録済みです。「印刷」ボタンからプリンタを選んで印刷してください。")}</p>
            {note && <p className="text-xs text-amber-700 font-bold mt-0.5">{note}</p>}
          </div>
          <button onClick={handlePrint}
            className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl text-sm">
            {t("manualPrint.printButton", "🖨 印刷")}
          </button>
          <button onClick={handleOpenTab}
            className="px-4 py-2.5 bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 font-bold rounded-xl text-sm">
            {t("manualPrint.openTabButton", "別タブで開く")}
          </button>
          <button onClick={handleClose}
            className="px-4 py-2.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl text-sm">
            {t("manualPrint.closeButton", "閉じる")}
          </button>
        </div>
        <iframe ref={frameRef} src={url} title="setup-sheet" className="flex-1 w-full border-0 bg-slate-100" />
      </div>
    </div>
  );
}
