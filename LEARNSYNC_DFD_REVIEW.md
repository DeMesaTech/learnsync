# LearnSync DFD Review

## Sources Reviewed

- `CHAPTER_1-3_CAPSTONE_post-proposal.docx`, Chapter 3 DFD explanations.
- `C:\Users\krisscelalmario\OneDrive\Desktop\Capstone_papers\Figures\dfd-of-teacher.jpg`
- `C:\Users\krisscelalmario\OneDrive\Desktop\Capstone_papers\Figures\dfd-student.jpg`
- Current prototype files under `static/teacher`, `static/student`, and `backend/main.py`.

## Short Answer

Reading the Data Flow Diagrams is possible. The images and written explanations are clear enough to review the intended system flow. The diagrams match the main LearnSync concept, but they need cleanup before final documentation because some process numbers, data store labels, and arrow directions are inconsistent.

The current system already has many UI screens that represent the DFD processes, but most flows are still static. The backend currently only serves static files and has one sample `/api/process` endpoint, so the actual database-backed DFD processes are not implemented yet.

## Teacher DFD Explanation

The Teacher DFD shows these intended teacher-side processes:

- `1.0 Create Class`: teacher creates a class record.
- `2.0 Assign Section`: teacher assigns a class to a section.
- `2.0 Upload Modules`: teacher uploads learning materials.
- `2.1 Extract Text From Module`: uploaded module is converted into text for AI retrieval.
- `3.0 Manage Assessment`: teacher manages assessment-related actions.
- `3.1 Upload Quiz`: teacher creates or uploads quizzes.
- `3.2 Upload Activities`: teacher creates activities.
- `4.0 View Performance`: teacher views quiz scores, submissions, and performance summaries.

Intended teacher data stores:

- `LM Materials`: uploaded modules or learning materials.
- `C1 Module Content`: extracted text chunks from uploaded modules.
- `Q1 Quiz`: quiz records.
- `A1 Activity`: activity records.
- `R1 Score`: quiz or assessment scores.
- `R2 Submission`: student activity submissions.

## Student DFD Explanation

The Student DFD shows these intended student-side processes:

- `1.0 Enroll Class`: student begins enrollment.
- `1.1 Submit Enrollment`: enrollment data is stored and connected to a class.
- `2.0 Query AI`: student sends an AI query.
- `2.1 AI Generation`: system retrieves module context and generates a response.
- `3.0 Answer Quiz`: student answers quiz questions.
- `3.1 Check Quiz`: system checks quiz answers and stores score.
- `4.0 Submit Activity`: student submits an activity.
- `4.1 Teacher Evaluation`: teacher evaluates submitted activity.
- `4.1 View Score`: student views quiz and activity scores.
- `4.2 View Submission`: student views submitted activity records.
- `5.0 View Performance`: student views overall performance summary.

Intended student data stores:

- `Enrollment`: student enrollment record.
- `Class`: class record linked to enrollment.
- `LM Module Context`: retrieved module content for AI.
- `Query Context`: AI query context linked to module content.
- `Student Answer`: quiz answer records.
- `Score`: quiz and activity scores.
- `Submission`: submitted activity records.

## Current System Building Status

| DFD Area | Current Prototype Status | Status |
| --- | --- | --- |
| Teacher create class | `static/teacher/classes.html` has a Create Class modal. | UI only |
| Assign/enroll section | `static/teacher/classes.html` has Enroll Student modal and class/section sample data. | UI only |
| Upload module | `static/teacher/classes.html` and `static/teacher/subject.html` have module upload forms. | UI only |
| Extract text from module | Mentioned in UI text, but no upload parser or backend extraction exists. | Missing |
| Manage assessment | Teacher subject page has Add Activity and Add Quiz controls. | UI only |
| Upload/create quiz | Teacher subject page has an AI quiz modal with generation requirements. | UI only |
| Upload/create activities | Teacher subject page and classes page have activity creation forms. | UI only |
| View teacher performance | Teacher dashboard and grading pages show sample submissions, scores, and grade tables. | UI only |
| Student enrollment | Student pages assume the student is already enrolled. | Missing/implicit |
| Student modules | Student dashboard, subject page, and To Do page show modules. | UI only |
| Query AI | `static/student/AI.html` has the AI assistant interface. | UI only |
| AI generation with module context | Student subject page has AI Study Context, but no real retrieval or generation exists. | UI only |
| Answer quiz | Student subject and To Do pages list quizzes, but no quiz-taking screen exists. | Missing |
| Check quiz | No automated quiz checker exists yet. | Missing |
| Submit activity | Student To Do page lists activities, but no file upload or submission flow exists. | Missing |
| Teacher evaluation | Teacher dashboard has score inputs for submissions. | UI only |
| View score/submission | Student subject page shows sample score/submission status. | UI only |
| View student performance | Student dashboard has sample KPI/status cards. | UI only |
| Backend/data stores | `backend/main.py` only serves static files and has a sample process endpoint. | Not implemented |

## DFD Issues To Fix

### 1. Duplicate Process Numbers

The Teacher DFD uses `2.0` for both `Assign Section` and `Upload Modules`. These should be unique.

Recommended fix:

- `1.0 Create Class`
- `1.1 Assign Section`
- `2.0 Upload Module`
- `2.1 Extract Module Text`
- `3.0 Manage Assessment`
- `3.1 Create Quiz`
- `3.2 Create Activity`
- `4.0 View Performance`

The Student DFD uses `4.1` for both `Teacher Evaluation` and `View Score`. These should also be unique.

Recommended fix:

- `4.0 Submit Activity`
- `4.1 Evaluate Activity`
- `4.2 View Submission`
- `5.0 View Score`
- `6.0 View Performance`

### 2. Duplicate Data Store IDs

The DFD repeats IDs for different stores:

