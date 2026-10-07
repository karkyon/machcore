#!/usr/bin/env python3
# coding: utf-8
"""
MachCore NC完全移行スクリプト (nc_full_import.py) — v2 (新スキーマ対応版)
========================================================================
v038で導入された新スキーマ(NcMachiningDetail + NcProgram)に対応する。

【v1からの変更点】
  旧ACC_NC(NC_id, B_id, K_id)は、MC側ACC_MC(MCID, 部品ID, 加工ID)と同じ構造の
  「部品ID×加工データの対応表」であり、同一K_id(加工データ)が複数のB_id(部品ID)
  から共有される「共通部品」パターンが旧データに実在する(診断v035/v036/v037で確認済み)。
  v1は(part_id, process_l)にunique制約をかけ、これを後勝ち上書きで1レコードに
  集約していたため、共通部品の一方の情報が失われる欠陥があった。

  v2では mc_full_import.py PHASE1/PHASE6 と完全に同じ設計方針を採用する:
    - NcMachiningDetail: PKに旧K_idをそのまま使用(ON CONFLICT(k_id) DO UPDATE)。
      加工データ本体は1K_idにつき1レコードのみ。
    - NcProgram: ACC_NCの行ごとに無条件INSERT(unique制約なし)。
      同一K_idに複数のB_id行があれば、複数のNcProgramレコードが作られ、
      全てが同じNcMachiningDetail(machining_id)を参照する。
    - nc_tools: ncProgramId参照 → machiningId(=K_id)参照に変更。
      K_id自体が新PKなので、旧kid_mapとnew_idの対応が単純化される。
    - change_history/setup_sheet_logs/work_records: 旧ACC_HistoryはK_id単位の
      レコードなので、mc_full_import.py PHASE6と同じく「1件の旧履歴行を、
      そのK_idに対応する全NcProgram行に複製してINSERTする」方式を採用する。

実行方法:
  python3 nc_full_import.py [--phase N] [--dry-run]

フェーズ:
  0 = 全フェーズ一括実行（本番用）
  1 = nc_machining_details + nc_programs 基本データ移行（ACC_NC × ACC_Lathe）
  2 = nc_tools移行（ACC_Tool、machining_id参照）
  3 = ACC_History → 3テーブル分離移行（setup_sheet_logs/work_records/change_history、
      K_id→全対応NcProgramへ複製）
  4 = nc_programs.status 正規化（K_id単位の判定をその全対応NcProgramへ展開）
  5 = NCプログラムファイル移行（folder_name配下→K_idフォルダへ。図・写真は対象外）
  6 = NC 加工リスト マスタ(加/工/形状/ホルダーの候補)投入（空のテーブルのみ）

ソースDB: imotomc (192.168.1.9) ※NC側ビューもMC側と同じimotomc DB内に存在
  - ACC_NC      : NC_id, B_id, K_id
  - ACC_Lathe   : K_id, L, Clamp, Machine, Tm, Ts, FD_name, F_name, oNo, Note,
                  Fig, Photo, Ver, Reco_P, Reco_D
  - ACC_Tool    : T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note
  - ACC_FD      : FD_id, FD_name
  - ACC_Machine : m_id, Model
  - ACC_Staff   : St_id, S_name, Password
  - ACC_History : Hist_id, K_id, NC_id, Mc, Out_Ver, Out_Cont, Out_Op, Out_Date,
                  In_Ver, In_Cont, In_Op, In_Date, Dan_Op, Dan_H, Dan_M,
                  La_Op, La_H, La_M, P

部品/得意先: parts テーブルは MC側で既に sync_parts.py により同期済みの
            既存資産を再利用する（imotodb 経由の新規移行は行わない）。

machines テーブルも既存資産を再利用する。ACC_Machine の Model(機械コード文字列)を
machines.machine_code に対して直引きする(MC方式と同じ)。
ACC_FD は nc_programs.folder_name の補完にのみ使う(FD_name→FD_idの逆引き)。

ユーザー: ACC_Staff の St_id → employee_code "STAFF{St_id:03d}" で users.id に解決する
         (migrate_v2.ts と同じ命名規則。既存usersデータが既にこの規則で作成済みのため
          新規ユーザー作成は行わない)。
"""

import sys, os, re, argparse, traceback, subprocess, json as _json
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from machine_name_match import MachineResolver  # ACC_Machine.Model(全角/半角・大小文字・ハイフンのゆれ) → machines.id
from name_match import PersonResolver  # 旧担当者名(全角/半角・空白のゆれ、複数名併記) → users.id

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _load_pg_dsn():
    import re as _re
    # 接続先の明示指定(コンバート試験 run_conversion_test.py が試験用DBを指定する)
    _ov = os.environ.get("MACHCORE_PG_DSN")
    if _ov:
        return _ov.split("?", 1)[0]
    _env = Path(__file__).resolve().parent.parent / "apps" / "api" / ".env"
    with open(_env, encoding="utf-8") as _f:
        for _line in _f:
            _m = _re.match(r'^DATABASE_URL="?([^"\n]*)"?$', _line.strip())
            if _m:
                _url = _m.group(1)
                # psycopg2はPrisma固有のクエリパラメータ(?schema=public等)を
                # 解釈できずinvalid dsnエラーになるため、クエリ部分を除去する。
                _url = _url.split("?", 1)[0]
                return _url
    raise RuntimeError(f"DATABASE_URL not found in {_env}")
PG_DSN = _load_pg_dsn()
SS_SERVER    = "192.168.1.9"
SS_USER      = "sa"
SS_PASS      = "RTW65b"
SS_DB        = "imotomc"   # NC側ビューもMC側と同じDB内に存在(diag_v017/v018bで確認済み)
LOG_FILE     = (Path(os.environ["MACHCORE_IMPORT_LOG_DIR"]) / "nc_full_import.log") if os.environ.get("MACHCORE_IMPORT_LOG_DIR") else Path(__file__).resolve().parent.parent / "logs" / "nc_full_import.log"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーティリティ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_log_fh = open(LOG_FILE, "a", encoding="utf-8")


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    _log_fh.write(line + "\n")
    _log_fh.flush()


def section(title):
    bar = "=" * 60
    log(f"\n{bar}\n  {title}\n{bar}")


def pg_connect():
    import psycopg2
    return psycopg2.connect(PG_DSN)

def _resolve_upload_base_nc():
    """company_settings.upload_base_path を見て、NCファイル格納先を実行時に上書きする。
    未設定の場合は従来のSMB(/mnt/mc_files)にフォールバックする。"""
    global DST_NC_ROOT, DST_NC_PRG
    try:
        _conn = pg_connect()
        _cur = _conn.cursor()
        _cur.execute("SELECT upload_base_path FROM company_settings LIMIT 1")
        _row = _cur.fetchone()
        _conn.close()
        _base = _row[0] if _row and _row[0] else None
    except Exception as _e:
        log(f"upload_base_path取得失敗、既定値({DST_NC_ROOT})を使用します: {_e}", "WARN")
        _base = None
    if _base:
        DST_NC_ROOT = Path(_base) / "NC" / "files"
        DST_NC_PRG  = DST_NC_ROOT / "Programs"
        log(f"NCファイル格納先: company_settings.upload_base_path = {DST_NC_ROOT}")
    else:
        log(f"company_settings.upload_base_path 未設定。既定値 {DST_NC_ROOT} を使用します", "WARN")


