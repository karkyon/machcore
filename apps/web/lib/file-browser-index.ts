// ファイルブラウザの検索高速化用 IndexedDB キャッシュユーティリティ。
//
// 背景: サーバー側で検索キーワードごとに再帰的にCIFSマウントをスキャンする方式(旧files/search)は、
//       9,500件超のディレクトリを毎回同期I/Oで走査するため応答に30〜90秒以上かかる重大な性能問題があった。
// 対応: タブを開いた時・更新ボタンを押した時の1回だけ、サーバーから全件フラットインデックス(files/index)
//       を取得してIndexedDBに保存する。検索はこのローカルキャッシュに対してJS側で行うため、ほぼ即時に
//       候補が返る。サーバー側の負荷も「検索ごと」から「キャッシュ構築ごと」に減る。

export type FbIndexItem = { name: string; path: string; type: "file" | "dir"; size?: number; mtime?: string };
export type FbTab = "photos" | "drawings" | "programs" | "nc_photos" | "nc_drawings";

const DB_NAME = "machcore_file_browser_cache";
const DB_VERSION = 1;
const STORE_NAME = "fb_index";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "tab" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

type CacheRecord = { tab: FbTab; rootPath: string; items: FbIndexItem[]; cachedAt: number };

/** 指定タブのキャッシュをIndexedDBから読み出す。無ければnull。 */
export async function fbGetCache(tab: FbTab): Promise<CacheRecord | null> {
  try {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readonly");
      const store = tx.objectStore(STORE_NAME);
      const req = store.get(tab);
      req.onsuccess = () => resolve((req.result as CacheRecord) ?? null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}

/** 指定タブのキャッシュをIndexedDBへ保存する（上書き）。 */
export async function fbSetCache(tab: FbTab, rootPath: string, items: FbIndexItem[]): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const record: CacheRecord = { tab, rootPath, items, cachedAt: Date.now() };
      const req = store.put(record);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    // IndexedDB利用不可環境でも検索機能以外は動くようにし、ここでは例外を飲み込む
  }
}

/** キャッシュ内をファイル名・フォルダ名で検索する（部分一致、大小文字無視）。 */
export function fbSearchCache(items: FbIndexItem[], keyword: string): FbIndexItem[] {
  const kw = keyword.trim().toLowerCase();
  if (!kw) return [];
  const hits = items.filter(it => it.name.toLowerCase().includes(kw));
  hits.sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name, "ja");
  });
  return hits;
}
