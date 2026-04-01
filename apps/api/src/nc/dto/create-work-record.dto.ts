// apps/api/src/nc/dto/create-work-record.dto.ts
import {
  IsInt, IsOptional, IsString, Min, Max, MaxLength,
} from 'class-validator';

export class CreateWorkRecordDto {
  /** 段取時間（時間部分）: フロントが h*60+m に変換して setup_time_min として送信 */
  @IsOptional() @IsInt() @Min(0)
  setup_time_min?: number;

  /** 加工時間（分単位合計） */
  @IsOptional() @IsInt() @Min(0)
  machining_time_min?: number;

  /** サイクルタイム（秒単位合計: m*60+s） */
  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  /** 加工個数 */
  @IsOptional() @IsInt() @Min(0)
  quantity?: number;

  /** 中断時間（分） */
  @IsOptional() @IsInt() @Min(0)
  interruption_time_min?: number;

  /** 種別: 量産 / 試作 / 変更 / 新規登録 */
  @IsOptional() @IsString() @MaxLength(20)
  work_type?: string;

  /** 備考（最大1000文字） */
  @IsOptional() @IsString() @MaxLength(1000)
  note?: string;

  /** 使用機械ID（Sessionから引き継ぎ可、省略時はncProgram.machineIdを使用） */
  @IsOptional() @IsInt()
  machine_id?: number;
}