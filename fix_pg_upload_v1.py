#!/usr/bin/env python3
"""
fix_pg_upload_v1.py
① PGエディタ検索: インクリメンタル廃止 → Enter/検索ボタンで実行
② edit/page.tsx プログラム情報ブロック: USBアップロードUIをボタン1つで完結
   - 「📥 USBからPGファイルを登録」ボタン
   - 押下 → モーダル表示（単体ファイル or フォルダ選択）
   - 単体: showOpenFilePicker → ファイル名=加工IDにリネームしてアップロード
   - フォルダ: showDirectoryPicker → フォルダ内ファイルを全て加工IDフォルダとしてアップロード
"""
import subprocess, sys, os, urllib.request, json

REPO  = "karkyon/machcore"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def gh_get(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3.raw"} if TOKEN else {"Accept": "application/vnd.github.v3.raw"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")

BASE = os.path.expanduser("~/projects/machcore")

def read_file(rel):
    return open(os.path.join(BASE, rel), encoding="utf-8").read()

def write_file(rel, content):
    open(os.path.join(BASE, rel), "w", encoding="utf-8").write(content)

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd or BASE, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip(), file=sys.stderr)
    return r.returncode

# ─────────────────────────────────────────────────────────────
# [1] edit/page.tsx の修正
# ─────────────────────────────────────────────────────────────
print("=== [1] edit/page.tsx 修正 ===")

edit_path = "apps/web/app/mc/[mc_id]/edit/page.tsx"
src = read_file(edit_path)
orig_len = len(src)

# ── 1-A: stateに pgUploadModalOpen 追加 ──
# pgUpdatedAtDisp の後に追加
OLD_STATE = '  const [pgUpdatedAtDisp, setPgUpdatedAtDisp] = useState<string>("");'
NEW_STATE = '''  const [pgUpdatedAtDisp, setPgUpdatedAtDisp] = useState<string>("");
  const [pgUploadModalOpen, setPgUploadModalOpen] = useState(false);
  const [pgUploading, setPgUploading] = useState(false);'''

if OLD_STATE not in src:
    print("  WARN: pgUpdatedAtDisp state アンカー不一致")
else:
    src = src.replace(OLD_STATE, NEW_STATE, 1)
    print("  OK: pgUploadModalOpen state 追加")

# ── 1-B: handlePgUploadFromUSB 関数追加（handleSave の前に挿入）──
# pgUploading は既存あり確認
HANDLE_ANCHOR = "  const handleSave = async () => {"

PG_UPLOAD_FUNC = '''  // PGファイルをUSBから登録（単体 or フォルダ）
  const handlePgUploadFromUSB = async (mode: "file" | "folder") => {
    if (!token) { showToast("❌ 認証が必要です"); return; }
    setPgUploadModalOpen(false);
    setPgUploading(true);
    // machiningId を detail から取得
    const machId = String(detail?.machiningId ?? "");
    try {
      if (mode === "file") {
        // 単体ファイル: showOpenFilePicker
        const [fileHandle] = await (window as any).showOpenFilePicker({ multiple: false });
        const file: File = await fileHandle.getFile();
        // ファイル名を加工IDにリネーム（拡張子はそのまま）
        const ext = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")) : "";
        const newName = machId + ext;
        const renamedFile = new File([file], newName, { type: file.type });
        const fd = new FormData();
        fd.append("file", renamedFile);
        fd.append("is_folder_upload", "false");
        const res = await fetch(`/api/mc/${mcId}/files/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
        const refreshed = await mcApi.findOne(mcId);
        setDetail((refreshed as any).data ?? refreshed);
        showToast(`✅ PGファイルを登録しました（${newName}）`);
      } else {
        // フォルダ: showDirectoryPicker → 中のファイルを全アップロード
        const dirHandle = await (window as any).showDirectoryPicker({ mode: "read" });
        let count = 0;
        for await (const [, fh] of dirHandle.entries()) {
          if (fh.kind !== "file") continue;
          const file: File = await fh.getFile();
          const fd = new FormData();
          fd.append("file", file);
          fd.append("is_folder_upload", "true");
          const res = await fetch(`/api/mc/${mcId}/files/upload`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: fd,
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          count++;
        }
        if (count === 0) { showToast("⚠️ フォルダ内にファイルが見つかりません"); return; }
        setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
        const refreshed = await mcApi.findOne(mcId);
        setDetail((refreshed as any).data ?? refreshed);
        showToast(`✅ PGフォルダを登録しました（${count}ファイル、加工ID: ${machId}フォルダとして保存）`);
      }
    } catch (e: any) {
      if (e.name === "AbortError") { setPgUploading(false); return; }
      showToast("❌ アップロード失敗: " + (e.message || "不明なエラー"));
    } finally {
      setPgUploading(false);
    }
  };

'''

