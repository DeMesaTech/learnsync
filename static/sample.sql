-- USER DATA
INSERT INTO User (name, username, password, role, created_at) VALUES
('Alice Santos', 'alice_s', 'password123', 'teacher', NOW()),
('Bob Reyes', 'bob_r', 'password123', 'student', NOW()),
('Carla Dizon', 'carla_d', 'password123', 'student', NOW());

-- TEACHER DATA
INSERT INTO Teacher (user_id) VALUES (1);

-- STUDENT DATA
INSERT INTO Student (user_id, grade_level) VALUES
(2, 'Grade 12'),
(3, 'Grade 12');

-- SECTION DATA
INSERT INTO Section (employee_id, section) VALUES
(1, 'ICT-12A');

-- CLASS DATA
INSERT INTO Class (employee_id, section_id, subject) VALUES
(1, 1, 'Computer Science');

-- MODULE DATA
INSERT INTO Module (class_id, user_id, title, file_path, upload_date) VALUES
(1, 1, 'Introduction to Programming', 'modules/intro_programming.pdf', NOW());

-- MODULE CONTENT DATA
INSERT INTO module_content (module_id, text, chunk_index) VALUES
(1, 'Programming is the process of creating software.', 1),
(1, 'It involves logic, syntax, and debugging.', 2);

-- QUIZ DATA
INSERT INTO Quiz (class_id, user_id, title, date_created) VALUES
(1, 1, 'Basic Programming Quiz', NOW());

-- QUESTION DATA
INSERT INTO Question (quiz_id, question_text, correct_answer) VALUES
(1, 'What is a variable?', 'A storage location for data'),
(1, 'What does "if" statement do?', 'Checks a condition');

-- STUDENT ANSWER DATA
INSERT INTO Student_answer (student_id, quiz_id, answer_text, is_correct) VALUES
(1, 1, 'A storage location for data', TRUE),
(2, 1, 'It checks a condition', TRUE);

-- QUIZ SCORE DATA
INSERT INTO Quiz_Score (student_id, quiz_id, is_online, total_score, date_taken) VALUES
(1, 1, TRUE, 100, NOW()),
(2, 1, TRUE, 90, NOW());

-- ACTIVITY DATA
INSERT INTO Activity (class_id, user_id, title, description, due_date) VALUES
(1, 1, 'Programming Exercise 1', 'Write a simple calculator program.', '2026-06-05');

-- ACT SUBMISSION DATA
INSERT INTO Act_Submission (activity_id, student_id, file_path, submission_date, score) VALUES
(1, 1, 'submissions/alice_calc.zip', NOW(), 95),
(1, 2, 'submissions/bob_calc.zip', NOW(), 88);

-- ATTENDANCE DATA
INSERT INTO Attendance (class_id, student_id, is_present, score, date_created) VALUES
(1, 1, TRUE, 10, NOW()),
(1, 2, FALSE, 0, NOW());

-- ATTENDANCE GRADE DATA
INSERT INTO Attendance_grade (class_id, student_id, attendance_total, attendance_grd, attendance_computed) VALUES
(1, 1, 10, 100, TRUE),
(1, 2, 0, 0, TRUE);

-- ACTIVITY GRADE DATA
INSERT INTO Activity_grade (class_id, student_id, activity_grade_total, activity_grd, activity_grade_computed) VALUES
(1, 1, 95, 95, TRUE),
(1, 2, 88, 88, TRUE);

-- QUIZ GRADE DATA
INSERT INTO Quiz_grade (class_id, student_id, quiz_grade_total, quiz_grd, quiz_grade_computed) VALUES
(1, 1, 100, 100, TRUE),
(1, 2, 90, 90, TRUE);

-- FINAL GRADE DATA
INSERT INTO Grade (class_id, student_id, attendance_grade_id, activity_grade_id, quiz_grade_id, p_grd, remark) VALUES
(1, 1, 1, 1, 1, 98, 'Excellent'),
(1, 2, 2, 2, 2, 85, 'Very Good');
s