import { IsInt, IsString, MinLength } from "class-validator";

export class ApproveNcDto {
  @IsInt()
  operator_id: number;

  @IsString() @MinLength(1)
  password: string;
}
