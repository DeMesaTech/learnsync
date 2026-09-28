function assessmentsPage() {
  const params = new URLSearchParams(location.search);
  return {
    classId:Number(params.get('class_id')), teacherId:Number(localStorage.getItem('teacher_id')),
    outline:{content:{chapters:[]},activities:[],quizzes:[],resources:[]}, sections:[], subjects:[],
    form:{open:false,kind:'activity',type:'online',title:'',description:'',points:10,period:'Midterm',date:'',placement:'course:',sectionIds:[],mcCount:3,idCount:0},
    draft:null, editingQuizId:null, scoreForm:{open:false,activityId:null,title:'',points:0,sectionId:null,sections:[],students:[],scores:{}},
    error:'',loading:true,busy:false,
    async api(path, options={}) {
      const response=await fetch(path,options),data=await response.json().catch(()=>({}));
      if(!response.ok) throw Error(data.detail||`Request failed (${response.status})`);
      return data;
    },
    async load() {
      try {
        const offerings=await this.api(`/api/academic/faculty/${this.teacherId}/offerings`);
        this.subjects=offerings.offerings||[];
        if(!this.classId) this.classId=this.subjects[0]?.class_id;
        if(!this.classId) throw Error('No assigned subjects yet.');
        await this.loadSubject();
        if(params.get('kind')) this.openCreate(params.get('kind'));
        this.error='';
      } catch(error) { this.error=error.message; }
      finally { this.loading=false; }
    },
    async loadSubject() {
      this.outline=await this.api(`/api/learning/${this.classId}/outline?teacher_id=${this.teacherId}`);
      const items=await this.api(`/api/faculty/${this.classId}/syllabus/items?teacher_id=${this.teacherId}`);
      this.sections=items.sections;
      this.form.open=false; this.draft=null; this.editingQuizId=null;
    },
    async refresh() { this.outline=await this.api(`/api/learning/${this.classId}/outline?teacher_id=${this.teacherId}`); },
    get placements() {
      const values=[{value:'course:',label:'Whole course'}];
      for(const chapter of this.outline.content.chapters||[]) {
        values.push({value:`chapter:${chapter.key}`,label:`Chapter · ${chapter.title}`});
        for(const topic of chapter.topics||[]) values.push({value:`topic:${topic.key}`,label:`Topic · ${topic.title}`});
        for(const subsection of chapter.subsections||[]) {
          values.push({value:`subsection:${subsection.key}`,label:`Subsection · ${subsection.title}`});
          for(const topic of subsection.topics||[]) values.push({value:`topic:${topic.key}`,label:`Topic · ${topic.title}`});
        }
      }
      return values;
    },
    get allItems() {
      const activities=this.outline.activities.map(a=>({...a,kind:'activity',id:a.activity_id,type:a.delivery_type==='offline'?'Offline activity':'Online activity'}));
      const quizzes=this.outline.quizzes.map(q=>({...q,kind:'quiz',id:q.quiz_id,type:q.delivery_type==='offline'?'Face-to-face quiz':'AI / online quiz'}));
      return [...activities,...quizzes];
    },
    placementLabel(item) { return this.placements.find(p=>p.value===`${item.content_level}:${item.content_key||''}`)?.label||item.content_level; },
    audienceLabel(item) { return (item.section_ids||[]).map(id=>this.sections.find(s=>s.section_id===id)?.section||id).join(', ')||'All sections'; },
    updateChoice(question, index, value) {
      const previous=question.choices[index];
      question.choices[index]=value;
      if(question.correct_answer===previous) question.correct_answer=value;
    },
    validateQuestions(questions) {
      for(const [index, question] of questions.entries()) {
        if(!question.question_text?.trim()) throw Error(`Question ${index+1} needs text.`);
        if(question.question_type==='multiple_choice') {
          const choices=question.choices||[];
          const cleaned=choices.map(choice=>choice.trim());
          if(cleaned.length!==4||cleaned.some(choice=>!choice)||new Set(cleaned.map(choice=>choice.toLowerCase())).size!==4)
            throw Error(`Question ${index+1} needs four different, nonempty options.`);
          if(!cleaned.includes(question.correct_answer?.trim()))
            throw Error(`Select the correct option for question ${index+1}.`);
          question.choices=cleaned;
          question.correct_answer=question.correct_answer.trim();
        } else if(!question.correct_answer?.trim()) {
          throw Error(`Question ${index+1} needs a correct answer.`);
        }
      }
    },
    openCreate(kind) {
      const level=params.get('level')||'course',key=params.get('key')||'';
      this.form={open:true,kind,type:kind==='quiz'?'ai':'online',title:'',description:'',points:10,
        period:'Midterm',date:new Date().toISOString().slice(0,10),
        placement:`${level}:${key}`,sectionIds:this.sections.map(s=>s.section_id),mcCount:3,idCount:0};
      this.draft=null;
      this.editingQuizId=null;
    },
    async create() {
      this.error=''; this.busy=true;
      try {
        const f=this.form,[level,key]=f.placement.split(':');
        if(!f.title.trim()||!f.sectionIds.length||!(Number(f.points)>0)) throw Error('Enter a title, points, and at least one teaching section.');
        if(f.kind==='activity') {
          await this.api(`/api/learning/${this.classId}/activities`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({teacher_id:this.teacherId,title:f.title,description:f.description,
            due_date:f.date?`${f.date}T23:59:00`:null,points:Number(f.points),grading_period:f.period,
            delivery_type:f.type,content_level:level,content_key:key||null,section_ids:f.sectionIds,publish:false})});
          await this.refresh(); f.open=false;
        } else if(f.type==='offline') {
          await this.api(`/api/faculty/${this.classId}/offline-quizzes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({teacher_id:this.teacherId,title:f.title,quiz_date:f.date,total_points:Number(f.points),
            grading_period:f.period,section_ids:f.sectionIds,content_level:level,content_key:key||null})});
          await this.refresh(); f.open=false;
        } else {
          const mc=Number(f.mcCount), identification=Number(f.idCount);
          if(!Number.isInteger(mc)||!Number.isInteger(identification)||mc<0||identification<0||mc+identification<1||mc+identification>50)
            throw Error('Choose 1–50 questions across multiple choice and identification.');
          const questionTypes=[...(mc?['multiple_choice']:[]),...(identification?['short_answer']:[])];
          this.draft=await this.api('/api/quizzes/generate-draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_id:this.classId,content_level:level,content_key:key||null,title:f.title,
            description:f.description,question_types:questionTypes,question_settings:{multiple_choice:{count:mc,points:Number(f.points)/(mc+identification)},short_answer:{count:identification,points:Number(f.points)/(mc+identification)}}})});
          f.open=false;
        }
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async saveGenerated() {
      this.error='';
      try {
        this.validateQuestions(this.draft.questions);
        this.busy=true;
        const f=this.form,[level,key]=f.placement.split(':');
        await this.api(this.editingQuizId?`/api/quizzes/${this.editingQuizId}`:'/api/quizzes',{method:this.editingQuizId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_id:this.classId,title:f.title,description:f.description,
          deadline:f.date?`${f.date}T23:59:00`:null,total_points:Number(f.points),status:'Draft',origin:'ai',
          grading_period:f.period,sections:f.sectionIds.map(id=>this.sections.find(s=>s.section_id===id)?.section).filter(Boolean),
          content_level:level,content_key:key||null,questions:this.draft.questions})});
        this.draft=null; this.editingQuizId=null; await this.refresh();
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async reviewQuiz(item) {
      this.error='';
      try {
        const quiz=await this.api(`/api/quizzes/teacher/${item.id}`);
        this.editingQuizId=item.id;
        this.form={open:false,kind:'quiz',type:'ai',title:quiz.title,description:quiz.description||'',
          points:Number(quiz.total_points),period:quiz.grading_period||'Midterm',
          date:quiz.deadline?String(quiz.deadline).slice(0,10):'',
          placement:`${quiz.content_level||item.content_level}:${quiz.content_key||item.content_key||''}`,
          sectionIds:this.sections.filter(s=>quiz.sections.includes(s.section)).map(s=>s.section_id),mcCount:3,idCount:0};
        this.draft={questions:quiz.questions};
      } catch(error) { this.error=error.message; }
    },
    async publish(item) {
      this.error=''; this.busy=true;
      try {
        if(item.kind==='quiz') await this.api(`/api/quizzes/${item.id}/status`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Published'})});
        else await this.api(`/api/learning/${this.classId}/activities/${item.id}/status?teacher_id=${this.teacherId}&status=Published`,{method:'PATCH'});
        await this.refresh();
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async deleteItem(item) {
      if(!confirm(`Delete ${item.title}?`)) return;
      this.error=''; this.busy=true;
      try {
        const path=item.kind==='activity'?`/api/learning/${this.classId}/activities/${item.id}?teacher_id=${this.teacherId}`:`/api/quizzes/${item.id}`;
        await this.api(path,{method:'DELETE'}); await this.refresh();
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async openScores(item) {
      this.scoreForm={open:true,activityId:item.id,title:item.title,points:Number(item.points),sectionId:item.section_ids[0],
        sections:this.sections.filter(s=>item.section_ids.includes(s.section_id)),students:[],scores:{}};
      await this.loadRoster();
    },
    async loadRoster() {
      const f=this.scoreForm; if(!f.sectionId) return;
      try {
        const data=await this.api(`/api/faculty/${this.classId}/offline-quizzes?teacher_id=${this.teacherId}&section_id=${f.sectionId}`);
        f.students=data.students;
      } catch(error) { this.error=error.message; }
    },
    async saveScores() {
      this.error=''; this.busy=true;
      try {
        const f=this.scoreForm;
        await this.api(`/api/learning/${this.classId}/activities/${f.activityId}/offline-scores`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({teacher_id:this.teacherId,
          scores:f.students.map(s=>({student_id:s.student_id,score:f.scores[s.student_id]===''||f.scores[s.student_id]===undefined?null:Number(f.scores[s.student_id])}))})});
        f.open=false;
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    }
  };
}
