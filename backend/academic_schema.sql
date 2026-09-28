-- Additive academic model. Existing class/enrollment/content identifiers are retained.
CREATE TABLE IF NOT EXISTS academic_term (
    term_id bigserial PRIMARY KEY,
    school_year varchar(9) NOT NULL CHECK (school_year ~ '^[0-9]{4}-[0-9]{4}$'),
    semester varchar(20) NOT NULL CHECK (semester IN ('First', 'Second', 'Summer')),
    is_active boolean NOT NULL DEFAULT false,
    UNIQUE (school_year, semester)
);

CREATE UNIQUE INDEX IF NOT EXISTS academic_term_one_active_idx
    ON academic_term (is_active) WHERE is_active;

CREATE TABLE IF NOT EXISTS subject_catalog (
    subject_id bigserial PRIMARY KEY,
    code varchar(30) NOT NULL UNIQUE,
    title varchar(150) NOT NULL,
    description text,
    units numeric(4, 1),
    active boolean NOT NULL DEFAULT true
);

ALTER TABLE public.class ADD COLUMN IF NOT EXISTS subject_id bigint REFERENCES subject_catalog(subject_id);
ALTER TABLE public.class ADD COLUMN IF NOT EXISTS term_id bigint REFERENCES academic_term(term_id);
ALTER TABLE public.class ADD COLUMN IF NOT EXISTS workflow_status varchar(20) NOT NULL DEFAULT 'legacy_review';
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'class_workflow_status_check') THEN
        ALTER TABLE public.class ADD CONSTRAINT class_workflow_status_check
            CHECK (workflow_status IN ('legacy_review', 'active', 'archived'));
    END IF;
END $$;

ALTER TABLE public.section ADD COLUMN IF NOT EXISTS term_id bigint REFERENCES academic_term(term_id);
ALTER TABLE public.section ADD COLUMN IF NOT EXISTS year_level integer;
ALTER TABLE public.section ADD COLUMN IF NOT EXISTS adviser_id integer REFERENCES public.teacher(employee_id);
ALTER TABLE public.section ADD COLUMN IF NOT EXISTS join_code varchar(24);
ALTER TABLE public.section ADD COLUMN IF NOT EXISTS workflow_status varchar(20) NOT NULL DEFAULT 'legacy_review';
CREATE UNIQUE INDEX IF NOT EXISTS section_join_code_idx ON public.section(join_code) WHERE join_code IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS section_term_year_name_idx
    ON public.section(term_id, year_level, section) WHERE term_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS class_section (
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    section_id integer NOT NULL REFERENCES public.section(section_id) ON DELETE CASCADE,
    PRIMARY KEY (class_id, section_id)
);

CREATE TABLE IF NOT EXISTS section_member (
    section_id integer NOT NULL REFERENCES public.section(section_id) ON DELETE CASCADE,
    student_id integer NOT NULL REFERENCES public.student(student_id) ON DELETE CASCADE,
    added_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (section_id, student_id)
);

