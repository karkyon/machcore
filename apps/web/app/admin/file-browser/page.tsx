"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AdminLayout } from "@/components/admin/AdminLayout";

type FileNode = { name: string; path: string; type: "file" | "dir"; size?: number; mtime?: string; hasChildren?: boolean; children?: FileNode[]; loaded?: boolean };
type TabType = "photos" | "drawings" | "programs";

const TAB_LABELS: Record<TabType, string> = { photos: "写真", drawings: "図", programs: "プログラム" };
const TAB_COLORS: Record<TabType, string> = {
  photos:   "bg-rose-50 text-rose-700 border-rose-300",
  drawings: "bg-violet-50 text-violet-700 border-violet-300",
  programs: "bg-teal-50 text-teal-700 border-teal-300",
};
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff"]);
const TEXT_EXTS = new Set([".txt", ".nc", ".mpf", ".spf", ".cnc", ".min", ".prg", ""]);
const PDF_EXTS   = new Set([".pdf"]);

function extOf(n: string) { return n.includes(".") ? "." + n.split(".").pop()!.toLowerCase() : ""; }
function fmtSize(b: number) { if (b < 1024) return b + " B"; if (b < 1024*1024) return (b/1024).toFixed(1) + " KB"; return (b/1024/1024).toFixed(1) + " MB"; }
function fmtDate(s?: string) { if (!s) return ""; try { return new Date(s).toLocaleString("ja-JP"); } catch { return s ?? ""; } }

function TreeNode({ node, depth, onSelect, onExpand, selectedPath, searchKw }: {
  node: FileNode; depth: number;
  onSelect: (n: FileNode) => void;
  onExpand: (n: FileNode) => void;
  selectedPath: string; searchKw: string;
}) {
  const isDir = node.type === "dir";
  const isSelected = node.path === selectedPath;
  const isOpen = node.loaded && (node.children ?? []).length >= 0;
  const nameMatch = searchKw ? node.name.toLowerCase().includes(searchKw.toLowerCase()) : false;

  const handleClick = () => {
    onSelect(node);
    if (isDir) {
      if (!node.loaded) { onExpand(node); }
      else { node.loaded = !isOpen; } // toggle: set loaded=false to collapse
    }
  };

  return (
    <div>
      <div
        className={"flex items-center gap-1 py-0.5 rounded cursor-pointer text-xs select-none transition-colors " +
          (isSelected ? "bg-sky-100 text-sky-800 font-bold" : nameMatch ? "bg-yellow-50 text-yellow-800" : "hover:bg-slate-100 text-slate-700")}
        style={{ paddingLeft: `${8 + depth * 14}px`, paddingRight: "8px" }}
        onClick={handleClick}
      >
        {isDir ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
            <path d={isOpen ? "M19 9l-7 7-7-7" : "M9 18l6-6-6-6"}/>
          </svg>
        ) : (
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 ml-0.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
          </svg>
        )}
        <span className="truncate flex-1">{node.name}</span>
        {!isDir && node.size !== undefined && <span className="text-slate-400 shrink-0 text-[10px]">{fmtSize(node.size)}</span>}
        {!isDir && node.mtime && <span className="text-slate-300 shrink-0 text-[10px] ml-1">{fmtDate(node.mtime)}</span>}
        {isDir && node.hasChildren && !node.loaded && <span className="text-slate-300 text-[10px]">▶</span>}
      </div>
      {isDir && node.loaded && (node.children ?? []).map((c, i) => (
        <TreeNode key={i} node={c} depth={depth + 1} onSelect={onSelect} onExpand={onExpand} selectedPath={selectedPath} searchKw={searchKw} />
      ))}
    </div>
  );
}

