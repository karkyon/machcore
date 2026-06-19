import { Injectable } from '@nestjs/common';
import { randomUUID } from 'crypto';

export interface UploadTicketPayload {
  ticket:         string;
  mcId:           number;
  machiningId:    number;
  fileType?:      'PHOTO' | 'DRAWING' | 'PROGRAM';
  replaceFileId?: number;
  isFolderUpload?: boolean;
  userId:         number;
  expiresAt:      number;
  used:           boolean;
}

const TICKET_TTL_MS = 60_000; // 60秒・1回限り

@Injectable()
export class UploadTicketService {
  private tickets = new Map<string, UploadTicketPayload>();

  constructor() {
    setInterval(() => this.cleanup(), 30_000).unref();
  }

  issue(params: {
    mcId: number; machiningId: number; userId: number;
    fileType?: 'PHOTO' | 'DRAWING' | 'PROGRAM';
    replaceFileId?: number; isFolderUpload?: boolean;
  }): UploadTicketPayload {
    const ticket: UploadTicketPayload = {
      ticket: randomUUID(),
      mcId: params.mcId,
      machiningId: params.machiningId,
      fileType: params.fileType,
      replaceFileId: params.replaceFileId,
      isFolderUpload: params.isFolderUpload,
      userId: params.userId,
      expiresAt: Date.now() + TICKET_TTL_MS,
      used: false,
    };
    this.tickets.set(ticket.ticket, ticket);
    return ticket;
  }

  /** チケットを検証し、有効なら即座に破棄して payload を返す（1回限り） */
  consume(ticketId: string): UploadTicketPayload | null {
    const t = this.tickets.get(ticketId);
    if (!t) return null;
    if (t.used) return null;
    if (Date.now() > t.expiresAt) { this.tickets.delete(ticketId); return null; }
    this.tickets.delete(ticketId);
    return t;
  }

  private cleanup() {
    const now = Date.now();
    for (const [id, t] of this.tickets.entries()) {
      if (t.used || now > t.expiresAt) this.tickets.delete(id);
    }
  }
}
