-- CreateEnum
CREATE TYPE "user_role" AS ENUM ('VIEWER', 'OPERATOR', 'ADMIN');

-- CreateEnum
CREATE TYPE "nc_program_status" AS ENUM ('NEW', 'PENDING_APPROVAL', 'APPROVED', 'CHANGING');

-- CreateEnum
CREATE TYPE "change_type" AS ENUM ('NEW_REGISTRATION', 'CHANGE', 'APPROVAL', 'MIGRATION');

-- CreateEnum
CREATE TYPE "file_type" AS ENUM ('PHOTO', 'DRAWING', 'PROGRAM', 'OTHER');

-- CreateEnum
CREATE TYPE "session_type" AS ENUM ('EDIT', 'SETUP_PRINT', 'WORK_RECORD', 'USB_DOWNLOAD');

-- CreateEnum
CREATE TYPE "action_type" AS ENUM ('VIEW', 'SEARCH', 'EDIT_START', 'EDIT_SAVE', 'APPROVE', 'SETUP_PRINT', 'WORK_RECORD', 'USB_DOWNLOAD', 'FILE_UPLOAD', 'FILE_DELETE', 'LOGIN', 'LOGOUT', 'SESSION_START', 'SESSION_END');

-- CreateTable
CREATE TABLE "users" (
    "id" SERIAL NOT NULL,
    "employee_code" VARCHAR(20) NOT NULL,
    "name" VARCHAR(50) NOT NULL,
    "name_kana" VARCHAR(50),
    "password_hash" VARCHAR(255) NOT NULL,
    "role" "user_role" NOT NULL DEFAULT 'OPERATOR',
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "avatar_path" VARCHAR(500),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "machines" (
    "id" SERIAL NOT NULL,
    "machine_code" VARCHAR(20) NOT NULL,
    "machine_name" VARCHAR(100) NOT NULL,
    "machine_type" VARCHAR(50),
    "maker" VARCHAR(50),
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "machines_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "parts" (
    "id" SERIAL NOT NULL,
    "part_id" VARCHAR(50) NOT NULL,
    "drawing_no" VARCHAR(50) NOT NULL,
    "name" VARCHAR(100) NOT NULL,
    "client_id" INTEGER,
    "client_name" VARCHAR(100),
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "synced_at" TIMESTAMP(3),

    CONSTRAINT "parts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "company_settings" (
    "id" INTEGER NOT NULL DEFAULT 1,
    "company_name" VARCHAR(100) NOT NULL,
    "logo_path" VARCHAR(500),
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "company_settings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "nc_programs" (
    "id" SERIAL NOT NULL,
    "part_id" INTEGER NOT NULL,
    "process_l" SMALLINT NOT NULL,
    "machine_id" INTEGER,
    "machining_time" INTEGER,
    "setup_time_ref" INTEGER,
    "folder_name" VARCHAR(100) NOT NULL,
    "file_name" VARCHAR(100) NOT NULL,
    "o_number" VARCHAR(20),
    "version" VARCHAR(10) NOT NULL DEFAULT 'A',
    "clamp_note" TEXT,
    "drawing_count" INTEGER NOT NULL DEFAULT 0,
    "photo_count" INTEGER NOT NULL DEFAULT 0,
    "status" "nc_program_status" NOT NULL DEFAULT 'NEW',
    "processing_id" VARCHAR(50),
    "registered_by" INTEGER NOT NULL,
    "approved_by" INTEGER,
    "registered_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "approved_at" TIMESTAMP(3),
    "legacy_ver" VARCHAR(20),
    "legacy_kid" INTEGER,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "nc_programs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "nc_tools" (
    "id" SERIAL NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "sort_order" SMALLINT NOT NULL,
    "process_type" VARCHAR(50),
    "chip_model" VARCHAR(100),
    "holder_model" VARCHAR(100),
    "nose_r" VARCHAR(20),
    "t_number" VARCHAR(10),
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "nc_tools_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "nc_files" (
    "id" SERIAL NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "file_type" "file_type" NOT NULL DEFAULT 'OTHER',
    "original_name" VARCHAR(255) NOT NULL,
    "stored_name" VARCHAR(255) NOT NULL,
    "mime_type" VARCHAR(100) NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "thumbnail_path" VARCHAR(500),
    "file_size" INTEGER NOT NULL,
    "uploaded_by" INTEGER NOT NULL,
    "uploaded_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "nc_files_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "special_sheets" (
    "id" SERIAL NOT NULL,
    "part_id" INTEGER,
    "keyword" VARCHAR(100),
    "sheet_name" VARCHAR(100) NOT NULL,
    "content" TEXT NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "special_sheets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "change_history" (
    "id" SERIAL NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "change_type" "change_type" NOT NULL,
    "operator_id" INTEGER NOT NULL,
    "version_before" VARCHAR(10),
    "version_after" VARCHAR(10),
    "content" TEXT,
    "field_changes" JSONB,
    "changed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "legacy_hist_id" INTEGER,

    CONSTRAINT "change_history_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "work_records" (
    "id" SERIAL NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "operator_id" INTEGER NOT NULL,
    "machine_id" INTEGER,
    "work_date" DATE NOT NULL,
    "setup_time_min" INTEGER,
    "machining_time_min" INTEGER,
    "quantity" INTEGER,
    "note" TEXT,
    "session_id" VARCHAR(36),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "work_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "setup_sheet_logs" (
    "id" SERIAL NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "operator_id" INTEGER NOT NULL,
    "printed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pdf_path" VARCHAR(500),
    "session_id" VARCHAR(36),

    CONSTRAINT "setup_sheet_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "operation_logs" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER,
    "nc_program_id" INTEGER,
    "action_type" "action_type" NOT NULL,
    "session_id" VARCHAR(36),
    "ip_address" VARCHAR(45),
    "user_agent" VARCHAR(500),
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "operation_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "work_sessions" (
    "id" TEXT NOT NULL,
    "user_id" INTEGER NOT NULL,
    "nc_program_id" INTEGER NOT NULL,
    "session_type" "session_type" NOT NULL,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ended_at" TIMESTAMP(3),
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "expires_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "work_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_employee_code_key" ON "users"("employee_code");

-- CreateIndex
CREATE UNIQUE INDEX "machines_machine_code_key" ON "machines"("machine_code");

-- CreateIndex
CREATE UNIQUE INDEX "parts_part_id_key" ON "parts"("part_id");

-- CreateIndex
CREATE INDEX "parts_drawing_no_idx" ON "parts"("drawing_no");

-- CreateIndex
CREATE INDEX "parts_name_idx" ON "parts"("name");

-- CreateIndex
CREATE INDEX "nc_programs_status_idx" ON "nc_programs"("status");

-- CreateIndex
CREATE INDEX "nc_programs_folder_name_idx" ON "nc_programs"("folder_name");

-- CreateIndex
CREATE INDEX "nc_programs_file_name_idx" ON "nc_programs"("file_name");

-- CreateIndex
CREATE INDEX "nc_programs_legacy_kid_idx" ON "nc_programs"("legacy_kid");

-- CreateIndex
CREATE UNIQUE INDEX "nc_programs_part_id_process_l_key" ON "nc_programs"("part_id", "process_l");

-- CreateIndex
CREATE INDEX "nc_tools_nc_program_id_sort_order_idx" ON "nc_tools"("nc_program_id", "sort_order");

-- CreateIndex
CREATE INDEX "nc_files_nc_program_id_file_type_idx" ON "nc_files"("nc_program_id", "file_type");

-- CreateIndex
CREATE INDEX "special_sheets_part_id_idx" ON "special_sheets"("part_id");

-- CreateIndex
CREATE INDEX "change_history_nc_program_id_changed_at_idx" ON "change_history"("nc_program_id", "changed_at");

-- CreateIndex
CREATE INDEX "change_history_legacy_hist_id_idx" ON "change_history"("legacy_hist_id");

-- CreateIndex
CREATE INDEX "work_records_nc_program_id_work_date_idx" ON "work_records"("nc_program_id", "work_date");

-- CreateIndex
CREATE INDEX "work_records_operator_id_work_date_idx" ON "work_records"("operator_id", "work_date");

-- CreateIndex
CREATE INDEX "setup_sheet_logs_nc_program_id_printed_at_idx" ON "setup_sheet_logs"("nc_program_id", "printed_at");

-- CreateIndex
CREATE INDEX "operation_logs_nc_program_id_created_at_idx" ON "operation_logs"("nc_program_id", "created_at");

-- CreateIndex
CREATE INDEX "operation_logs_user_id_created_at_idx" ON "operation_logs"("user_id", "created_at");

-- CreateIndex
CREATE INDEX "operation_logs_action_type_created_at_idx" ON "operation_logs"("action_type", "created_at");

-- CreateIndex
CREATE INDEX "work_sessions_nc_program_id_is_active_idx" ON "work_sessions"("nc_program_id", "is_active");

-- CreateIndex
CREATE INDEX "work_sessions_user_id_is_active_idx" ON "work_sessions"("user_id", "is_active");

-- AddForeignKey
ALTER TABLE "nc_programs" ADD CONSTRAINT "nc_programs_part_id_fkey" FOREIGN KEY ("part_id") REFERENCES "parts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_programs" ADD CONSTRAINT "nc_programs_machine_id_fkey" FOREIGN KEY ("machine_id") REFERENCES "machines"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_programs" ADD CONSTRAINT "nc_programs_registered_by_fkey" FOREIGN KEY ("registered_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_programs" ADD CONSTRAINT "nc_programs_approved_by_fkey" FOREIGN KEY ("approved_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_tools" ADD CONSTRAINT "nc_tools_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_files" ADD CONSTRAINT "nc_files_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "nc_files" ADD CONSTRAINT "nc_files_uploaded_by_fkey" FOREIGN KEY ("uploaded_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "special_sheets" ADD CONSTRAINT "special_sheets_part_id_fkey" FOREIGN KEY ("part_id") REFERENCES "parts"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "change_history" ADD CONSTRAINT "change_history_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "change_history" ADD CONSTRAINT "change_history_operator_id_fkey" FOREIGN KEY ("operator_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "work_records" ADD CONSTRAINT "work_records_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "work_records" ADD CONSTRAINT "work_records_operator_id_fkey" FOREIGN KEY ("operator_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "work_records" ADD CONSTRAINT "work_records_machine_id_fkey" FOREIGN KEY ("machine_id") REFERENCES "machines"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "setup_sheet_logs" ADD CONSTRAINT "setup_sheet_logs_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "setup_sheet_logs" ADD CONSTRAINT "setup_sheet_logs_operator_id_fkey" FOREIGN KEY ("operator_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "operation_logs" ADD CONSTRAINT "operation_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "operation_logs" ADD CONSTRAINT "operation_logs_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "work_sessions" ADD CONSTRAINT "work_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "work_sessions" ADD CONSTRAINT "work_sessions_nc_program_id_fkey" FOREIGN KEY ("nc_program_id") REFERENCES "nc_programs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
