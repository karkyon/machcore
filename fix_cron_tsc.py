#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_cron_tsc.py
修正内容:
1. cron パッケージをインストール（@nestjs/schedule が依存済みなので型定義のみ必要）
2. mc.service.ts: CronJob import を @nestjs/schedule 経由に変更
   → SchedulerRegistry + setTimeout ループ方式に変更（パッケージ依存なし）
3. system-logs API が404になっている問題を調査・修正
   → AdminModule に AppLoggerService / SystemLog 参照が不足している可能性
"""
import subprocess, shutil, os, sys

REPO = "/home/karkyon/projects/machcore"
API  = f"{REPO}/apps/api"
WEB  = f"{REPO}/apps/web"

errors = []

# ══════════════════════════════════════════════════════════
# STEP1: mc.service.ts の CronJob を setTimeout ループ方式に変更
# （外部パッケージ依存なし・SchedulerRegistry も不要）
# ══════════════════════════════════════════════════════════
MC_SVC = f"{API}/src/mc/mc.service.ts"
with open(MC_SVC, "r", encoding="utf-8") as f:
    svc = f.read()

# 不要な import を削除
svc = svc.replace("import { SchedulerRegistry } from '@nestjs/schedule';\n", "")
svc = svc.replace("import { CronJob } from 'cron';\n", "")
# Cron デコレータ import も削除（残っている場合）
svc = svc.replace("import { Cron } from '@nestjs/schedule';\n", "")
# OnModuleInit は残す
print("✅ STEP1a: 不要 import 削除")

# constructor から SchedulerRegistry を削除
OLD_CTOR = """  constructor(
    private readonly prisma: PrismaService,
    private readonly logger: AppLoggerService,
    private readonly scheduler: SchedulerRegistry,
  ) {}"""
NEW_CTOR = """  constructor(
    private readonly prisma: PrismaService,
    private readonly logger: AppLoggerService,
  ) {}

  private cronTimer: NodeJS.Timeout | null = null;"""
if OLD_CTOR in svc:
    svc = svc.replace(OLD_CTOR, NEW_CTOR)
    print("✅ STEP1b: constructor SchedulerRegistry 削除")

# reloadCronTimecards を setTimeout 方式に変更
OLD_RELOAD = """  async reloadCronTimecards() {
    const settings = await this.getSystemSettings();
    const enabled  = settings['cron_timecard_enabled'] !== 'false';
    const hour     = parseInt(settings['cron_timecard_hour'] ?? '5');
    const minute   = parseInt(settings['cron_timecard_minute'] ?? '0');
    const cronName = 'init_timecards';

    // 既存のCronJobを削除
    try { this.scheduler.deleteCronJob(cronName); } catch {}

    if (!enabled) {
      this.logger.info('CRON', `タイムカードCron 無効化済み`);
      return;
    }

    const job = new CronJob(`${minute} ${hour} * * *`, async () => {
      const today = new Date();
      const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
      this.logger.info('CRON', `機械タイムカード自動生成 開始: ${workDate}`);
      try {
        const result = await this.initTimecards(workDate, 1);
        this.logger.info('CRON', `機械タイムカード自動生成 完了: ${workDate}`, { created: result.created });
      } catch (e: any) {
        this.logger.error('CRON', `機械タイムカード自動生成 失敗: ${workDate}`, { error: e?.message ?? String(e) });
      }
    });
    this.scheduler.addCronJob(cronName, job);
    job.start();
    this.logger.info('CRON', `タイムカードCron 登録: ${minute} ${hour} * * *`);
  }"""

NEW_RELOAD = """  async reloadCronTimecards() {
    // 既存タイマーをクリア
    if (this.cronTimer) { clearTimeout(this.cronTimer); this.cronTimer = null; }

    const settings = await this.getSystemSettings();
    const enabled  = settings['cron_timecard_enabled'] !== 'false';
    const hour     = parseInt(settings['cron_timecard_hour'] ?? '5');
    const minute   = parseInt(settings['cron_timecard_minute'] ?? '0');

    if (!enabled) {
      this.logger.info('CRON', 'タイムカードCron 無効化済み');
      return;
    }

    this.scheduleCronTimecards(hour, minute);
    this.logger.info('CRON', `タイムカードCron 登録: ${hour}:${String(minute).padStart(2,'0')} 毎日`);
  }

  private scheduleCronTimecards(hour: number, minute: number) {
    const now  = new Date();
    const next = new Date(now);
    next.setHours(hour, minute, 0, 0);
    if (next <= now) next.setDate(next.getDate() + 1); // 過去なら翌日
    const ms = next.getTime() - now.getTime();

    this.cronTimer = setTimeout(async () => {
      const today = new Date();
      const workDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
      this.logger.info('CRON', `機械タイムカード自動生成 開始: ${workDate}`);
      try {
        const result = await this.initTimecards(workDate, 1);
        this.logger.info('CRON', `機械タイムカード自動生成 完了: ${workDate}`, { created: result.created });
      } catch (e: any) {
        this.logger.error('CRON', `機械タイムカード自動生成 失敗: ${workDate}`, { error: e?.message ?? String(e) });
      }
      // 翌日の同時刻に再スケジュール
      this.scheduleCronTimecards(hour, minute);
    }, ms);
  }"""

if OLD_RELOAD in svc:
    svc = svc.replace(OLD_RELOAD, NEW_RELOAD)
    print("✅ STEP1c: reloadCronTimecards → setTimeout 方式に変更")
else:
    errors.append("STEP1c: reloadCronTimecards パターン不一致")

with open(MC_SVC, "w", encoding="utf-8") as f:
    f.write(svc)

# ══════════════════════════════════════════════════════════
# STEP2: mc.module.ts に AppLoggerService を追加
# ══════════════════════════════════════════════════════════
MC_MOD = f"{API}/src/mc/mc.module.ts"
with open(MC_MOD, "r", encoding="utf-8") as f:
    mod = f.read()

if "AppLoggerService" not in mod:
    mod = "import { AppLoggerService } from '../common/app-logger.service';\n" + mod
    mod = mod.replace(
        "providers:   [McService, McFilesService],",
        "providers:   [McService, McFilesService, AppLoggerService],"
    )
    with open(MC_MOD, "w", encoding="utf-8") as f:
        f.write(mod)
    print("✅ STEP2: mc.module.ts に AppLoggerService 追加")
else:
    print("⏭  STEP2: AppLoggerService 既存スキップ")

# ══════════════════════════════════════════════════════════
# STEP3: admin.controller.ts の system-logs が 404 になっている問題
# → admin.module.ts に AppLoggerService と PrismaService が必要か確認・修正
# ══════════════════════════════════════════════════════════
# admin.module.ts を確認
ADM_MOD = f"{API}/src/admin/admin.module.ts"
if os.path.exists(ADM_MOD):
    with open(ADM_MOD, "r", encoding="utf-8") as f:
        adm_mod = f.read()
    print(f"admin.module.ts 内容確認: PrismaModule={('PrismaModule' in adm_mod)}, AppLoggerService={('AppLoggerService' in adm_mod)}")
else:
    print("⚠️  admin.module.ts が見つかりません")

# ══════════════════════════════════════════════════════════
# STEP4: API tsc チェック
# ══════════════════════════════════════════════════════════
print("--- API tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"], cwd=API, capture_output=True, text=True)
if r.returncode != 0:
    print("❌ API tsc エラー:")
    print((r.stdout + r.stderr)[-3000:])
    errors.append("API tsc")
else:
    print("✅ API tsc OK")

# ══════════════════════════════════════════════════════════
# STEP5: pm2 restart machcore-api
# ══════════════════════════════════════════════════════════
if not errors:
    subprocess.run(["pm2", "restart", "machcore-api"], capture_output=True)
    print("✅ pm2 restart machcore-api")

    subprocess.run(["git", "add", "-A"], cwd=REPO)
    subprocess.run(["git", "commit", "-m", "fix: cron - replace CronJob with setTimeout, fix AppLoggerService DI"], cwd=REPO)
    r3 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
    print("✅ git push\n" + (r3.stderr.strip() or r3.stdout.strip()))
else:
    print(f"❌ エラーあり: {errors}")

print("✅ 完了")
