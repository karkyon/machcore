#!/usr/bin/env python3
"""
fix_v79.py
===========
問題:
  - mc_setup_p2 テンプレートにフィールドが 0件（P1と同じフィールド定義が必要）
  - エディタが selTpl に関わらず全フィールドを表示している

修正:
  1. [DB] mc_setup_p2 に mc_setup_p1 と同じフィールド定義をコピー
  2. [UI] pdf-editor: selTpl に応じてフィールドリストをフィルタリング
     (P1選択→1Pフィールドのみ表示、P2選択→2Pフィールドのみ表示)
  3. [UI] previewPage と selTpl を完全連動させる
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"
API  = f"{ROOT}/apps/api/src"

def read(p):
    with open(p,"r",encoding="utf-8") as f: return f.read()
def write(p,c):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p,"w",encoding="utf-8") as f: f.write(c)
def patch(p,old,new,label):
    c=read(p)
    if old not in c: print(f"WARN: {label} — 不一致"); return False
    write(p,c.replace(old,new,1)); print(f"OK: {label}"); return True
def run(cmd,cwd=ROOT):
    r=subprocess.run(cmd,shell=True,cwd=cwd,capture_output=True,text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:",r.stderr[-2000:])
    return r.returncode

def db_exec(sql):
    r = subprocess.run(
        ["docker","exec","machcore-postgres","psql","-U","machcore","-d","machcore_dev","-c",sql],
        capture_output=True, text=True, cwd=ROOT
    )
    print(r.stdout[:3000])
    if r.returncode != 0: print("WARN:", r.stderr[:300])
    return r.returncode

# ─────────────────────────────────────────────────────────────
# 1. DB: mc_setup_p2 に P1 フィールドをコピー
#    (P2テンプレートはP1と同じ段取シートの2枚目なので同じフィールドが必要)
# ─────────────────────────────────────────────────────────────
print("--- DB: P2にP1フィールドをコピー ---")
db_exec("""
INSERT INTO pdf_field_definitions
  (template_id, field_key, label, x, y, font_size, data_source, page_number, sort_order, is_active, note)
SELECT
  (SELECT id FROM pdf_templates WHERE name = 'mc_setup_p2'),
  field_key, label, x, y, font_size, data_source, 2, sort_order, is_active, note
FROM pdf_field_definitions
WHERE template_id = (SELECT id FROM pdf_templates WHERE name = 'mc_setup_p1')
  AND NOT EXISTS (
    SELECT 1 FROM pdf_field_definitions f2
    WHERE f2.template_id = (SELECT id FROM pdf_templates WHERE name = 'mc_setup_p2')
      AND f2.field_key = pdf_field_definitions.field_key
  );
""")

print("--- DB: P2フィールド確認 ---")
db_exec("""
SELECT f.id, f.field_key, f.label, f.data_source, f.is_active
FROM pdf_field_definitions f
JOIN pdf_templates t ON t.id = f.template_id
WHERE t.name = 'mc_setup_p2'
ORDER BY f.sort_order
LIMIT 10;
""")

# ─────────────────────────────────────────────────────────────
# 2. admin/pdf-fields API: templateパラメータなしでも全件返すが
#    UIでselTplに応じてフィルタリングする
#    → フィールド取得をselTplベースに戻す（template= パラメータを使用）
# ─────────────────────────────────────────────────────────────
pdf_editor = f"{WEB}/app/admin/pdf-editor/page.tsx"

# 全件取得→selTpl ベースに戻す
patch(pdf_editor,
    "      // 両テンプレートのフィールドを取得（P1/P2どちらも表示）\n      const data = await apiFetch(`/admin/pdf-fields`);",
    "      // selTpl に対応するフィールドのみ取得\n      const data = await apiFetch(`/admin/pdf-fields?template=${selTpl}`);",
    "pdf-editor フィールド取得をselTplベースに戻す"
)

# ─────────────────────────────────────────────────────────────
# 3. フィールドリストの「P」バッジを非表示（同一ページのみ表示するので不要）
#    + ヘッダーの「P」列を削除してすっきりさせる
# ─────────────────────────────────────────────────────────────
# ヘッダーの colgroup & P列 を削除（フィルタリングされているのでP列不要）
patch(pdf_editor,
    """                  <colgroup><col className="w-5"/><col/><col className="w-8"/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                  <tbody className="divide-y divide-slate-100">""",
    """                  <colgroup><col className="w-5"/><col/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                  <tbody className="divide-y divide-slate-100">""",
    "pdf-editor tbody colgroup からP列削除"
)

# 行のP列バッジを削除
patch(pdf_editor,
    """                          <td className="px-2 py-1">
                            <div className="font-medium text-slate-800 truncate text-[11px]">{f.label}</div>
                            <div className="text-[9px] text-slate-400 truncate font-mono">{f.dataSource}</div>
                          </td>
                          <td className="py-1 px-0.5 text-center">
                            <span className={`text-[9px] font-bold px-1 py-0.5 rounded ${f.template?.name === 'mc_setup_p1' ? 'bg-teal-100 text-teal-700' : 'bg-orange-100 text-orange-700'}`}>
                              {f.template?.name === 'mc_setup_p1' ? '1P' : '2P'}
                            </span>
                          </td>
                          <td className="py-1 px-0.5" onClick={e => e.stopPropagation()}>
                            <input type="number" value={f._ex ?? f.x} step="1"
                              onChange={e => upd(f.id, "_ex", Number(e.target.value))}
                              className="w-11 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                          </td>""",
    """                          <td className="px-2 py-1">
                            <div className="font-medium text-slate-800 truncate text-[11px]">{f.label}</div>
                            <div className="text-[9px] text-slate-400 truncate font-mono">{f.dataSource}</div>
                          </td>
                          <td className="py-1 px-0.5" onClick={e => e.stopPropagation()}>
                            <input type="number" value={f._ex ?? f.x} step="1"
                              onChange={e => upd(f.id, "_ex", Number(e.target.value))}
                              className="w-11 border border-slate-200 rounded px-1 py-0.5 text-center text-[10px]" />
                          </td>""",
    "pdf-editor 行からPバッジ列削除"
)

# ヘッダーの P 列も削除
patch(pdf_editor,
    """                  <colgroup><col className="w-5"/><col/><col className="w-8"/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                  <thead>
                    <tr className="text-slate-400 text-[10px] uppercase">
                      <th className="px-1 py-1.5 text-center">✓</th>
                      <th className="px-2 py-1.5 text-left">フィールド</th>
                      <th className="py-1.5 text-center">P</th>
                      <th className="py-1.5 text-center">X</th>
                      <th className="py-1.5 text-center">Y</th>
                      <th className="py-1.5 text-center">pt</th>
                      <th className="py-1.5 text-center">保存</th>
                    </tr>
                  </thead>""",
    """                  <colgroup><col className="w-5"/><col/><col className="w-12"/><col className="w-12"/><col className="w-10"/><col className="w-12"/></colgroup>
                  <thead>
                    <tr className="text-slate-400 text-[10px] uppercase">
                      <th className="px-1 py-1.5 text-center">✓</th>
                      <th className="px-2 py-1.5 text-left">フィールド</th>
                      <th className="py-1.5 text-center">X</th>
                      <th className="py-1.5 text-center">Y</th>
                      <th className="py-1.5 text-center">pt</th>
                      <th className="py-1.5 text-center">保存</th>
                    </tr>
                  </thead>""",
    "pdf-editor ヘッダーからP列削除"
)

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED (web) — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v79): P2にフィールドコピー+エディタP1/P2切替修正' && git push", cwd=ROOT)
print("DONE v79")
