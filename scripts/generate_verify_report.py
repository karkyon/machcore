#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_verify_report.py
===========================
verify_old_new_db.py が出力したJSONを読み込み、
Tailwind CSSベースのインタラクティブHTMLレポートを生成する。

実行方法:
  python3 generate_verify_report.py --in /tmp/verify_result.json --out report.html
"""
import json
import argparse
import html as htmllib
from collections import defaultdict, Counter
from datetime import datetime


def esc(s):
    if s is None:
        return ""
    return htmllib.escape(str(s))


# ────────────────────────────────────────────────────────────
# 不一致パターンの自動分類（課題管理テーブル用）
# フィールド名と値の傾向から、既知の不一致パターンに自動でグルーピングする。
# ────────────────────────────────────────────────────────────

def classify_issue(field, old_v, new_v, category):
    """1件の不一致(field, old, new)から、既知の課題カテゴリを推測する。"""
    f = field

    if f == "H" and old_v.strip() != new_v.strip():
        # H列正規化のはずだが食い違いがある場合(正規化漏れの可能性)
        return "H列_正規化漏れ疑い"

    if f == "D値":
        return "D値_末尾ゼロ表記差(復元不可・既知差分)"

    if f == "順番" or (category == "ツーリング" and f == "row_count"):
        try:
            old_f = float(old_v)
            if old_f != int(old_f):
                return "ツーリング順番_小数枝番の整数変換による重複"
        except (TypeError, ValueError):
            pass
        return "ツーリング順番_不一致"

    if f == "機械":
        return "機械名_マスタ対応不一致"

    if f in ("加工個数", "サイクルタイム(秒)", "MC工程No"):
        return f"{f}_数値不一致"

    if f in ("ファイル名", "フォルダ1", "フォルダ2"):
        return f"{f}_文字列不一致"

    if f == "クランプ" or f == "備考" or f == "コメント":
        return f"{f}_テキスト差分"

    if f in ("N", "工具", "T", "D", "SUB"):
        return f"ツーリング_{f}列_不一致"

    if f in ("X", "Y", "Z", "A", "R", "Gコード"):
        return f"ワークオフセット_{f}列_不一致"

    if f in ("STEP_N", "第1軸", "第2軸"):
        return f"インデックスプログラム_{f}列_不一致"

    if f in ("印刷履歴件数", "変更履歴件数", "作業記録件数"):
        return f"履歴_{f}不一致"

    return f"{f}_その他不一致"


def build_issue_table(details):
    """全不一致を走査し、パターンごとに集約した課題管理テーブルを作る。"""
    issue_map = defaultdict(lambda: {"count": 0, "examples": [], "category_set": set()})

    # 基本情報
    for rec in details.get("basic_info", []):
        cat = "基本情報(MC)"
        if rec["status"] == "MISSING_IN_NEW":
            key = "基本情報_新システムにレコード無し"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"MCID:{rec['mcid']} / 加工ID:{rec['kakoid']}",
                    "old": "(レコード存在)", "new": "(レコード無し)",
                })
            continue
        for fd in rec.get("fields", []):
            key = classify_issue(fd["field"], fd["old"], fd["new"], cat)
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"MCID:{rec['mcid']} / 加工ID:{rec['kakoid']} / {fd['field']}",
                    "old": fd["old"], "new": fd["new"],
                })

    # ツーリング
    for rec in details.get("tooling", []):
        cat = "ツーリング"
        if rec["status"] == "MISSING_IN_NEW":
            key = "ツーリング_新システムにレコード無し"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": "(レコード存在)", "new": "(レコード無し)",
                })
            continue
        if rec["status"] == "ROW_COUNT_MISMATCH":
            key = "ツーリング_行数不一致(削除/重複の疑い)"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": f"{rec.get('old_count')}行", "new": f"{rec.get('new_count')}行",
                })
            continue
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                key = classify_issue(fd["field"], fd["old"], fd["new"], cat)
                issue_map[key]["count"] += 1
                issue_map[key]["category_set"].add(cat)
                if len(issue_map[key]["examples"]) < 5:
                    issue_map[key]["examples"].append({
                        "key": f"加工ID:{rec['kakoid']} / 行{row['row_index']} / {fd['field']}",
                        "old": fd["old"], "new": fd["new"],
                    })

    # ③ワークオフセット
    for rec in details.get("work_offsets", []):
        cat = "ワークオフセット"
        if rec["status"] == "MISSING_IN_NEW":
            key = "ワークオフセット_新システムにレコード無し"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": "(レコード存在)", "new": "(レコード無し)",
                })
            continue
        if rec["status"] == "ROW_COUNT_MISMATCH":
            key = "ワークオフセット_行数不一致"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": f"{rec.get('old_count')}行", "new": f"{rec.get('new_count')}行",
                })
            continue
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                key = classify_issue(fd["field"], fd["old"], fd["new"], cat)
                issue_map[key]["count"] += 1
                issue_map[key]["category_set"].add(cat)
                if len(issue_map[key]["examples"]) < 5:
                    issue_map[key]["examples"].append({
                        "key": f"加工ID:{rec['kakoid']} / {fd['field']}",
                        "old": fd["old"], "new": fd["new"],
                    })

    # ④インデックスプログラム
    for rec in details.get("index_programs", []):
        cat = "インデックスプログラム"
        if rec["status"] == "MISSING_IN_NEW":
            key = "インデックスプログラム_新システムにレコード無し"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": "(レコード存在)", "new": "(レコード無し)",
                })
            continue
        if rec["status"] == "ROW_COUNT_MISMATCH":
            key = "インデックスプログラム_行数不一致"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"加工ID:{rec['kakoid']}",
                    "old": f"{rec.get('old_count')}行", "new": f"{rec.get('new_count')}行",
                })
            continue
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                key = classify_issue(fd["field"], fd["old"], fd["new"], cat)
                issue_map[key]["count"] += 1
                issue_map[key]["category_set"].add(cat)
                if len(issue_map[key]["examples"]) < 5:
                    issue_map[key]["examples"].append({
                        "key": f"加工ID:{rec['kakoid']} / {fd['field']}",
                        "old": fd["old"], "new": fd["new"],
                    })

    # ⑤履歴(変更履歴/印刷履歴/作業記録)
    for rec in details.get("history", []):
        cat = "履歴(変更/印刷/作業記録)"
        if rec["status"] == "MISSING_IN_NEW":
            key = "履歴_新システムにMCレコード無し"
            issue_map[key]["count"] += 1
            issue_map[key]["category_set"].add(cat)
            if len(issue_map[key]["examples"]) < 5:
                issue_map[key]["examples"].append({
                    "key": f"MCID:{rec['kakoid']}",
                    "old": "(レコード存在)", "new": "(レコード無し)",
                })
            continue
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                key = classify_issue(fd["field"], fd["old"], fd["new"], cat)
                issue_map[key]["count"] += 1
                issue_map[key]["category_set"].add(cat)
                if len(issue_map[key]["examples"]) < 5:
                    issue_map[key]["examples"].append({
                        "key": f"MCID:{rec['kakoid']} / {fd['field']}",
                        "old": fd["old"], "new": fd["new"],
                    })

    # 件数降順でリスト化
    issues = []
    for key, v in sorted(issue_map.items(), key=lambda x: -x[1]["count"]):
        issues.append({
            "name": key,
            "count": v["count"],
            "categories": ", ".join(sorted(v["category_set"])),
            "examples": v["examples"],
        })
    return issues


# 既知の原因仮説・対応状況（手動メンテのナレッジベース）
# キーは classify_issue() が返す文字列パターンの先頭一致で判定する。
KNOWN_CAUSES = [
    ("H列_正規化漏れ疑い", "旧ACC_ツーリング.H列の表記不統一に対する正規化処理(normalize_h)の漏れ。要再調査。", "調査中"),
    ("D値_末尾ゼロ表記差", "SQL Server側float型のため末尾ゼロがDB到達時点で消失。表示側で3桁固定フォーマット済み。これは既知の復元不可能な差分であり、不具合ではない。", "対応済(表示側で整形)"),
    ("ツーリング順番_小数枝番の整数変換による重複", "旧DBの「順番」列が4.1や9.1等の小数枝番を持つ場合、新システムのsort_order(整数)へ変換する際に枝番が切り捨てられ、既存の整数値と重複する。mc_full_import.py PHASE2のsort_order採番ロジックの見直しが必要。", "未着手"),
    ("ツーリング_行数不一致", "削除されたはずの行が残存、または重複INSERTの可能性。個別調査が必要。", "未着手"),
    ("機械名_マスタ対応不一致", "全角/半角・大文字小文字・ハイフン表記ゆれは検証側で正規化済み。残存分は新システムmachinesマスタに該当機械が未登録のケース。①マスタに存在する機械はブランク→正しい機械名へ手入力修正。②マスタに存在しない機械(旧システム初期のみ使用された休止機器)は新システムに休止中機器として登録後、改めて手入力修正する運用。", "手入力対応"),
    ("ツーリング_T列_不一致", "T番号循環シフトロジック(mc.service.ts parseToolingProgram)の影響、または旧データのT番号自体が一連の処理で変化している可能性。要詳細調査。", "未着手"),
    ("新システムにレコード無し", "インポート対象から除外された(parts紐付け不可・valid_machining_idsに含まれない等)レコード。スキップ理由のログ確認が必要。", "未着手"),
    ("クランプ_テキスト差分", "手入力での修正で対応するため検証対象外。", "調査対象外"),
    ("MC工程No_数値不一致", "手入力での修正で対応するため検証対象外。", "調査対象外"),
    ("バージョン_その他不一致", "手入力での修正で対応するため検証対象外。現場ヒアリングの上で対応。", "調査対象外"),
]


def find_known_cause(issue_name):
    for prefix, cause, status in KNOWN_CAUSES:
        if issue_name.startswith(prefix):
            return cause, status
    return "原因未分類。個別確認が必要。", "未着手"


STATUS_COLORS = {
    "未着手":        ("bg-slate-100", "text-slate-600", "border-slate-300"),
    "調査中":        ("bg-amber-100", "text-amber-700", "border-amber-300"),
    "対応中":        ("bg-blue-100",  "text-blue-700",  "border-blue-300"),
    "対応済(表示側で整形)": ("bg-emerald-100", "text-emerald-700", "border-emerald-300"),
    "対応済":        ("bg-emerald-100", "text-emerald-700", "border-emerald-300"),
}


def render_summary_cards(summaries):
    cards = []
    for s in summaries:
        total = s["total"] or 1
        matched = s["matched"]
        rate = matched / total * 100
        rate_cls = "high" if rate >= 95 else ("mid" if rate >= 80 else "low")
        extra_rows = ""
        if "row_count_mismatch" in s:
            extra_rows += f'''
            <div class="foot-row"><span>行数不一致</span><span class="mono">{s["row_count_mismatch"]}</span></div>'''
        cards.append(f'''
        <div class="card">
          <div class="card-head">
            <h3>{esc(s["category"])}</h3>
            <span class="rate {rate_cls}">{rate:.1f}%</span>
          </div>
          <div class="bar-bg"><div class="bar-fg {rate_cls}" style="width:{rate:.1f}%"></div></div>
          <div class="stats3">
            <div><div class="num">{s["total"]:,}</div><div class="lbl">検証総数</div></div>
            <div><div class="num green">{s["matched"]:,}</div><div class="lbl">一致</div></div>
            <div><div class="num red">{s["mismatched"]:,}</div><div class="lbl">不一致</div></div>
          </div>
          <div class="foot-row"><span>新システム未存在</span><span class="mono">{s.get("missing_in_new", 0)}</span></div>
          {extra_rows}
        </div>''')
    return "\n".join(cards)


def render_issue_table(issues):
    rows = []
    for i, issue in enumerate(issues):
        cause, status = find_known_cause(issue["name"])
        status_cls = "st-" + status.replace("(", "_").replace(")", "_")
        examples_html = "".join(
            f'<div><span class="mono">{esc(ex["key"])}</span>: '
            f'<span class="old-val">{esc(ex["old"])}</span> → '
            f'<span class="new-val">{esc(ex["new"])}</span></div>'
            for ex in issue["examples"]
        )
        rows.append(f'''
        <tr data-cat="{esc(issue["categories"])}">
          <td class="mono" style="color:var(--slate-400)">{i+1}</td>
          <td>
            <div class="issue-name">{esc(issue["name"])}</div>
            <div class="issue-cat">{esc(issue["categories"])}</div>
          </td>
          <td style="text-align:center"><span class="count-pill">{issue["count"]:,}</span></td>
          <td style="max-width:320px">{esc(cause)}</td>
          <td>
            <select class="status-select {status_cls}" data-issue="{i}">
              {"".join(f'<option value="{esc(s)}" {"selected" if s==status else ""}>{esc(s)}</option>' for s in ["未着手","調査中","対応中","対応済","対応済(表示側で整形)","調査対象外","手入力対応"])}
            </select>
          </td>
          <td class="examples" style="max-width:360px">{examples_html}</td>
        </tr>''')
    return "\n".join(rows)


def render_detail_section_basic(details):
    rows = []
    for rec in details:
        if rec["status"] == "MISSING_IN_NEW":
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["mcid"]}</td>
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2"><span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[11px] font-bold">新システムに無し</span></td>
              <td class="px-3 py-2 text-xs text-slate-400" colspan="3">—</td>
            </tr>''')
            continue
        for fd in rec["fields"]:
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["mcid"]}</td>
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2 text-xs font-bold text-slate-700">{esc(fd["field"])}</td>
              <td class="px-3 py-2 text-xs text-red-500">{esc(fd["old"])}</td>
              <td class="px-3 py-2 text-xs text-emerald-600 font-bold">{esc(fd["new"])}</td>
            </tr>''')
    return "\n".join(rows)


def render_detail_section_tooling(details):
    rows = []
    for rec in details:
        if rec["status"] == "MISSING_IN_NEW":
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2 text-xs" colspan="4"><span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[11px] font-bold">新システムに無し</span></td>
            </tr>''')
            continue
        if rec["status"] == "ROW_COUNT_MISMATCH":
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2 text-xs" colspan="4">
                <span class="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold">行数不一致</span>
                <span class="ml-2 text-slate-500">旧:{rec["old_count"]}行 → 新:{rec["new_count"]}行</span>
              </td>
            </tr>''')
            continue
        for row in rec["rows"]:
            for fd in row["fields"]:
                rows.append(f'''
                <tr class="border-b border-slate-100">
                  <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
                  <td class="px-3 py-2 font-mono text-xs text-slate-400">{row["row_index"]}</td>
                  <td class="px-3 py-2 text-xs font-bold text-slate-700">{esc(fd["field"])}</td>
                  <td class="px-3 py-2 text-xs text-red-500">{esc(fd["old"])}</td>
                  <td class="px-3 py-2 text-xs text-emerald-600 font-bold">{esc(fd["new"])}</td>
                </tr>''')
    return "\n".join(rows)


def render_detail_section_generic(details, id_label="加工ID"):
    """ワークオフセット・インデックスプログラム共通の詳細テーブル行を生成する。
    rows構造が②ツーリングと同じ(kakoid/status/rows[].fields[])のため共通化する。
    """
    rows = []
    for rec in details:
        if rec["status"] == "MISSING_IN_NEW":
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2 text-xs" colspan="4"><span class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[11px] font-bold">新システムに無し</span></td>
            </tr>''')
            continue
        if rec["status"] == "ROW_COUNT_MISMATCH":
            rows.append(f'''
            <tr class="border-b border-slate-100">
              <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
              <td class="px-3 py-2 text-xs" colspan="4">
                <span class="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold">行数不一致</span>
                <span class="ml-2 text-slate-500">旧:{rec["old_count"]}行 → 新:{rec["new_count"]}行</span>
              </td>
            </tr>''')
            continue
        for row in rec.get("rows", []):
            for fd in row.get("fields", []):
                rows.append(f'''
                <tr class="border-b border-slate-100">
                  <td class="px-3 py-2 font-mono text-xs">{rec["kakoid"]}</td>
                  <td class="px-3 py-2 font-mono text-xs text-slate-400">{row.get("row_index","")}</td>
                  <td class="px-3 py-2 text-xs font-bold text-slate-700">{esc(fd["field"])}</td>
                  <td class="px-3 py-2 text-xs text-red-500">{esc(fd["old"])}</td>
                  <td class="px-3 py-2 text-xs text-emerald-600 font-bold">{esc(fd["new"])}</td>
                </tr>''')
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="/tmp/verify_result.json")
    ap.add_argument("--out", default="report.html")
    args = ap.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        data = json.load(f)

    summaries = data["summaries"]
    details = data["details"]
    issues = build_issue_table(details)

    total_checked = sum(s["total"] for s in summaries)
    total_mismatch = sum(s["mismatched"] for s in summaries)
    total_missing = sum(s.get("missing_in_new", 0) for s in summaries)

    html_out = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>MachCore 新旧データ検証レポート</title>
<style>
  :root {{
    --teal-50:#f0fdfa; --teal-100:#ccfbf1; --teal-200:#99f6e4; --teal-600:#0d9488; --teal-700:#0f766e;
    --slate-50:#f8fafc; --slate-100:#f1f5f9; --slate-200:#e2e8f0; --slate-300:#cbd5e1;
    --slate-400:#94a3b8; --slate-500:#64748b; --slate-600:#475569; --slate-700:#334155; --slate-800:#1e293b;
    --emerald-50:#ecfdf5; --emerald-100:#d1fae5; --emerald-500:#10b981; --emerald-600:#059669; --emerald-700:#047857;
    --red-50:#fef2f2; --red-100:#fee2e2; --red-500:#ef4444; --red-600:#dc2626; --red-700:#b91c1c;
    --amber-100:#fef3c7; --amber-500:#f59e0b; --amber-600:#d97706; --amber-700:#b45309;
    --blue-100:#dbeafe; --blue-600:#2563eb; --blue-700:#1d4ed8;
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Hiragino Sans','Meiryo',system-ui,sans-serif; background: var(--slate-50); color: var(--slate-800); margin:0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  header {{ background: linear-gradient(to right, var(--teal-700), var(--teal-600)); color: white; padding: 24px 32px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  .wrap {{ max-width: 1280px; margin: 0 auto; }}
  header h1 {{ font-size: 24px; font-weight: 800; margin: 0; letter-spacing: -0.02em; }}
  header p {{ margin: 4px 0 0; color: #bdeee6; font-size: 13px; }}
  header p.meta {{ color: #d3f1ec; font-size: 12px; margin-top: 8px; }}
  nav {{ max-width:1280px; margin: 24px auto 0; padding: 0 32px; display:flex; gap:8px; }}
  .tab-btn {{ padding: 8px 20px; border-radius: 999px; font-size: 14px; font-weight: 700; border: 1px solid var(--slate-300); color: var(--slate-600); background: white; cursor: pointer; transition: all .15s; }}
  .tab-btn.active {{ background: var(--teal-600); color: white; border-color: var(--teal-600); }}
  .cat-filter-btn {{ padding:5px 14px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid var(--slate-300); color:var(--slate-600); background:white; cursor:pointer; transition: all .15s; }}
  .cat-filter-btn.active {{ background: var(--slate-700); color: white; border-color: var(--slate-700); }}
  tr.cat-hidden {{ display:none; }}
  main {{ max-width: 1280px; margin: 0 auto; padding: 24px 32px 48px; }}
  .tab-content.hidden {{ display: none; }}
  .cards {{ display:flex; flex-wrap:wrap; gap:16px; }}
  .card {{ background:white; border:1px solid var(--slate-200); border-radius:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); padding:24px; flex:1; min-width:260px; }}
  .card-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }}
  .card-head h3 {{ font-size:13px; font-weight:700; color:var(--slate-500); margin:0; }}
  .rate {{ font-size:24px; font-weight:800; }}
  .rate.high {{ color: var(--emerald-600); }} .rate.mid {{ color: var(--amber-600); }} .rate.low {{ color: var(--red-600); }}
  .bar-bg {{ width:100%; height:8px; background:var(--slate-100); border-radius:999px; overflow:hidden; margin-bottom:16px; }}
  .bar-fg {{ height:100%; border-radius:999px; }}
  .bar-fg.high {{ background: var(--emerald-500); }} .bar-fg.mid {{ background: var(--amber-500); }} .bar-fg.low {{ background: var(--red-500); }}
  .stats3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; text-align:center; }}
  .stats3 .num {{ font-size:18px; font-weight:700; color: var(--slate-800); }}
  .stats3 .num.green {{ color: var(--emerald-600); }} .stats3 .num.red {{ color: var(--red-500); }}
  .stats3 .lbl {{ font-size:11px; color: var(--slate-400); }}
  .foot-row {{ display:flex; justify-content:space-between; font-size:12px; color:var(--slate-500); margin-top:12px; padding-top:12px; border-top:1px solid var(--slate-100); }}
  .panel {{ background:white; border:1px solid var(--slate-200); border-radius:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); overflow:hidden; }}
  .panel-head {{ padding:16px 20px; border-bottom:1px solid var(--slate-100); display:flex; align-items:center; justify-content:space-between; }}
  .panel-head h2 {{ font-size:15px; font-weight:700; color:var(--slate-700); margin:0; }}
  .panel-head .note {{ font-size:12px; color:var(--slate-400); }}
  .scroll-x {{ overflow-x:auto; }}
  .scroll-y {{ max-height:70vh; overflow-y:auto; }}
  thead.sticky th {{ position:sticky; top:0; background:var(--slate-50); z-index:1; }}
  th {{ text-align:left; padding:8px 16px; font-size:11px; color:var(--slate-500); border-bottom:1px solid var(--slate-200); background: var(--slate-50); }}
  td {{ padding:8px 16px; font-size:13px; border-bottom:1px solid var(--slate-100); vertical-align:top; }}
  tr:hover td {{ background: var(--slate-50); }}
  .mono {{ font-family: 'SF Mono', Consolas, monospace; }}
  .badge {{ display:inline-flex; align-items:center; padding:2px 10px; border-radius:999px; font-size:11px; font-weight:700; }}
  .badge.danger {{ background: var(--red-100); color: var(--red-700); }}
  .badge.warn {{ background: var(--amber-100); color: var(--amber-700); }}
  .old-val {{ color: var(--red-500); }}
  .new-val {{ color: var(--emerald-600); font-weight:700; }}
  .count-pill {{ display:inline-flex; align-items:center; justify-content:center; width:48px; height:28px; border-radius:999px; background:var(--red-50); color:var(--red-600); font-weight:700; font-size:13px; }}
  select.status-select {{ font-size:12px; font-weight:700; border-radius:999px; padding:4px 12px; border:1px solid; cursor:pointer; }}
  .st-未着手 {{ background:var(--slate-100); color:var(--slate-600); border-color:var(--slate-300); }}
  .st-調査対象外 {{ background:var(--slate-100); color:var(--slate-400); border-color:var(--slate-300); text-decoration:line-through; }}
  .st-手入力対応 {{ background:var(--blue-100); color:var(--blue-700); border-color:var(--blue-600); }}
  .st-調査中 {{ background:var(--amber-100); color:var(--amber-700); border-color:var(--amber-500); }}
  .st-対応中 {{ background:var(--blue-100); color:var(--blue-700); border-color:var(--blue-600); }}
  .st-対応済,.st-対応済_表示側で整形_ {{ background:var(--emerald-100); color:var(--emerald-700); border-color:var(--emerald-500); }}
  .examples div {{ font-size:11px; color:var(--slate-500); margin-top:2px; }}
  .issue-name {{ font-weight:700; color:var(--slate-800); font-size:13px; }}
  .issue-cat {{ font-size:11px; color:var(--slate-400); margin-top:2px; }}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <h1>MachCore 新旧データ検証レポート</h1>
    <p>旧システム(Access/SQL Server) ⇔ 新システム(MachCore/PostgreSQL) 全件自動比較</p>
    <p class="meta">生成日時: {esc(data.get("generated_at",""))}　/　検証総数: {total_checked:,}件　/　不一致: {total_mismatch:,}件　/　新システム未存在: {total_missing:,}件</p>
  </div>
</header>

<nav>
  <button class="tab-btn active" data-tab="summary">📊 サマリ</button>
  <button class="tab-btn" data-tab="issues">🧩 課題管理</button>
  <button class="tab-btn" data-tab="detail-basic">📋 詳細: 基本情報</button>
  <button class="tab-btn" data-tab="detail-tooling">🔧 詳細: ツーリング</button>
  <button class="tab-btn" data-tab="detail-wo">📐 詳細: ワークオフセット</button>
  <button class="tab-btn" data-tab="detail-ip">🧭 詳細: インデックスプログラム</button>
  <button class="tab-btn" data-tab="detail-history">🕘 詳細: 履歴(変更/印刷/作業記録)</button>
</nav>

<main>

  <section id="tab-summary" class="tab-content">
    <div class="cards">
      {render_summary_cards(summaries)}
    </div>
  </section>

  <section id="tab-issues" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head" style="flex-wrap:wrap; gap:12px; align-items:center;">
        <div>
          <h2>不一致パターン別 課題管理</h2>
          <span class="note">{len(issues)} パターン検出 / ステータスはブラウザ内でのみ変更可（保存はされません）</span>
        </div>
        <div class="cat-filter" style="display:flex; gap:6px; flex-wrap:wrap;">
          <button class="cat-filter-btn active" data-cat-filter="__all__">すべて</button>
          {"".join(f'<button class="cat-filter-btn" data-cat-filter="{esc(c)}">{esc(c)}</button>' for c in sorted(set(cat for issue in issues for cat in issue["categories"].split(", "))))}
        </div>
      </div>
      <div class="scroll-x">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>パターン名</th>
              <th style="text-align:center">件数</th>
              <th>原因仮説</th>
              <th>対応状況</th>
              <th>サンプル(最大5件)</th>
            </tr>
          </thead>
          <tbody>
            {render_issue_table(issues)}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="tab-detail-basic" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head"><h2>基本情報(MC) 不一致詳細</h2></div>
      <div class="scroll-x scroll-y">
        <table>
          <thead class="sticky">
            <tr>
              <th>MCID</th><th>加工ID</th><th>項目</th><th>旧値</th><th>新値</th>
            </tr>
          </thead>
          <tbody>
            {render_detail_section_basic(details["basic_info"])}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="tab-detail-tooling" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head"><h2>ツーリング 不一致詳細</h2></div>
      <div class="scroll-x scroll-y">
        <table>
          <thead class="sticky">
            <tr>
              <th>加工ID</th><th>行</th><th>項目</th><th>旧値</th><th>新値</th>
            </tr>
          </thead>
          <tbody>
            {render_detail_section_tooling(details["tooling"])}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="tab-detail-wo" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head"><h2>ワークオフセット 不一致詳細</h2></div>
      <div class="scroll-x scroll-y">
        <table>
          <thead class="sticky">
            <tr>
              <th>加工ID</th><th>#</th><th>項目</th><th>旧値</th><th>新値</th>
            </tr>
          </thead>
          <tbody>
            {render_detail_section_generic(details.get("work_offsets", []))}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="tab-detail-ip" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head"><h2>インデックスプログラム 不一致詳細</h2></div>
      <div class="scroll-x scroll-y">
        <table>
          <thead class="sticky">
            <tr>
              <th>加工ID</th><th>#</th><th>項目</th><th>旧値</th><th>新値</th>
            </tr>
          </thead>
          <tbody>
            {render_detail_section_generic(details.get("index_programs", []))}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section id="tab-detail-history" class="tab-content hidden">
    <div class="panel">
      <div class="panel-head"><h2>履歴(変更履歴/印刷履歴/作業記録) 不一致詳細</h2></div>
      <div class="scroll-x scroll-y">
        <table>
          <thead class="sticky">
            <tr>
              <th>MCID</th><th>#</th><th>項目</th><th>旧値</th><th>新値</th>
            </tr>
          </thead>
          <tbody>
            {render_detail_section_generic(details.get("history", []))}
          </tbody>
        </table>
      </div>
    </div>
  </section>

</main>

<script>
document.querySelectorAll(".tab-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    document.getElementById("tab-" + btn.dataset.tab).classList.remove("hidden");
  }});
}});
document.querySelectorAll(".status-select").forEach(sel => {{
  const applyClass = () => {{
    sel.className = "status-select st-" + sel.value.replace(/[()]/g, "_");
  }};
  applyClass();
  sel.addEventListener("change", applyClass);
}});
document.querySelectorAll(".cat-filter-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".cat-filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.catFilter;
    document.querySelectorAll("#tab-issues tbody tr").forEach(tr => {{
      const cats = (tr.dataset.cat || "").split(", ");
      const show = (target === "__all__") || cats.includes(target);
      tr.classList.toggle("cat-hidden", !show);
    }});
  }});
}});
</script>

</body>
</html>'''

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"レポート生成完了: {args.out}")


if __name__ == "__main__":
    main()
