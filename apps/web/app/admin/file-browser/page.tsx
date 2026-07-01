"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { fbGetCache, fbSetCache, fbSearchCache, type FbIndexItem, type FbTab } from "@/lib/file-browser-index";

type FileNode = { name: string; path: string; type: "file" | "dir"; size?: number; mtime?: string; hasChildren?: boolean; children?: FileNode[]; loaded?: boolean };
type TabType = "photos" | "drawings" | "programs" | "nc_photos" | "nc_drawings" | "nc_programs";
type TrashItem = { id: string; originalPath: string; trashPath: string; name: string; type: "file" | "dir"; deletedAt: string; existsInTrash: boolean };

const TAB_LABELS: Record<TabType, string> = {
  photos: "MC写真", drawings: "MC図", programs: "MCプログラム",
  nc_photos: "NC写真", nc_drawings: "NC図", nc_programs: "NCプログラム",
};
const TAB_COLORS: Record<TabType, string> = {
  photos:      "bg-rose-50 text-rose-700 border-rose-300",
  drawings:    "bg-violet-50 text-violet-700 border-violet-300",
  programs:    "bg-teal-50 text-teal-700 border-teal-300",
  nc_photos:   "bg-sky-50 text-sky-700 border-sky-300",
  nc_drawings: "bg-amber-50 text-amber-700 border-amber-300",
  nc_programs: "bg-emerald-50 text-emerald-700 border-emerald-300",
};
const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff"]);
const TEXT_EXTS = new Set([".txt", ".nc", ".mpf", ".spf", ".cnc", ".min", ".prg", ""]);
const PDF_EXTS   = new Set([".pdf"]);

function extOf(n: string) { return n.includes(".") ? "." + n.split(".").pop()!.toLowerCase() : ""; }
function fmtSize(b: number) { if (b < 1024) return b + " B"; if (b < 1024*1024) return (b/1024).toFixed(1) + " KB"; return (b/1024/1024).toFixed(1) + " MB"; }
function fmtDate(s?: string) { if (!s) return ""; try { return new Date(s).toLocaleString("ja-JP"); } catch { return s ?? ""; } }

function TreeNode({ node, depth, onSelect, onExpand, selectedPath, searchKw, activeHitPath, onSearchEnterNext }: {
  node: FileNode; depth: number;
  onSelect: (n: FileNode) => void;
  onExpand: (n: FileNode) => void;
  selectedPath: string; searchKw: string; activeHitPath: string;
  onSearchEnterNext: () => void;
}) {
  const isDir = node.type === "dir";
  const isSelected = node.path === selectedPath;
  const isOpen = node.loaded && (node.children ?? []).length >= 0;
  const nameMatch = searchKw ? node.name.toLowerCase().includes(searchKw.toLowerCase()) : false;
  const isActiveHit = !!activeHitPath && node.path === activeHitPath;

  const handleClick = () => {
    onSelect(node);
    if (isDir) {
      if (!node.loaded) { onExpand(node); }
      else { node.loaded = !isOpen; } // toggle: set loaded=false to collapse
    }
  };

  // ハイライト中の行にフォーカスがある状態でEnterを押すと、検索ボックスと同様に次候補へ移動できる
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && isActiveHit) {
      e.preventDefault();
      onSearchEnterNext();
    }
  };

  return (
    <div>
      <div
        data-path={node.path}
        tabIndex={-1}
        className={"flex items-center gap-1 py-0.5 rounded cursor-pointer text-xs select-none transition-colors outline-none focus:ring-2 focus:ring-amber-500 " +
          (isActiveHit ? "bg-amber-200 text-amber-900 font-bold ring-2 ring-amber-400" :
           isSelected ? "bg-sky-100 text-sky-800 font-bold" : nameMatch ? "bg-yellow-50 text-yellow-800" : "hover:bg-slate-100 text-slate-700")}
        style={{ paddingLeft: `${8 + depth * 14}px`, paddingRight: "8px" }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
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
        <TreeNode key={i} node={c} depth={depth + 1} onSelect={onSelect} onExpand={onExpand} selectedPath={selectedPath} searchKw={searchKw} activeHitPath={activeHitPath} onSearchEnterNext={onSearchEnterNext} />
      ))}
    </div>
  );
}

