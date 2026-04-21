-- ============================================================
-- MachCore MC システム マイグレーション
-- 対象DB: machcore_dev (PostgreSQL 16, port 5440)
-- 実行方法: docker exec machcore-postgres psql -U machcore -d machcore_dev -f /tmp/mc_migration.sql
-- ============================================================

BEGIN;

-- ============================================================
-- STEP 1: 新規 Enum 型作成
-- ============================================================

CREATE TYPE system_type AS ENUM ('NC', 'MC', 'BOTH');
CREATE TYPE mc_program_status AS ENUM ('NEW', 'PENDING_APPROVAL', 'APPROVED', 'CHANGING');

COMMIT;

-- ※ ALTER TYPE ADD VALUE はトランザクション外で実行必要（PostgreSQL制約）
-- STEP 2: 既存 Enum 拡張（トランザクション外）

ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'MC_EDIT';
ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'MC_SETUP_PRINT';
ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'MC_WORK_RECORD';
ALTER TYPE session_type ADD VALUE IF NOT EXISTS 'MC_USB_DOWNLOAD';

ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_VIEW';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_EDIT_START';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_EDIT_SAVE';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_APPROVE';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_SETUP_PRINT';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_WORK_RECORD';
ALTER TYPE action_type ADD VALUE IF NOT EXISTS 'MC_USB_DOWNLOAD';

BEGIN;

-- ============================================================
-- STEP 3: 既存テーブル変更
-- ============================================================

-- machines: system_type / mc_specs 追加
ALTER TABLE machines
  ADD COLUMN IF NOT EXISTS system_type system_type NOT NULL DEFAULT 'NC',
  ADD COLUMN IF NOT EXISTS mc_specs JSONB;

-- work_records: nc_program_id nullable化 + MC 用カラム追加
ALTER TABLE work_records
  ALTER COLUMN nc_program_id DROP NOT NULL;

ALTER TABLE work_records
  ADD COLUMN IF NOT EXISTS mc_program_id   INTEGER,
  ADD COLUMN IF NOT EXISTS started_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS checked_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS finished_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS interrupt_setup_min INTEGER,
  ADD COLUMN IF NOT EXISTS interrupt_work_min  INTEGER,
  ADD COLUMN IF NOT EXISTS setup_work_count    INTEGER;

-- work_sessions: nc_program_id nullable化 + mc_program_id 追加
ALTER TABLE work_sessions
  ALTER COLUMN nc_program_id DROP NOT NULL;

ALTER TABLE work_sessions
  ADD COLUMN IF NOT EXISTS mc_program_id INTEGER;

-- operation_logs: mc_program_id 追加
ALTER TABLE operation_logs
  ADD COLUMN IF NOT EXISTS mc_program_id INTEGER;

-- ============================================================
-- STEP 4: 新規テーブル作成（依存順）
-- ============================================================

