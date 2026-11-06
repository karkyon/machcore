import { IsInt, IsNumber, IsString, IsOptional, Min, MaxLength } from 'class-validator';
import { Type } from 'class-transformer';

export class UpdateMcDto {
  @IsOptional() @IsInt()
  machine_id?: number;

  // [No.76] 工程No(登録後の修正用)
  @IsOptional() @IsInt()
  mc_process_no?: number;

  @IsOptional() @IsString() @MaxLength(50)
  o_number?: string;

  // 旧システム(Access メモ型・最大65,535文字)から移行した長いクランプ/備考も保存できるよう DB(TEXT)に合わせる。
  // 2000文字を超えるコンバートデータは「作業完了(登録)」が 400 エラーになり変更・登録できなかった
  @IsOptional() @IsString() @MaxLength(65535)
  clamp_note?: string;

  @IsOptional() @IsInt() @Min(0)
  cycle_time_sec?: number;

  // ★PrismaのDecimal型はAPIレスポンスで文字列("1.0000"等)として返るため、
  //   フロントが一度も編集せず再送した場合などに文字列のまま届くケースがある。
  //   class-validatorのIsNumberは文字列を受け付けないため、Typeで事前に数値変換する。
  @IsOptional() @Type(() => Number) @IsNumber() @Min(0.0001)
  machining_qty?: number;

  @IsOptional() @IsString() @MaxLength(20)
  common_part_code?: string;

  // 旧システム(Access メモ型・最大65,535文字)から移行した長い備考も保存できるよう DB(TEXT)に合わせる。
  // 2000文字を超えるコンバートデータは「作業完了(登録)」が 400 エラーになり変更・登録できなかった
  @IsOptional() @IsString() @MaxLength(65535)
  note?: string;

  @IsOptional() @IsInt()
  creator_id?: number | null;

  @IsOptional() @IsString()
  sheet_created_at?: string | null;

  // [No.41] 編集画面の「PG作成者」(mc_machining_details.pg_created_by)。null で空欄
  @IsOptional() @IsInt()
  pg_created_by?: number | null;

  @IsOptional() @IsString() @MaxLength(50)
  nt1?: string;

  @IsOptional() @IsString() @MaxLength(50)
  nt2?: string;

  @IsOptional() @IsString() @MaxLength(50)
  nt3?: string;

  @IsOptional() @IsString() @MaxLength(50)
  nt4?: string;

}