if HANDLE_ANCHOR not in src:
    print("  WARN: handleSave アンカー不一致")
else:
    src = src.replace(HANDLE_ANCHOR, PG_UPLOAD_FUNC + HANDLE_ANCHOR, 1)
    print("  OK: handlePgUploadFromUSB 追加")

# ── 1-C: 検索バーの onChange インクリメンタルを廃止 → Enterのみ検索 ──
# 現在: onChange={e => { const q = e.target.value; setPgEditorSearch(q); if (!q) { ... } try { ... 検索実行 ... } ... }}
# 修正後: onChange={e => { const q = e.target.value; setPgEditorSearch(q); if (!q) { setPgMatchCount(0); ... } }}
# searchを実行するのはonKeyDown(Enter)と新設の「検索」ボタンのみ

# アンカー: onChange の開始と終了を特定
OLD_SEARCH_ONCHANGE = '''                  onChange={e => {
                    const q = e.target.value;
                    setPgEditorSearch(q);
                    if (!q) { setPgMatchCount(0); setPgMatchPositions([]); setPgMatchIndex(0); return; }
                    try {
                      const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, \'\\\\$&\');
                      const regex = new RegExp(esc, \'gi\');
                      const positions: number[] = [];
                      let m;
                      while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
                      setPgMatchPositions(positions);
                      setPgMatchCount(positions.length);
                      if (positions.length > 0 && pgTextareaRef.current) {
                        const cursor = pgTextareaRef.current.selectionStart ?? 0;
                        let idx = positions.findIndex(p => p >= cursor);
                        if (idx === -1) idx = 0;
                        setPgMatchIndex(idx);
                        pgTextareaRef.current.focus();
                        pgTextareaRef.current.setSelectionRange(positions[idx], positions[idx] + q.length);
                      }
                    } catch {}
                  }}'''

# 上記が見つからない場合は部分マッチで探す
if OLD_SEARCH_ONCHANGE not in src:
    # より短いアンカーで試みる
    SEARCH_ANCHOR_SHORT = "setPgEditorSearch(q);\n                    if (!q) { setPgMatchCount(0); setPgMatchPositions([]); setPgMatchIndex(0); return; }\n                    try {"
    if SEARCH_ANCHOR_SHORT in src:
        # onChange ブロック全体を差し替え（末尾の }}まで）
        # startを見つけてブロック全体を置換
        idx_start = src.find("onChange={e => {\n                    const q = e.target.value;\n                    setPgEditorSearch(q);")
        if idx_start >= 0:
            # ブロック終端を探す（`catch {}`の直後の`}}`）
            idx_end = src.find("                    } catch {}\n                  }}", idx_start)
            if idx_end >= 0:
                idx_end += len("                    } catch {}\n                  }}")
                old_block = src[idx_start:idx_end]
                NEW_SEARCH_ONCHANGE = """onChange={e => {
                    const q = e.target.value;
                    setPgEditorSearch(q);
                    if (!q) { setPgMatchCount(0); setPgMatchPositions([]); setPgMatchIndex(0); }
                  }}"""
                src = src[:idx_start] + NEW_SEARCH_ONCHANGE + src[idx_end:]
                print("  OK: 検索 onChange インクリメンタル廃止（short anchor）")
            else:
                print("  WARN: 検索ブロック終端が見つかりません")
        else:
            print("  WARN: 検索 onChange 開始アンカーが見つかりません")
    else:
        print("  WARN: 検索 onChange アンカーが見つかりません（スキップ）")
else:
    NEW_SEARCH_ONCHANGE = '''                  onChange={e => {
                    const q = e.target.value;
                    setPgEditorSearch(q);
                    if (!q) { setPgMatchCount(0); setPgMatchPositions([]); setPgMatchIndex(0); }
                  }}'''
    src = src.replace(OLD_SEARCH_ONCHANGE, NEW_SEARCH_ONCHANGE, 1)
    print("  OK: 検索 onChange インクリメンタル廃止")

