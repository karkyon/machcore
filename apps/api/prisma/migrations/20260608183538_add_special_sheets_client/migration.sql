-- add client_id and pdf_path to special_sheets, remove part_id
ALTER TABLE "special_sheets" ADD COLUMN IF NOT EXISTS "client_id" INTEGER;
ALTER TABLE "special_sheets" ADD COLUMN IF NOT EXISTS "pdf_path" VARCHAR(500);
ALTER TABLE "special_sheets" DROP COLUMN IF EXISTS "part_id";
CREATE INDEX IF NOT EXISTS "special_sheets_client_id_idx" ON "special_sheets"("client_id");