CREATE TABLE IF NOT EXISTS enrollment_request (
    request_id bigserial PRIMARY KEY,
    section_id integer NOT NULL REFERENCES public.section(section_id),
    student_id integer NOT NULL REFERENCES public.student(student_id),
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at timestamp,
    decided_by integer REFERENCES public.account(user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS enrollment_request_one_pending_idx
    ON enrollment_request(section_id, student_id) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS legacy_review (
    class_id bigint PRIMARY KEY REFERENCES public.class(class_id) ON DELETE CASCADE,
    reason text NOT NULL,
    resolved_at timestamp
);
INSERT INTO legacy_review(class_id, reason)
SELECT class_id, 'Assign a school year, semester, catalog subject, and shared sections.'
FROM public.class WHERE term_id IS NULL
ON CONFLICT (class_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS syllabus_version (
    syllabus_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    version integer NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'superseded')),
    source_name varchar(255),
    source_path varchar(255),
    content jsonb NOT NULL DEFAULT '{}'::jsonb,
    grading_rule jsonb NOT NULL DEFAULT '{}'::jsonb,
    import_warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    warnings_acknowledged boolean NOT NULL DEFAULT false,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at timestamp,
    UNIQUE (class_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS syllabus_one_draft_idx ON syllabus_version(class_id) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS syllabus_one_approved_idx ON syllabus_version(class_id) WHERE status = 'approved';
ALTER TABLE syllabus_version ADD COLUMN IF NOT EXISTS warnings_acknowledged boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS syllabus_section_override (
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    section_id integer NOT NULL REFERENCES public.section(section_id) ON DELETE CASCADE,
    item_type varchar(20) NOT NULL CHECK (item_type IN ('module', 'activity', 'quiz')),
    item_id integer NOT NULL,
    visible boolean NOT NULL DEFAULT true,
    due_at timestamp,
    PRIMARY KEY (class_id, section_id, item_type, item_id)
);

CREATE TABLE IF NOT EXISTS syllabus_item_link (
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    item_type varchar(20) NOT NULL CHECK (item_type IN ('module', 'activity', 'quiz')),
    item_id integer NOT NULL,
    topic_key varchar(64) NOT NULL,
    PRIMARY KEY (class_id, item_type, item_id)
);

ALTER TABLE public.activity ADD COLUMN IF NOT EXISTS topic_id bigint REFERENCES public.syllabus_topic(topic_id) ON DELETE SET NULL;
ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS topic_id bigint REFERENCES public.syllabus_topic(topic_id) ON DELETE SET NULL;
ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS grading_period varchar(20) NOT NULL DEFAULT 'Midterm';
ALTER TABLE public.grade ADD COLUMN IF NOT EXISTS grading_period varchar(20);

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'grading_column_category_check') THEN
        ALTER TABLE grading_column DROP CONSTRAINT grading_column_category_check;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'grading_column') THEN
        ALTER TABLE grading_column ADD CONSTRAINT grading_column_category_check
            CHECK (category IN ('attendance', 'activity', 'quiz', 'exam'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS grade_publication (
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    section_id integer NOT NULL REFERENCES public.section(section_id) ON DELETE CASCADE,
    grading_period varchar(20) NOT NULL CHECK (grading_period IN ('Midterm', 'Finals', 'Course')),
    syllabus_id bigint NOT NULL REFERENCES syllabus_version(syllabus_id),
    snapshot jsonb NOT NULL,
    published_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_by integer NOT NULL REFERENCES public.teacher(employee_id),
    PRIMARY KEY (class_id, section_id, grading_period)
);

-- A home section supplies normal subjects. Individual exceptions allow irregular
-- students to skip one subject or join an offering in another teaching section.
CREATE TABLE IF NOT EXISTS subject_enrollment_exception (
    student_id integer NOT NULL REFERENCES public.student(student_id),
    class_id bigint NOT NULL REFERENCES public.class(class_id),
    action varchar(12) NOT NULL CHECK (action IN ('include', 'exclude')),
    teaching_section_id integer REFERENCES public.section(section_id),
    reason text,
    updated_by integer REFERENCES public.account(user_id),
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, class_id),
    CHECK ((action = 'include' AND teaching_section_id IS NOT NULL) OR
           (action = 'exclude' AND teaching_section_id IS NULL))
);

CREATE TABLE IF NOT EXISTS subject_enrollment_history (
    history_id bigserial PRIMARY KEY,
    student_id integer NOT NULL REFERENCES public.student(student_id),
    class_id bigint NOT NULL REFERENCES public.class(class_id),
    section_id integer REFERENCES public.section(section_id),
    new_section_id integer REFERENCES public.section(section_id),
    action varchar(20) NOT NULL,
    reason text,
    changed_by integer REFERENCES public.account(user_id),
    changed_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE subject_enrollment_history ADD COLUMN IF NOT EXISTS new_section_id integer REFERENCES public.section(section_id);

CREATE TABLE IF NOT EXISTS attendance_session (
    session_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES public.class(class_id),
    section_id integer NOT NULL REFERENCES public.section(section_id),
    session_date date NOT NULL,
    grading_period varchar(20) NOT NULL CHECK (grading_period IN ('Midterm', 'Finals')),
    created_by integer NOT NULL REFERENCES public.teacher(employee_id),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (class_id, section_id, session_date)
);

CREATE TABLE IF NOT EXISTS attendance_mark (
    session_id bigint NOT NULL REFERENCES attendance_session(session_id) ON DELETE CASCADE,
    student_id integer NOT NULL REFERENCES public.student(student_id),
    status varchar(10) NOT NULL CHECK (status IN ('Present', 'Absent', 'Late', 'Excused')),
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, student_id)
);

ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS delivery_type varchar(12) NOT NULL DEFAULT 'online';
ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS origin varchar(12) NOT NULL DEFAULT 'manual';
ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS content_level varchar(12) NOT NULL DEFAULT 'course';
ALTER TABLE public.quiz ADD COLUMN IF NOT EXISTS content_key varchar(64);

CREATE TABLE IF NOT EXISTS learning_content (
    content_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES public.class(class_id),
    topic_key varchar(64) NOT NULL,
    title varchar(255) NOT NULL,
    source_type varchar(12) NOT NULL CHECK (source_type IN ('pdf', 'manual')),
    file_path varchar(512),
    extracted_text text,
    edited_html text,
    status varchar(12) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_by integer NOT NULL REFERENCES public.teacher(employee_id),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at timestamp
);

-- Published lessons, citations and downloadable teaching files follow the
-- approved outline without changing historical module/content records.
CREATE TABLE IF NOT EXISTS learning_resource (
    resource_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES public.class(class_id),
    kind varchar(12) NOT NULL CHECK (kind IN ('module','reference','material')),
    content_level varchar(12) NOT NULL CHECK (content_level IN ('chapter','topic')),
    content_key varchar(64) NOT NULL,
    title varchar(255) NOT NULL,
    body_html text NOT NULL DEFAULT '',
    extracted_text text,
    url text,
    file_path varchar(512),
    original_filename varchar(255),
    status varchar(12) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
    display_order integer NOT NULL DEFAULT 0,
    legacy_module_id integer UNIQUE REFERENCES public.module(module_id),
    created_by integer NOT NULL REFERENCES public.teacher(employee_id),
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at timestamp
);
CREATE INDEX IF NOT EXISTS learning_resource_outline_idx
    ON learning_resource(class_id,content_level,content_key,status,display_order);
ALTER TABLE learning_resource ADD COLUMN IF NOT EXISTS extracted_text text;

ALTER TABLE public.activity ADD COLUMN IF NOT EXISTS content_level varchar(12) NOT NULL DEFAULT 'course';
ALTER TABLE public.activity ADD COLUMN IF NOT EXISTS content_key varchar(64);
ALTER TABLE public.activity ADD COLUMN IF NOT EXISTS delivery_type varchar(12) NOT NULL DEFAULT 'online';

CREATE TABLE IF NOT EXISTS grade_publication_history (
    history_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL,
    section_id integer NOT NULL,
    grading_period varchar(20) NOT NULL,
    syllabus_id bigint NOT NULL,
    snapshot jsonb NOT NULL,
    published_at timestamp NOT NULL,
    published_by integer NOT NULL,
    archived_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION archive_grade_publication() RETURNS trigger AS $$
BEGIN
    INSERT INTO grade_publication_history(class_id,section_id,grading_period,syllabus_id,
                                          snapshot,published_at,published_by)
    VALUES (OLD.class_id,OLD.section_id,OLD.grading_period,OLD.syllabus_id,
            OLD.snapshot,OLD.published_at,OLD.published_by);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS grade_publication_archive_trigger ON grade_publication;
CREATE TRIGGER grade_publication_archive_trigger
BEFORE UPDATE OR DELETE ON grade_publication
FOR EACH ROW EXECUTE FUNCTION archive_grade_publication();
