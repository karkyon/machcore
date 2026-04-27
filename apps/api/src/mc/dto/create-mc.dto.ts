import { IsInt, IsString, IsOptional, Min, MaxLength } from 'class-validator';

export class CreateMcDto {
  @IsInt()
  part_id: number;

  @IsInt()
  machining_id: number;

  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsInt() @Min(0)
  mc_process_no?: number;

  @IsOptional() @IsString() @MaxLength(50)
  file_name?: string;

  @IsOptional() @IsString() @MaxLength(50)
  o_number?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  @IsOptional() @IsInt() @Min(1)
  machining_qty?: number;

  @IsOptional() @IsString() @MaxLength(20)
  common_part_code?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  note?: string;
}
