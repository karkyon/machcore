import { IsOptional, IsBoolean, IsInt, IsString } from 'class-validator';

export class PrintMcDto {
  @IsOptional() @IsBoolean() include_tooling?: boolean;
  @IsOptional() @IsBoolean() include_clamp?: boolean;
  @IsOptional() @IsBoolean() include_drawings?: boolean;
  @IsOptional() @IsBoolean() include_work_offsets?: boolean;
  @IsOptional() @IsBoolean() include_index_programs?: boolean;
  @IsOptional() @IsBoolean() is_reference?: boolean;
  @IsOptional() @IsBoolean() is_preview?: boolean;
  @IsOptional() @IsInt()     quantity?: number;
  @IsOptional() @IsInt()     machine_id?: number;
  @IsOptional() @IsString()  purpose?: string;
}
