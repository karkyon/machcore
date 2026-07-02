import { IsInt, IsString, MinLength } from 'class-validator';

export class ApproveMcDto {
  @IsInt()
  operator_id: number;

  @IsString() @MinLength(1)
  password: string;
}