- `A1` is used for Activity, Enrollment, and Query Context.
- `C1` is used for Module Content and Class.
- `Q1` is used for Quiz and Student Answer.

Recommended fix:

- `D1 Users`
- `D2 Classes`
- `D3 Enrollment`
- `D4 Modules`
- `D5 Module Content`
- `D6 Activities`
- `D7 Submissions`
- `D8 Quizzes`
- `D9 Questions`
- `D10 Student Answers`
- `D11 Scores`
- `D12 AI Queries`
- `D13 Query Context`
- `D14 Grade Components`

### 3. Some Arrow Directions Need Correction

In the Teacher DFD, `Upload Quiz` appears to receive data from the `Quiz` store. In most DFD conventions, the process should write created quiz data into the quiz data store.

Recommended flow:

- Teacher -> Create Quiz -> Quiz
- Create Quiz -> Questions
- Quiz/Questions -> Student Answer Quiz

In the Student DFD, enrollment flow should be simplified.

Recommended flow:

- Student -> Submit Enrollment -> Enrollment
- Submit Enrollment reads Class to validate selected class/section.
- Enrollment returns enrollment status to Student.

### 4. AI Context Flow Needs Cleaner Separation

The Student DFD correctly shows AI query and module context, but the labels should be clearer.

Recommended flow:

- Student -> Query AI
- Query AI -> AI Query store
- AI Generation reads Module Content
- AI Generation writes Query Context
- AI Generation returns AI Response to Student

This supports the paper's claim that AI responses should come strictly from teacher-uploaded modules.

### 5. Teacher AI Role Should Be Added

The research paper says teachers can use AI to generate quizzes, but the Teacher DFD does not clearly show AI-assisted quiz generation.

Recommended added teacher flow:

- Teacher -> Request Quiz Generation
- Request Quiz Generation reads Module Content
- AI Generation creates Quiz Draft
- Teacher Reviews Quiz Draft
- Approved Quiz -> Quiz and Questions data stores

This is important because the paper says generated quizzes should be reviewed by teachers before delivery.

## Recommended Revised DFD Structure

### Teacher Module

1. `Manage Class`
   - Create class.
   - Assign section.
   - Enroll or approve students.

2. `Manage Modules`
   - Upload PDF module.
   - Extract text.
   - Store module content chunks.

3. `Manage Assessments`
   - Create activity.
   - Generate quiz draft using AI.
   - Review and publish quiz.

4. `Record and Evaluate`
   - View submissions.
   - Score manual activities.
   - Record attendance, recitation, and participation.

5. `View Performance`
   - Read scores, submissions, attendance, and grade components.
   - Produce performance summary.

### Student Module

1. `Access Class`
   - View enrolled classes.
   - View class modules, activities, and quizzes.

2. `Use AI Assistant`
   - Ask question.
   - Retrieve module context.
   - Generate response.
   - Store AI query and query context.

3. `Answer Quiz`
   - Load published quiz.
   - Submit answers.
   - Auto-check objective questions.
   - Store student answers and score.

4. `Submit Activity`
   - Upload file.
   - Store submission.
   - Wait for teacher evaluation.

5. `View Performance`
   - View quiz scores.
   - View activity scores.
   - View submissions.
   - View AI study history.

## Recommendations For Current Build

### High Priority

- Add real backend models/routes for classes, enrollments, modules, module content, activities, submissions, quizzes, questions, student answers, scores, AI queries, and query context.
- Add module upload handling and PDF text extraction.
- Add quiz-taking UI for students.
- Add quiz checking logic for objective questions.
- Add teacher review step for AI-generated quiz drafts.
- Add student activity submission form with file upload.

### Medium Priority

- Add class detail pages or modals for each clickable module, activity, and quiz item.
- Add status labels: Draft, Published, Submitted, Pending Review, Scored, Overdue.
- Add AI source display in student AI responses, such as module title and content chunk.
- Add teacher performance dashboard that reads from real score/submission data.
- Add student performance page that combines scores, submissions, quiz attempts, and AI queries.

### Low Priority

- Improve DFD labels for grammar and consistency.
- Reduce line crossings in the DFD images.
- Use one deployment term consistently: cloud-based, LAN-based, or hybrid.
- Update sample content to match the final research scope if the system is limited to BS Entrepreneurship.

## Current Prototype Strengths

- The UI already separates teacher and student roles.
- Teacher pages already show the correct major actions: classes, modules, activities, quizzes, submissions, and grading.
- Student pages already show the correct major actions: modules, activities, quizzes, submissions, and AI support.
- AI Study Context is now correctly placed on the student side.
- The teacher quiz modal already reflects the needed AI quiz generation requirements.

## Current Prototype Gaps

- No real database schema yet.
- No persistent records for DFD data stores.
- No actual enrollment workflow.
- No module text extraction.
- No AI retrieval pipeline.
- No AI query logging.
- No query context linking.
- No quiz answer/checking workflow.
- No file submission workflow.
- No teacher evaluation workflow beyond static score inputs.
- No computed grade backend.

## Suggested Implementation Order

1. Build database schema from the cleaned data store list.
2. Implement class and enrollment records.
3. Implement module upload and module content extraction.
4. Implement student module access.
5. Implement AI query and query context logging.
6. Implement quiz creation, question storage, and quiz publishing.
7. Implement student quiz answering and automatic checking.
8. Implement activity submission and teacher evaluation.
9. Implement grade components and computed grades.
10. Implement teacher and student performance summaries.

## Conclusion

The DFD concept is strong and matches the main LearnSync research goals, but the diagrams need normalization before final submission. The current prototype is a good UI-first version of the DFD, but the real data flow is not implemented yet. The next major work should be converting the DFD data stores into database tables and connecting each static UI flow to backend routes.
