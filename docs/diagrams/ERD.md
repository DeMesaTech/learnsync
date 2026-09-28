# Updated LearnSync entity relationship diagram

This is the physical model for the current faculty flow, corresponding to the proposal's Figure 3.8. It uses actual table names. `class` now represents a faculty subject offering; `section_member` is the shared section roster. `enrollment` remains a synchronized delivery record for older screens and historical data.

## Academic assignment, syllabus, and publication

```mermaid
erDiagram
    account {
        int user_id PK
        string email
        string role
    }
    teacher {
        int employee_id PK
        int user_id FK
    }
    student {
        int student_id PK
        int user_id FK
    }
    academic_term {
        bigint term_id PK
        string school_year
        string semester
        boolean is_active
    }
    subject_catalog {
        bigint subject_id PK
        string code
        string title
    }
    class {
        bigint class_id PK
        int employee_id FK
        bigint term_id FK
        bigint subject_id FK
        string workflow_status
    }
    section {
        int section_id PK
        bigint term_id FK
        int adviser_id FK
        string section
        int year_level
        string join_code
    }
    class_section {
        bigint class_id PK
        int section_id PK
    }
    section_member {
        int section_id PK
        int student_id PK
        datetime added_at
    }
    enrollment {
        int enrollment_id PK
        int student_id FK
        bigint class_id FK
        int section_id FK
    }
    enrollment_request {
        bigint request_id PK
        int section_id FK
        int student_id FK
        string status
        int decided_by FK
    }
    legacy_review {
        bigint class_id PK
        string reason
        datetime resolved_at
    }
    syllabus_version {
        bigint syllabus_id PK
        bigint class_id FK
        int version
        string status
        jsonb content
        jsonb grading_rule
    }
    syllabus_item_link {
        bigint class_id PK
        string item_type PK
        int item_id PK
        string topic_key
    }
    syllabus_section_override {
        bigint class_id PK
        int section_id PK
        string item_type PK
        int item_id PK
        boolean visible
        datetime due_at
    }
    grade_publication {
        bigint class_id PK
        int section_id PK
        string grading_period PK
        bigint syllabus_id FK
        jsonb snapshot
    }
    subject_enrollment_exception {
        int student_id PK
        bigint class_id PK
        string action
        int teaching_section_id FK
    }
    subject_enrollment_history {
        bigint history_id PK
        int student_id FK
        bigint class_id FK
        int section_id FK
    }
    grade_publication_history {
        bigint history_id PK
        bigint class_id FK
        int section_id FK
        jsonb snapshot
    }

    account ||--o| teacher : has
    account ||--o| student : has
    teacher ||--o{ class : assigned
    teacher ||--o{ section : advises
    academic_term ||--o{ class : schedules
    academic_term ||--o{ section : contains
    subject_catalog ||--o{ class : defines
    class ||--o{ class_section : reaches
    section ||--o{ class_section : assigned_to
    section ||--o{ section_member : has
    student ||--o{ section_member : belongs_to
    section ||--o{ enrollment_request : receives
    student ||--o{ enrollment_request : submits
    account ||--o{ enrollment_request : decides
    class ||--o{ enrollment : delivers_to
    section ||--o{ enrollment : groups
    student ||--o{ enrollment : participates
    class ||--o{ legacy_review : waits_for
    class ||--o{ syllabus_version : versions
    class ||--o{ syllabus_item_link : links
    class ||--o{ syllabus_section_override : controls
    section ||--o{ syllabus_section_override : specializes
    class ||--o{ grade_publication : publishes
    section ||--o{ grade_publication : receives
    syllabus_version ||--o{ grade_publication : governs
    student ||--o{ subject_enrollment_exception : has
    class ||--o{ subject_enrollment_exception : overrides
    section ||--o{ subject_enrollment_exception : teaches_in
    student ||--o{ subject_enrollment_history : changes
    class ||--o{ subject_enrollment_history : preserves
    class ||--o{ grade_publication_history : archives
```

`syllabus_version.content` stores chapters, optional lesson subsections, topics, outcomes, references, and materials as JSONB; these are not separate relational tables. `syllabus_item_link.item_type` and `item_id` form a checked polymorphic reference to a module, activity, or quiz. `section.class_id` and `section.employee_id` remain nullable legacy columns. `grading_policy` and `grade_visibility` remain for historical records; approved active offerings use the syllabus grading rule and `grade_publication` snapshot.

## Learning content, assessment, scoring, and AI

```mermaid
erDiagram
    class {
        bigint class_id PK
    }
    student {
        int student_id PK
    }
    module {
        bigint module_id PK
        bigint class_id FK
        string title
    }
    module_content {
        bigint text_id PK
        bigint module_id FK
        string text
    }
    activity {
        int activity_id PK
        bigint class_id FK
        string grading_period
        string delivery_type
        string content_level
        string content_key
    }
    act_submission {
        int act_submission_id PK
        int activity_id FK
        int student_id FK
        decimal score
    }
    quiz {
        int quiz_id PK
        bigint class_id FK
        int module_id FK
        string grading_period
        string delivery_type
        string origin
        string content_level
        string content_key
    }
    question {
        int question_id PK
        int quiz_id FK
    }
    quiz_score {
        int score_id PK
        int quiz_id FK
        int student_id FK
        decimal total_score
    }
    attendance {
        int attendance_id PK
        bigint class_id FK
        int student_id FK
    }
    attendance_session {
        bigint session_id PK
        bigint class_id FK
        int section_id FK
        date session_date
        string grading_period
    }
    attendance_mark {
        bigint session_id PK
        int student_id PK
        string status
    }
    learning_content {
        bigint content_id PK
        bigint class_id FK
        string topic_key
        string source_type
        text edited_html
        string status
    }
    learning_resource {
        bigint resource_id PK
        bigint class_id FK
        string kind
        string content_level
        string content_key
        string title
        text body_html
        string file_path
        string status
        int legacy_module_id FK
    }
    grading_column {
        bigint column_id PK
        bigint class_id FK
        string section
        string category
        string grading_period
    }
    grading_score {
        bigint score_id PK
        bigint column_id FK
        int student_id FK
        decimal score
    }
    account {
        int user_id PK
    }
    ai_query {
        int query_id PK
        int user_id FK
    }
    query_context {
        int context_id PK
        int query_id FK
        bigint text_id FK
    }

    class ||--o{ module : contains
    module ||--o{ module_content : extracted_to
    class ||--o{ activity : contains
    activity ||--o{ act_submission : receives
    student ||--o{ act_submission : submits
    class ||--o{ quiz : contains
    module |o--o{ quiz : supports
    quiz ||--o{ question : has
    quiz ||--o{ quiz_score : scores
    student ||--o{ quiz_score : earns
    class ||--o{ attendance : records
    student ||--o{ attendance : attends
    class ||--o{ attendance_session : schedules
    attendance_session ||--o{ attendance_mark : marks
    student ||--o{ attendance_mark : receives
    class ||--o{ learning_content : contains
    class ||--o{ learning_resource : contains
    module |o--o| learning_resource : imported_as_draft
    class ||--o{ grading_column : defines
    grading_column ||--o{ grading_score : records
    student ||--o{ grading_score : earns
    account ||--o{ ai_query : asks
    ai_query ||--o{ query_context : cites
    module_content ||--o{ query_context : provides
```

This companion diagram keeps the proposal's content, quiz, submission, score, and AI context entities while showing chapter lesson, reference, and file resources plus manual grading columns. Resource placement uses keys from the approved syllabus JSON rather than separate chapter/topic tables. The source of truth for physical column types and constraints is `learnsync.sql` plus `backend/academic_schema.sql`.
