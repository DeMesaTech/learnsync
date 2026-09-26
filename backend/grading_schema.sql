-- Teacher grading columns and scores.
-- The API also creates these tables on demand for existing local databases.
CREATE TABLE IF NOT EXISTS grading_column (
    column_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL,
    section varchar(50) NOT NULL,
    grading_period varchar(20) NOT NULL,
    category varchar(20) NOT NULL CHECK (category IN ('attendance', 'activity', 'quiz')),
    label varchar(255) NOT NULL,
    total_items numeric(8, 2) NOT NULL CHECK (total_items > 0),
    record_date date,
    teacher_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (class_id, section, grading_period, category, label)
);

CREATE TABLE IF NOT EXISTS grading_score (
    score_id bigserial PRIMARY KEY,
    column_id bigint NOT NULL REFERENCES grading_column(column_id) ON DELETE CASCADE,
    student_id integer NOT NULL,
    score numeric(8, 2),
    UNIQUE (column_id, student_id)
);
