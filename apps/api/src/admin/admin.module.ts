import { Module } from '@nestjs/common';
import { FilesModule } from '../files/files.module';
import { AdminController } from './admin.controller';

@Module({
  imports: [FilesModule], controllers: [AdminController] })
export class AdminModule {}