# ── 1-D: 検索「Enter」キーで実行 + 「検索」ボタン追加 ──
# 現在の onKeyDown に検索実行ロジックがある場合は維持。
# ない場合は追加。まず現状確認してEnterで検索実行ロジックを補完する。
# onKeyDown 内の既存 Enter ハンドラ（次へ）の前に、検索実行ロジックを追加する。

# 既存のonKeyDownアンカー（次へ移動）
OLD_KEYDOWN = "                  onKeyDown={e => {\n                    if (e.key === 'Enter' && pgMatchPositions.length > 0 && pgTextareaRef.current) {"
NEW_KEYDOWN = """                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && pgMatchPositions.length === 0 && pgEditorSearch) {
                      // 初回Enter: 検索実行
                      e.preventDefault();
                      const q = pgEditorSearch;
                      try {
                        const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                        const regex = new RegExp(esc, 'gi');
                        const positions: number[] = [];
                        let m;
                        while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
                        setPgMatchPositions(positions);
                        setPgMatchCount(positions.length);
                        if (positions.length > 0 && pgTextareaRef.current) {
                          setPgMatchIndex(0);
                          pgTextareaRef.current.focus();
                          pgTextareaRef.current.setSelectionRange(positions[0], positions[0] + q.length);
                        }
                      } catch {}
                      return;
                    }
                    if (e.key === 'Enter' && pgMatchPositions.length > 0 && pgTextareaRef.current) {"""

if OLD_KEYDOWN not in src:
    print("  WARN: onKeyDown Enterアンカー不一致（スキップ）")
else:
    src = src.replace(OLD_KEYDOWN, NEW_KEYDOWN, 1)
    print("  OK: Enter初回検索実行ロジック追加")

# ── 1-E: 「検索」ボタンを追加（置換ボタンの前に） ──
OLD_BTN_REPLACE = '''              <button onClick={() => {
                if (!pgEditorSearch || pgMatchPositions.length === 0 || !pgTextareaRef.current) return;
                const pos = pgMatchPositions[pgMatchIndex];'''

NEW_BTN_REPLACE = '''              <button onClick={() => {
                if (!pgEditorSearch) return;
                const q = pgEditorSearch;
                try {
                  const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                  const regex = new RegExp(esc, 'gi');
                  const positions: number[] = [];
                  let m;
                  while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
                  setPgMatchPositions(positions);
                  setPgMatchCount(positions.length);
                  if (positions.length > 0 && pgTextareaRef.current) {
                    setPgMatchIndex(0);
                    pgTextareaRef.current.focus();
                    pgTextareaRef.current.setSelectionRange(positions[0], positions[0] + q.length);
                  }
                } catch {}
              }} className="px-3 py-1.5 text-xs bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-bold">🔍 検索</button>
              <button onClick={() => {
                if (!pgEditorSearch || pgMatchPositions.length === 0 || !pgTextareaRef.current) return;
                const pos = pgMatchPositions[pgMatchIndex];'''

if OLD_BTN_REPLACE not in src:
    print("  WARN: 検索ボタン追加アンカー不一致（スキップ）")
else:
    src = src.replace(OLD_BTN_REPLACE, NEW_BTN_REPLACE, 1)
    print("  OK: 「検索」ボタン追加")

# ── 1-F: プログラム情報ブロックに「USBから登録」ボタン追加 ──
# 「📄 PGエディタを開く」ボタンの横に追加する
OLD_PG_EDITOR_BTN = '''                    }} disabled={pgLoading}
                      className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                    </button>
                  </div>'''

NEW_PG_EDITOR_BTN = '''                    }} disabled={pgLoading}
                      className="px-3 py-1 text-xs font-bold bg-slate-700 hover:bg-slate-800 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgLoading ? "読込中..." : "📄 PGエディタを開く"}
                    </button>
                    <button onClick={() => {
                      if (!token) { showToast("❌ 認証が必要です"); return; }
                      if (!("showOpenFilePicker" in window)) { showToast("❌ Chrome/Edgeが必要です"); return; }
                      setPgUploadModalOpen(true);
                    }} disabled={pgUploading}
                      className="px-3 py-1 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors disabled:opacity-50">
                      {pgUploading ? "⏳ 登録中..." : "📥 USBから登録"}
                    </button>
                  </div>'''

