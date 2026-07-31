"use client";
import { useLanguage } from "@/lib/i18n/LanguageContext";

type Status = "PROVISIONAL" | "NEW" | "PENDING_APPROVAL" | "APPROVED" | "CHANGING";

const MAP: Record<Status, { key: string; label: string; cls: string }> = {
  PROVISIONAL:      { key: "statusBadge.provisional",      label: "仮登録", cls: "bg-slate-200 text-slate-500" },
  NEW:              { key: "statusBadge.new",              label: "新規",  cls: "bg-blue-100 text-blue-700" },
  PENDING_APPROVAL: { key: "statusBadge.pendingApproval",   label: "未承認", cls: "bg-amber-100 text-amber-700" },
  APPROVED:         { key: "statusBadge.approved",          label: "承認済", cls: "bg-green-100 text-green-700" },
  CHANGING:         { key: "statusBadge.changing",          label: "変更中", cls: "bg-red-100 text-red-700" },
};

export function StatusBadge({ status }: { status: Status }) {
  const { t: tr } = useLanguage();
  const { key, label, cls } = MAP[status] ?? MAP.NEW;
  return (
    <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${cls}`}>
      {tr(key, label)}
    </span>
  );
}