export default function FileBrowserPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [tab, setTab]             = useState<TabType>("photos");
  const [trees, setTrees]         = useState<Record<TabType, FileNode[]>>({ photos: [], drawings: [], programs: [] });
  const [rootPaths, setRootPaths] = useState<Record<TabType, string>>({ photos: "", drawings: "", programs: "" });
  const [rootLoading, setRootLoading] = useState(false);
  const [selected, setSelected]   = useState<FileNode | null>(null);
  const [preview, setPreview]     = useState<{ type: "image" | "pdf" | "text" | "none"; url?: string; text?: string } | null>(null);
  const [prevLoading, setPrevLoading] = useState(false);
  const [searchKw, setSearchKw]   = useState("");
  const [toast, setToast]         = useState<{ msg: string; ok: boolean } | null>(null);
  const [delConfirm, setDelConfirm] = useState<FileNode | null>(null);
  const [uploading, setUploading] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [uploadDir, setUploadDir] = useState("");

  const getToken = () => sessionStorage.getItem("admin_token") ?? "";
  const showToast = (msg: string, ok = true) => { setToast({ msg, ok }); setTimeout(() => setToast(null), 4000); };

  useEffect(() => {
    if (!sessionStorage.getItem("admin_token")) { router.replace("/admin/login"); return; }
    loadRoots();
  }, []);

  const apiFetch = useCallback(async (url: string, opts?: RequestInit) => {
    const res = await fetch(url, { ...opts, headers: { Authorization: `Bearer ${getToken()}`, ...(opts?.headers ?? {}) } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }, []);

  const loadRoots = async () => {
    setRootLoading(true);
    try {
      const data = await apiFetch("/api/admin/files/tree");
      setTrees({
        photos:   (data.photos?.children   ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        drawings: (data.drawings?.children ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        programs: (data.programs?.children ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
      });
      setRootPaths({
        photos:   data.photos?.path   ?? "",
        drawings: data.drawings?.path ?? "",
        programs: data.programs?.path ?? "",
      });
    } catch (e: any) { showToast("ツリー取得失敗: " + e.message, false); }
    finally { setRootLoading(false); }
  };

  // ディレクトリ展開: 対象ノードに子を遅延ロード
  const expandNode = useCallback(async (target: FileNode) => {
    try {
      const data = await apiFetch(`/api/admin/files/tree?path=${encodeURIComponent(target.path)}`);
      const children: FileNode[] = (data.children ?? []).map((n: FileNode) => ({ ...n, loaded: false }));

      const patchTree = (nodes: FileNode[]): FileNode[] =>
        nodes.map(n => {
          if (n.path === target.path) return { ...n, children, loaded: true };
          if (n.children) return { ...n, children: patchTree(n.children) };
          return n;
        });

      setTrees(prev => ({
        ...prev,
        [tab]: patchTree(prev[tab]),
      }));
    } catch (e: any) { showToast("展開失敗: " + e.message, false); }
  }, [tab, apiFetch]);

  // ディレクトリをクリック時はトグル（展開済みならcollapseも可）
  const handleExpand = useCallback((node: FileNode) => {
    if (node.loaded) {
      // collapse: loaded=false にする
      const patchTree = (nodes: FileNode[]): FileNode[] =>
        nodes.map(n => {
          if (n.path === node.path) return { ...n, loaded: false };
          if (n.children) return { ...n, children: patchTree(n.children) };
          return n;
        });
      setTrees(prev => ({ ...prev, [tab]: patchTree(prev[tab]) }));
    } else {
      expandNode(node);
    }
  }, [tab, expandNode]);

  const handleSelect = async (node: FileNode) => {
    setSelected(node);
    if (node.type === "dir") { setUploadDir(node.path); setPreview(null); return; }
    setPrevLoading(true); setPreview(null);
    const ext = extOf(node.name);
    const url = `/api/admin/files/preview?path=${encodeURIComponent(node.path)}`;
    try {
      if (IMAGE_EXTS.has(ext)) {
        const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
        const blob = await res.blob();
        setPreview({ type: "image", url: URL.createObjectURL(blob) });
      } else if (PDF_EXTS.has(ext)) {
        const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
        const blob = await res.blob();
        setPreview({ type: "pdf", url: URL.createObjectURL(blob) });
      } else if (TEXT_EXTS.has(ext)) {
        const res = await fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } });
        const text = await res.text();
        setPreview({ type: "text", text });
      } else { setPreview({ type: "none" }); }
    } catch { setPreview({ type: "none" }); }
    finally { setPrevLoading(false); }
  };

  const handleDownload = () => {
    if (!selected || selected.type === "dir") return;
    fetch(`/api/admin/files/download?path=${encodeURIComponent(selected.path)}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then(r => r.blob()).then(blob => {
        const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = selected.name; a.click(); URL.revokeObjectURL(a.href);
      });
  };

  const handleDelete = async (node: FileNode) => {
    try {
      await apiFetch(`/api/admin/files/delete?path=${encodeURIComponent(node.path)}`, { method: "DELETE" });
      showToast("削除しました: " + node.name);
      setDelConfirm(null);
      if (selected?.path === node.path) { setSelected(null); setPreview(null); }
      await loadRoots();
    } catch (e: any) { showToast("削除失敗: " + e.message, false); }
  };

  const handleUpload = async (file: File) => {
    if (!uploadDir) { showToast("アップロード先ディレクトリを選択してください", false); return; }
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", file); fd.append("dest_dir", uploadDir); fd.append("file_name", file.name);
      await apiFetch("/api/admin/files/upload", { method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: fd });
      showToast("アップロード完了: " + file.name);
      // 親ディレクトリを再ロード
      if (uploadDir) {
        const patchTree = (nodes: FileNode[]): FileNode[] =>
          nodes.map(n => {
            if (n.path === uploadDir) return { ...n, loaded: false }; // 再展開させる
            if (n.children) return { ...n, children: patchTree(n.children) };
            return n;
          });
        setTrees(prev => ({ ...prev, [tab]: patchTree(prev[tab]) }));
        // すぐ展開
        expandNode({ path: uploadDir, name: "", type: "dir", loaded: true });
      }
    } catch (e: any) { showToast("アップロード失敗: " + e.message, false); }
    finally { setUploading(false); }
  };

  const currentTree = trees[tab];
  const rootPath    = rootPaths[tab];

  return (
    <AdminLayout pathname={pathname}>
      <div className="flex flex-col h-full min-h-0 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 bg-white flex items-center gap-3 shrink-0 flex-wrap">
          <h1 className="text-lg font-bold text-slate-800">ファイルブラウザ</h1>
          <div className="flex gap-1">
            {(["photos", "drawings", "programs"] as TabType[]).map(t => (
              <button key={t} onClick={() => { setTab(t); setSelected(null); setPreview(null); setSearchKw(""); }}
                className={"px-3 py-1 text-xs font-bold rounded-full border transition-colors " +
                  (tab === t ? TAB_COLORS[t] : "bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200")}>
                {TAB_LABELS[t]}
              </button>
            ))}
          </div>
          <input value={searchKw} onChange={e => setSearchKw(e.target.value)} placeholder="ファイル名検索…"
            className="ml-auto border border-slate-200 rounded-lg px-3 py-1.5 text-xs w-44 focus:outline-none focus:ring-2 focus:ring-sky-400" />
          <button onClick={loadRoots} disabled={rootLoading}
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-bold rounded-lg border border-slate-200 transition-colors">
            {rootLoading ? "読込中…" : "↺ 更新"}
          </button>
        </div>

        {toast && (
          <div className={"fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-white text-sm font-bold shadow-lg " + (toast.ok ? "bg-green-600" : "bg-red-600")}>
            {toast.msg}
          </div>
        )}

        {delConfirm && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-96">
              <h2 className="text-base font-bold text-red-700 mb-3">強制削除の確認</h2>
              <p className="text-sm text-slate-600 mb-1">以下を完全に削除します（元に戻せません）:</p>
              <p className="text-xs font-mono bg-slate-50 rounded p-2 text-slate-800 break-all mb-4">{delConfirm.path}</p>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setDelConfirm(null)} className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-bold rounded-lg hover:bg-slate-200">キャンセル</button>
                <button onClick={() => handleDelete(delConfirm)} className="px-4 py-2 bg-red-600 text-white text-sm font-bold rounded-lg hover:bg-red-700">削除実行</button>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-1 min-h-0 overflow-hidden">
          <div className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 shrink-0">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{TAB_LABELS[tab]}</p>
              {rootPath && <p className="text-[10px] text-slate-400 font-mono truncate mt-0.5">{rootPath}</p>}
            </div>
            <div className="flex-1 overflow-y-auto py-1">
              {rootLoading ? (
                <div className="flex items-center justify-center h-20 text-slate-400 text-xs">読込中…</div>
              ) : currentTree.length === 0 ? (
                <div className="flex items-center justify-center h-20 text-slate-400 text-xs">ファイルがありません</div>
              ) : currentTree.map((node, i) => (
                <TreeNode key={i} node={node} depth={0} onSelect={handleSelect} onExpand={handleExpand} selectedPath={selected?.path ?? ""} searchKw={searchKw} />
              ))}
            </div>
            <div className="border-t border-slate-200 p-2 shrink-0">
              <p className="text-[10px] text-slate-400 mb-1 font-bold">
                📤 先: {uploadDir ? <span className="font-mono text-slate-600">{uploadDir.split("/").slice(-2).join("/")}</span> : <span className="text-slate-300">ディレクトリを選択</span>}
              </p>
              <button onClick={() => uploadRef.current?.click()} disabled={!uploadDir || uploading}
                className={"w-full py-1.5 text-xs font-bold rounded-lg border transition-colors " +
                  (uploadDir ? "bg-teal-50 text-teal-700 border-teal-200 hover:bg-teal-100" : "bg-slate-50 text-slate-300 border-slate-200 cursor-not-allowed")}>
                {uploading ? "アップロード中…" : "+ ファイルを登録"}
              </button>
              <input ref={uploadRef} type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { handleUpload(f); e.target.value = ""; } }} />
            </div>
          </div>

          <div className="flex-1 flex flex-col overflow-hidden">
            {selected ? (
              <>
                <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-200 bg-white shrink-0 flex-wrap">
                  <span className="text-sm font-bold text-slate-800 truncate max-w-xs">{selected.name}</span>
                  {selected.type === "file" && selected.size !== undefined && <span className="text-xs text-slate-400">{fmtSize(selected.size)}</span>}
                  {selected.mtime && <span className="text-xs text-slate-400">{fmtDate(selected.mtime)}</span>}
                  <p className="text-[10px] text-slate-300 font-mono truncate w-full">{selected.path}</p>
                  <div className="ml-auto flex gap-1.5">
                    {selected.type === "file" && (
                      <button onClick={handleDownload} className="px-3 py-1 bg-sky-50 text-sky-700 text-xs font-bold rounded-lg border border-sky-200 hover:bg-sky-100">⬇ DL</button>
                    )}
                    <button onClick={() => setDelConfirm(selected)} className="px-3 py-1 bg-red-50 text-red-600 text-xs font-bold rounded-lg border border-red-200 hover:bg-red-100">🗑 削除</button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto bg-slate-50 flex items-start justify-center p-4">
                  {prevLoading ? (
                    <div className="flex items-center justify-center h-32 text-slate-400 text-sm">プレビュー読込中…</div>
                  ) : selected.type === "dir" ? (
                    <div className="text-center text-slate-400 mt-20">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-3 text-slate-300"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                      <p className="text-sm font-bold text-slate-500">{selected.name}</p>
                    </div>
                  ) : !preview || preview.type === "none" ? (
                    <div className="text-center text-slate-400 mt-20"><p className="text-sm">プレビュー非対応: {extOf(selected.name)}</p></div>
                  ) : preview.type === "image" ? (
                    <img src={preview.url} alt={selected.name} className="max-w-full max-h-[70vh] object-contain rounded-lg shadow-md" />
                  ) : preview.type === "pdf" ? (
                    <iframe src={preview.url} className="w-full h-[70vh] rounded-lg border border-slate-200 bg-white" />
                  ) : preview.type === "text" ? (
                    <pre className="bg-white rounded-lg border border-slate-200 p-4 text-xs font-mono text-slate-700 whitespace-pre-wrap break-all max-w-full overflow-auto max-h-[70vh] shadow">{preview.text}</pre>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-300">
                <div className="text-center">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-4"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"/></svg>
                  <p className="text-sm">左のツリーからファイルまたはディレクトリを選択</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
