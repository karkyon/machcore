import { IsInt, IsNumber, IsString, IsOptional, Min, MaxLength } from 'class-validator';

export class UpdateMcDto {
  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsString() @MaxLength(50)
  o_number?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  @IsOptional() @IsNumber() @Min(0.0001)
  machining_qty?: number;

  @IsOptional() @IsString() @MaxLength(20)
  common_part_code?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  note?: string;

  @IsOptional() @IsInt()
  creator_id?: number | null;

  @IsOptional() @IsString()
  sheet_created_at?: string | null;

}
