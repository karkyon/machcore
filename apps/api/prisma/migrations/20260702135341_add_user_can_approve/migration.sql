-- [v094] 承認資格(旧ACCESS 社員.MC承認資格相当)フィールドを追加
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "can_approve" BOOLEAN NOT NULL DEFAULT false;
