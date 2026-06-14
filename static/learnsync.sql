BEGIN;
-- SQL script to create the database schema for LearnSync
-- This script defines tables for users, teachers, students, classes, enrollments, modules,
-- AI queries, quizzes, activities, attendance, and grading.
-- \i C:/Users/krisscelalmario/OneDrive/Desktop/learnsync/static/learnsync.sql
-- =========================
-- USERS
-- =========================
CREATE TABLE "user" (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    username VARCHAR(100),
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- TEACHER / STUDENT
-- =========================
CREATE TABLE teacher (
    employee_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE,
    FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE TABLE student (
    student_id INT PRIMARY KEY,
    user_id INT UNIQUE,
    FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

-- =========================
-- SECTION
-- =========================
CREATE TABLE section (
    section_id SERIAL PRIMARY KEY,
    employee_id INT,
    section VARCHAR(10),
    FOREIGN KEY (employee_id) REFERENCES teacher(employee_id)
);

-- =========================
-- CLASS (FIXED CORE)
-- =========================
CREATE TABLE class (
    class_id BIGSERIAL PRIMARY KEY,
    class_code VARCHAR(10),
    employee_id INT,
    section_id INT,
    subject VARCHAR(100),
    FOREIGN KEY (employee_id) REFERENCES teacher(employee_id),
    FOREIGN KEY (section_id) REFERENCES section(section_id)
);

-- =========================
-- ENROLLMENT
-- =========================
CREATE TABLE enrollment (
    enrollment_id SERIAL PRIMARY KEY,
    student_id INT,
    class_id BIGINT,
    FOREIGN KEY (student_id) REFERENCES student(student_id),
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    UNIQUE(student_id, class_id)
);

-- =========================
-- MODULES (LMS CONTENT)
-- =========================
CREATE TABLE module (
    module_id SERIAL PRIMARY KEY,
    class_id BIGINT,
    user_id INT,
    title VARCHAR(255),
    file_path VARCHAR(255),
    upload_date TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE TABLE module_content (
    text_id SERIAL PRIMARY KEY,
    module_id INT,
    text TEXT,
    chunk_index INT,
    FOREIGN KEY (module_id) REFERENCES module(module_id)
);

-- =========================
-- AI SYSTEM
-- =========================
CREATE TABLE ai_query (
    query_id SERIAL PRIMARY KEY,
    user_id INT,
    query_text TEXT,
    response_text TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE TABLE query_context (
    context_id SERIAL PRIMARY KEY,
    query_id INT,
    text_id INT,
    FOREIGN KEY (query_id) REFERENCES ai_query(query_id),
    FOREIGN KEY (text_id) REFERENCES module_content(text_id)
);

-- =========================
-- QUIZ SYSTEM
-- =========================
CREATE TABLE quiz (
    quiz_id SERIAL PRIMARY KEY,
    class_id BIGINT,
    title VARCHAR(255),
    date_created TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES class(class_id)
);

CREATE TABLE question (
    question_id SERIAL PRIMARY KEY,
    quiz_id INT,
    question_text TEXT,
    correct_answer TEXT,
    FOREIGN KEY (quiz_id) REFERENCES quiz(quiz_id)
);

CREATE TABLE student_answer (
    answer_id SERIAL PRIMARY KEY,
    student_id INT,
    quiz_id INT,
    answer_text TEXT,
    is_correct BOOLEAN,
    FOREIGN KEY (student_id) REFERENCES student(student_id),
    FOREIGN KEY (quiz_id) REFERENCES quiz(quiz_id)
);

CREATE TABLE quiz_score (
    score_id SERIAL PRIMARY KEY,
    student_id INT,
    quiz_id INT,
    is_online BOOLEAN,
    total_score NUMERIC(5,2),
    date_taken TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES student(student_id),
    FOREIGN KEY (quiz_id) REFERENCES quiz(quiz_id)
);

-- =========================
-- ACTIVITY SYSTEM
-- =========================
CREATE TABLE activity (
    activity_id SERIAL PRIMARY KEY,
    class_id BIGINT,
    title VARCHAR(255),
    description TEXT,
    due_date TIMESTAMP,
    employee_id INT,
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    FOREIGN KEY (employee_id) REFERENCES teacher(employee_id)
);

CREATE TABLE act_submission (
    act_submission_id SERIAL PRIMARY KEY,
    activity_id INT,
    student_id INT,
    file_path VARCHAR(255),
    submission_date TIMESTAMP,
    score NUMERIC(5,2),
    FOREIGN KEY (activity_id) REFERENCES activity(activity_id),
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);

CREATE TABLE act_recitation (
    act_recitation_id SERIAL PRIMARY KEY,
    class_id BIGINT,
    student_id INT,
    title VARCHAR(255),
    score NUMERIC(5,2),
    date_created TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);

-- =========================
-- ATTENDANCE SYSTEM
-- =========================
CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    class_id BIGINT,
    student_id INT,
    is_present BOOLEAN,
    score NUMERIC(5,2),
    date_created TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES class(class_id),
    FOREIGN KEY (student_id) REFERENCES student(student_id)
);

-- =========================
-- UNIFIED GRADING SYSTEM (FIX 3 OPTION A)
-- =========================
CREATE TABLE grade (
    grade_id SERIAL PRIMARY KEY,
    student_id INT,
    class_id BIGINT,
    type VARCHAR(20), -- attendance / activity / quiz / recitation
    score NUMERIC(5,2),
    total NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES student(student_id),
    FOREIGN KEY (class_id) REFERENCES class(class_id)
);

-- =========================
-- GRADING POLICY
-- =========================
CREATE TABLE grading_policy (
    policy_id SERIAL PRIMARY KEY,
    class_id BIGINT UNIQUE,
    attendance_weight NUMERIC(5,2),
    recit_weight NUMERIC(5,2),
    quizzes_weight NUMERIC(5,2),
    exam_weight NUMERIC(5,2),
    FOREIGN KEY (class_id) REFERENCES class(class_id)
);

COMMIT;