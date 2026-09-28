CREATE TABLE IF NOT EXISTS public.syllabus_topic
(
    topic_id bigserial PRIMARY KEY,
    class_id bigint NOT NULL REFERENCES public.class(class_id) ON DELETE CASCADE,
    title varchar(255) NOT NULL,
    display_order integer NOT NULL DEFAULT 0,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE IF EXISTS public.module
    ADD COLUMN IF NOT EXISTS topic_id bigint
    REFERENCES public.syllabus_topic(topic_id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS public.student_topic_progress
(
    topic_id bigint NOT NULL REFERENCES public.syllabus_topic(topic_id) ON DELETE CASCADE,
    student_id integer NOT NULL REFERENCES public.student(student_id) ON DELETE CASCADE,
    completed boolean NOT NULL DEFAULT false,
    completed_at timestamp without time zone,
    updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (topic_id, student_id)
);

CREATE INDEX IF NOT EXISTS syllabus_topic_class_order_idx
    ON public.syllabus_topic (class_id, display_order, topic_id);

CREATE TABLE IF NOT EXISTS public.class_syllabus
(
    class_id bigint PRIMARY KEY REFERENCES public.class(class_id) ON DELETE CASCADE,
    file_name varchar(255) NOT NULL,
    file_path varchar(255) NOT NULL,
    uploaded_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);