export default function FileBrowserPage() {
  const router   = useRouter();
  const pathname = usePathname();
  const [system, setSystem]       = useState<"MC" | "NC">("MC");
  const [tab, setTab]             = useState<TabType>("photos");
  const [trees, setTrees]         = useState<Record<TabType, FileNode[]>>({ photos: [], drawings: [], programs: [], nc_photos: [], nc_drawings: [], nc_programs: [] });
  const [rootPaths, setRootPaths] = useState<Record<TabType, string>>({ photos: "", drawings: "", programs: "", nc_photos: "", nc_drawings: "", nc_programs: "" });
  const [rootLoading, setRootLoading] = useState(false);
  const [selected, setSelected]   = useState<FileNode | null>(null);
  const [preview, setPreview]     = useState<{ type: "image" | "pdf" | "text" | "none"; url?: string; text?: string } | null>(null);
  const [prevLoading, setPrevLoading] = useState(false);
  const [searchKw, setSearchKw]   = useState("");
  const [searchHits, setSearchHits] = useState<{ path: string; type: "file" | "dir" }[]>([]);
  const [searchHitIndex, setSearchHitIndex] = useState(0);
  const [activeHitPath, setActiveHitPath] = useState("");
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // タブごとのIndexedDBキャッシュ(フラットなファイル/フォルダ一覧)。メモリにも保持し、
  // 検索はこの配列に対してJS側でフィルタするためサーバーへのリクエストは発生しない。
  const [fbIndexCache, setFbIndexCache] = useState<Record<TabType, FbIndexItem[]>>({ photos: [], drawings: [], programs: [], nc_photos: [], nc_drawings: [], nc_programs: [] });
  const [indexBuilding, setIndexBuilding] = useState(false);
  const [indexCachedAt, setIndexCachedAt] = useState<number | null>(null);
  const [toast, setToast]         = useState<{ msg: string; ok: boolean } | null>(null);
  const [delConfirm, setDelConfirm] = useState<FileNode | null>(null);
  const [uploading, setUploading] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [uploadDir, setUploadDir] = useState("");
  const [trashOpen, setTrashOpen] = useState(false);
  const [trashItems, setTrashItems] = useState<TrashItem[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);
  const [trashBusyId, setTrashBusyId] = useState<string | null>(null);

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

  const loadTrash = useCallback(async () => {
    setTrashLoading(true);
    try {
      const data = await apiFetch("/api/admin/files/trash-list");
      setTrashItems(data.items ?? []);
    } catch (e: any) { showToast("ゴミ箱取得失敗: " + e.message, false); }
    finally { setTrashLoading(false); }
  }, [apiFetch]);

  const handleRestoreTrash = async (id: string) => {
    setTrashBusyId(id);
    try {
      await apiFetch("/api/admin/files/trash-restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      showToast("復元しました");
      await loadTrash();
      await loadRoots();
    } catch (e: any) { showToast("復元失敗: " + e.message, false); }
    finally { setTrashBusyId(null); }
  };

  const handlePurgeTrash = async (id: string) => {
    if (!window.confirm("完全に削除します。元に戻せません。よろしいですか？")) return;
    setTrashBusyId(id);
    try {
      await apiFetch(`/api/admin/files/trash-purge?id=${encodeURIComponent(id)}`, { method: "DELETE" });
      showToast("完全に削除しました");
      await loadTrash();
    } catch (e: any) { showToast("完全削除失敗: " + e.message, false); }
    finally { setTrashBusyId(null); }
  };

  const loadRoots = async () => {
    setRootLoading(true);
    try {
      const data = await apiFetch("/api/admin/files/tree");
      setTrees({
        photos:      (data.photos?.children      ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        drawings:    (data.drawings?.children    ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        programs:    (data.programs?.children    ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        nc_photos:   (data.nc_photos?.children   ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        nc_drawings: (data.nc_drawings?.children ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
        nc_programs: (data.nc_programs?.children ?? []).map((n: FileNode) => ({ ...n, loaded: false })),
      });
      setRootPaths({
        photos:      data.photos?.path      ?? "",
        drawings:    data.drawings?.path    ?? "",
        programs:    data.programs?.path    ?? "",
        nc_photos:   data.nc_photos?.path   ?? "",
        nc_drawings: data.nc_drawings?.path ?? "",
        nc_programs: data.nc_programs?.path ?? "",
      });
    } catch (e: any) { showToast("ツリー取得失敗: " + e.message, false); }
    finally { setRootLoading(false); }
  };

  // 指定タブのフラットインデックスをサーバーから取得し、IndexedDB+メモリへキャッシュする(ReCache)。
  const buildIndexForTab = useCallback(async (t: TabType) => {
    setIndexBuilding(true);
    try {
      const data = await apiFetch(`/api/admin/files/index?tab=${t}`);
      const items: FbIndexItem[] = data.items ?? [];
      await fbSetCache(t as FbTab, data.rootPath ?? "", items);
      setFbIndexCache(prev => ({ ...prev, [t]: items }));
      setIndexCachedAt(Date.now());
    } catch (e: any) {
      showToast("検索インデックス構築失敗: " + e.message, false);
    } finally {
      setIndexBuilding(false);
    }
  }, [apiFetch]);

  // タブを開いた時、IndexedDBキャッシュが無ければ自動構築。あればそれをメモリへ読み込む。
  const ensureIndexForTab = useCallback(async (t: TabType) => {
    const cached = await fbGetCache(t as FbTab);
    if (cached && cached.items.length > 0) {
      setFbIndexCache(prev => ({ ...prev, [t]: cached.items }));
      setIndexCachedAt(cached.cachedAt);
    } else {
      await buildIndexForTab(t);
    }
  }, [buildIndexForTab]);

  useEffect(() => {
    ensureIndexForTab(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // 「↺ 更新」ボタン: ツリー表示の再取得と、検索インデックスのReCache(再構築)を両方行う
  const handleRefresh = async () => {
    await loadRoots();
    await buildIndexForTab(tab);
  };


  // ディレクトリ展開: 対象ノードに子を遅延ロード（展開完了をawaitできるようPromiseを返す）
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
      return children;
    } catch (e: any) { showToast("展開失敗: " + e.message, false); return []; }
  }, [tab, apiFetch]);

  // ツリー内の現在のノードを探索し、すでに読み込み済み(loaded)かを判定するヘルパー
  const findNodeInTree = useCallback((nodes: FileNode[], targetPath: string): FileNode | null => {
    for (const n of nodes) {
      if (n.path === targetPath) return n;
      if (n.children) {
        const found = findNodeInTree(n.children, targetPath);
        if (found) return found;
      }
    }
    return null;
  }, []);

  // 検索ヒットしたパスまで、ルートから祖先ディレクトリを順番に自動展開してスクロール表示する
  const revealPath = useCallback(async (fullPath: string) => {
    if (!rootPaths[tab] || !fullPath.startsWith(rootPaths[tab])) return;
    const rel = fullPath.slice(rootPaths[tab].length).replace(/^[/]+/, "");
    const segments = rel.split("/").filter(Boolean);
    // 対象自身がファイルなら最後のsegmentは展開しない(親までを展開すればよい)
    let cursor = rootPaths[tab];
    const dirsToExpand = segments.slice(0, -1); // 最後の要素(対象自身)は展開不要
    for (const seg of dirsToExpand) {
      cursor = `${cursor}/${seg}`;
      const existing = findNodeInTree(trees[tab], cursor);
      if (!existing || !existing.loaded) {
        await expandNode({ path: cursor, name: seg, type: "dir" });
      }
    }
    setActiveHitPath(fullPath);
    // DOMが描画されるのを少し待ってからスクロール＋キーボードフォーカスを移動する
    setTimeout(() => {
      const nodes = document.querySelectorAll("[data-path]");
      for (let i = 0; i < nodes.length; i++) {
        const el = nodes[i] as HTMLElement;
        if (el.getAttribute("data-path") === fullPath) {
          el.scrollIntoView({ block: "center", behavior: "smooth" });
          el.focus({ preventScroll: true });
          break;
        }
      }
    }, 80);
  }, [tab, rootPaths, trees, findNodeInTree, expandNode]);

  // 検索ボックス入力に対し、ローカルキャッシュ(IndexedDBから読み込んだfbIndexCache)を検索する。
  // サーバーへのリクエストは発生しないため、9,500件超のディレクトリでもほぼ即時に結果が出る。
  const runSearch = useCallback(async (kw: string) => {
    if (!kw.trim()) { setSearchHits([]); setSearchHitIndex(0); setActiveHitPath(""); return; }
    const items = fbIndexCache[tab] ?? [];
    const hits = fbSearchCache(items, kw).map(it => ({ path: it.path, type: it.type }));
    setSearchHits(hits);
    setSearchHitIndex(0);
    if (hits.length > 0) { await revealPath(hits[0].path); } else { setActiveHitPath(""); }
  }, [tab, fbIndexCache, revealPath]);

  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (!searchKw.trim()) { setSearchHits([]); setSearchHitIndex(0); setActiveHitPath(""); return; }
    searchTimerRef.current = setTimeout(() => { runSearch(searchKw); }, 100);
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); };
  }, [searchKw, runSearch]);

  // 次候補へ移動(末尾なら先頭へ循環)。検索ボックスのEnter、ツリー行フォーカス中のEnterの両方から呼ばれる。
  const goToNextHit = useCallback(async () => {
    if (searchHits.length === 0) return;
    const nextIndex = (searchHitIndex + 1) % searchHits.length;
    setSearchHitIndex(nextIndex);
    await revealPath(searchHits[nextIndex].path);
  }, [searchHits, searchHitIndex, revealPath]);

  const handleSearchKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter") return;
    await goToNextHit();
  };

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
      showToast("ゴミ箱へ移動しました: " + node.name);
      setDelConfirm(null);
      if (selected?.path === node.path) { setSelected(null); setPreview(null); }
      await loadRoots();
      await loadTrash();
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
          <div className="flex items-center gap-2">
            {/* MC/NC トグル(デフォルト:MC) */}
            <div className="flex items-center bg-slate-100 rounded-full p-0.5 border border-slate-200">
              {(["MC", "NC"] as const).map(sys => (
                <button key={sys} onClick={() => {
                    setSystem(sys);
                    const first = (sys === "MC" ? "photos" : "nc_photos") as TabType;
                    setTab(first); setSelected(null); setPreview(null);
                    setSearchKw(""); setSearchHits([]); setSearchHitIndex(0); setActiveHitPath("");
                  }}
                  className={"px-4 py-1 text-xs font-bold rounded-full transition-colors " +
                    (system === sys ? "bg-white text-slate-800 shadow-sm" : "text-slate-400 hover:text-slate-600")}>
                  {sys}
                </button>
              ))}
            </div>
            <span className="text-slate-200">|</span>
            <div className="flex gap-1">
              {(system === "MC" ? (["photos", "drawings", "programs"] as TabType[]) : (["nc_photos", "nc_drawings", "nc_programs"] as TabType[])).map(t => (
                <button key={t} onClick={() => { setTab(t); setSelected(null); setPreview(null); setSearchKw(""); setSearchHits([]); setSearchHitIndex(0); setActiveHitPath(""); }}
                  className={"px-3 py-1 text-xs font-bold rounded-full border transition-colors " +
                    (tab === t ? TAB_COLORS[t] : "bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200")}>
                  {TAB_LABELS[t]}
                </button>
              ))}
            </div>
            <span className="text-slate-200">|</span>
            <button onClick={() => { setTrashOpen(true); loadTrash(); }}
              className={"px-3 py-1 text-xs font-bold rounded-full border transition-colors " +
                (trashItems.length > 0 ? "bg-red-50 text-red-600 border-red-200 hover:bg-red-100" : "bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200")}>
              🗑️ ゴミ箱{trashItems.length > 0 ? ` (${trashItems.length})` : ""}
            </button>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <input value={searchKw} onChange={e => setSearchKw(e.target.value)} onKeyDown={handleSearchKeyDown}
              placeholder="ファイル名・フォルダ名検索…Enterで次候補"
              className="border border-slate-200 rounded-lg px-3 py-1.5 text-xs w-56 focus:outline-none focus:ring-2 focus:ring-sky-400" />
            {searchKw.trim() && (
              <span className="text-[10px] text-slate-400 whitespace-nowrap">
                {indexBuilding ? "検索インデックス構築中…" : searchHits.length > 0 ? `${searchHitIndex + 1} / ${searchHits.length} 件` : "0件"}
              </span>
            )}
          </div>
          <button onClick={handleRefresh} disabled={rootLoading || indexBuilding}
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-bold rounded-lg border border-slate-200 transition-colors">
            {rootLoading || indexBuilding ? "更新中…" : "↺ 更新"}
          </button>
          {indexCachedAt && !indexBuilding && (
            <span className="text-[10px] text-slate-300 whitespace-nowrap">
              索引: {new Date(indexCachedAt).toLocaleString("ja-JP", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}更新
            </span>
          )}
        </div>

        {toast && (
          <div className={"fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-white text-sm font-bold shadow-lg " + (toast.ok ? "bg-green-600" : "bg-red-600")}>
            {toast.msg}
          </div>
        )}

        {delConfirm && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-96">
              <h2 className="text-base font-bold text-red-700 mb-3">ゴミ箱へ移動の確認</h2>
              <p className="text-sm text-slate-600 mb-1">以下をゴミ箱へ移動します（後で復元できます）:</p>
              <p className="text-xs font-mono bg-slate-50 rounded p-2 text-slate-800 break-all mb-4">{delConfirm.path}</p>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setDelConfirm(null)} className="px-4 py-2 bg-slate-100 text-slate-600 text-sm font-bold rounded-lg hover:bg-slate-200">キャンセル</button>
                <button onClick={() => handleDelete(delConfirm)} className="px-4 py-2 bg-red-600 text-white text-sm font-bold rounded-lg hover:bg-red-700">ゴミ箱へ移動</button>
              </div>
            </div>
          </div>
        )}

        {trashOpen && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
              <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between shrink-0">
                <h2 className="text-base font-bold text-slate-800">🗑️ ゴミ箱</h2>
                <button onClick={() => setTrashOpen(false)} className="text-slate-400 hover:text-slate-700 text-lg font-bold">✕</button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {trashLoading ? (
                  <div className="text-center text-slate-400 text-xs py-8">読込中…</div>
                ) : trashItems.length === 0 ? (
                  <div className="text-center text-slate-400 text-xs py-8">ゴミ箱は空です</div>
                ) : (
                  <div className="space-y-2">
                    {trashItems.map(item => (
                      <div key={item.id} className="flex items-center gap-3 border border-slate-200 rounded-lg px-3 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-slate-700 truncate">{item.type === "dir" ? "📁" : "📄"} {item.name}</p>
                          <p className="text-[10px] text-slate-400 font-mono truncate">{item.originalPath}</p>
                          <p className="text-[10px] text-slate-400">削除日時: {new Date(item.deletedAt).toLocaleString("ja-JP")}</p>
                          {!item.existsInTrash && <p className="text-[10px] text-red-500 font-bold">⚠ ゴミ箱内の実体が見つかりません</p>}
                        </div>
                        <div className="flex gap-1.5 shrink-0">
                          <button disabled={trashBusyId === item.id || !item.existsInTrash} onClick={() => handleRestoreTrash(item.id)}
                            className="px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-bold rounded-lg hover:bg-emerald-100 disabled:opacity-40">
                            ↺ 復元
                          </button>
                          <button disabled={trashBusyId === item.id} onClick={() => handlePurgeTrash(item.id)}
                            className="px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 text-xs font-bold rounded-lg hover:bg-red-100 disabled:opacity-40">
                            完全削除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
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
                <TreeNode key={i} node={node} depth={0} onSelect={handleSelect} onExpand={handleExpand} selectedPath={selected?.path ?? ""} searchKw={searchKw} activeHitPath={activeHitPath} onSearchEnterNext={goToNextHit} />
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
