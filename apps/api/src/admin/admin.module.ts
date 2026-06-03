import { AppLoggerService } from '../common/app-logger.service';
import { Module } from '@nestjs/common';
import { FilesModule } from '../files/files.module';
import { McModule } from '../mc/mc.module';
import { AdminController } from './admin.controller';

@Module({
  imports: [FilesModule, McModule],
  controllers: [AdminController],
  providers: [AppLoggerService],
})
export class AdminModule {}
