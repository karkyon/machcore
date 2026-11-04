import {
  IsInt, IsString, IsOptional,
  Min, MaxLength, Matches,
} from 'class-validator';

export class UpdateNcDto {
  @IsOptional() @IsInt()
  machine_id?: number;

  @IsOptional() @IsInt() @Min(0)
  machining_time?: number;

  @IsOptional() @IsString() @MaxLength(50)
  folder_name?: string;

  @IsOptional() @IsString() @MaxLength(50)
  file_name?: string;

  // [MC統一] バージョンは手入力しない(終了確認=finalize()の作業種別でサーバー側が更新する)。
  // MCのUpdateMcDtoと同じく version は受け付けない。

  // 旧システム(Access メモ型・最大65,535文字)から移行した長いクランプ/備考も保存できるよう DB(TEXT)に合わせる。
  // 2000文字を超えるコンバートデータは「作業完了(登録)」が 400 エラーになり変更・登録できなかった
  @IsOptional() @IsString() @MaxLength(65535)
  clamp_note?: string;

  // [v101] 掴代(専用フィールド)
  @IsOptional() @IsString() @MaxLength(50)
  clamp_allowance?: string;

  // [v096] MC側UpdateMcDtoとの機能パリティのため追加。
  @IsOptional() @IsInt()
  creator_id?: number | null;

  @IsOptional() @IsString()
  sheet_created_at?: string | null;
}
