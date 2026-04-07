type Status = "NEW" | "PENDING_APPROVAL" | "APPROVED" | "CHANGING";

const MAP: Record<Status, { label: string; cls: string }> = {
  NEW:              { label: "新規",  cls: "bg-blue-100 text-blue-700" },
  PENDING_APPROVAL: { label: "未承認", cls: "bg-amber-100 text-amber-700" },
  APPROVED:         { label: "承認済", cls: "bg-green-100 text-green-700" },
  CHANGING:         { label: "変更中", cls: "bg-red-100 text-red-700" },
};

export function StatusBadge({ status }: { status: Status }) {
  const { label, cls } = MAP[status] ?? MAP.NEW;
  return (
    <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${cls}`}>
      {label}
    </span>
  );
}
