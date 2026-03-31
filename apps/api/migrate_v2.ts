// =============================================================================
// migrate.ts v2 — NC旋盤システム データ移行スクリプト（完全版）
// =============================================================================
// v1 からの主な変更点:
//   t_k_History の移行を完全に再設計（実データ 12,046件の分析結果を反映）
//
//   【旧 t_k_History の実態】
//   1レコードに最大3種類の情報が同居していた構造：
//
//   フィールドグループ    | 件数       | 移行先
//   ─────────────────────────────────────────────────────
//   Out_* (Out_Cont="印刷")| 9,674件    | setup_sheet_logs  (段取シート発行履歴)
//   Dan_*/La_*/P           | 9,579件    | work_records      (作業実績)
//   In_Cont="新規登録"/"変更"| 2,339件 | change_history    (NCデータ変更履歴)
//
//   ※ 9,554件は「印刷 + 作業記録」が混在 → 1レコードが2テーブルに分割される
//
//   【移行後の3テーブルの役割】
//   change_history   : NCデータの変更・登録・承認の履歴のみ
//   work_records     : 段取・加工時間・個数の作業実績のみ
//   setup_sheet_logs : 段取シートの印刷・発行の記録のみ
// =============================================================================

import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { Pool } from 'pg';
import * as fs from 'fs';
import * as path from 'path';
import * as bcrypt from 'bcrypt';
import * as iconv from 'iconv-lite';

// --- Prisma v7 初期化 ---
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter } as any);

const DATA_DIR = path.join(__dirname, 'migration', 'data');

// =============================================================================
// CSV ユーティリティ（Shift-JIS 対応）
// =============================================================================
async function readCsv(filename: string): Promise<Record<string, string>[]> {
  const filepath = path.join(DATA_DIR, filename);
  if (!fs.existsSync(filepath)) {
    console.warn(`⚠️  未存在: ${filepath}`);
    return [];
  }
  const buffer = fs.readFileSync(filepath);
  const decoded = iconv.decode(buffer, 'shift_jis');
  const lines = decoded.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
  return lines.slice(1).map(line => {
    const vals = parseCsvLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, i) => row[h] = (vals[i] ?? '').trim());
    return row;
  });
}

function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') { if (inQ && line[i+1] === '"') { cur += '"'; i++; } else inQ = !inQ; }
    else if (c === ',' && !inQ) { result.push(cur); cur = ''; }
    else cur += c;
  }
  result.push(cur);
  return result;
}

// =============================================================================
// 変換ユーティリティ
// =============================================================================
function toMinutes(h: string, m: string): number | null {
  const hours = parseInt(h || '0'), mins = parseInt(m || '0');
  if (isNaN(hours) && isNaN(mins)) return null;
  const total = (isNaN(hours) ? 0 : hours) * 60 + (isNaN(mins) ? 0 : mins);
  return total > 0 ? total : null;
}

