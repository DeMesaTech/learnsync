-- Program/curriculum ownership, official syllabi, and auditable masterlist imports.
-- This is intentionally additive so existing classes and historical grades remain intact.
CREATE TABLE IF NOT EXISTS program (
    program_id bigserial PRIMARY KEY,
    code varchar(30) NOT NULL UNIQUE,
    name varchar(150) NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Course codes are display values. Numeric subject IDs are the LMS identity,
-- so imported curricula may contain duplicate codes.
DO $$ DECLARE constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'subject_catalog'::regclass AND contype = 'u'
      AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                           WHERE attrelid='subject_catalog'::regclass AND attname='code')];
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE subject_catalog DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS curriculum_version (
    curriculum_version_id bigserial PRIMARY KEY,
    program_id bigint NOT NULL REFERENCES program(program_id),
    version_label varchar(100) NOT NULL,
    effective_school_year varchar(9),
    source_name varchar(255),
    source_path varchar(512),
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'archived')),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (program_id, version_label)
);

CREATE TABLE IF NOT EXISTS curriculum_subject (
    curriculum_version_id bigint NOT NULL REFERENCES curriculum_version(curriculum_version_id) ON DELETE CASCADE,
    subject_id bigint NOT NULL REFERENCES subject_catalog(subject_id),
    year_level integer NOT NULL CHECK (year_level BETWEEN 1 AND 8),
    semester varchar(20) NOT NULL CHECK (semester IN ('First', 'Second', 'Summer')),
    prerequisites text NOT NULL DEFAULT '',
    PRIMARY KEY (curriculum_version_id, subject_id)
);

CREATE TABLE IF NOT EXISTS student_program (
    student_program_id bigserial PRIMARY KEY,
    student_id integer NOT NULL REFERENCES student(student_id),
    program_id bigint NOT NULL REFERENCES program(program_id),
    curriculum_version_id bigint NOT NULL REFERENCES curriculum_version(curriculum_version_id),
    started_at date NOT NULL DEFAULT CURRENT_DATE,
    ended_at date,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS student_one_active_program_idx
    ON student_program(student_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS program_account (
    program_id bigint NOT NULL REFERENCES program(program_id) ON DELETE CASCADE,
    account_id integer NOT NULL REFERENCES account(user_id) ON DELETE CASCADE,
    PRIMARY KEY (program_id, account_id),
    UNIQUE (program_id)
);

ALTER TABLE section ADD COLUMN IF NOT EXISTS program_id bigint REFERENCES program(program_id);
ALTER TABLE section ADD COLUMN IF NOT EXISTS curriculum_version_id bigint REFERENCES curriculum_version(curriculum_version_id);

-- A new offering owns exactly one teaching/home section. Old mappings are preserved.
ALTER TABLE class ADD COLUMN IF NOT EXISTS teaching_section_id integer REFERENCES section(section_id);
CREATE UNIQUE INDEX IF NOT EXISTS active_offering_subject_section_idx
    ON class(term_id, subject_id, teaching_section_id) WHERE workflow_status = 'active' AND teaching_section_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS official_syllabus (
    official_syllabus_id bigserial PRIMARY KEY,
    curriculum_version_id bigint NOT NULL REFERENCES curriculum_version(curriculum_version_id) ON DELETE CASCADE,
    subject_id bigint NOT NULL REFERENCES subject_catalog(subject_id),
    source_name varchar(255) NOT NULL,
    source_path varchar(512) NOT NULL,
    uploaded_by integer NOT NULL REFERENCES account(user_id),
    uploaded_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (curriculum_version_id, subject_id)
);

CREATE TABLE IF NOT EXISTS official_syllabus_version (
    official_syllabus_version_id bigserial PRIMARY KEY,
    official_syllabus_id bigint NOT NULL REFERENCES official_syllabus(official_syllabus_id) ON DELETE CASCADE,
    version integer NOT NULL,
    content jsonb NOT NULL DEFAULT '{}'::jsonb,
    grading_rule jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'approved' CHECK (status IN ('draft', 'approved', 'superseded')),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at timestamp,
    UNIQUE (official_syllabus_id, version)
);

CREATE TABLE IF NOT EXISTS offering_official_syllabus (
    class_id bigint PRIMARY KEY REFERENCES class(class_id) ON DELETE CASCADE,
    official_syllabus_version_id bigint NOT NULL REFERENCES official_syllabus_version(official_syllabus_version_id),
    published_by integer NOT NULL REFERENCES account(user_id),
    published_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prospectus_import (
    prospectus_import_id bigserial PRIMARY KEY,
    program_id bigint REFERENCES program(program_id),
    curriculum_version_id bigint REFERENCES curriculum_version(curriculum_version_id),
    source_name varchar(255) NOT NULL,
    source_path varchar(512) NOT NULL,
    parsed_rows jsonb NOT NULL DEFAULT '[]'::jsonb,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
    submitted_by integer NOT NULL REFERENCES account(user_id),
    approved_by integer REFERENCES account(user_id),
    submitted_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at timestamp
);

CREATE TABLE IF NOT EXISTS masterlist_import (
    import_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES class(class_id),
    section_id integer NOT NULL REFERENCES section(section_id),
    source_name varchar(255) NOT NULL,
    imported_by integer NOT NULL REFERENCES account(user_id),
    imported_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enrolled_count integer NOT NULL DEFAULT 0,
    removed_count integer NOT NULL DEFAULT 0,
    override_reason text,
    status varchar(20) NOT NULL DEFAULT 'previewed' CHECK (status IN ('previewed', 'applied', 'rejected'))
);

CREATE TABLE IF NOT EXISTS masterlist_import_row (
    import_id bigint NOT NULL REFERENCES masterlist_import(import_id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    student_id integer,
    uploaded_name varchar(255),
    uploaded_section varchar(100),
    status varchar(20) NOT NULL CHECK (status IN ('added', 'unchanged', 'removed', 'invalid', 'blocked')),
    message text,
    PRIMARY KEY (import_id, row_number)
);
