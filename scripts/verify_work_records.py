#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_work_records.py
======================
作業記録(work_records)を旧DBと全件・全項目で比較する検証スクリプト(DBは読むだけ)。

  MC: 旧 ACC_変更履歴(作業記録の行 = 内容区分ID=17 または 総時間あり) ⇔ work_records(mc_program_id)
  NC: 旧 ACC_History(Dan_*/La_*/P に実データあり)                     ⇔ work_records(nc_program_id)

比較するもの
  [格納値]  新DBの列に入っている値 ⇔ 旧の値(コンバート規則どおりに入っているか)
  [画面表示] MC作業記録画面(apps/web/app/mc/[mc_id]/record/page.tsx calcTimes)が
            過去記録を開いたときに「時間集計」に出す値 ⇔ 旧「段取シート戻り」画面の値
            (未認証で開いたとき=タイムカードを使わない計算。lunch控除・中断控除も画面と同じ)
  [未移行]  旧にあるが新DBに入れる列が無い/入れていない値

旧の行と新の行の対応付け
  作業記録には旧の行IDを持たないため、同じプログラム内で
  作業日・段取開始・加工終了・段取時間・加工時間・数量 がもっとも多く一致する行を対応させる。
  対応する新の行が無い旧の行 = 「新に無し」、対応する旧の行が無い新の行 = 「新のみ(UATで登録した分など)」。

実行:
  python3 scripts/verify_work_records.py [--target mc|nc|all] [--examples 20]
出力:
  scripts/verify_reports/verify_work_records_YYYYMMDD_HHMMSS.md   (件数の一覧と例)
  scripts/verify_reports/verify_work_records_YYYYMMDD_HHMMSS.csv  (不一致の全件)
  scripts/verify_reports/verify_work_records_YYYYMMDD_HHMMSS.json
