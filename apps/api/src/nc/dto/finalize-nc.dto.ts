import { IsOptional, IsString, MaxLength } from 'class-validator';

export class FinalizeNcDto {
  @IsString() @MaxLength(50)
  change_type: string;

  @IsOptional() @IsString() @MaxLength(500)
  change_detail?: string;
}
