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
    origin: process.env.WEB_URL || 'http://localhost:3010',
    credentials: true,
  });

  const port = process.env.API_PORT || 3011;
  await app.listen(port, '0.0.0.0');
  console.log(`🚀 MachCore API ready: http://localhost:${port}/api`);
}
bootstrap();