function toDateTime(s: string | null | undefined): Date | null {
  if (!s?.trim()) return null;
  try { const d = new Date(s.replace(/\//g, '-')); return isNaN(d.getTime()) ? null : d; }
  catch { return null; }
}

function guessChangeType(inCont: string): 'NEW_REGISTRATION' | 'CHANGE' | 'APPROVAL' | 'MIGRATION' {
  if (!inCont) return 'CHANGE';
  if (inCont.includes('新規') || inCont.includes('仮登録')) return 'NEW_REGISTRATION';
  if (inCont.includes('承認')) return 'APPROVAL';
  if (inCont.includes('移行') || inCont.toLowerCase().includes('migration')) return 'MIGRATION';
  return 'CHANGE';
}

// =============================================================================
// STEP 1-1: machines
// =============================================================================
async function migrateMachines(): Promise<Map<number, number>> {
  console.log('\n📍 1-1: machines...');
  const rows = await readCsv('t_d_machine.csv');
  const map = new Map<number, number>();
  for (const row of rows) {
    const oid = parseInt(row['m_id'] || '0'), model = row['Model'] || '';
    if (!model) continue;
    try {
      const m = await prisma.machine.upsert({
        where: { machineCode: model }, update: {},
        create: { machineCode: model, machineName: model, machineType: 'NC旋盤', sortOrder: oid, isActive: true }
      });
      map.set(oid, m.id);
    } catch {}
  }
  console.log(`  ✅ ${map.size} 件`);
  return map;
}

// =============================================================================
// STEP 1-2: users（t_d_Staff）
// =============================================================================
async function migrateUsers(): Promise<{ byId: Map<number, number>; byName: Map<string, number> }> {
  console.log('\n📍 1-2: users...');
  const rows = await readCsv('t_d_staff.csv');
  const byId = new Map<number, number>();
  const byName = new Map<string, number>();

  for (const row of rows) {
    const oid = parseInt(row['St_id'] || '0');
    const name = (row['S_name'] || '').replace(/\u3000/g, ' ').trim();
    const nameFullWidth = row['S_name'] || '';
    const rawPw = row['Password'] || `init_${oid}`;
    if (!name) continue;
    const hash = await bcrypt.hash(rawPw, 10);
    const code = `STAFF${String(oid).padStart(3, '0')}`;
    try {
      const u = await prisma.user.upsert({
        where: { employeeCode: code }, update: {},
        create: { employeeCode: code, name, passwordHash: hash, role: 'OPERATOR', isActive: true }
      });
      byId.set(oid, u.id);
      byName.set(name, u.id);
      byName.set(nameFullWidth, u.id);
    } catch {}
  }
  // 管理者
  await prisma.user.upsert({
    where: { employeeCode: 'ADMIN001' }, update: {},
    create: { employeeCode: 'ADMIN001', name: '管理者', passwordHash: await bcrypt.hash('Admin@1234', 10), role: 'ADMIN', isActive: true }
  });
  console.log(`  ✅ ${byId.size} 件  ⚠️ パスワード変更通知必須`);
  return { byId, byName };
}

// =============================================================================
// STEP 1-3: parts（部品情報メイン × 納入先）
// =============================================================================
async function migrateParts(): Promise<Map<number, number>> {
  console.log('\n📍 1-3: parts...');
  const buhin = await readCsv('buhin_main.csv');
  const client = await readCsv('noirresaki.csv');
  const cMap = new Map<string, string>();
  for (const r of client) { const id = r['納入先ID'] || ''; if (id) cMap.set(id, r['会社名'] || ''); }
  const map = new Map<number, number>();
  for (const row of buhin) {
    const oid = parseInt(row['部品ID'] || '0');
    try {
      const p = await prisma.part.upsert({
        where: { partId: String(oid) }, update: {},
        create: {
          partId: String(oid),
          drawingNo: row['図面番号'] || '(不明)',
          name: row['名称'] || '(不明)',
          clientId: row['納入先ID'] ? parseInt(row['納入先ID']) : null,
          clientName: cMap.get(row['納入先ID']) || null,
          isActive: row['廃止部品'] !== '1',
        }
      });
      map.set(oid, p.id);
    } catch {}
  }
  console.log(`  ✅ ${map.size} 件`);
  return map;
}

// =============================================================================
// STEP 2-1: nc_programs（t1_NC × t2_Lathe）
// =============================================================================
async function migrateNcPrograms(
  machineMap: Map<number, number>,
  userMap: { byId: Map<number, number> },
  partMap: Map<number, number>
): Promise<{ ncIdMap: Map<number, number>; kidMap: Map<number, number> }> {
  console.log('\n📍 2-1: nc_programs...');
  const t1 = await readCsv('t1_nc.csv');
  const t2 = await readCsv('t2_lathe.csv');
  const fd = await readCsv('t_d_fd.csv');
  const fdMap = new Map<string, string>();
  for (const r of fd) fdMap.set(r['FD_id'], r['FD_name']);
  const t2Map = new Map<string, Record<string, string>>();
  for (const r of t2) t2Map.set(r['K_id'], r);

  const ncIdMap = new Map<number, number>();
  const kidMap = new Map<number, number>();
  let ok = 0, ng = 0;

  for (const r1 of t1) {
    const ncId = parseInt(r1['NC_id']), bId = parseInt(r1['B_id']), kId = r1['K_id'];
    const r2 = t2Map.get(kId);
    if (!r2) { ng++; continue; }
    const newPartId = partMap.get(bId);
    if (!newPartId) { ng++; continue; }
    const folderName = fdMap.get(r2['FD_name']) || r2['FD_name'] || '(未設定)';
    const clampNote = [r2['Clamp'] ? `クランプ: ${r2['Clamp']}` : '', r2['Note'] || ''].filter(Boolean).join('\n') || null;
    const regBy = userMap.byId.get(parseInt(r2['Reco_P'] || '0')) || 1;
    try {
      const prog = await prisma.ncProgram.upsert({
        where: { unique_part_process: { partId: newPartId, processL: parseInt(r2['L'] || '1') } },
        update: {},
        create: {
          partId: newPartId, processL: parseInt(r2['L'] || '1'),
          machineId: machineMap.get(parseInt(r2['Machine'] || '0')) || null,
          machiningTime: parseInt(r2['Tm'] || '0') || null,
          setupTimeRef: parseInt(r2['Ts'] || '0') || null,
          folderName, fileName: r2['F_name'] || '',
          oNumber: r2['oNo'] || null,
          version: String(parseInt(r2['Ver'] || '0') || 'A'),
          legacyVer: r2['Ver'] || null,
          legacyKid: parseInt(kId) || null,
          clampNote, drawingCount: parseInt(r2['Fig'] || '0'),
          photoCount: parseInt(r2['Photo'] || '0'),
          status: 'APPROVED', registeredBy: regBy,
          registeredAt: toDateTime(r2['Reco_D']) || new Date('2005-01-01'),
        }
      });
      ncIdMap.set(ncId, prog.id);
      kidMap.set(parseInt(kId), prog.id);
      ok++;
    } catch { ng++; }
  }
  console.log(`  ✅ ${ok} 件, ❌ ${ng} 件`);
  return { ncIdMap, kidMap };
}

// =============================================================================
// STEP 2-2: nc_tools（t3_Tool）
// =============================================================================
async function migrateNcTools(ncIdMap: Map<number, number>): Promise<void> {
  console.log('\n📍 2-2: nc_tools...');
  const tools = await readCsv('t3_tool.csv');
  const t1 = await readCsv('t1_nc.csv');
  const kToNc = new Map<string, number>();
  for (const r of t1) kToNc.set(r['K_id'], parseInt(r['NC_id']));
  let ok = 0, ng = 0;
  for (const r of tools) {
    const oldNcId = kToNc.get(r['K_id']);
    if (!oldNcId) { ng++; continue; }
    const newId = ncIdMap.get(oldNcId);
    if (!newId) { ng++; continue; }
    const pt = [r['Shave1'], r['Shave2']].filter(Boolean).join(' / ') || null;
    try {
      await prisma.ncTool.create({
        data: { ncProgramId: newId, sortOrder: parseInt(r['No'] || '0'),
          processType: pt, chipModel: r['Chip'] || null,
          holderModel: r['Holder'] || null,
          noseR: r['NorzR'] ? String(parseFloat(r['NorzR'])) : null,
          note: r['Note'] || null }
      });
      ok++;
    } catch { ng++; }
  }
  console.log(`  ✅ ${ok} 件, ❌ ${ng} 件`);
}

// =============================================================================
// STEP 3: t_k_History の完全分離移行
// =============================================================================
// 【設計方針】
// t_k_History の各レコードを以下のルールで振り分ける：
//
//   ┌────────────────────────────────────────────────────────────────┐
//   │ 条件                              │ 移行先                     │
//   ├───────────────────────────────────┼────────────────────────────┤
//   │ Out_Cont に "印刷" を含む         │ setup_sheet_logs            │
//   │   → Out_Op（印刷者）             │   operator_id              │
//   │   → Out_Date（印刷日時）         │   printed_at               │
//   ├───────────────────────────────────┼────────────────────────────┤
//   │ Dan_Op or La_H>0 or P>0 あり     │ work_records                │
//   │   → Dan_Op/La_Op（担当者）       │   operator_id              │
//   │   → Dan_H/M, La_H/M（時間）      │   setup_time_min 等        │
//   │   → P（個数）                    │   quantity                 │
//   │   → In_Date（作業日）            │   work_date                │
//   ├───────────────────────────────────┼────────────────────────────┤
//   │ In_Cont が "新規登録"/"変更" 等  │ change_history              │
//   │   → In_Op（入力者）              │   operator_id              │
//   │   → In_Ver, Out_Ver（Ver変化）   │   version_before/after     │
//   │   → In_Date（入力日時）          │   changed_at               │
//   └───────────────────────────────────┴────────────────────────────┘
//
// 1レコードが複数テーブルに分かれる場合あり（特に混在9,554件）
// =============================================================================
async function migrateHistory(
  ncIdMap: Map<number, number>,
  userMap: { byId: Map<number, number>; byName: Map<string, number> },
  machineMap: Map<number, number>
): Promise<void> {
  console.log('\n📍 3: t_k_History 完全分離移行...');

  const histRows = await readCsv('t_k_history.csv');

  // 氏名逆引きマップ構築
  const nameMap = new Map<string, number>(userMap.byName);

  let chOk = 0, wrOk = 0, slOk = 0;
  let chNg = 0, wrNg = 0, slNg = 0;

  for (const row of histRows) {
    const ncId = parseInt(row['NC_id'] || '0');
    const newNcId = ncIdMap.get(ncId);
    if (!newNcId) continue;

    const outCont = (row['Out_Cont'] || '').trim();
    const inCont = (row['In_Cont'] || '').trim();
    const outOp = parseInt(row['Out_Op'] || '0');
    const inOp = parseInt(row['In_Op'] || '0');
    const outDate = toDateTime(row['Out_Date']);
    const inDate = toDateTime(row['In_Date']);
    const danOp = (row['Dan_Op'] || '').trim();
    const laOp = (row['La_Op'] || '').trim();
    const danH = parseInt(row['Dan_H'] || '0');
    const danM = parseInt(row['Dan_M'] || '0');
    const laH = parseInt(row['La_H'] || '0');
    const laM = parseInt(row['La_M'] || '0');
    const p = parseInt(row['P'] || '0');
    const mcId = parseInt(row['Mc'] || '0');

    // ── A: setup_sheet_logs（Out_Cont = "印刷"）
    if (outCont.includes('印刷') && outDate) {
      const opId = userMap.byId.get(outOp) || 1;
      try {
        await prisma.setupSheetLog.create({
          data: { ncProgramId: newNcId, operatorId: opId, printedAt: outDate,
            pdfPath: null, sessionId: null }
        });
        slOk++;
      } catch { slNg++; }
    }

    // ── B: work_records（Dan_*/La_*/P に実データあり）
    const hasWorkData = danOp || danH > 0 || danM > 0 || laH > 0 || laM > 0 || p > 0;
    if (hasWorkData) {
      const setupMin = toMinutes(String(danH), String(danM));
      const machMin = toMinutes(String(laH), String(laM));
      const workOpId = nameMap.get(danOp) || nameMap.get(laOp) || userMap.byId.get(inOp) || 1;
      const workMcId = machineMap.get(mcId) || null;
      const workDate = inDate || outDate || new Date('2005-01-01');
      try {
        await prisma.workRecord.create({
          data: {
            ncProgramId: newNcId, operatorId: workOpId, machineId: workMcId,
            workDate, setupTimeMin: setupMin, machiningTimeMin: machMin,
            quantity: p > 0 ? p : null,
            note: [danOp && `段取: ${danOp}`, laOp && `加工: ${laOp}`].filter(Boolean).join(', ') || null
          }
        });
        wrOk++;
      } catch { wrNg++; }
    }

    // ── C: change_history（In_Cont が "新規登録" / "変更" / "承認"）
    const isNcChange = ['新規登録', '仮登録', '変更', '承認'].some(k => inCont.includes(k));
    if (isNcChange && inDate) {
      const opId = userMap.byId.get(inOp) || 1;
      try {
        await prisma.changeHistory.create({
          data: {
            ncProgramId: newNcId, changeType: guessChangeType(inCont),
            operatorId: opId,
            versionBefore: row['Out_Ver'] ? String(parseInt(row['Out_Ver'])) : null,
            versionAfter: row['In_Ver'] ? String(parseInt(row['In_Ver'])) : null,
            content: inCont || null,
            fieldChanges: outCont && !outCont.includes('印刷') ? { out_content: outCont } : undefined,
            changedAt: inDate,
            legacyHistId: parseInt(row['Hist_id']) || null,
          }
        });
        chOk++;
      } catch { chNg++; }
    }
  }

  console.log(`  ✅ setup_sheet_logs: ${slOk} 件 (❌${slNg})`);
  console.log(`  ✅ work_records:     ${wrOk} 件 (❌${wrNg})`);
  console.log(`  ✅ change_history:   ${chOk} 件 (❌${chNg})`);
  console.log(`\n  【内訳】t_k_History 12,046件 → 最大 ${slOk + wrOk + chOk} レコードに展開`);
}

// =============================================================================
// STEP 4: 検証
// =============================================================================
async function verify(): Promise<void> {
  console.log('\n📍 4: 移行後検証...');
  const [mc, us, pt, nc, nt, ch, wr, sl] = await Promise.all([
    prisma.machine.count(), prisma.user.count(), prisma.part.count(),
    prisma.ncProgram.count(), prisma.ncTool.count(),
    prisma.changeHistory.count(), prisma.workRecord.count(), prisma.setupSheetLog.count()
  ]);
  console.log('\n════ 移行結果サマリー ════');
  console.log(`  machines:          ${mc.toString().padStart(6)} 件  （t_d_Machine）`);
  console.log(`  users:             ${us.toString().padStart(6)} 件  （t_d_Staff）`);
  console.log(`  parts:             ${pt.toString().padStart(6)} 件  （部品情報メイン）`);
  console.log(`  nc_programs:       ${nc.toString().padStart(6)} 件  （t1_NC × t2_Lathe）`);
  console.log(`  nc_tools:          ${nt.toString().padStart(6)} 件  （t3_Tool）`);
  console.log(`  change_history:    ${ch.toString().padStart(6)} 件  （t_k_History → 変更履歴）`);
  console.log(`  work_records:      ${wr.toString().padStart(6)} 件  （t_k_History → 作業記録）`);
  console.log(`  setup_sheet_logs:  ${sl.toString().padStart(6)} 件  （t_k_History → 印刷履歴）`);
  console.log('═══════════════════════════');
}

// =============================================================================
// メイン
// =============================================================================
async function main() {
  console.log('════════════════════════════════════════════');
  console.log('  NC旋盤管理システム  データ移行スクリプト v2');
  console.log(`  実行日時: ${new Date().toLocaleString('ja-JP')}`);
  console.log('════════════════════════════════════════════');

  if (!fs.existsSync(DATA_DIR)) {
    console.error(`\n❌ データディレクトリ未存在: ${DATA_DIR}`);
    console.log('旧DBからCSVをエクスポートして配置してください');
    process.exit(1);
  }

  await prisma.$connect();
  try {
    const machineMap = await migrateMachines();
    const userMap = await migrateUsers();
    const partMap = await migrateParts();
    const { ncIdMap } = await migrateNcPrograms(machineMap, userMap, partMap);
    await migrateNcTools(ncIdMap);
    await migrateHistory(ncIdMap, userMap, machineMap);
    await verify();

    console.log('\n🎉 移行完了！');
    console.log('\n必須後処理:');
    console.log('  1. 全ユーザーにパスワード変更通知');
    console.log('  2. ADMIN権限ユーザーを手動設定');
    console.log('  3. ファイルサーバのパス整合性確認');
  } finally {
    await prisma.$disconnect();
    await pool.end();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
