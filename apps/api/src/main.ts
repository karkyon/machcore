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

  app.enableCors({
    // HTTPS:8443 (通常ブラウザ) + localhost (開発) + HTTP:3010 (Next.js内部rewrite) のみ許可
    origin: [
      'https://192.168.1.11:8443',
      'http://localhost:3010',
      'http://localhost:3011',
      'http://192.168.1.11:3010',  // Next.js→API内部rewrite用（サーバサイド）
    ],
    credentials: true,
  });

  const port = process.env.API_PORT || 3011;
  await app.listen(port, '0.0.0.0');
  console.log(`🚀 MachCore API ready: http://localhost:${port}/api`);
}
bootstrap();
