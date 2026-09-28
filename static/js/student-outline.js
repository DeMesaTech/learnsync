function studentOutline() {
  return {
    classId:Number(new URLSearchParams(location.search).get('class_id')),
    studentId:Number(localStorage.getItem('student_id')),
    outline:{status:'',content:{chapters:[]},materials:[],resources:[],activities:[],quizzes:[]},
    selected:{level:'course',key:null,title:'Course overview'},error:'',loading:true,
    async load() {
      try {
        const response=await fetch(`/api/learning/${this.classId}/outline?student_id=${this.studentId}`);
        const data=await response.json();
        if(!response.ok) throw Error(data.detail||'Could not load subject content.');
        this.outline=data;
      } catch(error) { this.error=error.message; }
      finally { this.loading=false; }
    },
    select(level,key,title) { this.selected={level,key,title}; },
    matches(item) { return item.content_level===this.selected.level && (item.content_key||null)===this.selected.key; },
    get selectedLessons() { return this.outline.resources.filter(item=>item.kind==='module'&&this.matches(item)); },
    get selectedReferences() { return this.outline.resources.filter(item=>item.kind==='reference'&&this.matches(item)); },
    get selectedMaterials() { return this.outline.resources.filter(item=>item.kind==='material'&&this.matches(item)); },
    get selectedContents() { return this.selected.level==='topic'?this.outline.materials.filter(item=>item.topic_key===this.selected.key):[]; },
    get selectedQuizzes() { return this.outline.quizzes.filter(item=>this.matches(item)); },
    get selectedActivities() { return this.outline.activities.filter(item=>this.matches(item)); }
  };
}