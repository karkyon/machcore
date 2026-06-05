import { IsInt, IsOptional, IsString } from 'class-validator';

export class RegisterCommonPartDto {
  @IsInt()
  target_part_id: number;

  @IsInt()
  source_machining_id: number;

  @IsOptional()
  @IsString()
  note?: string;
}
