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

  @IsNotEmpty() @IsString() @MaxLength(50)
  folder_name: string;

  @IsNotEmpty() @IsString() @MaxLength(50)
  file_name: string;

  @IsString() @Matches(/^[A-Z]$/, { message: 'version は A〜Z の1文字' })
  version: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;
}
