import {
  IsInt, IsString, IsOptional, IsNotEmpty,
  Min, MaxLength, Matches,
} from 'class-validator';

export class CreateNcDto {
  @IsInt()
  part_id: number;

  @IsInt()
  @Min(1)
  process_l: number;

  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsInt() @Min(0)
  machining_time?: number;

  // ★新規登録フロー実装: 機械マスタ(Machine.pgIsFolder)に基づきサーバー側で
  //   権威的に自動算出するため、フロントエンドからの指定は任意とする
  //   (MC側McMachiningDetail.fileName/pgFolderNameと同じ設計思想)。
  @IsOptional() @IsString() @MaxLength(50)
  folder_name?: string;

  @IsOptional() @IsString() @MaxLength(50)
  file_name?: string;

  @IsOptional() @IsString() @Matches(/^\d+\.\d{4}$/, { message: 'version は "1.0001" 形式の数値文字列' })
  version?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  // [v101] 掴代(専用フィールド)
  @IsOptional() @IsString() @MaxLength(50)
  clamp_allowance?: string;
}
