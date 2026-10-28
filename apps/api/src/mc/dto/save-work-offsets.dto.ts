import { IsArray, IsOptional, IsString, ValidateNested, MaxLength } from 'class-validator';
import { Type, Transform } from 'class-transformer';

const toNumOrNull = ({ value }: { value: any }) =>
  (value === '' || value === null || value === undefined) ? null : Number(value);

export class WorkOffsetItemDto {
  // DBは VARCHAR(50)。「EXT(MC10)」「54.1P14」等の機械名・補足付きの値を保存できるよう DB と同じ長さにする
  @IsString() @MaxLength(50)
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
