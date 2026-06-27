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

  @IsOptional() @IsString() @Matches(/^\d+\.\d{4}$/, { message: 'version は "1.0001" 形式の数値文字列' })
  version?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;
}
