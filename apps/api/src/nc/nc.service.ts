import { Injectable, NotFoundException, ForbiddenException } from "@nestjs/common";
import { CreateWorkRecordDto } from './dto/create-work-record.dto';
import { PrismaService } from "../prisma/prisma.service";
import { AuthService } from "../auth/auth.service";
import { CreateNcDto } from "./dto/create-nc.dto";
import { UpdateNcDto } from "./dto/update-nc.dto";
import { SaveNcToolingDto } from "./dto/save-nc-tooling.dto";

import * as fs from 'fs';
import { execSync } from 'child_process';
import * as path from 'path';
import * as chardet from 'chardet';
import * as iconv from 'iconv-lite';
import { UpdateWorkRecordDto } from "./dto/update-work-record.dto";
// ★新規登録フロー実装: MC側program-file-naming.utilと同一ロジックを再利用する。
import { calcProgramFileName, calcProgramFolderName } from "../mc/program-file-naming.util";
@Injectable()
export class NcService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly authService: AuthService,
  ) {}

  /** NC-01: 部品検索 */
  async search(key: string, q: string, limit = 50, offset = 0, clientName?: string, machineId?: number) {
    const where: any = {};
    if (q && q.trim()) {
      const trimQ = q.trim();
      switch (key) {
        case "nc_id":
          const ncId = parseInt(trimQ);
          if (!isNaN(ncId)) where.id = ncId;
          break;
        case "part_id":
          where.part = { partId: trimQ };
          break;
        case "drawing_no":
          where.part = { drawingNo: { contains: trimQ, mode: "insensitive" } };
          break;
        case "name":
          where.part = { name: { contains: trimQ, mode: "insensitive" } };
          break;
        default:
          where.OR = [
            { part: { drawingNo: { contains: trimQ, mode: "insensitive" } } },
            { part: { name:      { contains: trimQ, mode: "insensitive" } } },
          ];
      }
    }
    // 追加フィルタ
    if (clientName) {
      where.part = { ...(where.part ?? {}), clientName: { contains: clientName, mode: "insensitive" } };
    }
    if (machineId) {
      where.machining = { ...(where.machining ?? {}), machineId };
    }

    const [total, data] = await Promise.all([
      this.prisma.ncProgram.count({ where }),
      this.prisma.ncProgram.findMany({
        where,
        take: limit,
        skip: offset,
        select: {
          id: true, status: true, machiningId: true,
          part:     { select: { id: true, partId: true, drawingNo: true, name: true, clientName: true } },
          machining: {
            select: {
              processL: true, version: true, folderName: true,
              fileName: true, machiningTime: true,
              machine: { select: { machineCode: true } },
            },
          },
        },
        orderBy: [{ part: { drawingNo: "asc" } }, { machining: { processL: "asc" } }],
      }),
    ]);
    return {
      total,
      data: data.map(r => ({
        nc_id: r.id, part_db_id: r.part.id, part_id: r.part.partId,
        drawing_no: r.part.drawingNo, part_name: r.part.name,
        client_name: r.part.clientName, process_l: r.machining?.processL ?? null,
        machine_code: r.machining?.machine?.machineCode ?? null,
        status: r.status, version: r.machining?.version ?? null,
        folder_name: r.machining?.folderName ?? null, file_name: r.machining?.fileName ?? null,
        machining_time: r.machining?.machiningTime ?? null,
        // [v104] 共通加工登録(ncApi.registerCommonPart)のsource_machining_idに必要
        machining_id: r.machiningId,
      })),
    };
  }

  /** 納入先一覧（検索フォーム用） */
  async getClientNames(): Promise<string[]> {
    const rows = await this.prisma.part.findMany({
      where: { clientName: { not: null } },
      select: { clientName: true },
      distinct: ["clientName"],
      orderBy: { clientName: "asc" },
    });
    return rows.map(r => r.clientName!).filter(Boolean);
  }

  /** NC-XX: 同部品の工程一覧 */
  async byPart(partDbId: number) {
    const rows = await this.prisma.ncProgram.findMany({
      where: { partId: partDbId },
      select: {
        id: true, status: true,
        machining: {
          select: { processL: true, version: true, machine: { select: { machineCode: true } } },
        },
      },
      orderBy: { machining: { processL: "asc" } },
    });
    return rows.map(r => ({
      nc_id: r.id, process_l: r.machining?.processL ?? null, version: r.machining?.version ?? null,
      status: r.status, machine_code: r.machining?.machine?.machineCode ?? null,
    }));
  }

  /** NC-02: 最近のアクセス5件 */
  async recent() {
    const logs = await this.prisma.operationLog.findMany({
      where:   { ncProgramId: { not: null } },
      take:    5,
      orderBy: { createdAt: "desc" },
      select: {
        actionType: true, createdAt: true,
        user: { select: { name: true } },
        ncProgram: {
          select: {
            id: true, status: true,
            part:     { select: { drawingNo: true, name: true } },
            machining: {
              select: {
                processL: true, version: true,
                machine: { select: { machineCode: true } },
              },
            },
          },
        },
      },
    });
    return logs.map(l => ({
      nc_id: l.ncProgram?.id, drawing_no: l.ncProgram?.part.drawingNo,
      part_name: l.ncProgram?.part.name, process_l: l.ncProgram?.machining?.processL ?? null,
      machine_code: l.ncProgram?.machining?.machine?.machineCode ?? null,
      version: l.ncProgram?.machining?.version ?? null, action_type: l.actionType,
      operator_name: l.user?.name, accessed_at: l.createdAt,
    }));
  }

  /** Ridoc図面プロキシ用: 部品の図番取得（MC側 findPartDrawingNo と同方式） */
  async findPartDrawingNo(ncId: number): Promise<{ drawingNo: string | null } | null> {
    const r = await this.prisma.ncProgram.findUnique({
      where: { id: ncId },
      select: { part: { select: { drawingNo: true } } },
    });
    if (!r) return null;
    return { drawingNo: r.part.drawingNo || null };
  }

  /** NC-03: NC詳細 */
  async findOne(id: number) {
    const r = await this.prisma.ncProgram.findUnique({
      where: { id },
      include: {
        part:     true,
        machining: {
          include: {
            machine: true,
            tools:   { orderBy: { sortOrder: "asc" } },
            creator: { select: { id: true, name: true } },
          },
        },
        registrar: { select: { id: true, name: true } },
        approver:  { select: { id: true, name: true } },
      },
    });
    if (!r) throw new NotFoundException(`NC_id ${id} が存在しません`);
    // フロントエンドのNcDetail型との互換性のためmachining配下フィールドをフラット展開して返す
    return {
      ...r,
      machine:       r.machining?.machine     ?? null,
      tools:         r.machining?.tools        ?? [],
      processL:      r.machining?.processL     ?? null,
      version:       r.machining?.version      ?? '1.0001',
      folderName:    r.machining?.folderName   ?? '',
      fileName:      r.machining?.fileName     ?? '',
      oNumber:       r.machining?.oNumber      ?? null,
      clampNote:     r.machining?.clampNote    ?? null,
      machiningTime: r.machining?.machiningTime ?? null,
      setupTimeRef:  r.machining?.setupTimeRef  ?? null,
      drawingCount:  r.machining?.drawingCount  ?? 0,
      photoCount:    r.machining?.photoCount    ?? 0,
      processingId:  r.machining?.processingId  ?? null,
      // [v096] MC側findOne()との機能パリティのため追加。
      creatorId:      r.machining?.creatorId      ?? null,
      sheetCreatedAt: r.machining?.sheetCreatedAt  ?? null,
      creator:        r.machining?.creator         ?? null,
      // [v101] 掴代(専用フィールド) + 共通部品情報(MC側findOne()と同等)
      clampAllowance: r.machining?.clampAllowance ?? null,
      commonPartCode: r.machining?.commonPartCode ?? null,
      commonGroup:    await this.buildCommonGroup(r.machiningId, r.id),
    };
  }

  // [v101] 共通加工グループ(参照表示のみ、MC側 mc.service.ts の同名ロジックと同等)
  private async buildCommonGroup(machiningId: number, currentNcProgramId: number) {
    const rows = await this.prisma.ncProgram.findMany({
      where:   { machiningId },
      orderBy: { id: 'asc' },
      select: {
        id: true, legacyNcId: true, machiningId: true, status: true,
        part:      { select: { drawingNo: true, name: true, clientName: true, partId: true } },
        machining: { select: { version: true } },
      },
    });
    return rows.map(g => ({
      id:          g.id,
      legacyNcId:  g.legacyNcId ?? null,
      machiningId: g.machiningId,
      status:      g.status,
      version:     g.machining?.version ?? '1.0001',
      part:        g.part,
      isCurrent:   g.id === currentNcProgramId,
    }));
  }

  // ══════════════════════════════════════════
  // [新規登録フロー実装] 部品マスタ直接検索 (MC側 searchParts と同一ロジック)
  // ══════════════════════════════════════════
  async searchParts(key: string, q: string, limit = 50, offset = 0) {
    const where: any = { isActive: true };
    const kw = (q ?? '').trim();
    if (kw) {
      if (key === 'part_id') {
        where.partId = { contains: kw, mode: 'insensitive' };
      } else if (key === 'part_name') {
        where.name = { contains: kw, mode: 'insensitive' };
      } else {
        where.drawingNo = { contains: kw, mode: 'insensitive' };
      }
    }
    const [rows, total] = await Promise.all([
      this.prisma.part.findMany({
        where, skip: offset, take: limit,
        orderBy: { drawingNo: 'asc' },
        select: { id: true, partId: true, drawingNo: true, name: true, clientName: true },
      }),
      this.prisma.part.count({ where }),
    ]);
    return {
      total, limit, offset,
      rows: rows.map(r => ({
        id:          r.id,
        part_id:     r.partId,
        drawing_no:  r.drawingNo,
        name:        r.name,
        client_name: r.clientName,
      })),
    };
  }

  // ══════════════════════════════════════════
  // [新規登録フロー実装] 次のK_id(加工ID)候補のプレビュー
  // ══════════════════════════════════════════
  // ★MC側calcNextIdと同じ設計: 旧システムのNC_id体系(nc_programs.legacy_nc_id)の
  //   最大値と、現行システムのK_id(nc_machining_details.k_id)の最大値の両方を見て、
  //   どちらの体系に対しても既存IDと衝突しない値を次の候補として返す。
  private async calcNextKId(): Promise<number> {
    const [aggLegacy, aggKid] = await Promise.all([
      this.prisma.ncProgram.aggregate({ _max: { legacyNcId: true } }),
      this.prisma.ncMachiningDetail.aggregate({ _max: { kId: true } }),
    ]);
    return Math.max(aggLegacy._max.legacyNcId ?? 0, aggKid._max.kId ?? 0) + 1;
  }

  async nextMachiningId() {
    const next = await this.calcNextKId();
    return { next_machining_id: next };
  }

  // ★新規登録フロー実装: MC側resolveProgramNamingと同じ考え方で、機械マスタ
  //   (Machine.pgIsFolder)に基づきfolder_name/file_nameを自動算出する。
  //   フロントエンドから明示指定があればそちらを優先する(将来の拡張余地を残す)。
  private async resolveNewRegistrationNaming(
    machineId: number | null | undefined,
    newKid: number,
  ): Promise<{ folderName: string; fileName: string }> {
    let pgIsFolder = false;
    if (machineId) {
      const machine = await this.prisma.machine.findUnique({ where: { id: machineId }, select: { pgIsFolder: true } });
      pgIsFolder = !!machine?.pgIsFolder;
    }
    // ★MC側McMachiningDetail.resolveProgramNamingと完全に同一の命名規則
    //   (calcProgramFileName/calcProgramFolderName)を適用する。
    //   folder_name/file_nameいずれもNOT NULL制約があるため:
    //     - フォルダ単位機械: folder_nameに実際のフォルダ名({K_id}.pwd)を設定
    //       (MC側pgFolderNameと同じ意味)。file_nameはNOT NULL制約を満たす
    //       ためのフォールバック値としてcalcProgramFileNameを設定(実運用では
    //       PGアップロード機能から参照されない)。
    //     - 単体ファイル機械: folder_nameは旧システム互換の固定値"USB"
    //       (媒体種別のレガシー値、実運用では不使用)。file_nameに
    //       calcProgramFileNameの値(MC側fileNameと同じ意味)を設定。
    const fileName = calcProgramFileName(newKid);
    const folderName = pgIsFolder ? calcProgramFolderName(newKid) : "USB";
    return { folderName, fileName };
  }

  /** NC-04: 新規登録 */
  async create(dto: CreateNcDto, operatorId: number) {
    const part = await this.prisma.part.findUnique({ where: { id: dto.part_id } });
    if (!part) throw new NotFoundException(`part_id ${dto.part_id} が存在しません`);

    const nc = await this.prisma.$transaction(async (tx) => {
      // ★MC側calcNextIdと同じ設計(旧システムのNC_id体系も考慮したMAXロジック)。
      //   旧システム(access_NC_spec.html F_誰フォームOK_Click)でも、新規登録(仮登録)
      //   時は Kakou_id = NCsen_id (採番したNC_idをそのままK_idに使う)という挙動
      //   だったため、トランザクション内でも同じMAXロジックで再計算し衝突を防ぐ。
      const [aggLegacyTx, aggKidTx] = await Promise.all([
        tx.ncProgram.aggregate({ _max: { legacyNcId: true } }),
        tx.ncMachiningDetail.aggregate({ _max: { kId: true } }),
      ]);
      const newKid = Math.max(aggLegacyTx._max.legacyNcId ?? 0, aggKidTx._max.kId ?? 0) + 1;

      // ★folder_name/file_nameが明示指定されていない場合、機械マスタに基づき
      //   サーバー側で自動算出する。
      let folderName = dto.folder_name;
      let fileName = dto.file_name;
      if (!folderName || !fileName) {
        const naming = await this.resolveNewRegistrationNaming(dto.machine_id, newKid);
        folderName = folderName ?? naming.folderName;
        fileName = fileName ?? naming.fileName;
      }

      await tx.ncMachiningDetail.upsert({
        where: { kId: newKid },
        update: {},
        create: {
          kId:          newKid,
          processL:     dto.process_l,
          machineId:    dto.machine_id     ?? null,
          machiningTime: dto.machining_time ?? null,
          folderName,
          fileName,
          version:      dto.version ?? "1.0001",
          clampNote:    dto.clamp_note     ?? null,
          clampAllowance: dto.clamp_allowance ?? null,
        },
      });
      // ★MC側 legacyMcid: dto.machining_id と同じ考え方、かつ旧システムの
      //   Kakou_id = NCsen_id という実際の挙動とも一致させ、legacyNcIdに
      //   採番したnewKid自身をセットする。これにより次回以降のcalcNextKId()が
      //   このIDを正しく認識し、以降の採番と衝突しない。
      const created = await tx.ncProgram.create({
        data: {
          partId:       dto.part_id,
          machiningId:  newKid,
          legacyNcId:   newKid,
          // [仮登録] 「作業完了（登録）」(finalize)が行われるまではPROVISIONAL(未確定)。
          status:       "PROVISIONAL",
          registeredBy: operatorId,
        },
      });
      await tx.changeHistory.create({
        data: {
          ncProgramId:   created.id,
          operatorId,
          changeType:    "NEW_REGISTRATION",
          versionBefore: null,
          versionAfter:  dto.version ?? "1.0001",
          content:       `新規登録: ${part.drawingNo} L${dto.process_l}`,
        },
      });
      return created;
    });

    return { nc_id: nc.id, message: "新規登録が完了しました" };
  }

  // ══════════════════════════════════════════
  // [仮登録破棄] 新規登録(仮登録)が「作業完了（登録）」(finalize)を経由せずに
  // 離脱された場合に呼ばれる。PROVISIONAL状態のNcProgramと、他に共有していなければ
  // NcMachiningDetail(K_id)自体も削除し、採番したK_idを解放する。
  // 既に確定済み(PROVISIONAL以外)の場合は何もしない(誤って確定済みデータを
  // 消してしまわないための安全策)。
  // ══════════════════════════════════════════
  async abandonProvisional(ncId: number) {
    // [FIX] アップロード済みの写真・図面等は、確定前に離脱してもいきなり削除せず、
    // 他のPROGRAMファイル退避処理(purgeExistingProgramFiles等)と同じくtrash/へ
    // タイムスタンプ付きで退避する。
    const companySetting = await this.prisma.companySetting.findFirst();
    const basePath = companySetting?.uploadBasePath ?? '/mnt/mc_files';

    return this.prisma.$transaction(async (tx) => {
      const nc = await tx.ncProgram.findUnique({
        where:   { id: ncId },
        include: { files: true },
      });
      if (!nc) return { nc_id: ncId, released: false, message: '既に破棄済みです' };
      if (nc.status !== 'PROVISIONAL') {
        // 確定済みデータの誤削除を防ぐ(絶対にthrowで止める。無条件削除は絶対にしない)。
        throw new ForbiddenException('この登録は既に確定済みのため破棄できません。');
      }

      // アップロード済みの物理ファイル(PG/写真/図面等)があればtrash/へ退避する。
      // (DB行自体はNcProgram削除時にonDelete:Cascadeで自動的に削除される)
      const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
      const trashDir = path.join(basePath, 'trash');
      for (const f of nc.files) {
        try {
          if (fs.existsSync(f.filePath)) {
            if (!fs.existsSync(trashDir)) fs.mkdirSync(trashDir, { recursive: true });
            const ext  = path.extname(f.filePath);
            const base = path.basename(f.filePath, ext);
            let dest = path.join(trashDir, `${base}_${ts}${ext}`);
            if (fs.existsSync(dest)) dest = path.join(trashDir, `${base}_${ts}_${Date.now()}${ext}`);
            fs.renameSync(f.filePath, dest);
          }
        } catch { /* 既に無ければ無視 */ }
        // サムネイルは再生成可能なため退避せず削除のみでよい。
        if (f.thumbnailPath) { try { fs.unlinkSync(f.thumbnailPath); } catch { /**/ } }
      }

      // NcFile以外の子テーブルはonDelete未設定(FK制約)のため、先に明示削除する。
      await tx.changeHistory.deleteMany({ where: { ncProgramId: ncId } });
      await tx.operationLog.deleteMany({ where: { ncProgramId: ncId } });
      await tx.workRecord.deleteMany({ where: { ncProgramId: ncId } });
      await tx.setupSheetLog.deleteMany({ where: { ncProgramId: ncId } });
      await tx.workSession.deleteMany({ where: { ncProgramId: ncId } });

      const kId = nc.machiningId;
      await tx.ncProgram.delete({ where: { id: ncId } }); // NcFileはonDelete:Cascadeで自動削除

      // 同じK_id(共通部品)を他のNcProgramが参照していなければ、
      // NcMachiningDetail自体も削除しK_idを完全に解放する(NcToolはonDelete:Cascadeで自動削除)。
      const remaining = await tx.ncProgram.count({ where: { machiningId: kId } });
      if (remaining === 0) {
        await tx.ncMachiningDetail.delete({ where: { kId } });
      }

      return { nc_id: ncId, released_k_id: kId, released: true, message: '仮登録を破棄し、加工ID(K_id)を解放しました' };
    });
  }

  // ══════════════════════════════════════════
  // [v087] 共通部品: 加工グループ取得 (MC側 getCommonGroup と同等)
  // ══════════════════════════════════════════
  async getCommonGroup(machiningId: number) {
    return this.prisma.ncProgram.findMany({
      where:   { machiningId },
      orderBy: { id: 'asc' },
      include: {
        part:      { select: { drawingNo: true, name: true, clientName: true } },
        machining: { select: { version: true, machine: { select: { machineCode: true } } } },
      },
    });
  }

  // ══════════════════════════════════════════
  // [v087] 共通部品: 検索 (MC側 searchCommonParts と同等)
  // ══════════════════════════════════════════
  async searchCommonParts(params: {
    drawing_no?:   string;
    name?:         string;
    main_model?:   string;
    client_id?:    number;
    part_id_str?:  string;
    nc_id?:        number;
    machining_id?: number;
    page?:         number;
    limit?:        number;
  }) {
    const { page = 1, limit = 50 } = params;
    const offset = (page - 1) * limit;

    // 同一machining_id(K_id)に複数のNcProgram行が存在するもの(共通部品)を抽出
    const dupeRaw = await this.prisma.$queryRaw<Array<{ machining_id: bigint }>>`
      SELECT machining_id FROM nc_programs
      GROUP BY machining_id HAVING COUNT(*) > 1
    `;
    const dupeMachiningIds = dupeRaw.map((r: any) => Number(r.machining_id));

    const where: any = {
      OR: [
        { machining: { commonPartCode: { not: null } } },
        { machiningId: { in: dupeMachiningIds.length ? dupeMachiningIds : [-1] } },
      ],
    };
    if (params.drawing_no)
      where.part = { ...where.part, drawingNo: { contains: params.drawing_no, mode: 'insensitive' } };
    if (params.name)
      where.part = { ...where.part, name: { contains: params.name, mode: 'insensitive' } };
    if (params.main_model)
      where.part = { ...where.part, mainModel: { contains: params.main_model, mode: 'insensitive' } };
    if (params.client_id)
      where.part = { ...where.part, clientId: params.client_id };
    if (params.part_id_str)
      where.part = { ...where.part, partId: params.part_id_str };
    if (params.nc_id)
      where.id = params.nc_id;
    if (params.machining_id)
      where.machiningId = params.machining_id;

    const [rows, total] = await Promise.all([
      this.prisma.ncProgram.findMany({
        where, skip: offset, take: limit,
        orderBy: { machiningId: 'asc' },
        include: {
          part:      { select: { partId: true, drawingNo: true, name: true, mainModel: true, clientName: true } },
          machining: { select: { version: true, commonPartCode: true } },
        },
      }),
      this.prisma.ncProgram.count({ where }),
    ]);

    // グループ件数付与
    const mIds = [...new Set(rows.map(r => r.machiningId))];
    const groupCounts = mIds.length
      ? await this.prisma.ncProgram.groupBy({ by: ['machiningId'], where: { machiningId: { in: mIds } }, _count: true })
      : [];
    const cntMap: Record<number, number> = {};
    groupCounts.forEach((g: any) => { cntMap[g.machiningId] = g._count; });

    return {
      total, page, limit,
      data: rows.map(r => ({
        ncProgramId:    r.id,
        machiningId:    r.machiningId,
        legacyNcId:     r.legacyNcId  ?? null,
        partId:         r.part.partId ?? null,
        drawingNo:      r.part.drawingNo,
        name:           r.part.name,
        mainModel:      r.part.mainModel  ?? null,
        clientName:     r.part.clientName ?? null,
        version:        r.machining?.version        ?? '1.0001',
        status:         r.status,
        commonPartCode: r.machining?.commonPartCode ?? null,
        groupCount:     cntMap[r.machiningId] ?? 1,
      })),
    };
  }

  // ══════════════════════════════════════════
  // [v087] 共通部品: 登録（供用） (MC側 registerCommonPart と同等)
  // ══════════════════════════════════════════
  async registerCommonPart(dto: {
    target_part_id:      number;
    source_machining_id: number;
    note?:               string;
  }, operatorId: number) {
    const { target_part_id, source_machining_id, note } = dto;

    const mach = await this.prisma.ncMachiningDetail.findUnique({ where: { kId: source_machining_id } });
    if (!mach) throw new NotFoundException(`machining_id ${source_machining_id} が存在しません`);

    const part = await this.prisma.part.findUnique({ where: { id: target_part_id } });
    if (!part) throw new NotFoundException(`part_id ${target_part_id} が存在しません`);

    // 自己参照チェック
    const srcProg = await this.prisma.ncProgram.findFirst({ where: { machiningId: source_machining_id } });
    if (srcProg?.partId === target_part_id)
      throw new Error('供用元と供用先の部品IDが同じです');

    // 重複チェック
    const dup = await this.prisma.ncProgram.findFirst({ where: { partId: target_part_id, machiningId: source_machining_id } });
    if (dup) throw new Error(`部品ID:${target_part_id} にはすでに加工ID:${source_machining_id} が登録されています`);

    const version = mach.version ?? '1.0001';

    return this.prisma.$transaction(async (tx) => {
      // [v087] NC-04(新規登録)と同様、legacyNcId(旧ACC_NC.NC_id)は新規に採番せず
      //   nullのままとする。旧システムのNC_id体系を新規継続する仕様は既存の
      //   NC-04(新規登録)にも存在しないため、既存実装との一貫性を優先した。
      const newProg = await tx.ncProgram.create({
        data: {
          partId:       target_part_id,
          machiningId:  source_machining_id,
          status:       'APPROVED',
          registeredBy: operatorId,
        },
      });

      // common_part_code 未設定なら付与 (MC側と同じ採番規則: CP + K_id 6桁ゼロ埋め)
      if (!mach.commonPartCode) {
        const code = `CP${String(source_machining_id).padStart(6, '0')}`;
        await tx.ncMachiningDetail.update({
          where: { kId: source_machining_id },
          data:  { commonPartCode: code },
        });
      }

      // NcProgramにはnoteカラムが無いため、変更履歴のcontentに含める
      await tx.changeHistory.create({
        data: {
          ncProgramId:   newProg.id,
          changeType:    'CHANGE',
          operatorId,
          versionBefore: null,
          versionAfter:  version,
          content:       `共通登録: 部品ID=${target_part_id} に machining_id=${source_machining_id} を供用${note ? ` (${note})` : ''}`,
        },
      });

      return {
        ncProgramId:    newProg.id,
        machiningId:    source_machining_id,
        targetPartId:   target_part_id,
        version,
        commonPartCode: mach.commonPartCode ?? `CP${String(source_machining_id).padStart(6, '0')}`,
      };
    });
  }

  // ══════════════════════════════════════════
  // [v087] 共通部品: 解除 (MC側 unregisterCommonPart と同等)
  // ══════════════════════════════════════════
  async unregisterCommonPart(ncProgramId: number, operatorId: number) {
    const prog = await this.prisma.ncProgram.findUnique({ where: { id: ncProgramId } });
    if (!prog) throw new NotFoundException(`nc_program_id ${ncProgramId} が存在しません`);

    const groupCount = await this.prisma.ncProgram.count({ where: { machiningId: prog.machiningId } });
    if (groupCount <= 1)
      throw new Error('共通グループの最後の1件は解除できません');

    return this.prisma.$transaction(async (tx) => {
      await tx.changeHistory.create({
        data: {
          ncProgramId,
          changeType:  'CHANGE',
          operatorId,
          content:     `共通登録解除: nc_program_id=${ncProgramId}`,
        },
      });
      await tx.ncProgram.delete({ where: { id: ncProgramId } });
      return { message: '共通登録を解除しました', ncProgramId };
    });
  }

  /** NC-05: 更新（MC方式: ステータスをCHANGINGにするのみ。履歴登録はfinalize()で行う） */
  async update(id: number, dto: UpdateNcDto, operatorId: number) {
    const existing = await this.prisma.ncProgram.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException(`NC_id ${id} が存在しません`);

    // 既存データのmachining_id取得
    const existingWithMachining = await this.prisma.ncProgram.findUnique({
      where: { id },
      include: { machining: true },
    });
    if (!existingWithMachining) throw new NotFoundException(`NC_id ${id} が存在しません`);
    const existingM = existingWithMachining.machining;

    const updated = await this.prisma.$transaction(async (tx) => {
      // 加工データ(NcMachiningDetail)を更新
      await tx.ncMachiningDetail.update({
        where: { kId: existingWithMachining.machiningId },
        data: {
          machineId:    dto.machine_id     !== undefined ? dto.machine_id     : existingM.machineId,
          machiningTime: dto.machining_time !== undefined ? dto.machining_time : existingM.machiningTime,
          folderName:   dto.folder_name    ?? existingM.folderName,
          fileName:     dto.file_name      ?? existingM.fileName,
          clampNote:    dto.clamp_note     !== undefined ? dto.clamp_note     : existingM.clampNote,
          clampAllowance: dto.clamp_allowance !== undefined ? dto.clamp_allowance : existingM.clampAllowance,
          // [v096] MC側update()との機能パリティのため追加。
          creatorId:      dto.creator_id      !== undefined ? dto.creator_id      : existingM.creatorId,
          sheetCreatedAt: dto.sheet_created_at !== undefined
            ? (dto.sheet_created_at ? new Date(dto.sheet_created_at) : null)
            : existingM.sheetCreatedAt,
        },
      });
      // NcProgramのステータスを更新。
      // [v096] 「入力日」「オペレーター」は実際にこの保存操作を行った
      // 認証済みユーザー・時刻を都度反映する(旧ACCESS仕様準拠、MCと統一)。
      const result = await tx.ncProgram.update({
        where: { id },
        data: { status: "CHANGING", registeredBy: operatorId, registeredAt: new Date() },
      });
      // 変更履歴はfinalize()で登録するためupdateでは登録しない（MC方式）
      await tx.operationLog.create({
        data: { userId: operatorId, ncProgramId: id, actionType: "EDIT_SAVE", metadata: { action: "update" } },
      });
      return result;
    });

    return { nc_id: id, version: existingM.version, message: "更新しました" };
  }

  // ══════════════════════════════════════════
  // NC-05b: 終了確認（バージョンインクリ + 変更履歴登録）— MC finalize()のロジックを移植
  // ══════════════════════════════════════════
  async finalize(id: number, changeType: string, changeDetail: string | undefined, operatorId: number) {
    const ncWithMachining = await this.prisma.ncProgram.findUnique({
      where:   { id },
      include: { machining: true },
    });
    if (!ncWithMachining) throw new NotFoundException(`NC_id ${id} が存在しません`);
    const nc = ncWithMachining;

    const verStr   = nc.machining?.version ?? "1.0001";
    const verFloat = parseFloat(verStr) || 1.0001;
    const ver1 = Math.floor(verFloat);
    const ver2 = Math.floor(verFloat * 100) - ver1 * 100;
    const ver3 = Math.floor(verFloat * 10000) - ver1 * 10000 - ver2 * 100;
    const isMajor = ["大変更", "新規登録", "試作登録"].includes(changeType);
    const newVerFloat = isMajor
      ? ver1 + 1 + ver3 / 10000
      : ver1 + ver2 / 100 + 0.01 + ver3 / 10000;
    const newVer1    = Math.floor(newVerFloat);
    const newVer2    = Math.round((newVerFloat - newVer1) * 10000);
    const newVersion = `${newVer1}.${String(newVer2).padStart(4, "0")}`;
    const content    = `${changeType}${changeDetail ? " " + changeDetail : ""}`;

    return this.prisma.$transaction(async (tx) => {
      // バージョンはNcMachiningDetail側を更新
      await tx.ncMachiningDetail.update({
        where: { kId: nc.machiningId },
        data:  { version: newVersion },
      });
      // [v093] 編集内容選択(終了確認)完了時は必ず承認待ちに戻す。
      // 旧承認情報は無効化し、再承認を必須とする(旧ACCESS「終了確認」仕様準拠、MC finalize()と統一)。
      // [v096] 「入力日」「オペレーター」も、この終了確認操作を行った
      // 認証済みユーザー・時刻を都度反映する。
      await tx.ncProgram.update({
        where: { id },
        data:  {
          status: "PENDING_APPROVAL", approvedBy: null, approvedAt: null,
          registeredBy: operatorId, registeredAt: new Date(),
        },
      });
      await tx.changeHistory.create({
        data: {
          ncProgramId:   id,
          changeType:    "CHANGE",
          operatorId,
          versionBefore: nc.machining?.version ?? "1.0001",
          versionAfter:  newVersion,
          content,
        },
      });
      return { nc_id: id, version: newVersion, message: `${changeType}として登録しました(承認待ち)` };
    });
  }

  // ══════════════════════════════════════════
  // NC-05c: 変更キャンセル（CHANGING → 前の状態に戻す）— MC revert()のロジックを移植
  // ══════════════════════════════════════════
  async revert(id: number) {
    const nc = await this.prisma.ncProgram.findUnique({ where: { id } });
    if (!nc) throw new NotFoundException(`NC_id ${id} が存在しません`);
    if (nc.status !== "CHANGING") {
      return { nc_id: id, message: "ステータスはCHANGINGではありません", status: nc.status };
    }
    const nextStatus = nc.approvedBy ? "APPROVED" : "NEW";
    await this.prisma.ncProgram.update({
      where: { id },
      data:  { status: nextStatus },
    });
    return { nc_id: id, message: "変更をキャンセルしました", status: nextStatus };
  }

  // ══════════════════════════════════════════
  // NC-06: 承認 — MC approve()のロジックを移植
  // ══════════════════════════════════════════
  async approve(id: number, operatorId: number, password: string) {
    // [v094] 承認資格(canApprove)を持つ本人のパスワードをその場で検証する(MCと統一)。
    await this.authService.verifyApprover(operatorId, password);
    const ncApprove = await this.prisma.ncProgram.findUnique({
      where:   { id },
      include: { machining: { select: { version: true } } },
    });
    if (!ncApprove) throw new NotFoundException(`NC_id ${id} が存在しません`);
    if (ncApprove.status === "APPROVED") {
      throw new Error("既に承認済みです");
    }
    const approveVer = ncApprove.machining?.version ?? "1.0001";
    return this.prisma.$transaction(async (tx) => {
      await tx.ncProgram.update({
        where: { id },
        data: {
          status:     "APPROVED",
          approvedBy: operatorId,
          approvedAt: new Date(),
        },
      });
      await tx.changeHistory.create({
        data: {
          ncProgramId:   id,
          changeType:    "APPROVAL",
          operatorId,
          versionBefore: approveVer,
          versionAfter:  approveVer,
          content:       "承認",
        },
      });
      await tx.operationLog.create({
        data: {
          userId:      operatorId,
          ncProgramId: id,
          actionType:  "EDIT_SAVE",
          metadata:    { action: "approve", version: approveVer },
        },
      });
      return { nc_id: id, message: "承認しました", version: approveVer };
    });
  }

  // ══════════════════════════════════════════
  // ツーリングデータ — MC getTooling()/saveTooling()のロジックを移植
  // ══════════════════════════════════════════
  async getTooling(ncId: number) {
    const prog = await this.prisma.ncProgram.findUnique({
      where:  { id: ncId },
      select: { machiningId: true },
    });
    if (!prog) throw new NotFoundException(`NC_id ${ncId} が存在しません`);
    return this.prisma.ncTool.findMany({
      where:   { machiningId: prog.machiningId },
      orderBy: { sortOrder: "asc" },
    });
  }

  async saveTooling(ncId: number, dto: SaveNcToolingDto, operatorId: number) {
    const nc = await this.prisma.ncProgram.findUnique({ where: { id: ncId } });
    if (!nc) throw new NotFoundException(`NC_id ${ncId} が存在しません`);

    const progForTooling = await this.prisma.ncProgram.findUnique({
      where:  { id: ncId },
      select: { machiningId: true },
    });
    if (!progForTooling) throw new NotFoundException(`NC_id ${ncId} が存在しません`);
    const machiningId = progForTooling.machiningId;

    return this.prisma.$transaction(async (tx) => {
      await tx.ncTool.deleteMany({ where: { machiningId } });
      if (dto.items.length > 0) {
        await tx.ncTool.createMany({
          data: dto.items.map(item => ({
            machiningId,
            sortOrder:   item.sort_order,
            processType: item.process_type ?? null,
            chipModel:   item.chip_model   ?? null,
            holderModel: item.holder_model ?? null,
            noseR:       item.nose_r       ?? null,
            tNumber:     item.t_number     ?? null,
            note:        item.note         ?? null,
          })),
        });
      }
      await tx.operationLog.create({
        data: { userId: operatorId, ncProgramId: ncId, actionType: "EDIT_SAVE", metadata: { action: "save_tooling" } },
      });
      return { nc_id: ncId, count: dto.items.length, message: "ツーリングデータを保存しました" };
    });
  }

  /** NC-09: 変更履歴一覧 */
  async changeHistory(ncProgramId: number) {
    const rows = await this.prisma.changeHistory.findMany({
      where:   { ncProgramId },
      orderBy: { changedAt: "desc" },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id: r.id, changed_at: r.changedAt, change_type: r.changeType,
      change_detail: r.content, ver_before: r.versionBefore,
      ver_after: r.versionAfter, operator_name: r.operator?.name ?? null,
    }));
  }

  /** NC-10: 印刷履歴一覧 */
  async setupSheetLogs(ncProgramId: number, uncollectedOnly = false) {
    const rows = await this.prisma.setupSheetLog.findMany({
      where: {
        ncProgramId,
        ...(uncollectedOnly ? { workCollected: false } : {}),
      },
      orderBy: { printedAt: "desc" },
      include: { operator: { select: { id: true, name: true } } },
    });
    return rows.map(r => ({
      id: r.id, printed_at: r.printedAt, version: r.version ?? null,
      operator_name: r.operator?.name ?? null,
      work_collected: r.workCollected,
      // [v088] MC側と同様、「行方不明にする(mark as lost)」情報を返す。
      //   NC詳細画面側の表示対応は別途(現時点ではNC印刷履歴テーブルに
      //   未回収/紛失バッジ自体がまだ実装されていないため)。
      is_lost:     (r as any).isLost,
      lost_reason: (r as any).lostReason ?? null,
      lost_detail: (r as any).lostDetail ?? null,
      lost_at:     (r as any).lostAt     ?? null,
    }));
  }

  /** 操作ログ一覧（USB_DOWNLOAD/FILE_UPLOAD/FILE_DELETE/SESSION_START/END のみ） */
  async operationLogs(ncProgramId: number) {
    const rows = await this.prisma.operationLog.findMany({
      where: {
        ncProgramId,
        actionType: { in: ['USB_DOWNLOAD', 'FILE_UPLOAD', 'FILE_DELETE', 'SESSION_START', 'SESSION_END'] as any[] },
      },
      orderBy: { createdAt: 'desc' },
      include: { user: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:          r.id,
      action_type: r.actionType,
      user_name:   r.user?.name ?? null,
      session_id:  r.sessionId,
      metadata:    r.metadata,
      created_at:  r.createdAt,
    }));
  }

  /** FIL-01: ファイル一覧 */
  // [v085] 加工ID(machiningId/K_id)を共有する「共通部品」の全ncProgramIdを解決する。
  //   1つのK_idに複数のNcProgram行が存在しうる(共通部品)ため、写真・図面ファイルの
  //   一覧・件数は特定のncProgramIdだけでなく、同じK_idを共有する全ncProgramIdを
  //   またいで扱う必要がある。これを怠ると、共通部品の一部の行からアップロードした
  //   写真・図面が、別の行を開いたときに見えない(＝消えたように見える)不具合が発生する。
  private async resolveSiblingNcProgramIds(ncProgramId: number): Promise<number[]> {
    const prog = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { machiningId: true },
    });
    if (!prog) return [ncProgramId];
    const siblings = await this.prisma.ncProgram.findMany({
      where:  { machiningId: prog.machiningId },
      select: { id: true },
    });
    return siblings.map(s => s.id);
  }

  async listFiles(ncProgramId: number) {
    const ids = await this.resolveSiblingNcProgramIds(ncProgramId);
    const rows = await this.prisma.ncFile.findMany({
      // ★重複登録バグ防止(MC側と同方式): purgeExistingProgramFilesでisDeleted化された
      //   古いPROGRAM系レコードを一覧から除外する。
      where:   { ncProgramId: { in: ids }, isDeleted: false },
      orderBy: { uploadedAt: 'desc' },
      include: { uploader: { select: { name: true } } },
    });
    return rows.map(r => ({
      id:             r.id,
      file_type:      r.fileType,
      original_name:  r.originalName,
      stored_name:    r.storedName,
      mime_type:      r.mimeType,
      file_size:      r.fileSize,
      file_path:      r.filePath,
      thumbnail_path: r.thumbnailPath,
      uploaded_by:    r.uploader?.name ?? null,
      uploaded_at:    r.uploadedAt,
    }));
  }

    /** PRT-03: ダイレクト印刷 */
  async directPrint(
    ncProgramId: number,
    operatorId: number,
    options: { include_tools?: boolean; include_clamp?: boolean; include_drawings?: boolean },
  ): Promise<{ message: string }> {
    // プリンタ名取得
    const setting = await this.prisma.companySetting.findFirst({ select: { printerName: true } });
    const printerName = setting?.printerName;
    if (!printerName) throw new Error('プリンタが設定されていません。管理者設定で設定してください。');

    // PDF生成
    const pdfBuffer = await this.generateSetupSheetPdf(ncProgramId, operatorId, options);

    // 一時ファイルに書き出してlpで印刷
    const tmpPath = `/tmp/machcore-print-${ncProgramId}-${Date.now()}.pdf`;
    fs.writeFileSync(tmpPath, pdfBuffer);
    try {
      execSync(`lp -d ${printerName} -o media=A4 -o fit-to-page "${tmpPath}"`, { timeout: 15000 });
    } finally {
      try { fs.unlinkSync(tmpPath); } catch {}
    }
    return { message: `${printerName} に送信しました` };
  }

  /** SSL-01: 段取シート回収済みマーク */
  async collectSetupSheet(logId: number) {
    await this.prisma.setupSheetLog.update({
      where: { id: logId },
      data: { workCollected: true },
    });
    return { message: "段取シートを回収済みにしました" };
  }

  /** WR-01: 作業記録一覧 */
  async workRecords(ncProgramId: number) {
    const rows = await this.prisma.workRecord.findMany({
      where:   { ncProgramId },
      orderBy: { workDate: "desc" },
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    return rows.map(r => ({
      id: r.id, work_date: r.workDate, operator_name: r.operator?.name ?? null,
      machine_code: r.machine?.machineCode ?? null,
      machine_id: r.machineId,
      setup_time: r.setupTimeMin, machining_time: r.machiningTimeMin,
      cycle_time_sec: r.cycleTimeSec,
      quantity: r.quantity, note: r.note,
      interruption_time_min: r.interruptionTimeMin,
      work_type: r.workType,
      setup_operator_ids:      r.setupOperatorIds,
      production_operator_ids: r.productionOperatorIds,
    }));
  }
 

  /** WR-単件: 作業記録1件取得（編集モード用） */
  async findWorkRecord(ncProgramId: number, recordId: number) {
    const r = await this.prisma.workRecord.findFirst({
      where:   { id: recordId, ncProgramId },
      include: {
        operator: { select: { name: true } },
        machine:  { select: { machineCode: true } },
      },
    });
    if (!r) throw new NotFoundException(`work_record id:${recordId} が存在しません`);
    return {
      id:                   r.id,
      work_date:            r.workDate,
      operator_name:        r.operator?.name ?? null,
      machine_code:         r.machine?.machineCode ?? null,
      machine_id:           r.machineId,
      setup_time:           r.setupTimeMin,
      machining_time:       r.machiningTimeMin,
      cycle_time_sec:       r.cycleTimeSec,
      quantity:             r.quantity,
      interruption_time_min: r.interruptionTimeMin,
      work_type:            r.workType,
      note:                 r.note,
      setup_operator_ids:      r.setupOperatorIds,
      production_operator_ids: r.productionOperatorIds,
    };
  }

  /** WR-02: 作業記録 新規登録 */
  async createWorkRecord(
    ncProgramId: number,
    dto: CreateWorkRecordDto,
    operatorId: number,
  ) {
    // nc_program が存在するか確認
    const nc = await this.prisma.ncProgram.findUnique({
      where: { id: ncProgramId },
    });
    if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);
    // [仮登録] 「作業完了（登録）」で確定するまで作業記録は登録させない。
    if (nc.status === 'PROVISIONAL') {
      throw new ForbiddenException('この新規登録はまだ確定していません。「変更・登録」で「作業完了（登録）」を行ってください。');
    }
 
    // 使用機械: dto.machine_id → machining.machineId → null の優先順
    const ncWithMachiningForWR = await this.prisma.ncProgram.findUnique({
      where:  { id: ncProgramId },
      select: { machining: { select: { machineId: true } } },
    });
    const machineId = dto.machine_id ?? ncWithMachiningForWR?.machining?.machineId ?? null;
 
    const record = await this.prisma.workRecord.create({
      data: {
        ncProgramId,
        operatorId,
        machineId,
        workDate:            (() => { const n = new Date(); const jst = new Date(n.getTime() + 9*60*60*1000); return new Date(`${jst.getUTCFullYear()}-${String(jst.getUTCMonth()+1).padStart(2,'0')}-${String(jst.getUTCDate()).padStart(2,'0')}T00:00:00Z`); })(),
        setupTimeMin:        dto.setup_time_min        ?? null,
        machiningTimeMin:    dto.machining_time_min    ?? null,
        cycleTimeSec:        dto.cycle_time_sec        ?? null,
        quantity:            dto.quantity              ?? null,
        interruptionTimeMin: dto.interruption_time_min ?? null,
        workType:            dto.work_type             ?? null,
        note:                dto.note                  ?? null,
        setupOperatorIds:      dto.setup_operator_ids      ?? [],
        productionOperatorIds: dto.production_operator_ids ?? [],
      },
    });
 
    return {
      id:      record.id,
      message: '作業記録を登録しました',
    };
  }
  /** WR-03: 作業記録 更新 */
  async updateWorkRecord(
    ncProgramId: number,
    recordId: number,
    dto: UpdateWorkRecordDto,
    operatorId: number,
  ) {
    const record = await this.prisma.workRecord.findFirst({
      where: { id: recordId, ncProgramId },
    });
    if (!record) throw new NotFoundException(`work_record id:${recordId} が存在しません`);

    const updated = await this.prisma.workRecord.update({
      where: { id: recordId },
      data: {
        setupTimeMin:        dto.setup_time_min        !== undefined ? dto.setup_time_min        : record.setupTimeMin,
        machiningTimeMin:    dto.machining_time_min    !== undefined ? dto.machining_time_min    : record.machiningTimeMin,
        cycleTimeSec:        dto.cycle_time_sec        !== undefined ? dto.cycle_time_sec        : record.cycleTimeSec,
        quantity:            dto.quantity              !== undefined ? dto.quantity              : record.quantity,
        interruptionTimeMin: dto.interruption_time_min !== undefined ? dto.interruption_time_min : record.interruptionTimeMin,
        workType:            dto.work_type             !== undefined ? dto.work_type             : record.workType,
        note:                dto.note                 !== undefined ? dto.note                  : record.note,
        machineId:           dto.machine_id            !== undefined ? dto.machine_id            : record.machineId,
        setupOperatorIds:      dto.setup_operator_ids      !== undefined ? dto.setup_operator_ids      : (record.setupOperatorIds as any ?? []),
        productionOperatorIds: dto.production_operator_ids !== undefined ? dto.production_operator_ids : (record.productionOperatorIds as any ?? []),
      },
    });

    await this.prisma.operationLog.create({
      data: {
        userId:      operatorId,
        ncProgramId,
        actionType:  "EDIT_SAVE",
        metadata:    { action: "update_work_record", recordId },
      },
    });

    return { id: updated.id, message: "作業記録を更新しました" };
  }

  /** WR-04: 作業記録 削除 */
  async deleteWorkRecord(
    ncProgramId: number,
    recordId: number,
    operatorId: number,
  ) {
    const record = await this.prisma.workRecord.findFirst({
      where: { id: recordId, ncProgramId },
    });
    if (!record) throw new NotFoundException(`work_record id:${recordId} が存在しません`);

    await this.prisma.workRecord.delete({ where: { id: recordId } });

    await this.prisma.operationLog.create({
      data: {
        userId:      operatorId,
        ncProgramId,
        actionType:  "EDIT_SAVE",
        metadata:    { action: "delete_work_record", recordId },
      },
    });

    return { message: "作業記録を削除しました" };
  }

  // ── NC-07: 段取シートデータ取得 ─────────────────────────────────
async getPrintData(ncProgramId: number) {
  const nc = await this.prisma.ncProgram.findUnique({
    where: { id: ncProgramId },
    include: {
      part:     true,
      machining: {
        include: {
          machine: true,
          tools:   { orderBy: { sortOrder: 'asc' } },
        },
      },
      registrar: { select: { id: true, name: true } },
      approver:  { select: { id: true, name: true } },
      files: {
        where:   { fileType: 'DRAWING' },
        orderBy: { uploadedAt: 'desc' },
      },
    },
  });
  if (!nc) throw new NotFoundException(`NC_id ${ncProgramId} が存在しません`);
  // [仮登録] 「作業完了（登録）」で確定するまで段取シートは発行させない。
  if (nc.status === 'PROVISIONAL') {
    throw new ForbiddenException('この新規登録はまだ確定していません。「変更・登録」で「作業完了（登録）」を行ってください。');
  }
  // buildSetupSheetHtmlとの互換性のためにフラット展開したオブジェクトを返す
  return {
    ...nc,
    machine:      nc.machining?.machine   ?? null,
    tools:        nc.machining?.tools     ?? [],
    processL:     nc.machining?.processL  ?? null,
    version:      nc.machining?.version   ?? null,
    folderName:   nc.machining?.folderName ?? '',
    fileName:     nc.machining?.fileName  ?? '',
    oNumber:      nc.machining?.oNumber   ?? null,
    clampNote:    nc.machining?.clampNote ?? null,
    clampAllowance: nc.machining?.clampAllowance ?? null,
    machiningTime: nc.machining?.machiningTime ?? null,
    processingId: nc.machining?.processingId ?? null,
  };
}

// ── NC-08: 段取シートPDF生成（Puppeteer） ───────────────────────
async generateSetupSheetPdf(
  ncProgramId: number,
  operatorId:  number,
  options:     { include_tools?: boolean; include_clamp?: boolean; include_drawings?: boolean },
): Promise<Buffer> {
  const data = await this.getPrintData(ncProgramId);

  // Puppeteer 動的インポート
  const puppeteer = (await import('puppeteer')).default;
  const browser   = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  try {
    const page = await browser.newPage();
    // 図ファイルをBase64に変換（include_drawings=true の場合）
    const drawingBase64s: string[] = [];
    if (options.include_drawings === true && data.files && data.files.length > 0) {
      const sharpLib = (await import('sharp')).default;
      for (const f of (data.files as any[]).slice(0, 3)) {
        try {
          const filePath: string = f.filePath ?? f.file_path ?? '';
          if (!filePath || !fs.existsSync(filePath)) continue;
          const buf = fs.readFileSync(filePath);
          const mime: string = f.mimeType ?? f.mime_type ?? '';
          if (mime.includes('tiff') || mime.includes('tif')) {
            const imgBuf = await sharpLib(buf).png().toBuffer();
            drawingBase64s.push('data:image/png;base64,' + imgBuf.toString('base64'));
          } else if (!mime.includes('pdf')) {
            drawingBase64s.push('data:' + mime + ';base64,' + buf.toString('base64'));
          }
        } catch (e: any) {
          console.warn('Drawing embed failed:', e?.message);
        }
      }
    }
    const html = this.buildSetupSheetHtml(data, { ...options, drawingBase64s });
    await page.setContent(html, { waitUntil: 'domcontentloaded', timeout: 15000 });

    const pdfUint8 = await page.pdf({
      format:          'A4',
      printBackground: true,
      margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' },
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `
        <div style="font-size:8px;width:100%;text-align:center;color:#888;font-family:sans-serif;">
          <span class="pageNumber"></span> / <span class="totalPages"></span>
        </div>`,
    });

    const pdfBuffer = Buffer.from(pdfUint8);

    // SetupSheetLog INSERT（エラーはログのみ）
    await this.prisma.setupSheetLog.create({
      data: { ncProgramId, operatorId, version: (data as any)?.machining?.version ?? (data as any)?.version ?? null },
    }).catch(e => console.warn('SetupSheetLog insert failed:', e.message));

    return pdfBuffer;
  } finally {
    await browser.close();
  }
}

// ── HTMLテンプレートビルダー ────────────────────────────────────
private buildSetupSheetHtml(data: any, opts: any): string {
  const includeTools    = opts.include_tools    !== false;
  const includeClamp    = opts.include_clamp    !== false;
  const includeDrawings = opts.include_drawings === true;
  const drawingBase64s: string[] = opts.drawingBase64s ?? [];

  const now    = new Date();
  const fmtNow = `${now.getFullYear()}/${String(now.getMonth()+1).padStart(2,'0')}/${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const fmtDate = (d: string | null | undefined) => {
    if (!d) return '';
    try { const dt = new Date(d); return `${dt.getFullYear()}/${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`; }
    catch { return d; }
  };

  const toolRows = (includeTools && data.tools && data.tools.length > 0) ? data.tools.map((t: any) => `
    <tr style="page-break-inside:avoid;">
      <td class="c">${t.sortOrder ?? ''}</td>
      <td>${t.processType ?? ''}</td>
      <td class="mono">${t.chipModel ?? ''}</td>
      <td class="mono">${t.holderModel ?? ''}</td>
      <td class="c">${t.noseR ?? ''}</td>
      <td>${t.note ?? ''}</td>
    </tr>`).join('') : '<tr><td colspan="6" class="c" style="color:#aaa;font-size:8pt;padding:4px;">加工データなし</td></tr>';

  const drawingsHtml = (includeDrawings && drawingBase64s.length > 0)
    ? `<div style="margin-top:8px;page-break-inside:avoid;"><div class="sh">段取図</div>
       <div style="display:flex;flex-wrap:wrap;gap:8px;">
         ${drawingBase64s.map((src: string, i: number) => `<img src="${src}" alt="段取図${i+1}" style="max-width:49%;height:auto;border:1px solid #ccc;" />`).join('')}
       </div></div>` : '';

  const machTimeMin = data.machiningTime ?? 0;
  const machM = Math.floor(machTimeMin);
  const machS = Math.round((machTimeMin - machM) * 60);
  const machTimeStr = `${machM} M ${String(machS).padStart(2,'0')} S`;

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Noto Sans JP', sans-serif; font-size: 9pt; color: #000; background: #fff; padding: 8mm; }
  h1.title { font-size: 14pt; font-weight: 700; margin-bottom: 4px; }
  .id-row { font-size: 8pt; color: #444; margin-bottom: 6px; }
  table.info { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.info td { border: 1px solid #999; padding: 2px 5px; font-size: 9pt; vertical-align: middle; }
  table.info td.lbl { background: #e8e8e8; font-weight: 700; width: 80px; white-space: nowrap; }
  table.info td.val { }
  .備考box { background: #fffde7; border: 1px solid #ccc; padding: 4px 6px; font-size: 8.5pt;
              white-space: pre-wrap; min-height: 28px; margin-bottom: 4px; }
  table.sign { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.sign td { border: 1px solid #999; padding: 2px 5px; font-size: 8.5pt; }
  table.sign td.lbl { background: #e8e8e8; font-weight: 700; white-space: nowrap; }
  table.work { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.work td { border: 1px solid #999; padding: 3px 5px; font-size: 8.5pt; height: 22px; }
  table.work td.lbl { background: #e8e8e8; font-weight: 700; white-space: nowrap; width: 70px; }
  .sh { font-size: 8.5pt; font-weight: 700; background: #1e3a5f; color: #fff; padding: 2px 6px; margin-bottom: 1px; }
  table.tools { width: 100%; border-collapse: collapse; }
  table.tools th { background: #1e3a5f; color: #fff; font-weight: 700; padding: 3px 5px;
                   border: 1px solid #7a9cbf; font-size: 8.5pt; text-align: left; }
  table.tools td { border: 1px solid #ccc; padding: 2.5px 5px; font-size: 8.5pt; vertical-align: top; }
  table.tools tr:nth-child(even) td { background: #f5f5f5; }
  .c { text-align: center; }
  .mono { font-family: 'Courier New', monospace; }
  .foot { margin-top: 8px; padding-top: 4px; border-top: 1px solid #ccc;
          display: flex; justify-content: space-between; font-size: 7.5pt; color: #666; }
  @media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }
</style>
</head>
<body>
  <!-- タイトル行 -->
  <table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
    <tr>
      <td style="vertical-align:bottom;">
        <h1 class="title">NC段取シート</h1>
      </td>
      <td style="text-align:right;vertical-align:bottom;font-size:8pt;color:#555;">
        出力日時: ${fmtNow}
      </td>
    </tr>
  </table>

  <!-- ID行 -->
  <div class="id-row">
    NC_id <strong>${data.id}</strong>
    &nbsp;&nbsp;部品id <strong>${data.part?.partId ?? '—'}</strong>
    &nbsp;&nbsp;加工id <strong>${data.processingId ?? '—'}</strong>
  </div>

  <!-- 部品情報テーブル -->
  <table class="info">
    <tr>
      <td class="lbl">納入先</td>
      <td colspan="3">${data.part?.clientName ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">図面番号</td>
      <td>${data.part?.drawingNo ?? ''}</td>
      <td class="lbl" style="width:70px;">名　称</td>
      <td>${data.part?.name ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">主機種型式</td>
      <td colspan="3">${data.part?.machineType ?? data.machineType ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">Ｌ</td>
      <td style="width:60px;"><strong>${data.processL ?? ''}</strong></td>
      <td class="lbl">機　械</td>
      <td>${data.machine?.machineCode ?? ''}</td>
    </tr>
    <tr>
      <td class="lbl">タ イ ム</td>
      <td><strong>${machTimeStr}</strong></td>
      <td class="lbl">承認ステ</td>
      <td>${data.status === 'APPROVED' ? '承認済' : data.status === 'CHANGING' ? '変更中' : data.status === 'PENDING_APPROVAL' ? '未承認' : '新規'}</td>
    </tr>
    <tr>
      <td class="lbl">ﾌｧｲﾙ名</td>
      <td>${data.fileName ?? ''}</td>
      <td class="lbl">ｏﾅﾝﾊﾞｰ</td>
      <td><strong>${data.oNumber ?? ''}</strong></td>
    </tr>
    <tr>
      <td class="lbl">掴　代</td>
      <td colspan="3">${data.clampAllowance ? `${data.clampAllowance} mm` : ''}</td>
    </tr>
    <tr>
      <td class="lbl">FD名 / USB</td>
      <td colspan="3">${data.folderName ?? ''}</td>
    </tr>
  </table>

  ${includeClamp && data.clampNote ? `
  <!-- 備考 -->
  <div style="margin-bottom:4px;">
    <div class="sh" style="margin-bottom:0;">備　考</div>
    <div class="備考box">${(data.clampNote ?? '').replace(/\n/g, '<br/>')}</div>
  </div>` : ''}


  ${includeTools ? `
  <!-- 加工リスト -->
  <div class="sh">加工リスト</div>
  <table class="tools">
    <thead>
      <tr>
        <th class="c" style="width:28px;">No</th>
        <th style="width:90px;">加　工</th>
        <th style="width:70px;">形　状</th>
        <th>ホルダー</th>
        <th class="c" style="width:50px;">ノーズR</th>
        <th>備　考</th>
      </tr>
    </thead>
    <tbody>${toolRows}</tbody>
  </table>` : ''}

  <!-- Ver / 承認者 -->
  <table class="sign">
    <tr>
      <td class="lbl">Ver</td>
      <td style="width:80px;">${data.version ?? ''}</td>
      <td class="lbl">承認者</td>
      <td>${data.approver?.name ?? ''}</td>
      <td class="lbl">承認日</td>
      <td>${fmtDate(data.approvedAt)}</td>
    </tr>
  </table>

  <!-- 段取担当 / 量産担当 -->
  <table class="work">
    <tr>
      <td class="lbl">段取担当</td>
      <td style="min-width:100px;">&nbsp;</td>
      <td class="lbl">量産担当</td>
      <td style="min-width:100px;">&nbsp;</td>
      <td class="lbl">個　数</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td class="lbl">段取時間</td>
      <td><span style="color:#aaa;font-size:8pt;">&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;&nbsp;&nbsp;&nbsp;m</span></td>
      <td class="lbl">量産時間</td>
      <td><span style="color:#aaa;font-size:8pt;">&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;&nbsp;&nbsp;&nbsp;m</span></td>
      <td class="lbl">入　力</td>
      <td>&nbsp;</td>
    </tr>
  </table>

  <!-- 変更届 -->
  <table class="work" style="margin-bottom:4px;">
    <tr>
      <td class="lbl" style="width:60px;">変更届</td>
      <td>
        シート&nbsp;□&nbsp;&nbsp;
        プログラム&nbsp;□&nbsp;&nbsp;
        図&nbsp;□&nbsp;&nbsp;
        写真&nbsp;□
      </td>
    </tr>
    <tr>
      <td class="lbl">内　容</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td class="lbl">掴　代</td>
      <td><span style="margin-right:30px;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; mm</span>FD名&nbsp;&nbsp;&nbsp;${data.folderName ?? ''}</td>
    </tr>
  </table>

  ${drawingsHtml}

  <!-- フッター -->
  <div class="foot">
    <span>NC旋盤プログラム管理システム MachCore</span>
    <span>図面番号: ${data.part?.drawingNo ?? ''} | 部品ID: ${data.part?.partId ?? ''} | NC_id: ${data.id}</span>
  </div>
</body>
</html>`;
}

  // ─────────────────────────────────────────────────────────
  // PG ファイル関連  NC-06 / NC-06b
  // ─────────────────────────────────────────────────────────

  /** ファイルパス解決（company_settings.upload_base_path / folderName / fileName） */
  private async resolvePgFilePath(
    nc: { id: number; fileName: string; folderName?: string | null },
  ): Promise<string> {
    const setting = await this.prisma.companySetting.findFirst();
    const base =
      setting?.uploadBasePath ??
      '/home/karkyon/projects/machcore/uploads';
    if (nc.folderName) {
      return path.join(base, '\uff8c\uff9f\uff9b\uff78\uff9e\uff97\uff91', nc.folderName, nc.fileName);
    }
    return path.join(base, 'nc_files', String(nc.id), 'pg', nc.fileName);
  }

  /** NC-06: PGファイル読込（chardet でエンコード自動検出 → UTF-8 変換） */
  async getPgFile(id: number) {
    const ncPg = await this.prisma.ncProgram.findUniqueOrThrow({
      where:  { id },
      include: { machining: { select: { fileName: true, folderName: true } } },
    });
    const nc = { id: ncPg.id, fileName: ncPg.machining?.fileName ?? '', folderName: ncPg.machining?.folderName ?? null };
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(
        `PGファイルが見つかりません: ${nc.fileName}  (確認パス: ${filePath})`,
      );
    }

    const buf = fs.readFileSync(filePath);

    // エンコード検出
    const detected = chardet.detect(buf) ?? 'UTF-8';
    const d = detected.toLowerCase();
    let encoding = 'UTF-8';
    if (d.includes('shift') || d.includes('cp932') || d === 'windows-1252') {
      encoding = 'SJIS';
    } else if (d.includes('euc')) {
      encoding = 'EUC-JP';
    }

    const iconvEnc = encoding === 'SJIS' ? 'CP932' : encoding;
    const content  = iconv.decode(buf, iconvEnc);

    // 改行コード検出
    const lineEnding = content.includes('\r\n')
      ? 'CRLF'
      : content.includes('\r')
      ? 'CR'
      : 'LF';

    return { content, encoding, lineEnding, fileName: nc.fileName };
  }

  /** NC-06b: PGファイル保存（iconv-lite で元エンコードに変換して上書き） */
  async savePgFile(
    id: number,
    content: string,
    encoding = 'UTF-8',
    lineEnding = 'LF',
  ) {
    const ncSavePg = await this.prisma.ncProgram.findUniqueOrThrow({
      where:  { id },
      include: { machining: { select: { fileName: true, folderName: true } } },
    });
    const nc = { id: ncSavePg.id, fileName: ncSavePg.machining?.fileName ?? '', folderName: ncSavePg.machining?.folderName ?? null };
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(`PGファイルが見つかりません: ${nc.fileName}`);
    }

    // 改行コード正規化 → 指定形式に変換
    let text = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (lineEnding === 'CRLF') text = text.replace(/\n/g, '\r\n');
    else if (lineEnding === 'CR')  text = text.replace(/\n/g, '\r');

    // 元エンコードに変換して保存
    const iconvEnc = encoding === 'SJIS' ? 'CP932' : encoding;
    const encoded  = iconv.encode(text, iconvEnc);
    fs.writeFileSync(filePath, encoded);

    return { ok: true };
  }

  /** NC-07: PGファイルダウンロード（バイナリストリーム返却） */
  async downloadPgFile(id: number): Promise<{ buffer: Buffer; fileName: string }> {
    const ncDownPg = await this.prisma.ncProgram.findUniqueOrThrow({
      where:   { id },
      include: { machining: { select: { fileName: true, folderName: true } } },
    });
    const nc = { id: ncDownPg.id, fileName: ncDownPg.machining?.fileName ?? '', folderName: ncDownPg.machining?.folderName ?? null };
    const filePath = await this.resolvePgFilePath(nc);

    if (!fs.existsSync(filePath)) {
      throw new NotFoundException(
        `PGファイルが見つかりません: ${nc.fileName}  (パス: ${filePath})`,
      );
    }

    const buffer = fs.readFileSync(filePath);
    return { buffer, fileName: nc.fileName };
  }



  // ── [v066] ②③ プログラムファイル一覧・個別読み書き(nc_filesテーブル利用) ──
  // 既存のgetPgFile/savePgFile/downloadPgFileは旧resolvePgFilePath方式のまま維持し、
  // こちらはPHASE5で投入済みのnc_filesレコードを直接使う新方式として追加する。
  async listPgFilesNc(ncProgramId: number) {
    const recs = await this.prisma.ncFile.findMany({
      where:   { ncProgramId, fileType: 'PROGRAM' as any, isDeleted: false },
      orderBy: [{ originalName: 'asc' }],
    });
    return recs.map(r => ({
      id:            r.id,
      original_name: r.originalName,
      file_path:     r.filePath,
      file_size:     r.fileSize,
      uploaded_at:   r.uploadedAt,
    }));
  }

  async getPgFileContentByIdNc(fileId: number): Promise<{ content: string; original_name: string }> {
    const rec = await this.prisma.ncFile.findFirst({
      where: { id: fileId, fileType: 'PROGRAM' as any, isDeleted: false },
    });
    if (!rec || !fs.existsSync(rec.filePath)) {
      throw new NotFoundException('ファイルが見つかりません');
    }
    const buf = fs.readFileSync(rec.filePath);
    const detected = chardet.detect(buf) ?? 'UTF-8';
    const d = detected.toLowerCase();
    const iconvEnc = (d.includes('shift') || d.includes('cp932')) ? 'CP932' : 'UTF-8';
    const content = iconv.decode(buf, iconvEnc);
    return { content, original_name: rec.originalName };
  }

  async savePgFileContentByIdNc(fileId: number, content: string): Promise<{ message: string }> {
    const rec = await this.prisma.ncFile.findFirst({
      where: { id: fileId, fileType: 'PROGRAM' as any, isDeleted: false },
    });
    if (!rec || !fs.existsSync(rec.filePath)) {
      throw new NotFoundException('ファイルが見つかりません');
    }
    const buf = iconv.encode(content, 'CP932');
    fs.writeFileSync(rec.filePath, buf);
    return { message: '保存しました' };
  }

  // ── [v076] PG→USBチケット発行用のファイル情報取得(listPgFilesNcを利用) ──
  async getPgFileInfoNc(ncProgramId: number) {
    const files = await this.listPgFilesNc(ncProgramId);
    if (!files || files.length === 0) return null;
    return {
      files: files.map(f => ({ id: f.id, original_name: f.original_name, file_path: f.file_path })),
      fileCount: files.length,
    };
  }
}