import {
  Controller, Get, Put, Body, UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Roles } from '../common/decorators/roles.decorator';
import { RolesGuard } from '../common/guards/roles.guard';
import { PrismaService } from '../prisma/prisma.service';

/**
 * 多言語対応(i18n)設定 API。
 * - GET  /api/language/config        … 全ユーザー公開。既定言語 + カスタム辞書上書き分を返す。
 * - PUT  /api/language/default       … ADMIN限定。既定言語(ja|vi)を切り替える。
 * - PUT  /api/language/dictionary    … ADMIN限定。指定言語のカスタム辞書をアップロード(丸ごと上書き保存)。
 *
 * カスタム辞書は system_settings テーブルに `custom_dict_ja` / `custom_dict_vi` キーで
 * JSON文字列として保存する(新規テーブル追加なしで実現)。
 * フロントエンドは lib/i18n の標準辞書(ja.json/vi.json)をベースに、
 * ここで取得したカスタム辞書で上書き(ディープマージ)して使用する。
 */
@Controller('language')
export class LanguageController {
  constructor(private readonly prisma: PrismaService) {}

  private async getSetting(key: string): Promise<string | null> {
    const row = await this.prisma.systemSetting.findUnique({ where: { key } });
    return row?.value ?? null;
  }

  private async setSetting(key: string, value: string, description?: string) {
    await this.prisma.systemSetting.upsert({
      where:  { key },
      update: { value },
      create: { key, value, description },
    });
  }

  /** 公開: 現在の言語設定とカスタム辞書を返す（認証不要 = ログイン画面でも切替可能） */
  @Get('config')
  async getConfig() {
    const defaultLang = (await this.getSetting('default_language')) ?? 'ja';
    const customJa = await this.getSetting('custom_dict_ja');
    const customVi = await this.getSetting('custom_dict_vi');
    let parsedJa: Record<string, unknown> | null = null;
    let parsedVi: Record<string, unknown> | null = null;
    try { parsedJa = customJa ? JSON.parse(customJa) : null; } catch { parsedJa = null; }
    try { parsedVi = customVi ? JSON.parse(customVi) : null; } catch { parsedVi = null; }
    return {
      default_language: defaultLang,
      custom_dictionaries: { ja: parsedJa, vi: parsedVi },
    };
  }

  /** ADMIN: 既定言語切替 */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('default')
  async setDefault(@Body() body: { lang: 'ja' | 'vi' }) {
    if (body.lang !== 'ja' && body.lang !== 'vi') {
      return { message: '不正な言語コードです', ok: false };
    }
    await this.setSetting('default_language', body.lang, 'システム既定表示言語(ja|vi)');
    return { message: '既定言語を更新しました', ok: true };
  }

  /** ADMIN: カスタム辞書アップロード（丸ごと上書き保存） */
  @UseGuards(AuthGuard('jwt'), RolesGuard)
  @Roles('ADMIN')
  @Put('dictionary')
  async setDictionary(@Body() body: { lang: 'ja' | 'vi'; dictionary: Record<string, unknown> }) {
    if (body.lang !== 'ja' && body.lang !== 'vi') {
      return { message: '不正な言語コードです', ok: false };
    }
    if (!body.dictionary || typeof body.dictionary !== 'object') {
      return { message: '辞書データが不正です', ok: false };
    }
    const key = body.lang === 'ja' ? 'custom_dict_ja' : 'custom_dict_vi';
    await this.setSetting(key, JSON.stringify(body.dictionary), `カスタム翻訳辞書(${body.lang})`);
    return { message: '辞書を保存しました', ok: true };
  }
}
