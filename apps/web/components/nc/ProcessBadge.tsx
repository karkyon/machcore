export function ProcessBadge({ level }: { level: number }) {
  const colors = [
    "",
    "bg-sky-100 text-sky-700",
    "bg-indigo-100 text-indigo-700",
    "bg-violet-100 text-violet-700",
    "bg-purple-100 text-purple-700",
    "bg-pink-100 text-pink-700",
  ];
  return (
    <span className={`text-[11px] font-bold px-2 py-0.5 rounded font-mono ${colors[level] ?? "bg-slate-100 text-slate-600"}`}>
      L{level}
    </span>
  );
}
