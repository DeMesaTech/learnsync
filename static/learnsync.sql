-- =========================================
-- DATABASE
-- =========================================
CREATE DATABASE school_management_system;

\c school_management_system;

-- =========================================
-- USER TABLE
-- =========================================
CREATE TABLE "User" (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    username VARCHAR(100),
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================
-- STUDENT TABLE
-- =========================================
CREATE TABLE Student (
    student_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE,
    student_number INT UNIQUE,
    grade_level VARCHAR(50),

    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- TEACHER TABLE
-- =========================================
CREATE TABLE Teacher (
    employee_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE,

    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- SECTION TABLE
-- =========================================
CREATE TABLE Section (
    section_id SERIAL PRIMARY KEY,
    employee_id INT,
    section VARCHAR(100),

    FOREIGN KEY (employee_id) REFERENCES Teacher(employee_id)
);

-- =========================================
-- CLASS TABLE
-- =========================================
CREATE TABLE Class (
    class_id SERIAL PRIMARY KEY,
    employee_id INT,
    section_id INT,
    subject VARCHAR(100),

    FOREIGN KEY (employee_id) REFERENCES Teacher(employee_id),
    FOREIGN KEY (section_id) REFERENCES Section(section_id)
);

-- =========================================
-- MODULE TABLE
-- =========================================
CREATE TABLE Module (
    module_id SERIAL PRIMARY KEY,
    class_id INT,
    user_id INT,
    title VARCHAR(255),
    file_path VARCHAR(255),
    upload_date TIMESTAMP,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- MODULE CONTENT TABLE
-- =========================================
CREATE TABLE module_content (
    text_id SERIAL PRIMARY KEY,
    module_id INT,
    text TEXT,
    chunk_index INT,

    FOREIGN KEY (module_id) REFERENCES Module(module_id)
);

-- =========================================
-- AI QUERY TABLE
-- =========================================
CREATE TABLE AI_query (
    query_id SERIAL PRIMARY KEY,
    user_id INT,
    query_text TEXT,
    response_text TEXT,
    timestamp TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- QUERY CONTEXT TABLE
-- =========================================
CREATE TABLE Query_context (
    context_id SERIAL PRIMARY KEY,
    query_id INT,
    text_id INT,

    FOREIGN KEY (query_id) REFERENCES AI_query(query_id),
    FOREIGN KEY (text_id) REFERENCES module_content(text_id)
);

-- =========================================
-- ACTIVITY TABLE
-- =========================================
CREATE TABLE Activity (
    activity_id SERIAL PRIMARY KEY,
    class_id INT,
    user_id INT,
    title VARCHAR(255),
    description TEXT,
    due_date TIMESTAMP,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- ACT SUBMISSION TABLE
-- =========================================
CREATE TABLE Act_Submission (
    act_submission_id SERIAL PRIMARY KEY,
    activity_id INT,
    student_id INT,
    file_path VARCHAR(255),
    submission_date TIMESTAMP,
    score NUMERIC(5,2),

    FOREIGN KEY (activity_id) REFERENCES Activity(activity_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- ACT RECITATION TABLE
-- =========================================
CREATE TABLE Act_recitation (
    act_recitation_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    title VARCHAR(255),
    score NUMERIC(5,2),
    date_created TIMESTAMP,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- QUIZ TABLE
-- =========================================
CREATE TABLE Quiz (
    quiz_id SERIAL PRIMARY KEY,
    class_id INT,
    user_id INT,
    title VARCHAR(255),
    date_created TIMESTAMP,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (user_id) REFERENCES "User"(user_id)
);

-- =========================================
-- QUESTION TABLE
-- =========================================
CREATE TABLE Question (
    question_id SERIAL PRIMARY KEY,
    quiz_id INT,
    question_text TEXT,
    correct_answer TEXT,

    FOREIGN KEY (quiz_id) REFERENCES Quiz(quiz_id)
);

-- =========================================
-- STUDENT ANSWER TABLE
-- =========================================
CREATE TABLE Student_answer (
    answer_id SERIAL PRIMARY KEY,
    student_id INT,
    quiz_id INT,
    answer_text TEXT,
    is_correct BOOLEAN,

    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (quiz_id) REFERENCES Quiz(quiz_id)
);

-- =========================================
-- QUIZ SCORE TABLE
-- =========================================
CREATE TABLE Quiz_Score (
    score_id SERIAL PRIMARY KEY,
    student_id INT,
    quiz_id INT,
    is_online BOOLEAN,
    total_score NUMERIC(5,2),
    date_taken TIMESTAMP,

    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (quiz_id) REFERENCES Quiz(quiz_id)
);

-- =========================================
-- ENROLLMENT TABLE
-- =========================================
CREATE TABLE Enrollment (
    enrollment_id SERIAL PRIMARY KEY,
    student_id INT,
    class_id INT,

    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (class_id) REFERENCES Class(class_id)
);

-- =========================================
-- ATTENDANCE TABLE
-- =========================================
CREATE TABLE Attendance (
    attendance_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    is_present BOOLEAN,
    score NUMERIC(5,2),
    date_created TIMESTAMP,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- ATTENDANCE GRADE TABLE
-- =========================================
CREATE TABLE Attendance_grade (
    attendance_grade_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    attendance_total NUMERIC(5,2),
    attendance_grd NUMERIC(5,2),
    attendance_computed BOOLEAN,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- ACTIVITY GRADE TABLE
-- =========================================
CREATE TABLE Activity_grade (
    activity_grade_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    activity_grade_total NUMERIC(5,2),
    activity_grd NUMERIC(5,2),
    activity_grade_computed BOOLEAN,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- QUIZ GRADE TABLE
-- =========================================
CREATE TABLE Quiz_grade (
    quiz_grade_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    quiz_grade_total NUMERIC(5,2),
    quiz_grd NUMERIC(5,2),
    quiz_grade_computed BOOLEAN,

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- =========================================
-- FINAL GRADE TABLE
-- =========================================
CREATE TABLE Grade (
    grade_id SERIAL PRIMARY KEY,
    class_id INT,
    student_id INT,
    attendance_grade_id INT,
    activity_grade_id INT,
    quiz_grade_id INT,
    p_grd NUMERIC(5,2),
    remark VARCHAR(255),

    FOREIGN KEY (class_id) REFERENCES Class(class_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (attendance_grade_id) REFERENCES Attendance_grade(attendance_grade_id),
    FOREIGN KEY (activity_grade_id) REFERENCES Activity_grade(activity_grade_id),
    FOREIGN KEY (quiz_grade_id) REFERENCES Quiz_grade(quiz_grade_id)
);