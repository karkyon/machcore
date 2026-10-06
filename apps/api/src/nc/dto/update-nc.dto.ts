import {
  IsInt, IsString, IsOptional,
  Min, MaxLength, Matches,
} from 'class-validator';

export class UpdateNcDto {
  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsInt() @Min(0)
  machining_time?: number;

  @IsOptional() @IsString() @MaxLength(50)
  folder_name?: string;

  @IsOptional() @IsString() @MaxLength(50)
  file_name?: string;

  // [MC統一] バージョンは手入力しない(終了確認=finalize()の作業種別でサーバー側が更新する)。
  // MCのUpdateMcDtoと同じく version は受け付けない。

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  // [v101] 掴代(専用フィールド)
  @IsOptional() @IsString() @MaxLength(50)
  clamp_allowance?: string;

  // [v096] MC側UpdateMcDtoとの機能パリティのため追加。
  @IsOptional() @IsInt()
  creator_id?: number | null;

  @IsOptional() @IsString()
  sheet_created_at?: string | null;
}
