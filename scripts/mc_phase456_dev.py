import pymssql, psycopg2

PG_DSN = "host=localhost port=5440 dbname=machcore_dev user=machcore password=machcore_pass_change_me"
sql = pymssql.connect(server='192.168.1.9', user='sa', password='RTW65b',
                      database='imotomc', tds_version='7.4')
pg  = psycopg2.connect(PG_DSN)
sc  = sql.cursor()
pc  = pg.cursor()

# 共通マップ: legacy_kakoid(加工ID) → mc_programs.id
pc.execute("SELECT id, legacy_kakoid FROM mc_programs WHERE legacy_kakoid IS NOT NULL")
kakoid_map = {}
for r in pc.fetchall():
    kakoid_map.setdefault(r[1], r[0])

# legacy_mcid → mc_programs.id
pc.execute("SELECT id, legacy_mcid FROM mc_programs WHERE legacy_mcid IS NOT NULL")
mcid_map = {r[1]: r[0] for r in pc.fetchall()}

pc.execute("SELECT id FROM users WHERE employee_code = 'ADMIN001'")
admin_id = pc.fetchone()[0]
print(f"kakoidマップ={len(kakoid_map)}, mcidマップ={len(mcid_map)}", flush=True)

# ============================================================
# PHASE 4: mc_work_offsets (ACC_ワークオフセット)
# ============================================================
print("\n=== PHASE 4: mc_work_offsets ===", flush=True)
sc.execute("SELECT G, X, Y, Z, A, R, 加工ID FROM [imotomc].[dbo].[ACC_ワークオフセット] ORDER BY 加工ID")
INSERT4 = """
    INSERT INTO mc_work_offsets (mc_program_id, g_code, x_offset, y_offset, z_offset, a_offset, r_offset, created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    ON CONFLICT (mc_program_id, g_code) DO NOTHING
"""
ins4 = skip4 = err4 = 0
while True:
    rows = sc.fetchmany(500)
    if not rows: break
    for row in rows:
        g, x, y, z, a, r, kako_id = row
        mc_id = kakoid_map.get(kako_id)
        if mc_id is None:
            skip4 += 1
            continue
        pc.execute("SAVEPOINT sp")
        try:
            pc.execute(INSERT4, (mc_id, str(g)[:10] if g else 'G54', x, y, z, a, r))
            pc.execute("RELEASE SAVEPOINT sp")
            ins4 += 1
        except Exception as e:
            pc.execute("ROLLBACK TO SAVEPOINT sp")
            err4 += 1
            if err4 <= 3: print(f"  ERR4: {e}", flush=True)
pg.commit()
print(f"PHASE 4完了: 挿入={ins4}, スキップ={skip4}, エラー={err4}", flush=True)

# ============================================================
# PHASE 5: mc_index_programs (ACC_インデックスプログラム)
# ============================================================
print("\n=== PHASE 5: mc_index_programs ===", flush=True)
sc.execute("SELECT STEP_N, 第1軸, 第2軸, 加工ID FROM [imotomc].[dbo].[ACC_インデックスプログラム] ORDER BY 加工ID, STEP_N")
INSERT5 = """
    INSERT INTO mc_index_programs (mc_program_id, sort_order, axis_0, axis_1, created_at, updated_at)
    VALUES (%s, %s, %s, %s, NOW(), NOW())
    ON CONFLICT DO NOTHING
"""
ins5 = skip5 = err5 = 0
while True:
    rows = sc.fetchmany(500)
    if not rows: break
    for row in rows:
        step_n, axis1, axis2, kako_id = row
        mc_id = kakoid_map.get(kako_id)
        if mc_id is None:
            skip5 += 1
            continue
        try:
            sort = int(float(step_n)) if step_n is not None else 0
        except:
            sort = 0
        pc.execute("SAVEPOINT sp")
        try:
            pc.execute(INSERT5, (mc_id, sort,
                str(axis1)[:100] if axis1 else None,
                str(axis2)[:100] if axis2 else None))
            pc.execute("RELEASE SAVEPOINT sp")
            ins5 += 1
        except Exception as e:
            pc.execute("ROLLBACK TO SAVEPOINT sp")
            err5 += 1
            if err5 <= 3: print(f"  ERR5: {e}", flush=True)
pg.commit()
print(f"PHASE 5完了: 挿入={ins5}, スキップ={skip5}, エラー={err5}", flush=True)

# ============================================================
# PHASE 6: mc_change_history (ACC_変更履歴)
# ============================================================
print("\n=== PHASE 6: mc_change_history ===", flush=True)
sc.execute("""
    SELECT MCID, 加工ID, 内容, Ver, 作成日
    FROM [imotomc].[dbo].[ACC_変更履歴]
    ORDER BY 加工ID
""")
INSERT6 = """
    INSERT INTO mc_change_history (
        mc_program_id, change_type, operator_id,
        version_after, content, changed_at
    ) VALUES (%s, 'MIGRATION', %s, %s, %s, COALESCE(%s::timestamp, NOW()))
    ON CONFLICT DO NOTHING
"""
ins6 = skip6 = err6 = 0
while True:
    rows = sc.fetchmany(500)
    if not rows: break
    for row in rows:
        mcid, kako_id, naiyou, ver, sakusei_bi = row
        # MCIDで先に引き、なければkakoidで引く
        mc_id = mcid_map.get(mcid) or kakoid_map.get(kako_id)
        if mc_id is None:
            skip6 += 1
            continue
        reg_at = f"{sakusei_bi} 00:00:00" if sakusei_bi and len(str(sakusei_bi)) == 10 else None
        pc.execute("SAVEPOINT sp")
        try:
            pc.execute(INSERT6, (
                mc_id, admin_id,
                str(ver)[:10] if ver else None,
                str(naiyou)[:2000] if naiyou else None,
                reg_at,
            ))
            pc.execute("RELEASE SAVEPOINT sp")
            ins6 += 1
        except Exception as e:
            pc.execute("ROLLBACK TO SAVEPOINT sp")
            err6 += 1
            if err6 <= 3: print(f"  ERR6: {e}", flush=True)
    pg.commit()

print(f"PHASE 6完了: 挿入={ins6}, スキップ={skip6}, エラー={err6}", flush=True)

# ============================================================
# 最終サマリー
# ============================================================
print("\n=== 最終サマリー ===", flush=True)
for tbl in ['mc_programs','mc_tooling','mc_work_offsets','mc_index_programs','mc_change_history']:
    pc.execute(f"SELECT COUNT(*) FROM {tbl}")
    print(f"  {tbl:<25}: {pc.fetchone()[0]:>7,}件", flush=True)

# has_work_offset / has_index_program フラグ更新
pc.execute("""
    UPDATE mc_programs SET has_work_offset = true
    WHERE id IN (SELECT DISTINCT mc_program_id FROM mc_work_offsets)
""")
pc.execute("""
    UPDATE mc_programs SET has_index_program = true
    WHERE id IN (SELECT DISTINCT mc_program_id FROM mc_index_programs)
""")
pg.commit()
print("has_work_offset / has_index_program フラグ更新完了", flush=True)

sql.close()
pg.close()
