import { IsOptional, IsBoolean } from 'class-validator';

export class PrintMcDto {
  @IsOptional() @IsBoolean() include_tooling?: boolean;
  @IsOptional() @IsBoolean() include_clamp?: boolean;
  @IsOptional() @IsBoolean() include_drawings?: boolean;
  @IsOptional() @IsBoolean() include_work_offsets?: boolean;
  @IsOptional() @IsBoolean() include_index_programs?: boolean;
}
