import { Injectable } from '@nestjs/common';
import { randomUUID } from 'crypto';

export interface UploadTicketPayload {
  ticket:         string;
  mcId:           number;
  machiningId:    number;
  fileType?:      'PHOTO' | 'DRAWING' | 'PROGRAM';
  replaceFileId?: number;
  isFolderUpload?: boolean;
  isPgToUsb?:     boolean; // PG→USB機能用チケット（UAが直接ファイル情報を取得する）
  userId:         number;
  expiresAt:      number;
  used:           boolean;
  system:         'MC' | 'NC'; // どちらのシステム宛のチケットか（既定は'MC'、後方互換のため）
  // ★重複登録バグ修正: PROGRAM種別のアップロードで、このチケットにおいて既存の古い
  //   PROGRAM系ファイル(DB行+実ファイル)を既にpurge済みかどうかを記録する。
  //   フォルダアップロード用チケットは同一チケットで複数ファイルを順次アップロードする
  //   ため(consume()は同一オブジェクト参照を返す)、最初の1回だけpurgeし、以降は
  //   このフラグを見てスキップすることで、直前にアップロードしたファイル自身を
  //   誤ってpurgeしてしまう事故を防ぐ。
  programPurged?: boolean;
}

const TICKET_TTL_MS_SINGLE = 60_000;       // 単体アップロード: 60秒・1回限り
const TICKET_TTL_MS_FOLDER = 10 * 60_000;  // フォルダアップロード: 10分（グリッド選択のユーザー操作時間を考慮）

@Injectable()
export class UploadTicketService {
  private tickets = new Map<string, UploadTicketPayload>();

  constructor() {
    setInterval(() => this.cleanup(), 30_000).unref();
  }

  issue(params: {
    mcId: number; machiningId: number; userId: number;
    fileType?: 'PHOTO' | 'DRAWING' | 'PROGRAM';
    replaceFileId?: number; isFolderUpload?: boolean; isPgToUsb?: boolean;
    system?: 'MC' | 'NC';
  }): UploadTicketPayload {
    const ttl = params.isFolderUpload ? TICKET_TTL_MS_FOLDER : TICKET_TTL_MS_SINGLE;
    const ticket: UploadTicketPayload = {
      ticket: randomUUID(),
      mcId: params.mcId,
      machiningId: params.machiningId,
      fileType: params.fileType,
      replaceFileId: params.replaceFileId,
      isFolderUpload: params.isFolderUpload,
      isPgToUsb: params.isPgToUsb,
      userId: params.userId,
      expiresAt: Date.now() + ttl,
      used: false,
      system: params.system ?? 'MC',
    };
    this.tickets.set(ticket.ticket, ticket);
    return ticket;
  }

  /**
   * チケットを検証し payload を返す。
   * 単体アップロード用チケットは1回限り（取得と同時に破棄）。
   * フォルダアップロード用チケット（isFolderUpload=true）は有効期限内であれば
   * 複数回 consume 可能（フォルダ内の複数ファイルを同一チケットで順次アップロードするため）。
   */
  consume(ticketId: string): UploadTicketPayload | null {
    const t = this.tickets.get(ticketId);
    if (!t) return null;
    if (Date.now() > t.expiresAt) { this.tickets.delete(ticketId); return null; }

    if (t.isFolderUpload) {
      // フォルダ用チケットは使い回し可。延命はしない（元の60秒のまま）。
      return t;
    }

    // 単体アップロード用チケットは1回限り
    if (t.used) return null;
    t.used = true;
    this.tickets.delete(ticketId);
    return t;
  }

  /**
   * PG→USB専用: チケットを消費せずに参照する（1回限りの破棄はしない）。
   * UA側が「情報取得→コピー実行」の2段階でこのチケットを使うため。
   * 呼び出し元が完了後に明示的に invalidate() で破棄する。
   */
  peek(ticketId: string): UploadTicketPayload | null {
    const t = this.tickets.get(ticketId);
    if (!t) return null;
    if (Date.now() > t.expiresAt) { this.tickets.delete(ticketId); return null; }
    return t;
  }

  /** チケットを即時破棄する（PG→USB完了時に呼ぶ） */
  invalidate(ticketId: string): void {
    this.tickets.delete(ticketId);
  }

  private cleanup() {
    const now = Date.now();
    for (const [id, t] of this.tickets.entries()) {
      if (t.used || now > t.expiresAt) this.tickets.delete(id);
    }
  }
}
