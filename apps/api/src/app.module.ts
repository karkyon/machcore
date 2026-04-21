import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { MachinesModule } from './machines/machines.module';
import { NcModule } from './nc/nc.module';
import { McModule } from './mc/mc.module';
import { FilesModule } from './files/files.module';
import { AdminModule } from './admin/admin.module';
import { CommonModule } from './common/common.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    PrismaModule,
    AuthModule,
    UsersModule,
    MachinesModule,
    NcModule,
    McModule,
    FilesModule,
    AdminModule,
    CommonModule,
  ],
})
export class AppModule {}
