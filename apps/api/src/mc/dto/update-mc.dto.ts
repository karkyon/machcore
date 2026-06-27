import { IsInt, IsNumber, IsString, IsOptional, Min, MaxLength } from 'class-validator';
import { Type } from 'class-transformer';

export class UpdateMcDto {
  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsString() @MaxLength(50)
  o_number?: string;

  @IsOptional() @IsString() @MaxLength(2000)
  clamp_note?: string;

  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  // ★PrismaのDecimal型はAPIレスポンスで文字列("1.0000"等)として返るため、
  //   フロントが一度も編集せず再送した場合などに文字列のまま届くケースがある。
  //   class-validatorのIsNumberは文字列を受け付けないため、Typeで事前に数値変換する。
  @IsOptional() @Type(() => Number) @IsNumber() @Min(0.0001)
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
