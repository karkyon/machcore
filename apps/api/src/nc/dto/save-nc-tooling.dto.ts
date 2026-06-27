import { IsInt, IsString, IsOptional, IsArray, ValidateNested, Min, MaxLength } from 'class-validator';
import { Type } from 'class-transformer';

export class NcToolItemDto {
  @IsInt() @Min(0)
  sort_order: number;

  @IsOptional() @IsString() @MaxLength(50)
  process_type?: string;

  @IsOptional() @IsString() @MaxLength(100)
  chip_model?: string;

  @IsOptional() @IsString() @MaxLength(100)
  holder_model?: string;

  @IsOptional() @IsString() @MaxLength(20)
  nose_r?: string;

  @IsOptional() @IsString() @MaxLength(10)
  t_number?: string;

  @IsOptional() @IsString()
  note?: string;
}

export class SaveNcToolingDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => NcToolItemDto)
  items: NcToolItemDto[];
}
