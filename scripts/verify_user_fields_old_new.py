#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_user_fields_old_new.py — 担当者(ユーザー)欄の新旧全件比較(再利用スクリプト・DBは読むだけ)

旧システム(SQL Server imotomc)の担当者名と、新システム(PostgreSQL)に入っている users を
全件で突き合わせる。コンバート(mc_full_import.py / nc_full_import_v2.py)と同じ照合規則
(name_match.py: 全角/半角・空白のゆれ、通称「チューン」、同姓同名「ティン」、複数名併記)で
「旧の名前なら新ではこの人になるはず」を計算し、新DBの値と比べる。
users に無い旧担当者名は空欄が正(管理者で代替しない: 2026-10-07 ユーザー指定)。

  ① 旧担当者名の照合一覧 … 旧の全担当者名 → users の誰に結び付くか(結び付かない名前・同姓同名)
  ② MC加工データ(mc_programs / mc_machining_details) 1件ずつ
       オペレーター = ACC_マシニングraw.ｵﾍﾟﾚｰﾀｰ      → mc_programs.registered_by
       承認者       = ACC_マシニングraw.氏名          → mc_programs.approved_by
       作成者       = ACC_マシニングraw.作成(無ければ変更履歴の最初の作成) → mc_machining_details.creator_id
       PG作成者     = ACC_マシニングraw.prg           → mc_machining_details.pg_created_by
  ③ NC加工データ(nc_programs) 1件ずつ
       登録者 = ACC_Lathe.Reco_P(ACC_Staff.St_id) → nc_programs.registered_by
       承認者 = ACC_History 最新「承認」行の In_Op → nc_programs.approved_by
  ④ 履歴の操作者(印刷履歴・変更履歴・作業記録) … 担当者ごとの件数を旧と新で比べる
       (旧の行IDを持たない表があるため件数で比べる。NC変更履歴は legacy_hist_id で1件ずつ)
  ⑤ 個別確認(--mcid、既定 8507 = フィードバックNo.41 の F47367A01)

判定
  OK          新の値 = 旧の名前から決まる人(または両方空欄)
  NG_管理者    旧の名前では誰にも決まらない(空欄が正)のに新が管理者 … 旧コンバートの管理者代替
  NG_別人      新が旧の名前と別の人
  NG_欠落      旧の名前で人が決まるのに新が空欄
  NG_余計      旧が空欄/users に無いのに新に人が入っている(管理者以外)
  新で変更     新システム(UAT)で編集・承認・PG登録された加工データ(比較の対象外)

