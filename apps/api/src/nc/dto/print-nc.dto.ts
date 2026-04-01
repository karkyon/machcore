import { IsOptional, IsBoolean } from 'class-validator';

export class PrintNcDto {
  @IsOptional()
  @IsBoolean()
  include_tools?: boolean;

  @IsOptional()
  @IsBoolean()
  include_clamp?: boolean;

  @IsOptional()
  @IsBoolean()
  include_drawings?: boolean;
}
