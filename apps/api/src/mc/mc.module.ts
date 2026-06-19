import { AppLoggerService } from '../common/app-logger.service';
import { Module } from '@nestjs/common';
import { McController } from './mc.controller';
import { McService } from './mc.service';
import { McFilesService } from './mc-files.service';
import { UploadTicketService } from './upload-ticket.service';

@Module({
  controllers: [McController],
  providers:   [McService, McFilesService, UploadTicketService, AppLoggerService],
  exports:     [McService],
})
export class McModule {}
