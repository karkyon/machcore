import { IsInt, IsOptional, IsString, IsDateString, Min, MaxLength } from 'class-validator';

export class CreateMcWorkRecordDto {
  @IsOptional() @IsInt() @Min(0)
  setup_time_min?: number;

  @IsOptional() @IsInt() @Min(0)
  machining_time_min?: number;

  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  @IsOptional() @IsInt() @Min(0)
  quantity?: number;

  @IsOptional() @IsInt() @Min(0)
  setup_work_count?: number;

  /** 段取開始時刻 ISO8601 */
  @IsOptional() @IsDateString()
  started_at?: string;

  /** チェック時刻（量産開始） ISO8601 */
  @IsOptional() @IsDateString()
  checked_at?: string;

  /** 加工終了時刻 ISO8601 */
  @IsOptional() @IsDateString()
  finished_at?: string;

  @IsOptional() @IsInt() @Min(0)
  interrupt_setup_min?: number;

  @IsOptional() @IsInt() @Min(0)
  interrupt_work_min?: number;

  @IsOptional() @IsString() @MaxLength(20)
  work_type?: string;

  @IsOptional() @IsString() @MaxLength(1000)
  note?: string;

  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional()
  setup_operator_ids?: number[];

  @IsOptional()
  production_operator_ids?: number[];
}