def ss_connect():
    import pymssql
    from legacy_mssql import wrap
    # 旧DB読み出しは必ず共通層経由(非日本語照合の非Unicode列をCP932で確定デコード)
    return wrap(pymssql.connect(server=SS_SERVER, user=SS_USER,
                                password=SS_PASS, database=SS_DB, tds_version='7.4'))


def legacy_nc_ver_to_version(ver):
    """旧NCの整数Ver(ACC_Lathe.Ver / ACC_History.Out_Ver,In_Ver)をMCと同じ X.YYZZ 形式に変換する。
    旧システム: 仮登録=1、新規登録/変更ごとに+100(101, 201, ...)。
    百の位以上 → 整数部X、下2桁 → リビジョンZZ(1 → 0.0001、101 → 1.0001、201 → 2.0001)。
    apps/api/src/common/version.util.ts の legacyNcVerToVersion() と同じ規則。"""
    if ver is None:
        return None
    try:
        v = max(0, int(ver))
    except (TypeError, ValueError):
        return None
    return f"{v // 100}.00{v % 100:02d}"


def to_jst_utc(dt):
    """SQL Serverから来るJSTのnaive datetimeをUTCに変換（-9h）。mc_full_import.pyと同じ規則。"""
    if dt is None:
        return None
    try:
        return dt - timedelta(hours=9)
    except Exception:
        return dt


ADMIN_FALLBACK_ID = 22  # メモリ記載のADMIN_ID(MC側と共通、既定値。実行時に_resolve_admin_id_nc()で上書き)


def build_staff_id_map(pgc, ssc):
    """旧 ACC_Staff.St_id → users.id。
    ① 社員コード STAFF{St_id:03d}(旧システムから移した利用者の規則)
    ② ①が無い(社員コードを振り直した等)ときは氏名で照合(name_match.py、同姓同名は通称の表/系統NCで決める)
    返り値: (staff_id_map, 未対応の (St_id, 氏名) 一覧)"""
    pgc.execute("SELECT id, employee_code FROM users")
    code_to_userid = {r[1]: r[0] for r in pgc.fetchall()}
    person = PersonResolver.from_db(pgc, system="NC")
    ssc.execute("SELECT St_id, S_name FROM ACC_Staff")
    staff_id_map, unmatched = {}, []
    for st_id, s_name in ssc.fetchall():
        try:
            code = f"STAFF{int(st_id):03d}"
        except (TypeError, ValueError):
            continue
        uid = code_to_userid.get(code) or person.resolve(s_name)
        if uid is not None:
            staff_id_map[st_id] = uid
            staff_id_map[int(st_id)] = uid   # 参照側(Out_Op/In_Op等)の型の違いに備えて整数でも引けるように
        else:
            unmatched.append((st_id, s_name))
    return staff_id_map, unmatched

def _resolve_admin_id_nc():
    """users.employee_code='ADMIN001' のidを実行時に取得し、NC側の2つのADMIN定数に反映する。"""
    global ADMIN_FALLBACK_ID, NC_FILE_ADMIN_FALLBACK_ID
    try:
        _conn = pg_connect()
        _cur = _conn.cursor()
        _cur.execute("SELECT id FROM users WHERE employee_code='ADMIN001' LIMIT 1")
        _row = _cur.fetchone()
        _conn.close()
        if _row:
            ADMIN_FALLBACK_ID = _row[0]
            NC_FILE_ADMIN_FALLBACK_ID = _row[0]
            log(f"ADMIN_FALLBACK_ID(ADMIN001)を動的解決: {ADMIN_FALLBACK_ID}")
        else:
            log(f"users.employee_code='ADMIN001' が見つかりません。既定値{ADMIN_FALLBACK_ID}のまま続行します", "WARN")
    except Exception as _e:
        log(f"ADMIN_ID動的解決に失敗、既定値{ADMIN_FALLBACK_ID}のまま続行します: {_e}", "WARN")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: nc_machining_details + nc_programs 基本データ移行
