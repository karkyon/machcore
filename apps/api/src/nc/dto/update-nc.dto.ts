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

  @IsOptional() @IsString() @Matches(/^\d+\.\d{4}$/, { message: 'version は "1.0001" 形式の数値文字列' })
  version?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  // [v096] MC側UpdateMcDtoとの機能パリティのため追加。
  @IsOptional() @IsInt()
  creator_id?: number | null;

  @IsOptional() @IsString()
  sheet_created_at?: string | null;
}
