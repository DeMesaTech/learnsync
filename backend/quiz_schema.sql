-- Run once against an existing LearnSync database before enabling quiz APIs.

ALTER TABLE IF EXISTS public.quiz
    ADD COLUMN IF NOT EXISTS description text,
    ADD COLUMN IF NOT EXISTS module_id integer,
    ADD COLUMN IF NOT EXISTS deadline timestamp without time zone,
    ADD COLUMN IF NOT EXISTS time_limit_minutes integer,
    ADD COLUMN IF NOT EXISTS total_points numeric(8, 2),
    ADD COLUMN IF NOT EXISTS status character varying(20) NOT NULL DEFAULT 'Published';

ALTER TABLE IF EXISTS public.question
    ADD COLUMN IF NOT EXISTS question_type character varying(30) NOT NULL DEFAULT 'short_answer',
    ADD COLUMN IF NOT EXISTS choices jsonb,
    ADD COLUMN IF NOT EXISTS points numeric(8, 2) NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS display_order integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS explanation text;

ALTER TABLE IF EXISTS public.quiz_score
    ADD COLUMN IF NOT EXISTS max_score numeric(8, 2),
    ADD COLUMN IF NOT EXISTS submitted_at timestamp without time zone DEFAULT now();

ALTER TABLE IF EXISTS public.student_answer
    ADD COLUMN IF NOT EXISTS score_id integer,
    ADD COLUMN IF NOT EXISTS question_id integer,
    ADD COLUMN IF NOT EXISTS answer_json jsonb,
    ADD COLUMN IF NOT EXISTS answered_at timestamp without time zone DEFAULT now();

CREATE TABLE IF NOT EXISTS public.quiz_sections
(
    id serial PRIMARY KEY,
    quiz_id integer NOT NULL REFERENCES public.quiz(quiz_id) ON DELETE CASCADE,
    section_id integer NOT NULL REFERENCES public.section(section_id) ON DELETE CASCADE,
    UNIQUE (quiz_id, section_id)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'quiz_module_id_fkey') THEN
        ALTER TABLE public.quiz ADD CONSTRAINT quiz_module_id_fkey
            FOREIGN KEY (module_id) REFERENCES public.module(module_id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'student_answer_score_id_fkey') THEN
        ALTER TABLE public.student_answer ADD CONSTRAINT student_answer_score_id_fkey
            FOREIGN KEY (score_id) REFERENCES public.quiz_score(score_id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'student_answer_question_id_fkey') THEN
        ALTER TABLE public.student_answer ADD CONSTRAINT student_answer_question_id_fkey
            FOREIGN KEY (question_id) REFERENCES public.question(question_id) ON DELETE CASCADE;
    END IF;
END $$;
