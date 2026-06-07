BEGIN;

-- =========================
-- USERS
-- =========================
INSERT INTO "user" (name, email, username, password, role)
VALUES
('Alice Teacher', 'alice@school.com', 'alice', 'pass123', 'teacher'),
('Bob Teacher', 'bob@school.com', 'bob', 'pass123', 'teacher'),
('Charlie Student', 'charlie@school.com', 'charlie', 'pass123', 'student'),
('David Student', 'david@school.com', 'david', 'pass123', 'student');

-- =========================
-- TEACHERS
-- =========================
INSERT INTO teacher (user_id)
VALUES
(1),
(2);

-- =========================
-- STUDENTS
-- =========================
INSERT INTO student (student_id, user_id)
VALUES
(1001, 3),
(1002, 4);

-- =========================
-- SECTIONS
-- =========================
INSERT INTO section (employee_id, section)
VALUES
(1, '3A'),
(2, '3B');

-- =========================
-- CLASSES
-- =========================
INSERT INTO class (class_id, employee_id, section_id, subject)
VALUES
('C001', 1, 1, 'Mathematics'),
('C002', 2, 2, 'Science');

-- =========================

COMMIT;