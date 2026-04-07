// apps/api/src/nc/dto/update-work-record.dto.ts
import { IsInt, IsNumber, IsOptional, IsString, Min } from "class-validator";

export class UpdateWorkRecordDto {
  @IsOptional() @IsInt() @Min(0) setup_time_min?: number;
  @IsOptional() @IsInt() @Min(0) machining_time_min?: number;
  @IsOptional() @IsInt() @Min(0) cycle_time_sec?: number;
  @IsOptional() @IsInt() @Min(0) quantity?: number;
  @IsOptional() @IsInt() @Min(0) interruption_time_min?: number;
  @IsOptional() @IsString()      work_type?: string;
  @IsOptional() @IsString()      note?: string;
  @IsOptional() @IsInt()         machine_id?: number;
  @IsOptional()                   setup_operator_ids?: number[];
  @IsOptional()                   production_operator_ids?: number[];
}