if OLD_PG_EDITOR_BTN not in src:
    print("  WARN: PGエディタボタンアンカー不一致（スキップ）")
else:
    src = src.replace(OLD_PG_EDITOR_BTN, NEW_PG_EDITOR_BTN, 1)
    print("  OK: USBから登録ボタン追加")

# ── 1-G: pgUploadModalOpen モーダルを追加 (PGエディタモーダルの直前に) ──
PG_EDITOR_MODAL_ANCHOR = "      {/* PGエディタモーダル */}\n      {pgEditorOpen && ("

PG_UPLOAD_MODAL = '''      {/* PGアップロードモーダル（単体 or フォルダ） */}
      {pgUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-800 text-base">📥 PGファイル登録方法を選択</h3>
              <button onClick={() => setPgUploadModalOpen(false)} className="text-slate-400 hover:text-slate-600 text-xl font-bold">✕</button>
            </div>
            <p className="text-xs text-slate-500">
              加工ID: <span className="font-mono font-bold text-teal-700">{detail?.machiningId}</span> として登録します
            </p>
            <div className="space-y-3">
              <button onClick={() => handlePgUploadFromUSB("file")}
                className="w-full px-4 py-4 bg-teal-50 hover:bg-teal-100 border-2 border-teal-300 rounded-xl text-left transition-colors">
                <div className="font-bold text-teal-800 mb-1">📄 単体ファイル</div>
                <div className="text-xs text-teal-600">拡張子なしのプログラムファイル（テキスト形式）を1つ選択。ファイル名は加工IDに自動リネームされます。</div>
                <div className="text-[10px] text-teal-400 mt-1 font-mono">例: O6000 → {detail?.machiningId}</div>
              </button>
              <button onClick={() => handlePgUploadFromUSB("folder")}
                className="w-full px-4 py-4 bg-amber-50 hover:bg-amber-100 border-2 border-amber-300 rounded-xl text-left transition-colors">
                <div className="font-bold text-amber-800 mb-1">📁 フォルダ単位</div>
                <div className="text-xs text-amber-600">メインPG + サブPGを含むフォルダを選択。フォルダ内の全ファイルが加工IDフォルダとして保存されます。</div>
                <div className="text-[10px] text-amber-400 mt-1 font-mono">例: 1846.WPD/ → {detail?.machiningId}/</div>
              </button>
            </div>
            <p className="text-[10px] text-slate-400 text-center">Chrome / Edge のみ対応（HTTPS必須）</p>
          </div>
        </div>
      )}

'''

if PG_EDITOR_MODAL_ANCHOR not in src:
    print("  WARN: PGエディタモーダルアンカー不一致（スキップ）")
else:
    src = src.replace(PG_EDITOR_MODAL_ANCHOR, PG_UPLOAD_MODAL + PG_EDITOR_MODAL_ANCHOR, 1)
    print("  OK: pgUploadModalOpen モーダル追加")

write_file(edit_path, src)
print(f"  edit/page.tsx: {orig_len} → {len(src)}文字")

# ─────────────────────────────────────────────────────────────
# [2] ビルドチェック
# ─────────────────────────────────────────────────────────────
print("\n=== [2] API tsc ===")
rc = run("npx tsc --noEmit", cwd=os.path.join(BASE, "apps/api"))
if rc != 0:
    print("  ❌ API TSC エラー")
    sys.exit(1)
print("  OK")

print("\n=== [3] nest build ===")
rc = run("npx nest build", cwd=os.path.join(BASE, "apps/api"))
if rc != 0:
    print("  ❌ nest build エラー")
    sys.exit(1)
print("  OK")

print("\n=== [4] Next.js build ===")
rc = run("npx next build 2>&1 | tail -20", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ Next.js build エラー")
    sys.exit(1)
print("  OK")

print("\n=== [5] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [6] git push ===")
run("git add -A")
run('git commit -m "feat: PGエディタ検索Enter方式に変更 / USBからPGファイル登録UI改善（単体/フォルダ選択モーダル）"')
run("git push origin main")

print("\n=== 完了 ===")
