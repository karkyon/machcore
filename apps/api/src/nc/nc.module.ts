import { Module } from '@nestjs/common';
import { NcController } from './nc.controller';
import { NcService } from './nc.service';

@Module({
  controllers: [NcController],
  providers: [NcService],
})
export class NcModule {}
