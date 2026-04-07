export function ProcessBadge({ level }: { level: number }) {
  const colors = ["", "bg-sky-500", "bg-indigo-500", "bg-violet-500", "bg-purple-500", "bg-pink-500"];
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-bold text-white shrink-0 ${colors[level] ?? "bg-slate-400"}`}>
      L{level}
    </span>
  );
}
