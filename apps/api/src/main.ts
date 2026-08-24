import { NestFactory } from '@nestjs/core';
import fastifyMultipart from '@fastify/multipart';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter({ logger: false }),
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (app as any).register(fastifyMultipart, {
    attachFieldsToBody: false,
    limits: { fileSize: 50 * 1024 * 1024 },
  });
  app.setGlobalPrefix('api');

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // CORS許可オリジンは環境変数 CORS_ORIGINS (カンマ区切り) で上書き可能。
  // 未設定時は従来のデフォルト値（自社環境）を使用する。複数インスタンス共存時は
  // インスタンスごとの .env に CORS_ORIGINS を設定すること。
  const corsOrigins = (
    process.env.CORS_ORIGINS ??
    'https://192.168.1.11:8443,http://localhost:3010,http://localhost:3011,http://192.168.1.11:3010'
  )
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  app.enableCors({
    origin: corsOrigins,
    credentials: true,
  });

  const port = process.env.API_PORT || 3011;
  await app.listen(port, '0.0.0.0');
  console.log(`🚀 MachCore API ready: http://localhost:${port}/api`);
}
bootstrap();
