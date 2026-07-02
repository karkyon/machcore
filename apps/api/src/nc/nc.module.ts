import { Module } from '@nestjs/common';
import { NcController } from './nc.controller';
import { NcService } from './nc.service';
import { NcFilesService } from './nc-files.service';
import { McModule } from '../mc/mc.module';
import { AuthModule } from '../auth/auth.module';

@Module({
  imports: [McModule, AuthModule],
  controllers: [NcController],
  providers: [NcService, NcFilesService],
})
export class NcModule {}
