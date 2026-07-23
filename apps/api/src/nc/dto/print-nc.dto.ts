import { IsOptional, IsBoolean, IsInt, IsString } from 'class-validator';

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

  // [v113] NC印刷画面MC同一仕様化: リピート発行(用途/数量/使用機械)対応
  @IsOptional() @IsBoolean() is_reference?: boolean;
  @IsOptional() @IsBoolean() is_preview?: boolean;
  @IsOptional() @IsInt()     quantity?: number;
  @IsOptional() @IsInt()     machine_id?: number;
  @IsOptional() @IsString()  purpose?: string;
}
