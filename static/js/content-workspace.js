function contentWorkspace() {
  return {
    classId: Number(new URLSearchParams(location.search).get('class_id')),
    teacherId: Number(localStorage.getItem('teacher_id')),
    outline: {version:'', content:{chapters:[]}, materials:[], resources:[], activities:[], quizzes:[]},
    selected:{level:'course',key:null,title:'Course-wide'}, sections:[], unmatched:[],
    syllabusDraft:null, outlineForm:{open:false,kind:'chapter',title:''},
    resourceForm:{open:false,id:null,kind:'module',title:'',url:''},
    uploadForm:{open:false,title:'',file:null}, contentForm:{open:false,id:null,title:'',file:null},
    error:'', loading:true, busy:false, history:[''], historyIndex:0,
    async api(path, options={}) {
      const response = await fetch(path, options);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(data.detail || `Request failed (${response.status})`);
      return data;
    },
    async load() {
      try {
        this.outline = await this.api(`/api/learning/${this.classId}/outline?teacher_id=${this.teacherId}`);
        await this.loadSyllabusDraft();
        const items = await this.api(`/api/faculty/${this.classId}/syllabus/items?teacher_id=${this.teacherId}`);
        this.sections = items.sections;
        const imported = await this.api(`/api/learning/${this.classId}/resources/import-legacy?teacher_id=${this.teacherId}`, {method:'POST'});
        this.unmatched = imported.unmatched;
        if (imported.imported) {
          this.outline = await this.api(`/api/learning/${this.classId}/outline?teacher_id=${this.teacherId}`);
          await this.loadSyllabusDraft();
        }
        this.error = '';
      } catch (error) { this.error = error.message; }
      finally { this.loading = false; }
    },
    async refresh() {
      this.outline = await this.api(`/api/learning/${this.classId}/outline?teacher_id=${this.teacherId}`);
      await this.loadSyllabusDraft();
    },
    async loadSyllabusDraft() {
      const syllabus=await this.api(`/api/faculty/${this.classId}/syllabus?teacher_id=${this.teacherId}`);
      this.syllabusDraft=syllabus.draft;
      if(syllabus.draft) {
        this.outline.content=JSON.parse(JSON.stringify(syllabus.draft.content));
        this.outline.version=syllabus.draft.version;
      }
    },
    openOutlineForm(kind) { this.outlineForm={open:true,kind,title:''}; },
    async addOutlineNode() {
      const title=this.outlineForm.title.trim();
      if(!title) { this.error='Enter a title.'; return; }
      const saved=await this.changeOutline(content=>{
        const node={key:crypto.randomUUID().replaceAll('-',''),title};
        if(this.outlineForm.kind==='chapter') {
          node.topics=[]; node.subsections=[]; content.chapters.push(node);
        } else if(this.selected.level==='chapter') {
          const chapter=content.chapters.find(chapter=>chapter.key===this.selected.key);
          (chapter.topics ||= []).push(node);
        } else {
          for(const chapter of content.chapters) {
            const subsection=(chapter.subsections||[]).find(item=>item.key===this.selected.key);
            if(subsection) { (subsection.topics ||= []).push(node); break; }
          }
        }
        this.selected={level:this.outlineForm.kind,key:node.key,title};
      });
      if(saved) this.outlineForm.open=false;
    },
    async deleteOutlineNode() {
      const {level,key,title}=this.selected;
      if(!['chapter','topic','subsection'].includes(level)||!confirm(`Delete ${title} from the next syllabus version?`)) return;
      const removedKeys=new Set([key]);
      for(const chapter of this.outline.content.chapters||[]) {
        if(level==='chapter'&&chapter.key===key) {
          for(const topic of chapter.topics||[]) removedKeys.add(topic.key);
          for(const subsection of chapter.subsections||[]) {
            removedKeys.add(subsection.key);
            for(const topic of subsection.topics||[]) removedKeys.add(topic.key);
          }
        } else if(level==='subsection') {
          for(const subsection of chapter.subsections||[]) if(subsection.key===key)
            for(const topic of subsection.topics||[]) removedKeys.add(topic.key);
        }
      }
      if(this.outline.resources.some(x=>removedKeys.has(x.content_key))||
         this.outline.materials.some(x=>removedKeys.has(x.topic_key))||
         this.outline.activities.some(x=>removedKeys.has(x.content_key))||
         this.outline.quizzes.some(x=>removedKeys.has(x.content_key))) {
        this.error='Move or delete attached content and assessments before removing this outline item.'; return;
      }
      await this.changeOutline(content=>{
        if(level==='chapter') {
          if(content.chapters.length===1) throw Error('A syllabus needs at least one chapter.');
          content.chapters=content.chapters.filter(item=>item.key!==key);
        } else {
          for(const chapter of content.chapters) {
            chapter.topics=(chapter.topics||[]).filter(item=>item.key!==key);
            chapter.subsections=(chapter.subsections||[]).filter(item=>item.key!==key);
            for(const subsection of chapter.subsections) subsection.topics=(subsection.topics||[]).filter(item=>item.key!==key);
          }
        }
        this.selected={level:'course',key:null,title:'Course-wide'};
      });
    },
    async changeOutline(change) {
      this.error=''; this.busy=true;
      try {
        let syllabus=await this.api(`/api/faculty/${this.classId}/syllabus?teacher_id=${this.teacherId}`);
        if(!syllabus.draft) {
          await this.api(`/api/faculty/${this.classId}/syllabus/draft?teacher_id=${this.teacherId}`,{method:'POST'});
          syllabus=await this.api(`/api/faculty/${this.classId}/syllabus?teacher_id=${this.teacherId}`);
        }
        const content=JSON.parse(JSON.stringify(syllabus.draft.content));
        change(content);
        await this.api(`/api/faculty/${this.classId}/syllabus/draft`,{method:'PUT',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({teacher_id:this.teacherId,content,grading_rule:syllabus.draft.grading_rule,
            acknowledge_warnings:syllabus.draft.warnings_acknowledged})});
        await this.loadSyllabusDraft();
        return true;
      } catch(error) { this.error=error.message; }
      finally { this.busy=false; }
    },
    async approveOutline() {
      this.error=''; this.busy=true;
      try {
        await this.api(`/api/faculty/${this.classId}/syllabus/approve?teacher_id=${this.teacherId}`,{method:'POST'});
        await this.refresh();
      } catch(error) { this.error=error.message; }
      finally { this.busy=false; }
    },
    select(level,key,title) {
      this.selected={level,key,title}; this.resourceForm.open=false;
      this.uploadForm.open=false; this.contentForm.open=false;
    },
    get currentResources() {
      return this.outline.resources.filter(item => item.content_level===this.selected.level && item.content_key===this.selected.key);
    },
    get currentContents() { return this.outline.materials.filter(item => item.topic_key===this.selected.key); },
    get currentAssessments() {
      const matching = item => item.content_level===this.selected.level && (item.content_key||null)===this.selected.key;
      return [
        ...this.outline.activities.filter(matching).map(item => ({kind:'activity',id:item.activity_id,title:item.title,type:item.delivery_type,status:item.status})),
        ...this.outline.quizzes.filter(matching).map(item => ({kind:'quiz',id:item.quiz_id,title:item.title,type:item.delivery_type,status:item.status}))
      ];
    },
    newResource(kind) {
      this.resourceForm={open:true,id:null,kind,title:'',url:''};
      this.uploadForm.open=false; this.contentForm.open=false;
      this.$nextTick(() => { if (this.$refs.editor) this.$refs.editor.innerHTML=''; this.resetHistory(''); });
    },
    editResource(item) {
      this.select(item.content_level,item.content_key,item.title);
      this.resourceForm={open:true,id:item.resource_id,kind:item.kind,title:item.title,url:item.url||''};
      this.$nextTick(() => { const text=item.body_html||(item.extracted_text?`<p>${this.escape(item.extracted_text).replaceAll('\n','<br>')}</p>`:''); if (this.$refs.editor) this.$refs.editor.innerHTML=text; this.resetHistory(text); });
    },
    async saveResource(publish) {
      this.error=''; this.busy=true;
      try {
        const form=this.resourceForm;
        const body={teacher_id:this.teacherId,kind:form.kind,content_level:this.selected.level,content_key:this.selected.key,
          title:form.title,url:form.url||null,body_html:this.$refs.editor.innerHTML,publish};
        const url=`/api/learning/${this.classId}/resources${form.id?'/'+form.id:''}`;
        await this.api(url,{method:form.id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        await this.refresh(); form.open=false;
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async publishResource(item) {
      this.editResource(item); await this.$nextTick(); await this.saveResource(true);
    },
    async deleteResource(item) {
      if(!confirm(`Delete ${item.title}?`)) return;
      this.error=''; this.busy=true;
      try { await this.api(`/api/learning/${this.classId}/resources/${item.resource_id}?teacher_id=${this.teacherId}`,{method:'DELETE'}); await this.refresh(); }
      catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async deleteContent(item) {
      if(!confirm(`Delete ${item.title}?`)) return;
      this.error=''; this.busy=true;
      try { await this.api(`/api/learning/${this.classId}/contents/${item.content_id}?teacher_id=${this.teacherId}`,{method:'DELETE'}); await this.refresh(); }
      catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async deleteAssessment(item) {
      if(!confirm(`Delete ${item.title}?`)) return;
      this.error=''; this.busy=true;
      try {
        const url=item.kind==='activity'?`/api/learning/${this.classId}/activities/${item.id}?teacher_id=${this.teacherId}`:`/api/quizzes/${item.id}`;
        await this.api(url,{method:'DELETE'}); await this.refresh();
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    newUpload() { this.uploadForm={open:true,title:'',file:null}; this.resourceForm.open=false; this.contentForm.open=false; },
    async uploadResource() {
      this.error=''; this.busy=true;
      try {
        const form=new FormData();
        form.append('teacher_id',this.teacherId); form.append('kind','material');
        form.append('content_level',this.selected.level); form.append('content_key',this.selected.key);
        form.append('title',this.uploadForm.title); form.append('file',this.uploadForm.file);
        await this.api(`/api/learning/${this.classId}/resources/upload`,{method:'POST',body:form});
        await this.refresh(); this.uploadForm.open=false;
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    newContent() { this.resourceForm.open=false;this.uploadForm.open=false;this.contentForm={open:true,id:null,title:this.selected.title,file:null}; this.$nextTick(()=>{this.$refs.topicEditor.innerHTML='';this.resetHistory('');}); },
    editContent(item) {
      this.contentForm={open:true,id:item.content_id,title:item.title,file:null};
      this.$nextTick(()=>{this.$refs.topicEditor.innerHTML=item.edited_html||`<p>${this.escape(item.extracted_text||'').replaceAll('\n','<br>')}</p>`;this.resetHistory(this.$refs.topicEditor.innerHTML);});
    },
    escape(value) { const el=document.createElement('div'); el.textContent=value; return el.innerHTML; },
    async extractPdf() {
      this.error=''; this.busy=true;
      try {
        const form=new FormData(); form.append('teacher_id',this.teacherId);
        form.append('topic_key',this.selected.key); form.append('title',this.contentForm.title);
        form.append('file',this.contentForm.file);
        const result=await this.api(`/api/learning/${this.classId}/contents/pdf`,{method:'POST',body:form});
        await this.refresh(); const item=this.outline.materials.find(x=>x.content_id===result.content_id);
        this.editContent(item);
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    async saveContent(publish) {
      this.error=''; this.busy=true;
      try {
        const form=this.contentForm;
        const body={teacher_id:this.teacherId,topic_key:this.selected.key,title:form.title,
          edited_html:this.$refs.topicEditor.innerHTML,publish};
        const url=`/api/learning/${this.classId}/contents${form.id?'/'+form.id:''}`;
        await this.api(url,{method:form.id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        await this.refresh(); form.open=false;
      } catch(error) { this.error=error.message; } finally { this.busy=false; }
    },
    resetHistory(value) { this.history=[value]; this.historyIndex=0; },
    record(ref='editor') {
      const value=this.$refs[ref].innerHTML;
      if (value===this.history[this.historyIndex]) return;
      this.history=this.history.slice(0,this.historyIndex+1); this.history.push(value);
      this.historyIndex=this.history.length-1;
    },
    undo(ref='editor') { if(this.historyIndex>0) this.$refs[ref].innerHTML=this.history[--this.historyIndex]; },
    redo(ref='editor') { if(this.historyIndex<this.history.length-1) this.$refs[ref].innerHTML=this.history[++this.historyIndex]; },
    pastePlain(event) {
      event.preventDefault();
      const text=event.clipboardData.getData('text/plain');
      const selection=window.getSelection(); if(!selection.rangeCount) return;
      const range=selection.getRangeAt(0); range.deleteContents();
      const node=document.createTextNode(text); range.insertNode(node);
      range.setStartAfter(node); range.collapse(true); selection.removeAllRanges(); selection.addRange(range);
      this.record(event.target===this.$refs.editor?'editor':'topicEditor');
    },
    format(type,ref='editor') {
      const editor=this.$refs[ref], selection=window.getSelection();
      if (!selection.rangeCount || !editor.contains(selection.anchorNode)) { editor.focus(); return; }
      const range=selection.getRangeAt(0);
      const wasCollapsed=range.collapsed;
      let tag={heading:'h3',bold:'strong',italic:'em',list:'ul',link:'a'}[type];
      const node=document.createElement(tag);
      if(type==='link') { const href=prompt('Link URL (https://)'); if(!href?.startsWith('https://')) return; node.href=href; node.rel='noopener noreferrer'; }
      if(type==='list') { const li=document.createElement('li'); if(wasCollapsed) li.append(document.createTextNode('\u200b')); else li.append(range.extractContents()); node.append(li); }
      else if(wasCollapsed) node.append(document.createTextNode(type==='link'?'link text':'\u200b'));
      else node.append(range.extractContents());
      range.insertNode(node); selection.removeAllRanges();
      const next=document.createRange();
      if(wasCollapsed) { const textNode=type==='list'?node.firstChild.firstChild:node.firstChild; next.setStart(textNode,textNode.textContent.length); next.collapse(true); }
      else next.selectNodeContents(node);
      selection.addRange(next);
      this.record(ref);
    }
  };
}
