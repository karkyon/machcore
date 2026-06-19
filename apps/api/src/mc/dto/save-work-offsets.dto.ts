import { IsArray, IsOptional, IsString, ValidateNested, MaxLength } from 'class-validator';
import { Type, Transform } from 'class-transformer';

const toNumOrNull = ({ value }: { value: any }) =>
  (value === '' || value === null || value === undefined) ? null : Number(value);

export class WorkOffsetItemDto {
  @IsString() @MaxLength(10)
  g_code: string;

  @IsOptional()
  @Transform(toNumOrNull)
  x_offset?: number | null;

  @IsOptional()
  @Transform(toNumOrNull)
  y_offset?: number | null;

  @IsOptional()
  @Transform(toNumOrNull)
  z_offset?: number | null;

  @IsOptional()
  @Transform(toNumOrNull)
  a_offset?: number | null;

  @IsOptional()
  @Transform(toNumOrNull)
  r_offset?: number | null;

  @IsOptional() @IsString() @MaxLength(100)
  note?: string;
}

export class SaveWorkOffsetsDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => WorkOffsetItemDto)
  items: WorkOffsetItemDto[];
}