実行(.11):  python3 scripts/verify_user_fields_old_new.py [--mcid 8507 ...]
試験用DB:   MACHCORE_PG_DSN=postgresql://.../machcore_convtest python3 scripts/verify_user_fields_old_new.py
出力:       scripts/verify_reports/user_fields_YYYYMMDD_HHMMSS.md / .json / _ng.csv
"""
import os, sys, csv, json, argparse
from datetime import datetime, timedelta
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from verify_old_new_db import pg_connect, ss_connect, SS_MC_DB, log  # 接続先は既存の検証と同じ
from name_match import PersonResolver, person_key, staff_id_map_from_rows
from legacy_snapshot import conversion_read_jst, after  # コンバート後に旧で入力された行は比較対象外

OUT_DIR = os.path.join(HERE, "verify_reports")
NC_CHANGE_KW = ("新規登録", "仮登録", "変更", "承認")
MC_CH_KINDS = (2, 4, 5, 6, 8, 9, 10, 11, 13, 14, 15, 16, 99)


def s(v):
    if v is None:
        return ""
    return str(v).strip()


def nk_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def judge(exp, act, admin_id):
    if exp == act:
        return "OK"
    if exp is None and act == admin_id:
        return "NG_管理者"
    if exp is None:
        return "NG_余計"
    if act is None:
        return "NG_欠落"
    return "NG_別人"


class Report:
    def __init__(self, uname, admin_id):
        self.uname = uname
        self.admin_id = admin_id
        self.fields = OrderedCounter()
        self.ng_rows = []
        self.examples = defaultdict(list)

    def name(self, uid):
        if uid is None:
            return "(空欄)"
        return self.uname.get(uid, f"id={uid}")

    def add(self, area, field, key, raw, exp, act, edited=False, ex_limit=15):
        st = "新で変更" if (edited and exp != act) else judge(exp, act, self.admin_id)
        self.fields.add((area, field), st)
        if st.startswith("NG"):
            row = {"区分": area, "項目": field, "キー": key, "旧の値": s(raw),
                   "期待(旧から)": self.name(exp), "新の値": self.name(act), "判定": st}
            self.ng_rows.append(row)
            if len(self.examples[(area, field, st)]) < ex_limit:
                self.examples[(area, field, st)].append(row)
        return st


class OrderedCounter:
    def __init__(self):
        self.d = {}

    def add(self, k, st):
        self.d.setdefault(k, Counter())[st] += 1

    def items(self):
        return self.d.items()


# ───────────────────────── ① 旧担当者名の照合一覧 ─────────────────────────

def name_inventory(mcc, mc_res, nc_res, staff_rows, staff_map, uinfo):
    cols = Counter()
    mcc.execute("SELECT ｵﾍﾟﾚｰﾀｰ, 氏名, 作成, prg FROM ACC_マシニングraw")
    for r in mcc.fetchall():
        for lab, v in zip(("MC オペレーター", "MC 承認者(氏名)", "MC 作成者(作成)", "MC PG作成者(prg)"), r):
            if s(v):
                cols[(s(v), lab)] += 1
    mcc.execute("SELECT 作成, ｵﾍﾟﾚｰﾀｰ, 承認, 段取, 作業者, ﾁｪｯｸMan FROM ACC_変更履歴")
    for r in mcc.fetchall():
        for lab, v in zip(("MC履歴 作成", "MC履歴 ｵﾍﾟﾚｰﾀｰ", "MC履歴 承認", "MC履歴 段取", "MC履歴 作業者", "MC履歴 ﾁｪｯｸMan"), r):
            if s(v):
                cols[(s(v), lab)] += 1
    mcc.execute("SELECT Dan_Op, La_Op FROM ACC_History")
    for r in mcc.fetchall():
        for lab, v in zip(("NC履歴 段取(Dan_Op)", "NC履歴 量産(La_Op)"), r):
            if s(v):
                cols[(s(v), lab)] += 1
    by_name = defaultdict(dict)
    for (nm, lab), n in cols.items():
        by_name[nm][lab] = n
    rows = []
    for nm, labs in by_name.items():
        res = nc_res if all(l.startswith("NC") for l in labs) else mc_res
        uid, how = res.explain(nm)
        multi = []
        if how.startswith("複数名"):
            multi, _ = res.resolve_multi(nm)
        u = uinfo.get(uid)
        rows.append({
            "旧の名前": nm, "件数": sum(labs.values()),
            "欄": ", ".join(f"{k}:{v}" for k, v in sorted(labs.items(), key=lambda x: -x[1])),
            "照合": how,
            "新の担当者": (f"{u[0]}({u[1]})" if u else "(空欄)"),
            "複数名の全員": ", ".join(f"{uinfo[i][0]}({uinfo[i][1]})" for i in multi if i in uinfo),
        })
    rows.sort(key=lambda r: (r["新の担当者"] != "(空欄)", -r["件数"]))
    staff = []
    for st_id, s_name in staff_rows:
        uid = staff_map.get(st_id)
        u = uinfo.get(uid)
        staff.append({"St_id": st_id, "旧の氏名": s(s_name), "新の担当者": f"{u[0]}({u[1]})" if u else "(空欄)"})
    return rows, staff


# ───────────────────────── ② MC加工データ ─────────────────────────

def verify_mc_programs(mcc, pgc, res, rep, cutoff, mcids_detail, detail, mc_cut=None):
    mcc.execute("""
        SELECT mc.MCID, mc.加工ID, m.ｵﾍﾟﾚｰﾀｰ, m.氏名, m.作成, m.prg, m.IN_DATE, m.入力日
        FROM ACC_MC mc INNER JOIN ACC_マシニングraw m ON mc.加工ID = m.加工ID
    """)
    old = {r[0]: r[:6] for r in mcc.fetchall()}
    mcc.execute("""
        SELECT mc.MCID, m.IN_DATE, m.入力日
        FROM ACC_MC mc INNER JOIN ACC_マシニングraw m ON mc.加工ID = m.加工ID
    """)
    old_after = {r[0] for r in mcc.fetchall() if after(r[1], mc_cut) or after(r[2], mc_cut)}
    # 作成者: 旧の作成が空・照合できない時は、変更履歴の最初の作成(照合できる行)で補う(PHASE6F と同じ)
    mcc.execute("""
        SELECT MCID, 加工ID, 作成, 作成日 FROM ACC_変更履歴
        WHERE 作成日 IS NOT NULL AND 作成 IS NOT NULL AND LEN(RTRIM(作成)) > 0
        ORDER BY MCID, 入力日 ASC
    """)
    hist_creator = {}
    for _mcid, kakoid, sakusha, _d in mcc.fetchall():
        if kakoid and kakoid not in hist_creator:
            uid = res.resolve_first(sakusha)
            if uid:
                hist_creator[kakoid] = uid
    pgc.execute("""
        SELECT p.id, p.legacy_mcid, p.machining_id, p.registered_by, p.approved_by,
               p.registered_at, p.approved_at, d.creator_id, d.pg_created_by, d.pg_updated_at
        FROM mc_programs p JOIN mc_machining_details d ON d.machining_id = p.machining_id
        WHERE p.legacy_mcid IS NOT NULL
    """)
    new = pgc.fetchall()
    pgc.execute("""SELECT DISTINCT mc_program_id FROM operation_logs
                   WHERE mc_program_id IS NOT NULL AND action_type::text IN ('MC_EDIT_SAVE','EDIT_SAVE','MC_APPROVE','APPROVE','FILE_UPLOAD')""")
    edited_ops = {r[0] for r in pgc.fetchall()}
    missing = 0
    for (pid, mcid, mach, reg, appr, reg_at, appr_at, creator, pgc_by, pg_upd) in new:
        o = old.get(mcid)
        if not o:
            missing += 1
            continue
        _, kakoid, op, shimei, sakusei, prg = o
        edited = (pid in edited_ops or (reg_at and reg_at > cutoff) or (appr_at and appr_at > cutoff)
                  or mcid in old_after)  # 新システムで編集 / コンバート後に旧で入力し直し
        key = f"MCID={mcid}"
        st = {}
        st["オペレーター"] = rep.add("MC加工", "オペレーター", key, op, res.resolve_first(op), reg, edited)
        st["承認者"] = rep.add("MC加工", "承認者", key, shimei, res.resolve_first(shimei), appr, edited)
        exp_cr = res.resolve_first(sakusei) or hist_creator.get(kakoid)
        st["作成者"] = rep.add("MC加工", "作成者(段取シート)", key, sakusei, exp_cr, creator, edited)
        pg_edited = bool(pg_upd and pg_upd > cutoff) or edited
        st["PG作成者"] = rep.add("MC加工", "PG作成者", key, prg, res.resolve_first(prg), pgc_by, pg_edited)
        if mcid in mcids_detail:
            detail.append({"MCID": mcid, "加工ID": kakoid, "mc_programs.id": pid,
                           "旧 ｵﾍﾟﾚｰﾀｰ": s(op), "新 オペレーター": rep.name(reg), "判定 オペレーター": st["オペレーター"],
                           "旧 氏名(承認者)": s(shimei), "新 承認者": rep.name(appr), "判定 承認者": st["承認者"],
                           "旧 作成": s(sakusei), "新 作成者": rep.name(creator), "判定 作成者": st["作成者"],
                           "旧 prg": s(prg), "照合(prg)": res.explain(prg)[1],
                           "新 PG作成者": rep.name(pgc_by), "判定 PG作成者": st["PG作成者"],
                           "新 PG更新日時(UTC)": str(pg_upd) if pg_upd else ""})
    return {"旧の加工データ": len(old), "新の加工データ(旧から)": len(new), "旧に無い": missing}


# ───────────────────────── ③ NC加工データ ─────────────────────────

def staff_uid(staff_map, raw):
    if raw is None:
        return None
    uid = staff_map.get(raw)
    if uid is None:
        try:
            uid = staff_map.get(int(str(raw).strip()))
        except (TypeError, ValueError):
            uid = None
    return uid


def verify_nc_programs(mcc, pgc, staff_map, rep, cutoff, nc_cut=None):
    mcc.execute("SELECT K_id, Reco_P FROM ACC_Lathe")
    reco = {int(r[0]): r[1] for r in mcc.fetchall() if r[0] is not None}
    mcc.execute("""SELECT K_id, In_Cont, In_Date, In_Op FROM ACC_History
                   WHERE In_Cont IS NOT NULL ORDER BY K_id, In_Date DESC""")
    latest_appr = {}
    for kid, ic, idt, iop in mcc.fetchall():
        if kid is None or idt is None or "承認" not in s(ic) or after(idt, nc_cut):
            continue
        latest_appr.setdefault(int(kid), iop)
    pgc.execute("""SELECT id, legacy_nc_id, machining_id, registered_by, approved_by, status::text,
                          registered_at, approved_at
                   FROM nc_programs WHERE legacy_nc_id IS NOT NULL""")
    rows = pgc.fetchall()
    pgc.execute("""SELECT DISTINCT nc_program_id FROM operation_logs
                   WHERE nc_program_id IS NOT NULL AND action_type::text IN ('EDIT_SAVE','APPROVE','FILE_UPLOAD')""")
    edited_ops = {r[0] for r in pgc.fetchall()}
    for pid, ncid, kid, reg, appr, status, reg_at, appr_at in rows:
        edited = pid in edited_ops or (reg_at and reg_at > cutoff) or (appr_at and appr_at > cutoff)
        rp = reco.get(kid)
        rep.add("NC加工", "登録者", f"NC_id={ncid}", rp, staff_uid(staff_map, rp), reg, edited)
        ap = latest_appr.get(kid) if status == "APPROVED" else None
        rep.add("NC加工", "承認者", f"NC_id={ncid}", ap, staff_uid(staff_map, ap), appr, edited)
    return {"新の加工データ(旧から)": len(rows)}


# ───────────────────────── ④ 履歴の操作者 ─────────────────────────

def compare_counts(area, field, exp, act, rep, out):
    """担当者ごとの件数(旧から期待する件数 ⇔ 新の件数)"""
    keys = set(exp) | set(act)
    diffs = []
    for k in keys:
        e, a = exp.get(k, 0), act.get(k, 0)
        if e != a:
            diffs.append((rep.name(k), e, a))
    diffs.sort(key=lambda x: -abs(x[1] - x[2]))
    adm = act.get(rep.admin_id, 0) - exp.get(rep.admin_id, 0)
    out.append({"区分": area, "項目": field, "旧から期待する件数": sum(exp.values()), "新の件数": sum(act.values()),
                "空欄(期待)": exp.get(None, 0), "空欄(新)": act.get(None, 0),
                "管理者(期待)": exp.get(rep.admin_id, 0), "管理者(新)": act.get(rep.admin_id, 0),
                "件数が違う担当者": len(diffs), "差の合計": sum(abs(e - a) for _, e, a in diffs),
                "差の例": "; ".join(f"{n} 旧{e}→新{a}" for n, e, a in diffs[:12])})
    st = "OK" if not diffs else ("NG_管理者" if adm > 0 else "NG_件数")
    rep.fields.add((area, field + "(担当者別件数)"), st)


def verify_history_mc(mcc, pgc, res, rep, mc_cut, out):
    """MC: mc_full_import.py PHASE6 と同じ規則で、担当者ごとの件数を作る。
    mc_cut(JST)より後に旧で入力された行はコンバート時点に無かったので数えない。
    新の側も、それより後に新システムで入力された行(UAT)は数えない"""
    cutoff_utc = (mc_cut - timedelta(hours=9)) if mc_cut else datetime.now()
    skipped = 0
    pgc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    mcid_map = defaultdict(list)
    for pid, lm in pgc.fetchall():
        mcid_map[lm].append(pid)
    mcc.execute("""SELECT MCID, 内容区分ID, ｵﾍﾟﾚｰﾀｰ, 作成, 承認, 総時間, 入力日, 承認日 FROM ACC_変更履歴""")
    e_sl, e_ch, e_wr = Counter(), Counter(), Counter()
    # 旧の入力日が空の行は取込時に「取込日時」が入るため、基準日時までの比較から外す
    for mcid, nk, op, sakusei, shonin, total, in_dt, appr_dt in mcc.fetchall():
        n = len(mcid_map.get(mcid, []))
        if not n:
            continue
        if after(in_dt, mc_cut):
            skipped += 1
            continue
        nk = nk_int(nk)
        op_id = res.resolve_first(op)
        cr_id = res.resolve_first(sakusei)
        if nk in (1, 3, 7) and in_dt is not None:
            e_sl[op_id] += n
        if nk in MC_CH_KINDS and ((appr_dt or in_dt) if nk == 4 else in_dt) is not None:
            if nk == 4:
                ch = (res.resolve_first(shonin) if s(shonin) else None) or cr_id
            else:
                ch = op_id or cr_id
            e_ch[ch] += n
        if (nk == 17 or s(total)) and in_dt is not None:
            e_wr[op_id] += n
    pgc.execute("SELECT operator_id, COUNT(*) FROM mc_setup_sheet_logs WHERE mc_program_id IS NOT NULL AND printed_at <= %s GROUP BY 1", (cutoff_utc,))
    compare_counts("MC履歴", "印刷履歴の操作者", e_sl, Counter(dict(pgc.fetchall())), rep, out)
    pgc.execute("SELECT operator_id, COUNT(*) FROM mc_change_history WHERE changed_at <= %s GROUP BY 1", (cutoff_utc,))
    compare_counts("MC履歴", "変更履歴の操作者", e_ch, Counter(dict(pgc.fetchall())), rep, out)
    pgc.execute("SELECT operator_id, COUNT(*) FROM work_records WHERE mc_program_id IS NOT NULL AND work_date <= %s GROUP BY 1", (cutoff_utc.date(),))
    compare_counts("MC履歴", "作業記録の操作者(ｵﾍﾟﾚｰﾀｰ)", e_wr, Counter(dict(pgc.fetchall())), rep, out)
    log(f"  MC: コンバート後({mc_cut})に旧で入力された履歴 {skipped}行は比較対象外")
    for h in out[-3:]:
        h["コンバート後に旧で入力(対象外)"] = skipped


def verify_history_nc(mcc, pgc, res, staff_map, rep, nc_cut, out):
    """NC: nc_full_import_v2.py PHASE3 と同じ規則。
    nc_cut(JST)より後の印刷(Out_Date)・戻り入力(In_Date)はコンバート時点に無かったので、その時点の状態で数える"""
    cutoff_utc = (nc_cut - timedelta(hours=9)) if nc_cut else datetime.now()
    skipped_out = skipped_in = 0
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    kid_map = defaultdict(list)
    for pid, kid in pgc.fetchall():
        kid_map[kid].append(pid)
    mcc.execute("""SELECT Hist_id, K_id, Out_Cont, Out_Op, Out_Date, In_Cont, In_Op, In_Date,
                          Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P FROM ACC_History""")
    e_sl, e_wr = Counter(), Counter()
    ch_exp = {}
    for (hid, kid, oc, oop, odt, ic, iop, idt, dop, dh, dm, lop, lh, lm, p) in mcc.fetchall():
        n = len(kid_map.get(int(kid), [])) if kid is not None else 0
        if not n:
            continue
        ocs, ics = s(oc), s(ic)
        if after(odt, nc_cut):
            skipped_out += 1
            continue
        in_after = after(idt, nc_cut)
        if in_after:
            # 戻り(作業記録・変更)の入力がコンバートより後: コンバート時点では未回収・作業記録なし
            skipped_in += 1
            ics, dop, dh, dm, lh, lm, p, idt = "", None, 0, 0, 0, 0, 0, None
        if ("印刷" in ocs or ocs == "仮登録") and odt is not None:
            e_sl[staff_uid(staff_map, oop)] += n
        has_work = bool(s(dop)) or nk_int(dh) > 0 or nk_int(dm) > 0 or nk_int(lh) > 0 or nk_int(lm) > 0 or nk_int(p) > 0
        if has_work:
            su, _ = res.resolve_multi(s(dop))
            pu, _ = res.resolve_multi(s(lop))
            e_wr[(su[0] if su else None) or (pu[0] if pu else None) or staff_uid(staff_map, iop)] += n
        if any(k in ics for k in NC_CHANGE_KW) and idt is not None:
            ch_exp[int(hid)] = (staff_uid(staff_map, iop), iop)
    pgc.execute("SELECT operator_id, COUNT(*) FROM setup_sheet_logs WHERE printed_at <= %s GROUP BY 1", (cutoff_utc,))
    compare_counts("NC履歴", "印刷履歴の操作者", e_sl, Counter(dict(pgc.fetchall())), rep, out)
    pgc.execute("SELECT operator_id, COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL AND work_date <= %s GROUP BY 1", (cutoff_utc.date(),))
    compare_counts("NC履歴", "作業記録の操作者", e_wr, Counter(dict(pgc.fetchall())), rep, out)
    log(f"  NC: コンバート後({nc_cut})に旧で印刷 {skipped_out}行 / 戻り入力 {skipped_in}行 は比較対象外(コンバート時点の状態で比較)")
    for h in out[-2:]:
        h["コンバート後に旧で入力(対象外)"] = skipped_out + skipped_in
    # NC変更履歴は legacy_hist_id で1件ずつ
    pgc.execute("SELECT legacy_hist_id, operator_id FROM change_history WHERE legacy_hist_id IS NOT NULL")
    for hid, opid in pgc.fetchall():
        if hid in ch_exp:
            exp, raw = ch_exp[hid]
            rep.add("NC履歴", "変更履歴の操作者(In_Op)", f"Hist_id={hid}", raw, exp, opid)


# ───────────────────────── 出力 ─────────────────────────

def write_md(path, meta, rep, inventory, staff, hist_counts, detail):
    L = [f"# 担当者欄 新旧全件比較 ({meta['実行']})", ""]
    L.append(f"- 新DB: {meta['新DB']} / 旧DB: SQL Server {SS_MC_DB}")
    L.append(f"- 管理者(ADMIN001) = users.id {meta['管理者id']} / 基準日時(これより後の入力・編集は新システム分として比較対象外): {meta['基準日時']}")
    L.append(f"- コンバートが旧を読んだ時刻(JST。これより後に旧システムで入力・回収された行は新に無いのが正しいため比較対象外): "
             f"{meta['コンバートが旧を読んだ時刻(JST)']}")
    L.append(f"- 照合規則: name_match.py(全角/半角・空白のゆれ、通称 チューン=MC140、ティン=STAFF030、複数名は先頭)。users に無い名前は空欄が正")
    L.append(f"- **NG 合計: {meta['NG合計']}件**  (内訳は下表)")
    L.append("")
    L.append("## 判定の集計")
    L.append("")
    L.append("| 区分 | 項目 | OK | NG_管理者 | NG_別人 | NG_欠落 | NG_余計 | NG_件数 | 新で変更 |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for (area, field), c in rep.fields.items():
        L.append(f"| {area} | {field} | {c.get('OK',0)} | {c.get('NG_管理者',0)} | {c.get('NG_別人',0)} | "
                 f"{c.get('NG_欠落',0)} | {c.get('NG_余計',0)} | {c.get('NG_件数',0)} | {c.get('新で変更',0)} |")
    L.append("")
    if detail:
        L.append("## 個別確認")
        L.append("")
        for d in detail:
            L.append(f"### MCID {d['MCID']}")
            for k, v in d.items():
                L.append(f"- {k}: {v}")
            L.append("")
    L.append("## 履歴の操作者(担当者別件数)")
    L.append("")
    L.append("| 区分 | 項目 | 期待件数 | 新の件数 | 空欄 期待/新 | 管理者 期待/新 | 件数が違う担当者 | 差の合計 | コンバート後に旧で入力(対象外) | 差の例 |")
    L.append("|---|---|---:|---:|---|---|---:|---:|---:|---|")
    for h in hist_counts:
        L.append(f"| {h['区分']} | {h['項目']} | {h['旧から期待する件数']} | {h['新の件数']} | {h['空欄(期待)']}/{h['空欄(新)']} | "
                 f"{h['管理者(期待)']}/{h['管理者(新)']} | {h['件数が違う担当者']} | {h['差の合計']} | "
                 f"{h.get('コンバート後に旧で入力(対象外)', 0)} | {h['差の例']} |")
    L.append("")
    L.append("## NG の例(項目・判定ごとに最大15件。全件は _ng.csv)")
    L.append("")
    for (area, field, st), rows in rep.examples.items():
        L.append(f"### {area} {field} {st}")
        L.append("")
        L.append("| キー | 旧の値 | 期待(旧から) | 新の値 |")
        L.append("|---|---|---|---|")
        for r in rows:
            L.append(f"| {r['キー']} | {r['旧の値']} | {r['期待(旧から)']} | {r['新の値']} |")
        L.append("")
    L.append("## 旧担当者名の照合一覧(新の担当者が空欄になる名前を先頭に)")
    L.append("")
    L.append("| 旧の名前 | 件数 | 照合 | 新の担当者 | 複数名の全員 | 欄 |")
    L.append("|---|---:|---|---|---|---|")
    for r in inventory:
        L.append(f"| {r['旧の名前']} | {r['件数']} | {r['照合']} | {r['新の担当者']} | {r['複数名の全員']} | {r['欄']} |")
    L.append("")
    L.append("## NC 旧担当者マスタ(ACC_Staff) → users")
    L.append("")
    L.append("| St_id | 旧の氏名 | 新の担当者 |")
    L.append("|---:|---|---|")
    for r in staff:
        L.append(f"| {r['St_id']} | {r['旧の氏名']} | {r['新の担当者']} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcid", type=int, nargs="*", default=[8507], help="個別に詳しく出すMCID(既定 8507 = No.41)")
    ap.add_argument("--out", default=None, help="出力のjsonパス(既定 scripts/verify_reports/user_fields_日時.json)")
    a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = a.out or os.path.join(OUT_DIR, f"user_fields_{ts}.json")
    base = out_json[:-5] if out_json.endswith(".json") else out_json

    log("DB接続中...")
    ss = ss_connect(SS_MC_DB)
    mcc = ss.cursor()
    pg = pg_connect()
    pgc = pg.cursor()
    pgc.execute("SELECT current_database()")
    dbname = pgc.fetchone()[0]

    pgc.execute("SELECT id, name, employee_code, system_type::text, is_active FROM users ORDER BY id")
    users = pgc.fetchall()
    uname = {u[0]: u[1] for u in users}
    uinfo = {u[0]: (u[1], u[2]) for u in users}
    pgc.execute("SELECT id FROM users WHERE employee_code='ADMIN001'")
    r = pgc.fetchone()
    admin_id = r[0] if r else None
    mc_res = PersonResolver(users, system="MC")
    nc_res = PersonResolver(users, system="NC")
    mcc.execute("SELECT St_id, S_name FROM ACC_Staff")
    staff_rows = mcc.fetchall()
    staff_map, _ = staff_id_map_from_rows(pgc, staff_rows, system="NC")

    # 基準日時: コンバートで作った行の作成時刻(mc_programs.created_at の最小)。
    # これより後の registered_at / approved_at / pg_updated_at は新システムでの入力・編集
    pgc.execute("SELECT MIN(created_at) FROM mc_programs WHERE legacy_mcid IS NOT NULL")
    cutoff = pgc.fetchone()[0] or datetime.now()
    # 旧の履歴は「コンバートが旧を読んだ時刻(JST)」までを旧データとして比べる(legacy_snapshot.py)
    #   旧システムは UAT 中も並行稼働しているため、それより後に旧で入力された行は新に無いのが正しい
    mc_cut = conversion_read_jst(pgc, "MC")
    nc_cut = conversion_read_jst(pgc, "NC")
    log(f"コンバートが旧を読んだ時刻(JST): MC={mc_cut} / NC={nc_cut}")

    rep = Report(uname, admin_id)
    log("① 旧担当者名の照合一覧...")
    inventory, staff = name_inventory(mcc, mc_res, nc_res, staff_rows, staff_map, uinfo)
    log("② MC加工データ...")
    detail = []
    mc_stat = verify_mc_programs(mcc, pgc, mc_res, rep, cutoff, set(a.mcid or []), detail, mc_cut)
    log("③ NC加工データ...")
    nc_stat = verify_nc_programs(mcc, pgc, staff_map, rep, cutoff, nc_cut)
    log("④ 履歴の操作者...")
    hist_counts = []
    verify_history_mc(mcc, pgc, mc_res, rep, mc_cut, hist_counts)
    verify_history_nc(mcc, pgc, nc_res, staff_map, rep, nc_cut, hist_counts)

    ng_total = sum(v for (_, _), c in rep.fields.items() for k, v in c.items() if k.startswith("NG"))
    meta = {"実行": datetime.now().strftime("%Y-%m-%d %H:%M"), "新DB": dbname, "管理者id": admin_id,
            "基準日時": str(cutoff), "コンバートが旧を読んだ時刻(JST)": {"MC": str(mc_cut), "NC": str(nc_cut)},
            "NG合計": ng_total,
            "MC": mc_stat, "NC": nc_stat,
            "照合できない旧担当者名": sum(1 for r in inventory if r["新の担当者"] == "(空欄)"),
            "同姓同名で決まらない": {"MC": mc_res.ambiguous, "NC": nc_res.ambiguous}}
    summary = [{"区分": a_, "項目": f_, **dict(c)} for (a_, f_), c in rep.fields.items()]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "summary": summary, "history_counts": hist_counts, "detail": detail,
                   "inventory": inventory, "staff": staff, "ng": rep.ng_rows}, f, ensure_ascii=False, indent=1, default=str)
    with open(base + "_ng.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["区分", "項目", "キー", "旧の値", "期待(旧から)", "新の値", "判定"])
        w.writeheader()
        w.writerows(rep.ng_rows)
    write_md(base + ".md", meta, rep, inventory, staff, hist_counts, detail)

    log("──── 判定の集計 ────")
    for (area, field), c in rep.fields.items():
        log(f"  {area} {field}: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    for d in detail:
        log(f"  [個別] MCID={d['MCID']} 旧prg='{d['旧 prg']}'({d['照合(prg)']}) → 新PG作成者={d['新 PG作成者']} [{d['判定 PG作成者']}]"
            f" / 旧ｵﾍﾟﾚｰﾀｰ='{d['旧 ｵﾍﾟﾚｰﾀｰ']}' → {d['新 オペレーター']} [{d['判定 オペレーター']}]")
    log(f"照合できない旧担当者名: {meta['照合できない旧担当者名']}件(新では空欄が正)")
    log(f"NG 合計: {ng_total}件")
    log(f"結果: {base}.md / {out_json} / {base}_ng.csv")
    pg.close()
    ss.close()


if __name__ == "__main__":
    main()
