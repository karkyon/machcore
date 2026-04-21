import { IsInt, IsString, IsOptional, IsArray, ValidateNested, Min } from 'class-validator';
import { Type } from 'class-transformer';

export class IndexProgramItemDto {
  @IsInt() @Min(0)
  sort_order: number;

  @IsOptional() @IsString() axis_0?: string;
  @IsOptional() @IsString() axis_1?: string;
  @IsOptional() @IsString() axis_2?: string;
  @IsOptional() @IsString() note?: string;
}

export class SaveIndexProgramsDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => IndexProgramItemDto)
  items: IndexProgramItemDto[];
}
