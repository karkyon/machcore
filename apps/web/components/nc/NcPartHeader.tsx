// apps/web/components/nc/NcPartHeader.tsx
// NC側4画面(詳細/変更登録/段取シート/作業記録)共通の部品情報ヘッダー。
// MC側の構造(text-2xl図番 + "/"セパレータ + バッジ群 + ID行)に準拠。
import { StatusBadge } from "@/components/nc/StatusBadge";
import { ProcessBadge } from "@/components/nc/ProcessBadge";

type NcPartHeaderPart = {
  drawingNo: string;
  name: string;
  partId?: string | number | null;
  clientName?: string | null;
};

type NcPartHeaderData = {
  id: number | string;
  processL: number;
  status: "NEW" | "PENDING_APPROVAL" | "APPROVED" | "CHANGING";
  version: string;
  processingId?: string | null;
  part: NcPartHeaderPart;
};

export function NcPartHeader({ data }: { data: NcPartHeaderData }) {
  const d = data;
  return (
    <div className="bg-white border-b border-slate-200 px-5 py-3 shrink-0">
      <div className="flex items-center gap-3 flex-wrap mb-1.5">
        <span className="font-mono text-sky-600 font-bold text-2xl leading-none">{d.part.drawingNo}</span>
        <span className="text-slate-300 text-xl font-light">/</span>
        <span className="font-bold text-slate-800 text-xl leading-none">{d.part.name}</span>
        <div className="flex items-center gap-2 ml-2">
          <ProcessBadge level={d.processL} />
          <StatusBadge status={d.status} />
          <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono">Ver. {d.version}</span>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[13px] text-slate-500 font-mono font-medium">
        <span>NC_id: <span className="text-slate-700">{d.id}</span></span>
        {d.part.partId != null && <><span className="text-slate-400">|</span><span>部品ID: <span className="text-slate-700">{d.part.partId}</span></span></>}
        {d.part.clientName && <><span className="text-slate-400">|</span><span>納入先: <span className="text-slate-700">{d.part.clientName}</span></span></>}
        {d.processingId && <><span className="text-slate-400">|</span><span>加工ID: <span className="text-slate-700">{d.processingId}</span></span></>}
      </div>
    </div>
  );
}