#   (ACC_NC × ACC_Lathe)
#   mc_full_import.py PHASE1と同じ2段階方式:
#     ① K_id単位でnc_machining_details(加工データ本体)を1件だけUPSERT
#     ② ACC_NCの行ごとに(B_id単位で)nc_programsを無条件INSERT
#        → 同一K_idが複数のB_idから参照されれば、複数のnc_programs行が作られ、
#          全てが同じnc_machining_details.k_idを指す(共通部品の正しい表現)。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase1(pg, dry_run=False):
    section("PHASE 1: nc_machining_details + nc_programs 基本データ移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    if not dry_run:
        log("既存NC関連データ全破棄...")
        pgc.execute("DELETE FROM nc_files")
        pgc.execute("DELETE FROM change_history")
        pgc.execute("DELETE FROM setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM operation_logs WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM work_sessions WHERE nc_program_id IS NOT NULL")
        pgc.execute("DELETE FROM nc_tools")  # onDelete:Cascadeだが明示削除して件数を見える化
        pgc.execute("DELETE FROM nc_programs")
        pgc.execute("DELETE FROM nc_machining_details")
        pg.commit()
        log("全破棄完了")
        log("⚠️  nc_files / change_history / setup_sheet_logs / work_records / "
            "operation_logs / work_sessions / nc_tools も連動して全削除されました"
            "（nc_programs.idがSERIALで再採番されるため、既存の紐付けが無効になる想定動作です）。", "WARN")
        log("⚠️  --phase 0（全フェーズ一括）以外で個別フェーズ実行している場合、"
            "この後に必ず python3 nc_full_import_v2.py --phase 3 と --phase 5 を"
            "再実行してください。実行し忘れると、物理ファイルは残っていてもDB上は"
            "未登録のままになります（MC側で2026-09-15に実際に発生した事象と同種）。", "WARN")

    # parts は既存資産を再利用(MC側 sync_parts.py で同期済み)
    pgc.execute("SELECT id, part_id FROM parts")
    parts_map = {r[1]: r[0] for r in pgc.fetchall()}
    log(f"parts既存件数: {len(parts_map)}件（新規移行は行わない）")

    # machines は既存資産を再利用。ACC_Machine.Model(文字列) → machines.machine_code
    # (全角/半角・大小文字・ハイフンの表記ゆれを正規化して照合: machine_name_match.py)
    ssc.execute("SELECT m_id, Model FROM ACC_Machine")
    acc_machine_rows = ssc.fetchall()
    _mres = MachineResolver.from_db(pgc, system_types=None)
    machine_id_map = {}
    machine_unmatched = 0
    for m_id, model in acc_machine_rows:
        _mid = _mres.resolve(model)
        if _mid is not None:
            machine_id_map[m_id] = _mid
        else:
            machine_unmatched += 1
    log(f"ACC_Machine取得: {len(acc_machine_rows)}件, machines対応: {len(machine_id_map)}件, 未対応: {machine_unmatched}件")
    if _mres.unresolved:
        log(f"  [WARN] machinesマスタに無い旧機械(Model): {_mres.unresolved_summary()}", "WARN")

    # ACC_FD: 参考情報のみ(folder_name解決には未使用、v1から継続)
    ssc.execute("SELECT FD_id, FD_name FROM ACC_FD")
    fd_map = {r[0]: (r[1] or "").strip() for r in ssc.fetchall()}
    log(f"ACC_FD取得: {len(fd_map)}件 (参考情報として取得のみ。folder_name解決には未使用)")

    # ACC_Staff: St_id → users.id (社員コード STAFF{:03d}、無ければ氏名で照合: build_staff_id_map)
    staff_id_map, _staff_unmatched = build_staff_id_map(pgc, ssc)
    staff_unmatched = len(_staff_unmatched)
    log(f"ACC_Staff: users対応 {len({int(k) for k in staff_id_map})}件, 未対応: {staff_unmatched}件")
    if staff_unmatched > 0:
        log(f"  [WARN] 未対応St_id(管理者で代替): " + ", ".join(f"{a}:{b}" for a, b in _staff_unmatched), "WARN")

    # ── ① ACC_Lathe単位(K_id単位)でnc_machining_detailsを構築 ──
    ssc.execute("""
        SELECT l.K_id, l.L, l.Clamp, l.Machine, l.Tm, l.Ts, l.FD_name, l.F_name,
               l.oNo, l.Note, l.Fig, l.Photo, l.Ver
        FROM ACC_Lathe l
        ORDER BY l.K_id
    """)
    lathe_rows = ssc.fetchall()
    log(f"旧DB ACC_Lathe取得: {len(lathe_rows)}件 (K_id単位、加工データ本体)")

    detail_ok = detail_skip = detail_err = 0
    kid_set = set()  # 正常に登録できたK_idの集合(PHASE1②での参照整合性チェック用)

    for row in lathe_rows:
        try:
            (kid, l_no, clamp, machine_raw, tm, ts, fd_name_raw, f_name,
             ono, note, fig, photo, ver) = row

            machine_db_id = machine_id_map.get(machine_raw) if machine_raw is not None else None

            # FD_name: ACC_Lathe.FD_name列の値をそのままfolder_nameとして使用する。
            # (ACC_FD経由の逆引きは未確証のため今回は採用しない。v1から継続)
            folder_name = str(fd_name_raw or "").strip() or "(未設定)"

            clamp_str = str(clamp or "").strip() or None
            note_str = str(note or "").strip() or None
            # [v101] 掴代は専用カラム(clamp_allowance)に保持する。
            # clamp_noteには旧システムのNote列のみを入れ、「クランプ: xxx」という
            # 重複表現は行わない(掴代欄が独立して表示されるようになったため)。
            clamp_allowance = clamp_str
            clamp_note = note_str

            machining_time = int(tm) if tm is not None else None
            setup_time_ref = int(ts) if ts is not None else None
            process_l = int(l_no) if l_no is not None else 1
            # [MC統一] 旧Ver(101等)は X.YYZZ に変換して保持する(旧値そのものは legacy_ver に残す)
            ver_str = legacy_nc_ver_to_version(ver) or "1.0001"

            if dry_run:
                kid_set.add(int(kid))
                detail_ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_machining_details (
                    k_id, process_l, machine_id, machining_time, setup_time_ref,
                    folder_name, file_name, o_number, version, clamp_note, clamp_allowance,
                    drawing_count, photo_count, legacy_ver, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (k_id) DO UPDATE SET
                    process_l=EXCLUDED.process_l, machine_id=EXCLUDED.machine_id,
                    machining_time=EXCLUDED.machining_time, setup_time_ref=EXCLUDED.setup_time_ref,
                    folder_name=EXCLUDED.folder_name, file_name=EXCLUDED.file_name,
                    o_number=EXCLUDED.o_number, version=EXCLUDED.version,
                    clamp_note=EXCLUDED.clamp_note, clamp_allowance=EXCLUDED.clamp_allowance,
                    drawing_count=EXCLUDED.drawing_count,
                    photo_count=EXCLUDED.photo_count, legacy_ver=EXCLUDED.legacy_ver,
                    updated_at=NOW()
            """, (int(kid), process_l, machine_db_id, machining_time, setup_time_ref,
                  folder_name, str(f_name) if f_name is not None else "",
                  str(ono) if ono is not None else None, ver_str, clamp_note, clamp_allowance,
                  int(fig or 0), int(photo or 0), str(ver) if ver is not None else None))
            kid_set.add(int(kid))
            detail_ok += 1
            if detail_ok % 2000 == 0:
                pg.commit()
                log(f"  nc_machining_details {detail_ok}件挿入中...")
        except Exception as e:
            detail_err += 1
            if not dry_run:
                pg.rollback()
            if detail_err <= 5:
                log(f"  ERR(detail): K_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_machining_details")
        log(f"nc_machining_details完了: ok={detail_ok} err={detail_err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"nc_machining_details完了(dry-run): ok={detail_ok} err={detail_err}")

    # ── ② ACC_NC単位(B_id×K_id単位)でnc_programsを無条件INSERT ──
    # 1つのK_idに複数のNC_id(=B_id行)が存在する場合、その全件がnc_programsとして
    # 個別にINSERTされる(unique制約なし、MC側mc_programs方式と同じ)。
    #
    # 登録者(Reco_P)・登録日(Reco_D)はACC_Lathe側のカラム(=加工データ本体側の情報)。
    # mc_full_import.py PHASE1でも同様に、登録者情報はACC_マシニングraw(加工データ本体)
    # 側から取得しており、共通部品(複数mc_programs)では同じ値が複製される設計になっている。
    # NC側もこれに合わせ、ACC_Lathe.Reco_P/Reco_Dを全NC_id行に対して共通で適用する。
    ssc.execute("""
        SELECT K_id, Reco_P, Reco_D
        FROM ACC_Lathe
    """)
    lathe_reco = {int(r[0]): (r[1], r[2]) for r in ssc.fetchall() if r[0] is not None}
    log(f"ACC_Lathe Reco_P/Reco_D取得: {len(lathe_reco)}件(K_id単位)")

    ssc.execute("""
        SELECT NC_id, B_id, K_id
        FROM ACC_NC
        ORDER BY NC_id
    """)
    nc_rows = ssc.fetchall()
    log(f"旧DB ACC_NC取得: {len(nc_rows)}件 (部品×加工の対応行)")

    ok = skip = err = 0
    nc_id_map = {}   # 旧NC_id(int) → nc_programs.id
    kid_to_dbid = {}  # 旧K_id(int) → nc_machining_details.k_id (=そのままK_id)

    for row in nc_rows:
        try:
            (ncid, bid, kid) = row
            kid_i = int(kid)

            if kid_i not in kid_set:
                # ACC_Lathe側に対応するK_idが存在しない(孤立NC_id行)
                skip += 1
                continue

            part_db_id = parts_map.get(str(bid))
            if not part_db_id:
                skip += 1
                continue

            rp, rd_ = lathe_reco.get(kid_i, (None, None))

            registered_by = staff_id_map.get(rp, ADMIN_FALLBACK_ID)
            registered_at = to_jst_utc(rd_) if rd_ else datetime(2005, 1, 1)

            if dry_run:
                virtual_id = -int(ncid)
                nc_id_map[ncid] = virtual_id
                kid_to_dbid[kid_i] = kid_i
                ok += 1
                continue

            pgc.execute("""
                INSERT INTO nc_programs (
                    part_id, machining_id, registered_by, registered_at,
                    legacy_nc_id, status, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,'APPROVED'::nc_program_status,NOW(),NOW())
                RETURNING id
            """, (part_db_id, kid_i, registered_by, registered_at, int(ncid)))
            new_id = pgc.fetchone()[0]
            nc_id_map[ncid] = new_id
            kid_to_dbid[kid_i] = kid_i
            ok += 1
            if ok % 2000 == 0:
                pg.commit()
                log(f"  nc_programs {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run:
                pg.rollback()
            if err <= 5:
                log(f"  ERR(program): NC_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_programs")
        log(f"PHASE1(nc_programs)完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE1(nc_programs)完了(dry-run): ok={ok} skip={skip} err={err}")

    ss.close()
    return nc_id_map, kid_to_dbid, staff_id_map, machine_id_map


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: nc_tools 移行 (ACC_Tool)
#   machining_id(=K_id)参照に変更。K_id自体が新PKのため、
#   旧kid_mapのような変換マッピングは不要(K_idがそのままmachining_idとして使える)。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase2(pg, dry_run=False, kid_to_dbid=None):
    section("PHASE 2: nc_tools 移行")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    if not kid_to_dbid:
        # phase1を経ずに--phase 2単独実行された場合に備え、DBから再構築する。
        pgc.execute("SELECT k_id FROM nc_machining_details")
        kid_to_dbid = {r[0]: r[0] for r in pgc.fetchall()}
        log(f"kid_to_dbid再構築: {len(kid_to_dbid)}件")

    if not dry_run:
        pgc.execute("DELETE FROM nc_tools")
        pg.commit()
        log("nc_tools既存データ削除完了")

    # [仕様] 加工リストの並びは旧システムと同じ T_id の昇順。No(TNo)は t_number にそのまま保持し、
    # 段取シート/NC情報画面のNo欄に表示する(従来の K_id, No, T_id 順は旧システムの表示順と異なっていた)。
    ssc.execute("""
        SELECT T_id, K_id, No, Shave1, Shave2, Chip, Holder, NorzR, Note
        FROM ACC_Tool
        ORDER BY K_id, T_id
    """)
    rows = ssc.fetchall()
    log(f"ACC_Tool取得: {len(rows)}件 (K_id, T_id 昇順)")

    ok = skip = err = 0
    reseq_prev_kid = None
    reseq_counter = 0

    for row in rows:
        try:
            t_id, k_id, no, shave1, shave2, chip, holder, nose_r, note = row
            kid_i = int(k_id) if k_id is not None else None
            if kid_i is None or kid_i not in kid_to_dbid:
                skip += 1
                continue
            machining_id = kid_to_dbid[kid_i]

            if k_id != reseq_prev_kid:
                reseq_prev_kid = k_id
                reseq_counter = 0
            reseq_counter += 1
            sort_order = reseq_counter * 10

            process_type = " / ".join([s for s in (
                str(shave1).strip() if shave1 else None,
                str(shave2).strip() if shave2 else None,
            ) if s]) or None

            if dry_run:
                ok += 1
                continue

            # [v101] NorzRはSQL Server側でreal(浮動小数点)型のため、str()でそのまま
            # 文字列化すると "0.800000011920929" のような誤差込みの桁数になる。
            # [修正] 従来は小数第1位に丸めていたため 0.25→0.2、0.05→0.1、0.87→0.9 と値が変わっていた。
            # real型の誤差(0.23999999463558197 等)だけを取り除き、旧システムの値をそのまま継承する。
            nose_r_str = None
            if nose_r is not None:
                try:
                    nose_r_str = f"{round(float(nose_r), 4):g}"
                except (TypeError, ValueError):
                    nose_r_str = str(nose_r).strip() or None

            pgc.execute("""
                INSERT INTO nc_tools (
                    machining_id, sort_order, process_type, chip_model,
                    holder_model, nose_r, t_number, note, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            """, (machining_id, sort_order, process_type,
                  str(chip).strip() if chip else None,
                  str(holder).strip() if holder else None,
                  nose_r_str,
                  str(no).strip() if no is not None else None,
                  str(note).strip() if note else None))
            ok += 1
            if ok % 5000 == 0:
                pg.commit()
                log(f"  {ok}件挿入中...")
        except Exception as e:
            err += 1
            if not dry_run:
                pg.rollback()
            if err <= 5:
                log(f"  ERR: T_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_tools")
        log(f"PHASE2完了: ok={ok} skip={skip} err={err} DB総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE2完了(dry-run): ok={ok} skip={skip} err={err}")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3: ACC_History → 3テーブル分離移行
#   旧ACC_Historyの1レコードはK_id単位。K_idに複数のnc_programs(共通部品)が
#   対応する場合、mc_full_import.py PHASE6と同じく、その全てに履歴を複製してINSERTする。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def guess_change_type(in_cont):
    if not in_cont:
        return "CHANGE"
    s = str(in_cont)
    if "新規" in s or "仮登録" in s:
        return "NEW_REGISTRATION"
    if "承認" in s:
        return "APPROVAL"
    if "移行" in s or "migration" in s.lower():
        return "MIGRATION"
    return "CHANGE"


def phase3(pg, dry_run=False, nc_id_map=None, staff_id_map=None, machine_id_map=None):
    section("PHASE 3: ACC_History 完全分離移行(K_id→全対応NcProgramへ複製)")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    # K_id → [nc_programs.id, ...] (共通部品で複数あり得る)。DBから再構築する。
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    kid_to_program_ids = {}
    for prog_id, machining_id in pgc.fetchall():
        kid_to_program_ids.setdefault(machining_id, []).append(prog_id)
    log(f"kid_to_program_ids構築: {len(kid_to_program_ids)}件のK_idに対応するNcProgram群")

    if staff_id_map is None:
        staff_id_map, _ = build_staff_id_map(pgc, ssc)

    # 氏名文字列(Dan_Op/La_Op) → users.id
    # 全角/半角・空白の表記ゆれを正規化、姓だけの記載は同姓が1人なら救済、
    # 「井本　昌成 アイン」「ソン＋フォン」のような複数名併記は分割して全員を照合(name_match.py)
    _person = PersonResolver.from_db(pgc, system="NC")
    _resolve_op = _person.resolve
    _resolve_ops = _person.resolve_multi

    unresolved_op_names = {}

    if machine_id_map is None:
        ssc.execute("SELECT m_id, Model FROM ACC_Machine")
        acc_rows = ssc.fetchall()
        _mres = MachineResolver.from_db(pgc, system_types=None)
        machine_id_map = {}
        for m_id, model in acc_rows:
            _mid = _mres.resolve(model)
            if _mid is not None:
                machine_id_map[m_id] = _mid

    if not dry_run:
        pgc.execute("DELETE FROM change_history")
        pgc.execute("DELETE FROM setup_sheet_logs")
        pgc.execute("DELETE FROM work_records WHERE nc_program_id IS NOT NULL")
        pg.commit()
        log("change_history / setup_sheet_logs / work_records(NC分) 削除完了")

    ssc.execute("""
        SELECT Hist_id, K_id, NC_id, Mc,
               Out_Ver, Out_Cont, Out_Op, Out_Date,
               In_Ver, In_Cont, In_Op, In_Date,
               Dan_Op, Dan_H, Dan_M, La_Op, La_H, La_M, P
        FROM ACC_History
        ORDER BY K_id, In_Date
    """)
    rows = ssc.fetchall()
    log(f"ACC_History取得: {len(rows)}件")

    sl_ok = sl_skip = sl_err = 0
    wr_ok = wr_skip = wr_err = 0
    wr_linked = 0
    ch_ok = ch_skip = ch_err = 0
    # 共通部品で複製INSERTされた件数をカウント(参考値)
    sl_dup = wr_dup = ch_dup = 0

    for row in rows:
        try:
            (hist_id, k_id, nc_id_old, mc_raw,
             out_ver, out_cont, out_op, out_date,
             in_ver, in_cont, in_op, in_date,
             dan_op, dan_h, dan_m, la_op, la_h, la_m, p) = row

            kid_i = int(k_id) if k_id is not None else None
            program_ids = kid_to_program_ids.get(kid_i, []) if kid_i is not None else []
            if not program_ids:
                sl_skip += 1
                wr_skip += 1
                ch_skip += 1
                continue

            out_cont_s = str(out_cont or "").strip()
            in_cont_s = str(in_cont or "").strip()
            out_date_utc = to_jst_utc(out_date)
            in_date_utc = to_jst_utc(in_date)

            # 旧ACC_Historyは1行=1枚の段取シート。この行で作った印刷履歴に、同じ行の作業記録を結び付ける
            row_sl_ids = {}
            # ── A: setup_sheet_logs（Out_Cont = "印刷"）→ 対応する全NcProgramに複製 ──
            # 旧システムの段取シート = Out_Cont が「印刷…」または「仮登録」(新規段取シート r_New_NC_Lathe)。
            # 未回収 = 旧「段取シート戻り」画面の判定(Out_Cont Like '印刷*' or ='仮登録') かつ IsNull(In_Cont)。
            is_new_sheet = (out_cont_s == "仮登録")
            if ("印刷" in out_cont_s or is_new_sheet) and out_date_utc:
                sheet_collected = not (in_cont is None and (out_cont_s.startswith("印刷") or is_new_sheet))
                sheet_type = "NEW" if is_new_sheet else "REPEAT"
                op_id = staff_id_map.get(out_op, ADMIN_FALLBACK_ID)
                out_ver_str = legacy_nc_ver_to_version(out_ver)
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO setup_sheet_logs (
                                    nc_program_id, operator_id, printed_at, version,
                                    pdf_path, session_id, work_collected, sheet_type
                                ) VALUES (%s,%s,%s,%s,NULL,NULL,%s,%s)
                                RETURNING id
                            """, (prog_id, op_id, out_date_utc, out_ver_str, sheet_collected, sheet_type))
                            row_sl_ids[prog_id] = pgc.fetchone()[0]
                        sl_ok += 1
                        if idx > 0:
                            sl_dup += 1
                    except Exception:
                        sl_err += 1
                        if not dry_run:
                            pg.rollback()

            # ── B: work_records（Dan_*/La_*/P に実データあり）→ 対応する全NcProgramに複製 ──
            dan_h_i = int(dan_h) if dan_h is not None else 0
            dan_m_i = int(dan_m) if dan_m is not None else 0
            la_h_i = int(la_h) if la_h is not None else 0
            la_m_i = int(la_m) if la_m is not None else 0
            p_i = int(p) if p is not None else 0
            dan_op_s = str(dan_op or "").strip()
            la_op_s = str(la_op or "").strip()
            has_work_data = bool(dan_op_s) or dan_h_i > 0 or dan_m_i > 0 or la_h_i > 0 or la_m_i > 0 or p_i > 0

            if has_work_data:
                setup_min = (dan_h_i * 60 + dan_m_i) or None
                mach_min = (la_h_i * 60 + la_m_i) or None
                dan_norm = re.sub(r"[\s\u3000]+", " ", dan_op_s).strip()
                la_norm = re.sub(r"[\s\u3000]+", " ", la_op_s).strip()
                # [バグ修正] 従来operator_id(単一)にしか反映しておらず、新スキーマの
                # setup_operator_ids/production_operator_ids(複数可の配列)に一切
                # 投入していなかったため、NC側の作業記録画面で段取担当者・量産担当者が
                # 常に空欄になっていた。旧システムは段取(Dan)/加工(La)それぞれ単一の
                # 担当者名しか持たないため、解決できた場合は要素数1の配列として投入する。
                setup_ids, setup_unres = _resolve_ops(dan_op_s)
                prod_ids, prod_unres = _resolve_ops(la_op_s)
                for _nm in setup_unres + prod_unres:
                    unresolved_op_names[_nm] = unresolved_op_names.get(_nm, 0) + 1
                work_op_id = ((setup_ids[0] if setup_ids else None) or (prod_ids[0] if prod_ids else None)
                              or staff_id_map.get(in_op, ADMIN_FALLBACK_ID))
                setup_operator_ids_json = _json.dumps(setup_ids)
                production_operator_ids_json = _json.dumps(prod_ids)
                work_machine_id = machine_id_map.get(mc_raw) if mc_raw is not None else None
                # 作業日(DATE列) = 旧 In_Date(無ければOut_Date) の JST 日付
                _wd_raw = in_date or out_date
                work_date = _wd_raw.date() if hasattr(_wd_raw, "year") else datetime(2005, 1, 1).date()
                # 備考: 旧システムの戻り内容(In_Cont)のみを継承する。
                # [仕様変更] 段取/量産の担当者は setup_operator_ids / production_operator_ids に入れて
                # 担当者欄に表示するため、備考への「段取: ○○, 加工: ○○」の併記は行わない。
                note_str = in_cont_s or None
                if note_str:
                    note_str = note_str[:1000]
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO work_records (
                                    nc_program_id, operator_id, machine_id, work_date,
                                    setup_time_min, machining_time_min, quantity, note,
                                    setup_operator_ids, production_operator_ids, nc_setup_sheet_log_id, created_at
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                            """, (prog_id, work_op_id, work_machine_id, work_date,
                                  setup_min, mach_min, p_i if p_i > 0 else None, note_str,
                                  setup_operator_ids_json, production_operator_ids_json,
                                  row_sl_ids.get(prog_id)))
                        wr_ok += 1
                        if row_sl_ids.get(prog_id): wr_linked += 1
                        if idx > 0:
                            wr_dup += 1
                    except Exception:
                        wr_err += 1
                        if not dry_run:
                            pg.rollback()

            # ── C: change_history（In_Cont が新規登録/仮登録/変更/承認）→ 対応する全NcProgramに複製 ──
            is_nc_change = any(kw in in_cont_s for kw in ("新規登録", "仮登録", "変更", "承認"))
            if is_nc_change and in_date_utc:
                op_id = staff_id_map.get(in_op, ADMIN_FALLBACK_ID)
                ver_before = legacy_nc_ver_to_version(out_ver)
                ver_after = legacy_nc_ver_to_version(in_ver)
                field_changes = None
                if out_cont_s and "印刷" not in out_cont_s:
                    # [バグ修正] ここにあったローカル`import json as _json`が、
                    # 関数冒頭でモジュールレベルimportした_jsonをPythonの
                    # スコープ規則上シャドーイングしてしまい、このローカルimportより
                    # 前にある work_records 処理で_json参照時にUnboundLocalErrorに
                    # なっていた(2026-09-16 --phase 3実行で全件エラー確認)。
                    # モジュール冒頭で既にimport済みのためここでは何もしない。
                    field_changes = _json.dumps({"out_content": out_cont_s})
                for idx, prog_id in enumerate(program_ids):
                    try:
                        if not dry_run:
                            pgc.execute("""
                                INSERT INTO change_history (
                                    nc_program_id, change_type, operator_id,
                                    version_before, version_after, content,
                                    field_changes, changed_at, legacy_hist_id
                                ) VALUES (%s,%s::change_type,%s,%s,%s,%s,%s,%s,%s)
                            """, (prog_id, guess_change_type(in_cont_s), op_id,
                                  ver_before, ver_after, in_cont_s or None,
                                  field_changes, in_date_utc, int(hist_id)))
                        ch_ok += 1
                        if idx > 0:
                            ch_dup += 1
                    except Exception:
                        ch_err += 1
                        if not dry_run:
                            pg.rollback()

            if not dry_run and (sl_ok + wr_ok + ch_ok) % 5000 == 0:
                pg.commit()
        except Exception as e:
            log(f"  ERR: Hist_id={row[0] if row else '?'} {e}", "WARN")

    if not dry_run:
        pg.commit()

    log(f"PHASE3完了: setup_sheet_logs ok={sl_ok}(共通部品複製分={sl_dup}) skip={sl_skip} err={sl_err}")
    log(f"  作業記録のうち段取シートに結び付けた件数: {wr_linked}/{wr_ok}")
    log(f"            work_records     ok={wr_ok}(共通部品複製分={wr_dup}) skip={wr_skip} err={wr_err}")
    if unresolved_op_names:
        log(f"  [WARN] 段取/量産担当者名がusersに無く担当者欄に入らなかった名前: "
            + ", ".join(f"{k}({v}件)" for k, v in sorted(unresolved_op_names.items(), key=lambda x: -x[1])), "WARN")
    else:
        log("  段取/量産担当者名は全件usersで解決")
    log(f"            change_history   ok={ch_ok}(共通部品複製分={ch_dup}) skip={ch_skip} err={ch_err}")
    log(f"  【内訳】ACC_History {len(rows)}件 → 最大 {sl_ok + wr_ok + ch_ok} レコードに展開")
    log("  ※ legacy_hist_idは複製元の旧Hist_idをそのまま保持するため、共通部品では")
    log("    同一legacy_hist_idを持つchange_history行が複数件(NcProgram数分)存在しうる。")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: nc_programs.status 正規化
#   K_id単位で判定したstatusを、そのK_idに対応する全NcProgram行に同一適用する。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase4(pg, dry_run=False):
    section("PHASE 4: nc_programs.status 正規化")
    ss = ss_connect()
    ssc = ss.cursor()
    pgc = pg.cursor()

    PRINT_CONTENTS = {"印刷"}
    TENTATIVE_CONTENTS = {"仮登録", "仮試作"}
    APPROVAL_CONTENTS = {"承認"}

    ssc.execute("""
        SELECT K_id, In_Cont, Out_Cont, In_Date, In_Op
        FROM ACC_History
        WHERE In_Cont IS NOT NULL OR Out_Cont IS NOT NULL
        ORDER BY K_id, In_Date DESC
    """)
    rows = ssc.fetchall()
    log(f"ACC_History取得: {len(rows)}件")

    kid_latest_in = {}
    kid_has_print = set()
    kid_has_approval = set()
    kid_latest_approval = {}  # K_id → (In_Op, In_Date) 最新の「承認」行

    for k_id, in_cont, out_cont, in_date, in_op in rows:
        if k_id is None:
            continue
        ic = str(in_cont or "").strip()
        oc = str(out_cont or "").strip()
        if k_id not in kid_latest_in:
            kid_latest_in[k_id] = ic
        if any(kw in oc for kw in PRINT_CONTENTS):
            kid_has_print.add(k_id)
        if any(kw in ic for kw in APPROVAL_CONTENTS):
            kid_has_approval.add(k_id)
            if k_id not in kid_latest_approval and in_date is not None:
                kid_latest_approval[k_id] = (in_op, in_date)

    log(f"PRINT系有りK_id: {len(kid_has_print)}件")
    log(f"承認有りK_id: {len(kid_has_approval)}件")

    # K_id(=machining_id)単位で、その全NcProgram行(id一覧)を取得
    pgc.execute("SELECT id, machining_id FROM nc_programs")
    program_rows = pgc.fetchall()

    # 承認者(旧In_Op = ACC_Staff.St_id → users.id。PHASE1/3と同じ build_staff_id_map)
    _staff_map4, _ = build_staff_id_map(pgc, ssc)
    def _approver_uid(st_id):
        try:
            return _staff_map4.get(st_id) or _staff_map4.get(int(st_id))
        except (TypeError, ValueError):
            return None
    stat_approver = 0
    log(f"nc_programs取得: {len(program_rows)}件")

    stat_new = stat_approved = stat_pending = 0

    if not dry_run:
        for nc_db_id, kid in program_rows:
            latest_in = kid_latest_in.get(kid, "")
            has_print = kid in kid_has_print
            has_approval = kid in kid_has_approval

            is_tentative = any(kw in latest_in for kw in TENTATIVE_CONTENTS)

            if has_print:
                if is_tentative:
                    new_status = "NEW"
                    stat_new += 1
                else:
                    new_status = "APPROVED"
                    stat_approved += 1
            else:
                if has_approval:
                    new_status = "APPROVED"
                    stat_approved += 1
                else:
                    new_status = "PENDING_APPROVAL"
                    stat_pending += 1

            # 承認者・承認日: 承認済みで旧「承認」行があるものは、その最新行の In_Op / In_Date(JST→UTC)
            appr = kid_latest_approval.get(kid) if new_status == "APPROVED" else None
            appr_by = _approver_uid(appr[0]) if appr else None
            appr_at = to_jst_utc(appr[1]) if appr else None
            if appr_by: stat_approver += 1
            pgc.execute(
                "UPDATE nc_programs SET status = %s::nc_program_status, approved_by = %s, approved_at = %s WHERE id = %s",
                (new_status, appr_by, appr_at, nc_db_id)
            )
        pg.commit()
        log(f"status更新: NEW={stat_new} APPROVED={stat_approved} PENDING_APPROVAL={stat_pending}")
        log(f"承認者・承認日を設定: {stat_approver}件")

        pgc.execute("SELECT status, COUNT(*) FROM nc_programs GROUP BY status ORDER BY status")
        for row in pgc.fetchall():
            log(f"  DB確認 status={row[0]}: {row[1]}件")
    else:
        log("(dry-run のため status 更新はスキップ)")

    ss.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 最終レポート
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def final_report(pg):
    section("最終レポート")
    pgc = pg.cursor()
    for label, sql in [
        ("nc_machining_details", "SELECT COUNT(*) FROM nc_machining_details"),
        ("nc_programs", "SELECT COUNT(*) FROM nc_programs"),
        ("nc_tools", "SELECT COUNT(*) FROM nc_tools"),
        ("change_history(NC)", "SELECT COUNT(*) FROM change_history"),
        ("setup_sheet_logs", "SELECT COUNT(*) FROM setup_sheet_logs"),
        ("work_records(NC)", "SELECT COUNT(*) FROM work_records WHERE nc_program_id IS NOT NULL"),
        ("nc_files(PROGRAM)", "SELECT COUNT(*) FROM nc_files WHERE file_type='PROGRAM'"),
    ]:
        pgc.execute(sql)
        log(f"  {label}: {pgc.fetchone()[0]}件")

    # 共通部品(1つのK_idに複数nc_programsが対応)の件数を参考表示
    pgc.execute("""
        SELECT COUNT(*) FROM (
            SELECT machining_id FROM nc_programs GROUP BY machining_id HAVING COUNT(*) > 1
        ) t
    """)
    log(f"  共通部品(1つのK_idを複数部品で共有)のK_id数: {pgc.fetchone()[0]}件")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ----------------------------------------------------------------
# PHASE 5: NCプログラムファイル移行
#   mc_full_import.py PHASE7(7C: プログラム)と同じ考え方。
#   旧サーバ上のプログラム保存場所は nc_machining_details.folder_name
#   (=ACC_Lathe.FD_name)で、E:\imotodb\D1\NC\プログラム\ 配下のフォルダ名
#   (A, B, C...)と完全一致することを現地確認済み(2026-06-30, KARKYONさん確認)。
#   NC側はfolder1+folder2のような2階層構成ではなくfolder_name1本の単一階層
#   構成のため、MC側PHASE7Cより単純な1階層直下コピーで表現できる。
#   写真・図(MC側7A/7B相当)は旧サーバ上で実質1枚ずつしか存在せず運用実態が
#   ないため、本フェーズの対象外とする(現地確認結果を踏まえた判断)。
# ----------------------------------------------------------------
SRC_NC_ROOT = Path("/mnt/mcfiles/NC")
SRC_NC_PRG  = SRC_NC_ROOT / "ﾌﾟﾛｸﾞﾗﾑ"  # NC側プログラムフォルダ(半角ｶﾅ、MC側SRC_PRGと同じ表記)
DST_NC_ROOT = Path("/mnt/mc_files/NC/files")
DST_NC_PRG  = DST_NC_ROOT / "Programs"
NC_FILE_ADMIN_FALLBACK_ID = 22  # ADMIN001 users.id (MC側ADMIN_IDと共通)


def _nc_safe_rmtree_and_mkdir(dst_dir, label):
    """CIFS上でrmtree後mkdir失敗する問題をリトライで対処(mc_full_import.pyと同方式、rm -rf使用)。"""
    import time as _time
    if dst_dir.exists():
        log(f"  {label}: コピー先クリア ({dst_dir})")
        _res = subprocess.run(["rm", "-rf", str(dst_dir)], capture_output=True, text=True)
        if _res.returncode != 0:
            log(f"  [WARN] rm -rf failed: {_res.stderr}", "WARN")
    for _attempt in range(10):
        try:
            os.makedirs(str(dst_dir), exist_ok=True)
            return
        except OSError:
            _time.sleep(1)
    os.makedirs(str(dst_dir), exist_ok=True)


def phase5(pg, dry_run=False):
    section("PHASE 5: NCプログラムファイル移行 (folder_name配下 -> K_idフォルダへ)")
    import shutil as _shutil
    import mimetypes

    pgc = pg.cursor()

    if not SRC_NC_PRG.exists():
        log(f"[WARN] SRC_NC_PRG が存在しない: {SRC_NC_PRG} - PHASE5をスキップします", "WARN")
        return

    if not dry_run:
        log("nc_files(PROGRAM分)既存データ削除...")
        pgc.execute("DELETE FROM nc_files WHERE file_type = 'PROGRAM'")
        pg.commit()
        _nc_safe_rmtree_and_mkdir(DST_NC_PRG, "プログラム(NC)")
    else:
        os.makedirs(str(DST_NC_PRG), exist_ok=True)

    # K_id -> [(nc_programs.id, registered_by, registered_at), ...]
    # (共通部品で複数あり得る。phase3と同じ構築方法)
    pgc.execute("SELECT id, machining_id, registered_by, registered_at FROM nc_programs")
    kid_to_programs = {}
    for prog_id, machining_id, registered_by, registered_at in pgc.fetchall():
        kid_to_programs.setdefault(machining_id, []).append((prog_id, registered_by, registered_at))
    log(f"kid_to_programs構築: {len(kid_to_programs)}件のK_idに対応するNcProgram群")

    pgc.execute("""
        SELECT k_id, folder_name, file_name
        FROM nc_machining_details
        WHERE file_name IS NOT NULL AND file_name != ''
          AND folder_name IS NOT NULL AND folder_name != '' AND folder_name != '(未設定)'
        ORDER BY k_id
    """)
    details = pgc.fetchall()
    log(f"  対象K_id: {len(details)}件")

    ok = nomatch = notfound = err = 0

    def _insert_nc_program_file(nc_program_id, orig_name, stored_name, mime, fpath, fsize,
                                 uploaded_by_id, uploaded_at_val):
        if dry_run:
            return
        pgc.execute("""
            INSERT INTO nc_files
              (nc_program_id, file_type, original_name, stored_name, mime_type,
               file_path, thumbnail_path, file_size, uploaded_by, uploaded_at)
            VALUES (%s,'PROGRAM',%s,%s,%s,%s,NULL,%s,%s,%s)
        """, (nc_program_id, orig_name, stored_name, mime, str(fpath), fsize,
              uploaded_by_id, uploaded_at_val))

    for i, (kid, folder_name, file_name) in enumerate(details):
        # ★v053修正: フォルダ全件ではなく file_name で指定された1ファイルのみコピー。
        #   folder_name(A,B,C...)は複数K_idが共有する親フォルダ。
        #   各K_idが使うファイルはnc_machining_details.file_nameで一意に特定できる。
        src_file = SRC_NC_PRG / str(folder_name).strip() / str(file_name).strip()
        if not src_file.exists():
            notfound += 1
            if notfound <= 10:
                log(f"  [WARN] notfound: K_id={kid} folder={folder_name} file={file_name}", "WARN")
            continue
        if kid not in kid_to_programs:
            nomatch += 1
            continue

        dst_dir = DST_NC_PRG / str(kid)
        try:
            if not dry_run:
                os.makedirs(str(dst_dir), exist_ok=True)
            dst = dst_dir / src_file.name
            if not dry_run:
                _shutil.copy2(src_file, dst)
            fsize = src_file.stat().st_size
            mime = mimetypes.guess_type(src_file.name)[0] or "application/octet-stream"
            for prog_id, registered_by, registered_at in kid_to_programs[kid]:
                _insert_nc_program_file(
                    prog_id, src_file.name, src_file.name, mime, dst, fsize,
                    registered_by or NC_FILE_ADMIN_FALLBACK_ID,
                    registered_at,
                )
            ok += 1
        except Exception as e:
            err += 1
            if err <= 10:
                log(f"  ERR K_id={kid} folder={folder_name} file={file_name}: {e}", "WARN")

        if (i + 1) % 500 == 0:
            if not dry_run:
                pg.commit()
            log(f"    {i+1}/{len(details)} ok={ok} nomatch={nomatch} notfound={notfound} err={err}")

    if not dry_run:
        pg.commit()
        pgc.execute("SELECT COUNT(*) FROM nc_files WHERE file_type='PROGRAM'")
        log(f"PHASE5完了: ok(K_id)={ok} nomatch={nomatch} notfound={notfound} err={err} "
            f"nc_files(PROGRAM)総数={pgc.fetchone()[0]}")
    else:
        log(f"PHASE5完了(dry-run): ok(K_id)={ok} nomatch={nomatch} notfound={notfound} err={err}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 6: NC 加工リスト マスタ(加/工/形状/ホルダーの候補)投入 — 空のテーブルにだけ投入
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def phase6(pg, dry_run=False):
    section("PHASE 6: NC 加工リスト マスタ(加/工/形状/ホルダーの候補)投入")
    import seed_nc_tool_master
    ss = ss_connect()
    try:
        seed_nc_tool_master.seed(pg, ss, log=log, dry_run=dry_run)
    finally:
        ss.close()


def _final_consistency_check_nc(pg):
    """nc_programsに対してnc_filesが異常に少ない/0件でないかを検知する。
    MC側と同じ構造の「個別フェーズ再実行でPHASE5(ファイル移行)の再実行が漏れる」
    事故を二度と見逃さないための読み取り専用チェック。書き込みは一切行わない。"""
    from legacy_mssql import report_lines
    for _ln in report_lines():
        log(f"[旧DB文字コード] {_ln}")
    pgc = pg.cursor()
    pgc.execute("SELECT COUNT(*) FROM nc_programs")
    n_programs = pgc.fetchone()[0]
    pgc.execute("SELECT COUNT(*) FROM nc_files")
    n_files = pgc.fetchone()[0]
    pgc.execute("""
        SELECT COUNT(*) FROM nc_machining_details
        WHERE file_name IS NOT NULL AND file_name != '' AND folder_name IS NOT NULL AND folder_name != ''
    """)
    n_expect_program = pgc.fetchone()[0]
    pgc.execute("SELECT COUNT(DISTINCT nc_program_id) FROM nc_files WHERE file_type = 'PROGRAM'")
    n_have_program = pgc.fetchone()[0]

    log("\n--- 完了時整合性チェック ---")
    if n_programs > 0 and n_files == 0:
        log(f"[WARN] nc_programsは{n_programs}件あるのにnc_filesが0件です。", "WARN")
        log("[WARN] PHASE5(プログラムファイル移行)が未実行、または個別フェーズ再実行で"
            "破棄されたまま復元されていない可能性が高いです。", "WARN")
        log("[WARN] → python3 nc_full_import_v2.py --phase 5 を実行してください。", "WARN")
    elif n_expect_program > 0 and n_have_program < n_expect_program * 0.9:
        log(f"[WARN] プログラムファイル紐付けが不完全な可能性があります: "
            f"旧DB側に情報のあるmachining_id={n_expect_program}件に対し、"
            f"nc_files(PROGRAM)が紐付いているのは{n_have_program}件のみです。", "WARN")
        log("[WARN] → PHASE5の再実行を検討してください: python3 nc_full_import_v2.py --phase 5", "WARN")
    else:
        log(f"[OK] 整合性チェック: nc_programs={n_programs}件 nc_files={n_files}件 "
            f"(PROGRAM紐付け {n_have_program}/{n_expect_program}件)")


def main():
    parser = argparse.ArgumentParser(description="MachCore NC完全移行スクリプト v2(新スキーマ対応)")
    parser.add_argument("--phase", type=int, default=0, help="実行フェーズ (0=全, 1-6=個別。6=加工リスト マスタ候補投入)")
    parser.add_argument("--dry-run", action="store_true", help="DBへの書き込みなし")
    parser.add_argument("--skip-file-copy", action="store_true",
                        help="PHASE5をスキップ（プログラムファイルコピーなし、データのみ移行）")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        log("*** DRY RUN ***", "WARN")

    start = datetime.now()
    log(f"開始: {start.strftime('%Y-%m-%d %H:%M:%S')} phase={args.phase} dry_run={dry}")

    _resolve_admin_id_nc()

    pg = pg_connect()
    try:
        nc_id_map = kid_to_dbid = staff_id_map = machine_id_map = None

        if args.phase in (0, 1):
            nc_id_map, kid_to_dbid, staff_id_map, machine_id_map = phase1(pg, dry_run=dry)
        if args.phase in (0, 2):
            phase2(pg, dry_run=dry, kid_to_dbid=kid_to_dbid)
        if args.phase in (0, 3):
            phase3(pg, dry_run=dry, nc_id_map=nc_id_map, staff_id_map=staff_id_map, machine_id_map=machine_id_map)
        if args.phase in (0, 4):
            phase4(pg, dry_run=dry)
        if args.phase == 5 or (args.phase == 0 and not args.skip_file_copy):
            phase5(pg, dry_run=dry)
        if args.phase in (0, 6):
            phase6(pg, dry_run=dry)

        if args.phase == 0:
            final_report(pg)
        _final_consistency_check_nc(pg)
    except Exception as e:
        log(f"エラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        raise
    finally:
        pg.close()
        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n総実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        _log_fh.close()


if __name__ == "__main__":
    main()
