import { Module } from '@nestjs/common';
import { McController } from './mc.controller';
import { McService } from './mc.service';
import { McFilesService } from './mc-files.service';

@Module({
  controllers: [McController],
  providers:   [McService, McFilesService],
})
export class McModule {}
