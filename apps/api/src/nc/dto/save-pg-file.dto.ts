import { IsString, IsOptional, IsIn } from 'class-validator';

export class SavePgFileDto {
  @IsString()
  content!: string;

  @IsOptional()
  @IsIn(['UTF-8', 'SJIS', 'EUC-JP'])
  encoding?: string;

  @IsOptional()
  @IsIn(['CRLF', 'LF', 'CR'])
  lineEnding?: string;
}