"""
import sys, os, re, csv, json, argparse, unicodedata
from datetime import datetime, timedelta, date
from collections import defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from verify_old_new_db import pg_connect, ss_connect, SS_MC_DB, log  # 接続先は既存の検証と同じ
from machine_name_match import MachineResolver
from name_match import PersonResolver
import legacy_work_time as lwt  # 取込と同じ時間・サイクルの変換規則

OUT_DIR = os.path.join(HERE, "verify_reports")


# ───────────────────────── 共通ヘルパー ─────────────────────────

def s_norm(v):
    if v is None:
        return None
    s = str(v).replace("\r\n", "\n").replace("\r", "\n").strip()
    s = re.sub(r"[ \t　]+", " ", s)
    return s or None


def i_or0(v):
    if v is None:
        return 0
    try:
        return int(float(str(v).strip() or 0))
    except (TypeError, ValueError):
        return 0


def i_or_none(v):
    """0 と 空 は同じ(None)として扱う"""
    n = i_or0(v)
    return n or None


parse_hms_sec = lwt.parse_hms_sec   # 旧の時間文字列 → 秒(負・空は None)


def has_sec_part(v):
    return v is not None and re.search(r"\d+\s*S", unicodedata.normalize("NFKC", str(v)).upper()) is not None


def fmt_sec(sec):
    """画面(fmtSec)と同じ表記"""
    if sec is None:
        return "—"
    t = int(round(sec))
    return f"{t // 3600}h{(t % 3600) // 60}m{t % 60}s"


def fmt_min(m):
    return "—" if m is None or m < 0 else fmt_sec(m * 60)


def to_naive_utc(v):
    """新DBの timestamp → naive UTC"""
    if v is None:
        return None
    if getattr(v, "tzinfo", None) is not None:
        v = (v - v.utcoffset()).replace(tzinfo=None)
    return v.replace(microsecond=0)


def old_dt_to_utc(v):
    """旧(JST naive) → naive UTC(-9h)。文字列の日付も受ける(取込と同じ)"""
    if v is None:
        return None
    if hasattr(v, "year") and hasattr(v, "hour"):
        return (v - timedelta(hours=9)).replace(microsecond=0)
    s = str(v).strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt) - timedelta(hours=9)
        except ValueError:
            pass
    return None


def utc_to_jst(v):
    return None if v is None else v + timedelta(hours=9)


def lunch_deduct_min(s, e):
    """画面の lunchDeductMin と同じ(JSTの各日 12:00-13:00 との重なり分)"""
    if s is None or e is None or e <= s:
        return 0
    total = 0
    d = s.date()
    while d <= e.date():
        ls = datetime(d.year, d.month, d.day, 12, 0)
        le = datetime(d.year, d.month, d.day, 13, 0)
        os_ = max(s, ls)
        oe = min(e, le)
        if oe > os_:
            total += int(round((oe - os_).total_seconds() / 60))
        d += timedelta(days=1)
    return total


def js_round(x):
    """JavaScript Math.round と同じ(0.5は+∞方向)"""
    import math
    return int(math.floor(x + 0.5))


class Tally:
    """項目ごとの件数・不一致の例・全件"""

    def __init__(self, n_examples):
        self.n_examples = n_examples
        self.items = OrderedDict()   # label → {"group","checked","ng","examples"}
        self.rows = []               # 不一致の全件(CSV)

    def _get(self, group, label):
        key = (group, label)
        if key not in self.items:
            self.items[key] = {"group": group, "label": label, "checked": 0, "ng": 0, "examples": []}
        return self.items[key]

    def check(self, group, label, ok, ident, old, new):
        it = self._get(group, label)
        it["checked"] += 1
        if ok:
            return
        it["ng"] += 1
        rec = dict(ident)
        rec.update({"区分": group, "項目": label, "旧": "" if old is None else str(old), "新": "" if new is None else str(new)})
        self.rows.append(rec)
        if len(it["examples"]) < self.n_examples:
            it["examples"].append(rec)


def pair_rows(old_rows, new_rows, key_fn_old, key_fn_new):
    """同じプログラム内で旧と新を対応付け。key_fn は (作業日, その他比較値のtuple)"""
    used = set()
    pairs = []
    unmatched_old = []
    new_keys = [(i, key_fn_new(n)) for i, n in enumerate(new_rows)]
    for o in old_rows:
        ok = key_fn_old(o)
        best, best_score = None, -1
        for i, nk in new_keys:
            if i in used:
                continue
            score = (5 if ok[0] == nk[0] else 0) + sum(1 for a, b in zip(ok[1], nk[1]) if a == b and a is not None)
            if score > best_score:
                best, best_score = i, score
        # 作業日が一致するか、他の値が3つ以上一致すれば同じ記録とみなす
        if best is not None and best_score >= 3:
            used.add(best)
            pairs.append((o, new_rows[best]))
        else:
            unmatched_old.append(o)
    unmatched_new = [n for i, n in enumerate(new_rows) if i not in used]
    return pairs, unmatched_old, unmatched_new


# ───────────────────────── MC ─────────────────────────

def verify_mc(ss, pg, tally):
    log("MC 作業記録の検証を開始")
    pgc = pg.cursor()
    mcc = ss.cursor()

    mcc.execute("SELECT TOP 0 * FROM ACC_変更履歴")
    cols = [d[0] for d in mcc.description]
    log(f"  ACC_変更履歴の列({len(cols)}): {cols}")
    stop_cols = [c for c in cols if ("中断" in c) or re.search(r"stop", c, re.I)]
    log(f"  中断に関係する旧の列: {stop_cols if stop_cols else '(該当なし)'}")

    def col_of(*conds):
        for c in stop_cols:
            if all(re.search(p, c, re.I) for p in conds):
                return c
        return None

    # 段取時/量産時の中断(時間・分)の列名を推定(名前に 段取/D と 量産/Y、末尾 H/M)
    st_cols = {
        "dH": col_of(r"(段取|^D|_D|ﾀﾞﾝ)", r"(H$|時$|_H)"),
        "dM": col_of(r"(段取|^D|_D|ﾀﾞﾝ)", r"(M$|分$|_M)"),
        "yH": col_of(r"(量産|^Y|_Y|ﾘｮｳ)", r"(H$|時$|_H)"),
        "yM": col_of(r"(量産|^Y|_Y|ﾘｮｳ)", r"(M$|分$|_M)"),
    }
    log(f"  中断の列の対応(推定): {st_cols}")

    sel = ", ".join(f"[{c}]" for c in cols)
    mcc.execute(f"SELECT {sel} FROM ACC_変更履歴 ORDER BY MCID, 入力日")
    old_all = [dict(zip(cols, r)) for r in mcc.fetchall()]
    log(f"  旧 ACC_変更履歴: {len(old_all)}行")

    def is_work(r):
        try:
            nk = int(r.get("内容区分ID") or 0)
        except (TypeError, ValueError):
            nk = 0
        tt = r.get("総時間")
        return nk == 17 or (tt is not None and str(tt).strip() != "")

    old_work = [r for r in old_all if is_work(r)]
    log(f"  旧の作業記録行: {len(old_work)}行")

    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_map = defaultdict(list)
    for pid, lm in pgc.fetchall():
        mcid_map[lm].append(pid)

    pgc.execute("SELECT id, name, employee_code, system_type::text, is_active FROM users ORDER BY id")
    users = pgc.fetchall()
    uname = {u[0]: u[1] for u in users}
    person = PersonResolver(users, system="MC")  # 取込と同じ照合(同姓同名は系統で決める)
    if person.ambiguous:
        log(f"  [注意] 同姓同名で担当者が決まらない名前: {person.ambiguous}")
    pgc.execute("SELECT id, machine_code FROM machines")
    mcode = dict(pgc.fetchall())
    mres = MachineResolver.from_db(pgc)
    pgc.execute("SELECT id FROM users WHERE employee_code = 'ADMIN001'")
    _a = pgc.fetchone()
    admin_id = _a[0] if _a else 22

    pgc.execute("""
        SELECT id, mc_program_id, operator_id, machine_id, work_date,
               setup_time_min, machining_time_min, cycle_time_sec, quantity,
               started_at, checked_at, finished_at,
               interrupt_setup_min, interrupt_work_min, interruption_time_min,
               setup_work_count, prg_man, prg_time_min, prg_plas,
               setup_operator_ids, production_operator_ids, note, created_at,
               cycle_pcs, check_operator_id, total_time_min
        FROM work_records WHERE mc_program_id IS NOT NULL ORDER BY mc_program_id, id
    """)
    wcols = [d[0] for d in pgc.description]
    new_by_prog = defaultdict(list)
    for r in pgc.fetchall():
        d = dict(zip(wcols, r))
        for k in ("started_at", "checked_at", "finished_at"):
            d[k] = to_naive_utc(d[k])
        new_by_prog[d["mc_program_id"]].append(d)
    n_new_total = sum(len(v) for v in new_by_prog.values())
    log(f"  新 work_records(MC): {n_new_total}行")

    old_by_mcid = defaultdict(list)
    for r in old_work:
        old_by_mcid[r["MCID"]].append(r)

    def okey(o):
        return (o["入力日"].date() if hasattr(o.get("入力日"), "year") else None,
                (old_dt_to_utc(o.get("段取開始")), old_dt_to_utc(o.get("加工終了")),
                 lwt.parse_hms_min(o.get("段取時間")),
                 lwt.parse_hms_min(o.get("加工時間")),
                 i_or_none(o.get("ﾜｰｸ数"))))

    def nkey(n):
        return (n["work_date"], (n["started_at"], n["finished_at"], n["setup_time_min"] or None,
                                 n["machining_time_min"] or None, n["quantity"] or None))

    stat = {"old": len(old_work), "paired": 0, "missing_in_new": 0, "new_only": 0, "no_program": 0}
    missing_list, new_only_list = [], []
    paired_prog = set()

    for mcid, orows in old_by_mcid.items():
        pids = mcid_map.get(mcid, [])
        if not pids:
            stat["no_program"] += len(orows)
            continue
        for pid in pids:
            paired_prog.add(pid)
            pairs, um_old, um_new = pair_rows(orows, new_by_prog.get(pid, []), okey, nkey)
            stat["missing_in_new"] += len(um_old)
            for o in um_old:
                missing_list.append({"MCID": mcid, "mc_program_id": pid, "入力日": str(o.get("入力日"))})
            for n in um_new:
                stat["new_only"] += 1
                new_only_list.append({"MCID": mcid, "mc_program_id": pid, "work_record_id": n["id"],
                                      "作業日": str(n["work_date"]), "created_at": str(n["created_at"])})
            for o, n in pairs:
                stat["paired"] += 1
                compare_mc_pair(o, n, mcid, pid, tally, person, mres, uname, mcode, admin_id, st_cols)
    for pid, nrows in new_by_prog.items():
        if pid not in paired_prog:
            for n in nrows:
                stat["new_only"] += 1
                new_only_list.append({"MCID": None, "mc_program_id": pid, "work_record_id": n["id"],
                                      "作業日": str(n["work_date"]), "created_at": str(n["created_at"])})
    log(f"  MC 対応付け: {stat}")
    return stat, missing_list, new_only_list, {"columns": cols, "stop_columns": stop_cols, "stop_map": st_cols}


def compare_mc_pair(o, n, mcid, pid, tally, person, mres, uname, mcode, admin_id, st_cols):
    ident = {"系統": "MC", "MCID": mcid, "mc_program_id": pid, "work_record_id": n["id"],
             "入力日(旧)": str(o.get("入力日"))}
    G1, G2, G3 = "格納値", "画面表示(時間集計)", "未移行"
    chk = lambda g, lab, ok, old, new: tally.check(g, lab, ok, ident, old, new)

    # ── 格納値 ──
    od = o["入力日"].date() if hasattr(o.get("入力日"), "year") else None
    chk(G1, "作業日", od == n["work_date"], od, n["work_date"])

    om = s_norm(o.get("機械"))
    exp_mid = mres.resolve(om, count_unresolved=False) if om else None
    chk(G1, "機械", exp_mid == n["machine_id"], om, mcode.get(n["machine_id"]))
    if om and exp_mid is None:
        chk(G3, "機械(マスタ未登録で空欄)", False, om, None)

    for lab, oc, nc in (("段取開始", "段取開始", "started_at"), ("段取終了(ﾁｪｯｸTime)", "ﾁｪｯｸTime", "checked_at"),
                        ("加工終了", "加工終了", "finished_at")):
        ov = old_dt_to_utc(o.get(oc))
        chk(G1, lab, ov == n[nc], utc_to_jst(ov), utc_to_jst(n[nc]))

    o_setup = parse_hms_sec(o.get("段取時間"))
    o_mach = parse_hms_sec(o.get("加工時間"))
    o_total = parse_hms_sec(o.get("総時間"))
    e_setup, e_mach, e_total = lwt.parse_hms_min(o.get("段取時間")), lwt.parse_hms_min(o.get("加工時間")), lwt.parse_hms_min(o.get("総時間"))
    chk(G1, "段取時間(列)", e_setup == (n["setup_time_min"] or None), o.get("段取時間"), fmt_min(n["setup_time_min"]))
    chk(G1, "加工時間(列)", e_mach == (n["machining_time_min"] or None), o.get("加工時間"), fmt_min(n["machining_time_min"]))
    chk(G1, "総時間(列)", e_total == (n["total_time_min"] or None), o.get("総時間"), fmt_min(n["total_time_min"]))

    e_cyc, e_pcs = lwt.cycle_sec(o), lwt.cycle_pcs(o)
    chk(G1, "サイクルタイム(列)", e_cyc == (n["cycle_time_sec"] or None),
        f"{i_or0(o.get('TH'))}H {i_or0(o.get('TM'))}M {i_or0(o.get('TS'))}S", fmt_sec(n["cycle_time_sec"]) if n["cycle_time_sec"] else None)
    chk(G1, "個/1サイクル(列)", e_pcs == (n["cycle_pcs"] or None), o.get("1S_個数"), n["cycle_pcs"])
    o_chk = s_norm(o.get("ﾁｪｯｸMan"))
    e_chk = person.resolve(o_chk) if o_chk else None
    chk(G1, "チェック担当(列)", e_chk == n["check_operator_id"], o_chk, uname.get(n["check_operator_id"]))
    if o_chk and e_chk is None:
        chk(G3, "チェック担当(usersに無く空欄)", False, o_chk, None)

    chk(G1, "全良品数(ワーク数)", i_or_none(o.get("ﾜｰｸ数")) == (n["quantity"] or None), o.get("ﾜｰｸ数"), n["quantity"])
    chk(G1, "段取良品数", i_or_none(o.get("段取_ﾜｰｸ数")) == (n["setup_work_count"] or None), o.get("段取_ﾜｰｸ数"), n["setup_work_count"])

    for lab, oc, nc in (("段取担当", "段取", "setup_operator_ids"), ("量産担当", "作業者", "production_operator_ids")):
        exp_ids, unres = person.resolve_multi(o.get(oc))
        got = n[nc] if isinstance(n[nc], list) else (json.loads(n[nc]) if n[nc] else [])
        chk(G1, lab, sorted(exp_ids) == sorted(got), s_norm(o.get(oc)), ", ".join(uname.get(i, str(i)) for i in got))
        if unres:
            chk(G3, f"{lab}(usersに無く空欄)", False, ", ".join(unres), None)

    exp_op = person.resolve(o.get("ｵﾍﾟﾚｰﾀｰ")) or admin_id
    chk(G1, "オペレーター", exp_op == n["operator_id"], s_norm(o.get("ｵﾍﾟﾚｰﾀｰ")), uname.get(n["operator_id"]))

    chk(G1, "プログラム担当", s_norm(o.get("Prg")) == s_norm(n["prg_man"]), s_norm(o.get("Prg")), n["prg_man"])
    chk(G1, "PrgPlas", s_norm(o.get("PrgPlas")) == s_norm(n["prg_plas"]), s_norm(o.get("PrgPlas")), n["prg_plas"])
    o_prg = i_or0(o.get("PrgTimeH")) * 60 + i_or0(o.get("PrgTimeM"))
    chk(G1, "PrgTime", (o_prg or None) == (n["prg_time_min"] or None), fmt_min(o_prg), fmt_min(n["prg_time_min"]))

    o_note = s_norm(str(o.get("内容"))[:1000] if o.get("内容") is not None else None)
    chk(G1, "備考(内容)", o_note == s_norm(n["note"]), o_note, s_norm(n["note"]))

    o_dstop = o_ystop = None
    if st_cols.get("dH") or st_cols.get("dM"):
        o_dstop = i_or0(o.get(st_cols["dH"])) * 60 + i_or0(o.get(st_cols["dM"]))
        chk(G1, "段取時の中断", (o_dstop or None) == (n["interrupt_setup_min"] or None), fmt_min(o_dstop), fmt_min(n["interrupt_setup_min"]))
    if st_cols.get("yH") or st_cols.get("yM"):
        o_ystop = i_or0(o.get(st_cols["yH"])) * 60 + i_or0(o.get(st_cols["yM"]))
        chk(G1, "量産時の中断", (o_ystop or None) == (n["interrupt_work_min"] or None), fmt_min(o_ystop), fmt_min(n["interrupt_work_min"]))

    # ── 画面表示: page.tsx loadRecord → calcTimes を再現 ──
    #   過去記録を開いた直後は保存値(段取/加工/総時間)をそのまま表示する。
    #   総時間 = total_time_min、無ければ 段取+加工。サイクルタイム/1P = サイクルタイム ÷ 個/1サイクル
    qty = n["quantity"] or 0
    sq = n["setup_work_count"] or 0
    mach_base = max(1, qty - sq) if (qty > 0 and qty != sq) else max(1, qty)
    smin, mmin = n["setup_time_min"], n["machining_time_min"]
    if n["total_time_min"] is not None:
        tmin = n["total_time_min"]
    elif smin is not None or mmin is not None:
        tmin = (smin or 0) + (mmin or 0)
    else:
        tmin = None
    mode = "保存値"
    disp_mach_p = js_round(mmin / mach_base * 60) if (mmin and qty > 0) else None
    disp_total_p = js_round(tmin / qty * 60) if (tmin and qty > 0) else None
    disp_cyc_p = (n["cycle_time_sec"] / n["cycle_pcs"]) if (n["cycle_time_sec"] and n["cycle_pcs"]) else None

    def same_min(old_txt, new_min):
        ov = parse_hms_sec(old_txt)
        if not ov and not new_min:      # 旧 空/0/負 と 新 空/0 は同じ(どちらも時間なし)
            return True
        if ov is None or new_min is None:
            return False
        return ov // 60 == new_min

    def same_sec(old_txt, new_sec):
        ov = parse_hms_sec(old_txt)
        if (ov is None or ov == 0) and new_sec is None:
            return True
        if ov is None or new_sec is None:
            return False
        # 旧画面はちょうどx時間を「xH 1M」と表示する(旧の端数処理の癖)。値としては一致とみなし参考として数える
        m1 = re.fullmatch(r"\s*(\d+)\s*H\s*1\s*M\s*", unicodedata.normalize("NFKC", str(old_txt)).upper())
        if m1 and int(m1.group(1)) > 0 and abs(new_sec - int(m1.group(1)) * 3600) < 60:
            chk("参考(旧データ内)", "旧の/1P表示の端数(ちょうどx時間を xH 1M と表示)", False, old_txt, fmt_sec(new_sec))
            return True
        if has_sec_part(old_txt):
            return abs(ov - new_sec) <= 1
        return abs(ov - new_sec) < 60      # 旧が分までの表示なら分の単位で比較

    chk(G2, f"段取時間", same_min(o.get("段取時間"), smin), o.get("段取時間"), f"{fmt_min(smin)}[{mode}]")
    chk(G2, f"加工時間", same_min(o.get("加工時間"), mmin), o.get("加工時間"), f"{fmt_min(mmin)}[{mode}]")
    chk(G2, f"総時間", same_min(o.get("総時間"), tmin), o.get("総時間"), f"{fmt_min(tmin)}[{mode}]")
    o_cyc_p = o.get("ｻｲｸﾙﾀｲﾑ/1P")
    chk(G2, "サイクルタイム/1P", same_sec(o_cyc_p, disp_cyc_p), o_cyc_p,
        fmt_sec(disp_cyc_p) if disp_cyc_p is not None else "表示なし")
    chk(G2, "加工時間/1P", same_sec(o.get("加工時間/1P"), disp_mach_p), o.get("加工時間/1P"),
        fmt_sec(disp_mach_p) if disp_mach_p is not None else "表示なし")
    chk(G2, "総時間/1P", same_sec(o.get("総時間/1P"), disp_total_p), o.get("総時間/1P"),
        fmt_sec(disp_total_p) if disp_total_p is not None else "表示なし")

    # 旧の値どうしの整合(旧の 段取+加工 = 総時間 か): 旧データ自体の参考
    if o_total is not None:
        chk("参考(旧データ内)", "旧 段取時間+加工時間=総時間", (o_setup or 0) + (o_mach or 0) == o_total,
            f"{o.get('段取時間')} + {o.get('加工時間')}", o.get("総時間"))


# ───────────────────────── NC ─────────────────────────

def verify_nc(ss, pg, tally):
    log("NC 作業記録の検証を開始")
    pgc = pg.cursor()
    ssc = ss.cursor()
    ssc.execute("""
        SELECT Hist_id, K_id, NC_id, Mc, Out_Ver, Out_Cont, Out_Op, Out_Date,
               In_Ver, In_Cont, In_Op, In_Date, Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P
        FROM ACC_History ORDER BY K_id, In_Date, Hist_id
    """)
    hcols = [d[0] for d in ssc.description]
    rows = [dict(zip(hcols, r)) for r in ssc.fetchall()]
    log(f"  旧 ACC_History: {len(rows)}行")

    def is_work(r):
        return bool(s_norm(r["Dan_Op"])) or i_or0(r["Dan_H"]) > 0 or i_or0(r["Dan_M"]) > 0 \
            or i_or0(r["La_H"]) > 0 or i_or0(r["La_M"]) > 0 or i_or0(r["P"]) > 0

    old_work = [r for r in rows if is_work(r)]
    log(f"  旧の作業記録行: {len(old_work)}行")

    ssc.execute("SELECT m_id, Model FROM ACC_Machine")
    acc_machine = dict(ssc.fetchall())
    ssc.execute("SELECT St_id, S_name FROM ACC_Staff")
    staff = dict(ssc.fetchall())

    pgc.execute("SELECT id, machining_id FROM nc_programs")
    kid_map = defaultdict(list)
    for pid, kid in pgc.fetchall():
        kid_map[kid].append(pid)
    pgc.execute("SELECT id, name, employee_code, system_type::text, is_active FROM users ORDER BY id")
    users = pgc.fetchall()
    uname = {u[0]: u[1] for u in users}
    person = PersonResolver(users, system="NC")  # 取込と同じ照合(同姓同名は系統で決める)
    if person.ambiguous:
        log(f"  [注意] 同姓同名で担当者が決まらない名前: {person.ambiguous}")
    pgc.execute("SELECT id, machine_code FROM machines")
    mcode = dict(pgc.fetchall())
    mres = MachineResolver.from_db(pgc, system_types=None)

    pgc.execute("""
        SELECT id, nc_program_id, operator_id, machine_id, work_date, setup_time_min, machining_time_min,
               cycle_time_sec, quantity, note, setup_operator_ids, production_operator_ids, created_at
        FROM work_records WHERE nc_program_id IS NOT NULL ORDER BY nc_program_id, id
    """)
    wcols = [d[0] for d in pgc.description]
    new_by_prog = defaultdict(list)
    for r in pgc.fetchall():
        d = dict(zip(wcols, r))
        new_by_prog[d["nc_program_id"]].append(d)
    log(f"  新 work_records(NC): {sum(len(v) for v in new_by_prog.values())}行")

    old_by_kid = defaultdict(list)
    for r in old_work:
        old_by_kid[i_or0(r["K_id"])].append(r)

    def okey(o):
        wd = o["In_Date"] or o["Out_Date"]
        return (wd.date() if hasattr(wd, "year") else None,
                ((i_or0(o["Dan_H"]) * 60 + i_or0(o["Dan_M"])) or None,
                 (i_or0(o["La_H"]) * 60 + i_or0(o["La_M"])) or None,
                 i_or_none(o["P"]), s_norm(o["In_Cont"])))

    def nkey(n):
        return (n["work_date"], (n["setup_time_min"] or None, n["machining_time_min"] or None,
                                 n["quantity"] or None, s_norm(n["note"])))

    stat = {"old": len(old_work), "paired": 0, "missing_in_new": 0, "new_only": 0, "no_program": 0}
    missing_list, new_only_list = [], []
    seen_prog = set()
    for kid, orows in old_by_kid.items():
        pids = kid_map.get(kid, [])
        if not pids:
            stat["no_program"] += len(orows)
            continue
        for pid in pids:
            seen_prog.add(pid)
            pairs, um_old, um_new = pair_rows(orows, new_by_prog.get(pid, []), okey, nkey)
            stat["missing_in_new"] += len(um_old)
            for o in um_old:
                missing_list.append({"K_id": kid, "nc_program_id": pid, "Hist_id": o["Hist_id"]})
            for n in um_new:
                stat["new_only"] += 1
                new_only_list.append({"K_id": kid, "nc_program_id": pid, "work_record_id": n["id"],
                                      "作業日": str(n["work_date"]), "created_at": str(n["created_at"])})
            for o, n in pairs:
                stat["paired"] += 1
                ident = {"系統": "NC", "K_id": kid, "nc_program_id": pid, "work_record_id": n["id"], "Hist_id": o["Hist_id"]}
                chk = lambda g, lab, ok, old, new: tally.check(g, lab, ok, ident, old, new)
                k = okey(o)
                chk("格納値", "作業日", k[0] == n["work_date"], k[0], n["work_date"])
                model = acc_machine.get(o["Mc"]) if o["Mc"] is not None else None
                exp_mid = mres.resolve(model, count_unresolved=False) if model else None
                chk("格納値", "機械", exp_mid == n["machine_id"], model, mcode.get(n["machine_id"]))
                if model and exp_mid is None:
                    chk("未移行", "機械(マスタ未登録で空欄)", False, model, None)
                chk("格納値", "段取時間", k[1][0] == (n["setup_time_min"] or None),
                    f"{i_or0(o['Dan_H'])}H {i_or0(o['Dan_M'])}M", fmt_min(n["setup_time_min"]))
                chk("格納値", "加工時間", k[1][1] == (n["machining_time_min"] or None),
                    f"{i_or0(o['La_H'])}H {i_or0(o['La_M'])}M", fmt_min(n["machining_time_min"]))
                chk("格納値", "数量(P)", k[1][2] == (n["quantity"] or None), o["P"], n["quantity"])
                o_note = s_norm(str(o["In_Cont"])[:1000]) if o["In_Cont"] is not None else None
                chk("格納値", "備考(In_Cont)", o_note == s_norm(n["note"]), o_note, s_norm(n["note"]))
                for lab, oc, nc in (("段取担当", "Dan_Op", "setup_operator_ids"), ("量産担当", "La_Op", "production_operator_ids")):
                    exp_ids, unres = person.resolve_multi(o[oc])
                    got = n[nc] if isinstance(n[nc], list) else (json.loads(n[nc]) if n[nc] else [])
                    chk("格納値", lab, sorted(exp_ids) == sorted(got), s_norm(o[oc]), ", ".join(uname.get(i, str(i)) for i in got))
                    if unres:
                        chk("未移行", f"{lab}(usersに無く空欄)", False, ", ".join(unres), None)
    for pid, nrows in new_by_prog.items():
        if pid not in seen_prog:
            for n in nrows:
                stat["new_only"] += 1
                new_only_list.append({"K_id": None, "nc_program_id": pid, "work_record_id": n["id"],
                                      "作業日": str(n["work_date"]), "created_at": str(n["created_at"])})
    log(f"  NC 対応付け: {stat}")
    return stat, missing_list, new_only_list


# ───────────────────────── 出力 ─────────────────────────

def write_report(path_md, stats, tally_mc, tally_nc, extra):
    L = []
    L.append(f"# 作業記録 新旧全件検証 ({datetime.now():%Y-%m-%d %H:%M})\n")
    for sysname, st, ta in (("MC", stats.get("mc"), tally_mc), ("NC", stats.get("nc"), tally_nc)):
        if st is None:
            continue
        L.append(f"## {sysname}\n")
        L.append(f"- 旧の作業記録: {st['old']}件 / 対応付けできた: {st['paired']}件 / "
                 f"新に無し: {st['missing_in_new']}件 / 新のみ: {st['new_only']}件 / "
                 f"プログラム無し(孤立): {st['no_program']}件\n")
        L.append("| 区分 | 項目 | 比較件数 | 不一致 |\n|---|---|---:|---:|")
        for it in ta.items.values():
            L.append(f"| {it['group']} | {it['label']} | {it['checked']} | {it['ng']} |")
        L.append("")
        for it in ta.items.values():
            if not it["ng"]:
                continue
            L.append(f"### {sysname} {it['group']}：{it['label']}（{it['ng']}件）\n")
            L.append("| 識別 | 旧 | 新 |\n|---|---|---|")
            for e in it["examples"]:
                idt = " ".join(f"{k}={e[k]}" for k in e if k not in ("区分", "項目", "旧", "新", "系統"))
                L.append(f"| {idt} | {str(e['旧']).replace('|', '／').replace(chr(10), ' ⏎ ')[:120]} | "
                         f"{str(e['新']).replace('|', '／').replace(chr(10), ' ⏎ ')[:120]} |")
            L.append("")
    if extra.get("mc_meta"):
        L.append("## 参考: 旧 ACC_変更履歴 の列\n")
        L.append(", ".join(extra["mc_meta"]["columns"]))
        L.append(f"\n中断の列: {extra['mc_meta']['stop_columns']} → 対応(推定): {extra['mc_meta']['stop_map']}\n")
    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["mc", "nc", "all"], default="all")
    ap.add_argument("--examples", type=int, default=20, help="レポートに載せる不一致の例の件数(項目ごと)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(OUT_DIR, f"verify_work_records_{stamp}")

    ss = ss_connect(SS_MC_DB)
    pg = pg_connect()
    pg.set_session(readonly=True)
    tally_mc, tally_nc = Tally(args.examples), Tally(args.examples)
    stats, extra = {}, {}
    try:
        if args.target in ("mc", "all"):
            st, miss, newonly, meta = verify_mc(ss, pg, tally_mc)
            stats["mc"] = st
            extra.update(mc_missing=miss, mc_new_only=newonly, mc_meta=meta)
        if args.target in ("nc", "all"):
            st, miss, newonly = verify_nc(ss, pg, tally_nc)
            stats["nc"] = st
            extra.update(nc_missing=miss, nc_new_only=newonly)
    finally:
        ss.close()
        pg.close()

    write_report(base + ".md", stats, tally_mc, tally_nc, extra)
    rows = tally_mc.rows + tally_nc.rows
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys or ["項目"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"stats": stats,
                   "items": {"mc": list(tally_mc.items.values()), "nc": list(tally_nc.items.values())},
                   "extra": extra}, f, ensure_ascii=False, indent=1, default=str)

    # 画面に件数一覧
    print()
    for sysname, ta in (("MC", tally_mc), ("NC", tally_nc)):
        if sysname.lower() not in stats:
            continue
        st = stats[sysname.lower()]
        print(f"=== {sysname}: 旧 {st['old']} / 対応 {st['paired']} / 新に無し {st['missing_in_new']} / "
              f"新のみ {st['new_only']} / 孤立 {st['no_program']}")
        for it in ta.items.values():
            mark = "NG" if it["ng"] else "OK"
            print(f"  [{mark}] {it['group']:<14} {it['label']:<28} 比較 {it['checked']:>6}  不一致 {it['ng']:>6}")
    print(f"\nレポート: {base}.md\n全件CSV : {base}.csv\nJSON    : {base}.json")


if __name__ == "__main__":
    main()
