import { AppLoggerService } from '../common/app-logger.service';
import { Module } from '@nestjs/common';
import { McController } from './mc.controller';
import { McService } from './mc.service';
import { McFilesService } from './mc-files.service';

@Module({
  controllers: [McController],
  providers:   [McService, McFilesService, AppLoggerService],
  exports:     [McService],
})
export class McModule {}
