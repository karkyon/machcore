import { IsInt, IsString, IsOptional, IsArray, ValidateNested, Min, MaxLength } from 'class-validator';
import { Type } from 'class-transformer';

export class ToolingItemDto {
  @IsInt() @Min(0)
  sort_order: number;

  @IsOptional() @IsString() @MaxLength(20)
  tool_no?: string;

  @IsOptional() @IsString() @MaxLength(10)
  t_no?: string;

  @IsOptional() @IsString() @MaxLength(100)
  tool_name?: string;

  @IsOptional()
  diameter?: number;

  @IsOptional() @IsString() @MaxLength(10)
  length_offset_no?: string;

  @IsOptional() @IsString() @MaxLength(10)
  dia_offset_no?: string;

  @IsOptional() @IsString() @MaxLength(50)
  tool_type?: string;

  @IsOptional() @IsString() @MaxLength(20)
  sub_pg_no?: string;

  @IsOptional() @IsString() @MaxLength(50)
  d_value_content?: string;

  @IsOptional() @IsString()
  note?: string;

  @IsOptional() @IsString()
  raw_program_line?: string;
}

export class SaveToolingDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => ToolingItemDto)
  items: ToolingItemDto[];
}
