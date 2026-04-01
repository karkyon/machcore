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

  @IsOptional() @IsString() @Matches(/^[A-Z]$/, { message: 'version は A〜Z の1文字' })
  version?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;
}
