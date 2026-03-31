export function ProcessBadge({ level }: { level: number }) {
  const colors = ["", "bg-sky-500", "bg-indigo-500", "bg-violet-500"];
  return (
    <span className={`text-[10px] font-bold text-white px-1.5 py-0.5 rounded ${colors[level] ?? "bg-slate-400"}`}>
      L{level}
    </span>
  );
}
