import { Module } from '@nestjs/common';
import { McController } from './mc.controller';
import { McService } from './mc.service';

@Module({
  controllers: [McController],
  providers:   [McService],
})
export class McModule {}