-- mc_programs（マシニングデータ本体）
CREATE TABLE IF NOT EXISTS mc_programs (
  id               SERIAL PRIMARY KEY,
  part_id          INTEGER NOT NULL REFERENCES parts(id),
  machining_id     INTEGER NOT NULL,
  machine_id       INTEGER REFERENCES machines(id),
  status           mc_program_status NOT NULL DEFAULT 'NEW',
  version          VARCHAR(10) NOT NULL DEFAULT '1.0001',
  o_number         VARCHAR(50),
  clamp_note       TEXT,
  cycle_time_sec   INTEGER,
  machining_qty    INTEGER DEFAULT 1,
  common_part_code VARCHAR(20),
  note             TEXT,
  registered_by    INTEGER NOT NULL REFERENCES users(id),
  approved_by      INTEGER REFERENCES users(id),
  registered_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  approved_at      TIMESTAMP(3),
  legacy_mcid      INTEGER,
  legacy_kakoid    INTEGER,
  created_at       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mc_programs_machining_id ON mc_programs(machining_id);
CREATE INDEX IF NOT EXISTS idx_mc_programs_part_id ON mc_programs(part_id);
CREATE INDEX IF NOT EXISTS idx_mc_programs_status ON mc_programs(status);
CREATE INDEX IF NOT EXISTS idx_mc_programs_legacy_mcid ON mc_programs(legacy_mcid);

-- mc_tooling（ツーリングデータ）
CREATE TABLE IF NOT EXISTS mc_tooling (
  id               SERIAL PRIMARY KEY,
  mc_program_id    INTEGER NOT NULL REFERENCES mc_programs(id) ON DELETE CASCADE,
  sort_order       SMALLINT NOT NULL,
  tool_no          VARCHAR(10) NOT NULL,
  tool_name        VARCHAR(100),
  diameter         DECIMAL(8, 3),
  length_offset_no VARCHAR(10),
  dia_offset_no    VARCHAR(10),
  tool_type        VARCHAR(50),
  note             TEXT,
  raw_program_line TEXT,
  created_at       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mc_tooling_program_sort ON mc_tooling(mc_program_id, sort_order);

-- mc_work_offsets（ワークオフセットデータ）
CREATE TABLE IF NOT EXISTS mc_work_offsets (
  id            SERIAL PRIMARY KEY,
  mc_program_id INTEGER NOT NULL REFERENCES mc_programs(id) ON DELETE CASCADE,
  g_code        VARCHAR(10) NOT NULL,
  x_offset      DECIMAL(12, 3),
  y_offset      DECIMAL(12, 3),
  z_offset      DECIMAL(12, 3),
  a_offset      DECIMAL(12, 3),
  r_offset      DECIMAL(12, 3),
  note          VARCHAR(100),
  created_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(mc_program_id, g_code)
);

-- mc_index_programs（インデックスプログラム）
CREATE TABLE IF NOT EXISTS mc_index_programs (
  id            SERIAL PRIMARY KEY,
  mc_program_id INTEGER NOT NULL REFERENCES mc_programs(id) ON DELETE CASCADE,
  sort_order    SMALLINT NOT NULL,
  axis_0        VARCHAR(100),
  axis_1        VARCHAR(100),
  axis_2        VARCHAR(100),
  note          TEXT,
  created_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mc_index_programs_sort ON mc_index_programs(mc_program_id, sort_order);

-- machine_timecards（機械タイムカード）
CREATE TABLE IF NOT EXISTS machine_timecards (
  id          SERIAL PRIMARY KEY,
  machine_id  INTEGER NOT NULL REFERENCES machines(id),
  operator_id INTEGER NOT NULL REFERENCES users(id),
  work_date   DATE NOT NULL,
  start_time  TIME(0) NOT NULL,
  end_time    TIME(0) NOT NULL,
  note        VARCHAR(200),
  created_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_machine_timecards_machine_date ON machine_timecards(machine_id, work_date);
CREATE INDEX IF NOT EXISTS idx_machine_timecards_date ON machine_timecards(work_date);

-- mc_files（MCプログラム用ファイル）
CREATE TABLE IF NOT EXISTS mc_files (
  id             SERIAL PRIMARY KEY,
  mc_program_id  INTEGER NOT NULL REFERENCES mc_programs(id) ON DELETE CASCADE,
  file_type      file_type NOT NULL DEFAULT 'OTHER',
  original_name  VARCHAR(255) NOT NULL,
  stored_name    VARCHAR(255) NOT NULL,
  mime_type      VARCHAR(100) NOT NULL,
  file_path      VARCHAR(500) NOT NULL,
  thumbnail_path VARCHAR(500),
  file_size      INTEGER NOT NULL,
  uploaded_by    INTEGER NOT NULL REFERENCES users(id),
  uploaded_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mc_files_program_type ON mc_files(mc_program_id, file_type);

-- mc_change_history（MC変更履歴）
CREATE TABLE IF NOT EXISTS mc_change_history (
  id              SERIAL PRIMARY KEY,
  mc_program_id   INTEGER NOT NULL REFERENCES mc_programs(id),
  change_type     change_type NOT NULL,
  operator_id     INTEGER NOT NULL REFERENCES users(id),
  version_before  VARCHAR(10),
  version_after   VARCHAR(10),
  content         TEXT,
  field_changes   JSONB,
  changed_at      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  legacy_hist_id  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_mc_change_history_program ON mc_change_history(mc_program_id, changed_at);
CREATE INDEX IF NOT EXISTS idx_mc_change_history_legacy ON mc_change_history(legacy_hist_id);

-- mc_setup_sheet_logs（MC段取シート印刷履歴）
CREATE TABLE IF NOT EXISTS mc_setup_sheet_logs (
  id            SERIAL PRIMARY KEY,
  mc_program_id INTEGER NOT NULL REFERENCES mc_programs(id),
  operator_id   INTEGER NOT NULL REFERENCES users(id),
  printed_at    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  version       VARCHAR(10),
  pdf_path      VARCHAR(500),
  session_id    VARCHAR(36)
);

CREATE INDEX IF NOT EXISTS idx_mc_setup_sheet_logs_program ON mc_setup_sheet_logs(mc_program_id, printed_at);

-- ============================================================
-- STEP 5: 新規テーブルの FK を既存テーブルに追加
-- ============================================================

-- work_records → mc_programs
ALTER TABLE work_records
  ADD CONSTRAINT fk_work_records_mc_program
  FOREIGN KEY (mc_program_id) REFERENCES mc_programs(id);

CREATE INDEX IF NOT EXISTS idx_work_records_mc_program_date
  ON work_records(mc_program_id, work_date);

-- work_sessions → mc_programs
ALTER TABLE work_sessions
  ADD CONSTRAINT fk_work_sessions_mc_program
  FOREIGN KEY (mc_program_id) REFERENCES mc_programs(id);

CREATE INDEX IF NOT EXISTS idx_work_sessions_mc_program_active
  ON work_sessions(mc_program_id, is_active);

-- operation_logs → mc_programs
ALTER TABLE operation_logs
  ADD CONSTRAINT fk_operation_logs_mc_program
  FOREIGN KEY (mc_program_id) REFERENCES mc_programs(id);

CREATE INDEX IF NOT EXISTS idx_operation_logs_mc_program_created
  ON operation_logs(mc_program_id, created_at);

-- ============================================================
-- STEP 6: updated_at 自動更新トリガー（mc_programs等）
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ language 'plpgsql';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mc_programs_updated_at') THEN
    CREATE TRIGGER trg_mc_programs_updated_at
      BEFORE UPDATE ON mc_programs
      FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mc_tooling_updated_at') THEN
    CREATE TRIGGER trg_mc_tooling_updated_at
      BEFORE UPDATE ON mc_tooling
      FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mc_work_offsets_updated_at') THEN
    CREATE TRIGGER trg_mc_work_offsets_updated_at
      BEFORE UPDATE ON mc_work_offsets
      FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_mc_index_programs_updated_at') THEN
    CREATE TRIGGER trg_mc_index_programs_updated_at
      BEFORE UPDATE ON mc_index_programs
      FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  END IF;
END $$;

COMMIT;

-- ============================================================
-- 確認クエリ
-- ============================================================
SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'mc_%'
ORDER BY table_name;
