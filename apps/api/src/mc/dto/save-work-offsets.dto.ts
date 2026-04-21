import { IsString, IsOptional, IsArray, ValidateNested, MaxLength } from 'class-validator';
import { Type } from 'class-transformer';

export class WorkOffsetItemDto {
  @IsString() @MaxLength(10)
  g_code: string;

  @IsOptional() x_offset?: number;
  @IsOptional() y_offset?: number;
  @IsOptional() z_offset?: number;
  @IsOptional() a_offset?: number;
  @IsOptional() r_offset?: number;

  @IsOptional() @IsString() @MaxLength(100)
  note?: string;
}

export class SaveWorkOffsetsDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkOffsetItemDto)
  items: WorkOffsetItemDto[];
}
