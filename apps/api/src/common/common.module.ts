import { Global, Module } from '@nestjs/common';
import { OperationLogService } from './operation-log.service';
import { PrismaModule } from '../prisma/prisma.module';

@Global()
@Module({
  imports:   [PrismaModule],
  providers: [OperationLogService],
  exports:   [OperationLogService],
})
export class CommonModule {}
