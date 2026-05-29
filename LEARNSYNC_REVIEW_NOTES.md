# LearnSync Review Notes

## Purpose

This file is a working review document for the current LearnSync prototype. It summarizes recent UI changes, explains what still needs revision, and lists suggestions based on the capstone paper `CHAPTER_1-3_CAPSTONE_post-proposal.pdf`.

## Recent UI Changes

- Moved the AI Study Context responsibility to the student side.
- Removed the AI Study Context panel from `static/teacher/subject.html`.
- Kept the AI Study Context panel in `static/student/subject.html`, where students can review saved AI queries linked to teacher-uploaded module content.
- Teacher subject workspace now focuses on teacher actions:
  - Add Module
  - Add Class Item
  - Add Quiz
  - Add Activity
  - View submission status
- Student subject workspace now better matches the paper's student flow:
  - Access modules
  - View activities
  - Take quizzes
  - Submit work
  - Review AI study context

## Research Paper Alignment

The paper describes LearnSync as an integrated LMS with AI academic assistance, grading/recording tools, and performance tracking for GMVCC. The current UI should follow these boundaries:

- Teachers manage classes, upload modules, create quizzes, assign activities, record scores, and monitor student performance.
- Students access modules, answer quizzes, submit activities, view scores/submissions, and use the AI assistant for study support.
- The AI assistant should answer using teacher-uploaded materials, not generic unsupported responses.
- Teacher-side AI should mainly support quiz generation and content preparation.
- Student-side AI should mainly support summaries, explanations, guided feedback, and review questions based on enrolled class modules.
- Generated quizzes should be reviewed by teachers before publishing.

## Suggested Revisions

- Clarify whether the system is cloud-based, LAN-based, or hybrid. The paper uses both "cloud-based" and "offline LAN-based" language, so the UI and documentation should use one consistent deployment description.
- Update sample class data to match the stated scope if needed. The paper limits the study to BS Entrepreneurship, but the prototype currently uses Capstone Research Project examples.
- Add teacher controls for customizable grade percentages because the paper says grading weights vary per subject.
- Separate automated and manual grading clearly:
  - Automated: online quizzes.
  - Manual: attendance, recitation, participation, reporting, face-to-face quizzes, and major assessments.
- Add validation hints for file formats:
  - Teacher modules should be PDF-based.
  - Student written outputs may use Word format.
- Add AI source transparency on the student side, such as "Answer based on: Module title / content chunk."
- Add a teacher review step before publishing AI-generated quizzes.
- Add a student progress view that combines quiz scores, activity submissions, and AI interaction history.
- Add privacy notes or admin controls for AI query logs because the ERD includes AI query and query context records.
- Add empty states for classes/modules/quizzes/activities so the UI works before demo data exists.

## Suggested Data Features

- `ai_queries`: store user prompt, AI response, user ID, class ID, and timestamp.
- `query_context`: connect each AI response to one or more module content chunks.
- `module_content`: store extracted text chunks from uploaded PDF modules.
- `quiz_generation_drafts`: store AI-generated quizzes before teacher approval.
- `grade_components`: store configurable grading percentages per class or subject.
- `student_progress_summary`: aggregate scores, submissions, quiz attempts, and AI study activity.

## Suggested UX Improvements

- On the student subject page, make each module, activity, and quiz open a detail page or modal.
- On the AI Assistant page, show the active class/module context before the student sends a prompt.
- On the teacher quiz modal, add a preview screen before final publish.
- On the teacher side, add a "Needs Review" badge for generated quizzes.
- On student quizzes, show score, attempt status, and due date in one compact row.
- On submissions, show whether the score was automated or teacher-reviewed.

## Research Paper Revision Notes

- Fix repeated or inconsistent title wording:
  - "Cloud-Based AI Academic Assistant"
  - "Offline LAN-based Learning Management System"
- Review grammar in the introduction, scope, and methodology sections.
- Make the deployment model consistent with the hardware/software requirements.
- Confirm if internet is required. The requirements mention internet speed, while other sections mention LAN/local server behavior.
- Clarify whether Mistral 7B runs locally, on a cloud server, or through a hosted API.
- Clarify the role of "cloud-based storage" if the system is intended for school LAN deployment.
- Align the ERD, DFD, and UI labels so entities like module content, AI query, query context, quizzes, scores, and submissions appear consistently.

## Current Priority Checklist

- Done: Move AI Study Context out of teacher subject page.
- Done: Keep AI Study Context on student subject page.
- Done: Add teacher quiz modal requirements for AI quiz generation.
- To do: Add real links or detail pages for clickable module/activity/quiz items.
- To do: Add teacher approval flow for AI-generated quizzes.
- To do: Add student AI context selector connected to modules.
- To do: Add grade percentage configuration.
