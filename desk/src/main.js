import {basicSetup} from 'codemirror';
import {EditorView, keymap, highlightActiveLine, drawSelection} from '@codemirror/view';
import {EditorState, Compartment, Prec} from '@codemirror/state';
import {sql, MySQL} from '@codemirror/lang-sql';
import {python} from '@codemirror/lang-python';
import {syntaxHighlighting, HighlightStyle} from '@codemirror/language';
import {tags} from '@lezer/highlight';
import {format as formatSQL} from 'sql-formatter';
import {themes, layouts} from './themes.js';
import {icon, hydrateIcons} from './icons.js';
import {currentStatement, statements} from './sql.js';
import {RemoteConnection} from './connection.js';

const $=id=>document.getElementById(id);
const config=window.STUDY_CONTEXT||{},remote=config.mode==='remote'?new RemoteConnection(config.apiBase||'./api/'):null;
const escape = value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const id=()=>globalThis.crypto?.randomUUID?.()||'tab-'+Date.now()+'-'+Math.random().toString(36).slice(2);
const starter="-- Your database is connected. Make yourself at home.\n-- Run a statement: Ctrl / ⌘ Enter · Run everything: Ctrl / ⌘ Shift Enter\n\nSELECT\n    'Hello, MySQL' AS message,\n    1 + 1 AS answer,\n    CURRENT_DATE() AS today;\n";
const demo="-- A small practice dataset. Safe to run again: existing rows stay in place.\nCREATE TABLE IF NOT EXISTS students (\n    id INT AUTO_INCREMENT PRIMARY KEY,\n    name VARCHAR(100) NOT NULL,\n    subject VARCHAR(80) NOT NULL DEFAULT 'Computing',\n    score INT NOT NULL DEFAULT 0\n);\n\nINSERT INTO students (id, name, subject, score) VALUES\n    (1, 'Alex', 'Computing', 92),\n    (2, 'Sam', 'Mathematics', 85),\n    (3, 'Jordan', 'Computing', 78),\n    (4, 'Taylor', 'Physics', 96),\n    (5, 'Riley', 'Mathematics', 88)\nON DUPLICATE KEY UPDATE id = id;\n\nSELECT id, name, subject, score\nFROM students\nORDER BY score DESC;\n";
const pythonExample=`# Python uses the same MySQL database as your SQL tabs.\nimport os\nimport mysql.connector\n\nwith mysql.connector.connect(\n    host=os.environ['MYSQL_HOST'],\n    user=os.environ['MYSQL_USER'],\n    password=os.environ['MYSQL_PASSWORD'],\n    database=os.environ['MYSQL_DATABASE'],\n) as connection:\n    with connection.cursor() as cursor:\n        cursor.execute('SELECT DATABASE(), VERSION()')\n        for database, version in cursor:\n            print(f'Connected to {database} · MySQL {version}')\n`;
const language = new Compartment(), palette = new Compartment(), fontSize = new Compartment();
let view, tabs=[], active=null, database={tables:[],files:[],database:'schoolwork'}, sideView='database';
let theme=themes[0], layout='classic', editorSize=13, history=[], expanded=new Set(), currentTable=null;
let runId=null, pollTimer=null, resultSets=[], resultIndex=0, resultError=null, output=null, sourceLabel='', resultElapsed=0;
let saveTimer=null, toastTimer=null, savingState=false, stateQueued=false, booting=true, tableRequest=0, runningSince=0;
let resultRolledBack=false;
let tableSort=null, tableDirection='ASC', tableSearch='', tableOffset=0, selectedCell=null;
hydrateIcons();

async function api(action,body={}) {
  if(remote)return remote.request(action,body);
  const response=await fetch('/__study/desk/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Study-Token':window.STUDY_CONTEXT.token},body:JSON.stringify(body)});
  let payload;try{payload=await response.json();}catch{throw Error('The workspace connection was interrupted. Try again.');}
  if(!response.ok)throw Error(payload.error||'The workspace could not finish that operation.');
  return payload;
}
const call=(op,body={})=>api('call',{op,...body});
function on(name,event,handler){$(name).addEventListener(event,e=>{try{Promise.resolve(handler(e)).catch(error=>toast(error.message));}catch(error){toast(error.message);}});}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5500);}
function setTask(text,error=false){$('status-task').textContent=text;$('status-task').classList.toggle('danger',error);}
function activeTab(){return tabs.find(t=>t.id===active);}
function languageFor(tab){return tab?.language==='python'?python():sql({dialect:MySQL,schema:{[database.database]:Object.fromEntries(database.tables.map(t=>[t.name,t.columns.map(c=>c.name)]))},defaultSchema:database.database,upperCaseKeywords:true});}
function makeEditor() {
  view=new EditorView({parent:$('editor'),state:EditorState.create({doc:starter,extensions:[
    basicSetup,language.of(languageFor()),palette.of([]),fontSize.of(EditorView.theme({'&':{fontSize:'13px'}})),
    Prec.highest(keymap.of([
      {key:'Mod-Enter',run:()=>{run('smart').catch(e=>toast(e.message));return true;}},
      {key:'Mod-Shift-Enter',run:()=>{run('all').catch(e=>toast(e.message));return true;}},
      {key:'Mod-s',run:()=>{saveDocument().catch(e=>toast(e.message));return true;}},
      {key:'Mod-k',run:()=>{showCommands();return true;}}
    ])),
    EditorView.updateListener.of(update=>{
      if(update.docChanged&&!booting){const tab=activeTab();if(tab){tab.text=view.state.doc.toString();tab.dirty=tab.text!==tab.savedText;renderTabs();scheduleState();}}
      if(update.selectionSet||update.docChanged){const pos=view.state.selection.main.head,line=view.state.doc.lineAt(pos);$('cursor-position').textContent=`Ln ${line.number}, Col ${pos-line.from+1}`;updateRunLabel();}
    })
  ]})});
}
function applyTheme(next, nextLayout=next.layout, persist=true){
  theme=next;layout=layouts.some(l=>l.id===nextLayout)?nextLayout:next.layout;
  document.body.dataset.theme=theme.id;document.body.dataset.layout=layout;
  document.documentElement.style.colorScheme=theme.dark?'dark':'light';
  for(const [key,value] of Object.entries(theme.colors))document.documentElement.style.setProperty('--'+key,value);
  document.documentElement.style.setProperty('--success',theme.dark?'#80c9a4':'#28734b');
  document.documentElement.style.setProperty('--danger',theme.dark?'#f29d9d':'#ac3545');
  $('theme-status').textContent=theme.name;
  const c=theme.colors;
  view.dispatch({effects:palette.reconfigure([
    EditorView.theme({'&':{backgroundColor:c.editor,color:c.text},'.cm-content':{caretColor:c.accent},'.cm-cursor, .cm-dropCursor':{borderLeftColor:c.accent},
      '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection':{backgroundColor:c.selection},'.cm-gutters':{backgroundColor:c.editor,color:c.muted},
      '.cm-activeLine':{backgroundColor:theme.dark?'#ffffff04':'#00000003'},'.cm-activeLineGutter':{backgroundColor:'transparent',color:c.text},
      '.cm-tooltip':{backgroundColor:c.panel,color:c.text,border:'1px solid '+c.line},'.cm-tooltip-autocomplete > ul > li[aria-selected]':{backgroundColor:c.selection,color:c.text},
      '.cm-panels':{backgroundColor:c.panel,color:c.text},'&.cm-focused':{outline:'none'}},{dark:theme.dark}),
    syntaxHighlighting(HighlightStyle.define([
      {tag:tags.keyword,color:theme.id==='vscode'?'#569cd6':c.accent},
      {tag:[tags.string,tags.special(tags.string)],color:theme.dark?'#ceab91':'#8b4f30'},
      {tag:[tags.number,tags.bool,tags.null],color:theme.dark?'#a9cda3':'#4e6c3b'},
      {tag:tags.comment,color:theme.dark?'#7d9b73':'#73836b',fontStyle:'italic'},
      {tag:[tags.function(tags.variableName),tags.typeName],color:theme.dark?'#d9cb96':'#8b6333'},
      {tag:tags.operator,color:c.text},{tag:tags.punctuation,color:c.muted}
    ]))
  ])});
  try{localStorage.setItem('study-theme',theme.id);}catch{}
  if(persist)scheduleState();
}
function newTab(text=starter,lang='sql',name){
  if(tabs.length>=12){toast('Keep up to 12 tabs open. Save and close a tab first.');return;}
  const tab={id:id(),name:name||`query-${tabs.filter(t=>t.language==='sql').length+1}.sql`,language:lang,text,savedText:null,savedName:null,dirty:true,selection:0};
  tabs.push(tab);switchTab(tab.id);scheduleState();return tab;
}
function switchTab(identifier){
  const previous=activeTab();if(previous&&view){previous.text=view.state.doc.toString();previous.selection=view.state.selection.main.head;}
  active=identifier;const tab=activeTab();if(!tab)return;
  booting=true;
  view.dispatch({changes:{from:0,to:view.state.doc.length,insert:tab.text},selection:{anchor:Math.min(tab.selection||0,tab.text.length)},effects:language.reconfigure(languageFor(tab))});
  booting=false;renderTabs();updateRunLabel();$('language-switch').textContent=tab.language==='python'?'Python 3.12':'SQL · MySQL';
  $('document-status').textContent=tab.savedName||'Unsaved file · draft kept in workspace';
  $('format').disabled=tab.language!=='sql';$('explain').disabled=tab.language!=='sql';
  $('run-options').disabled=tab.language!=='sql';$('run-options').hidden=tab.language!=='sql';
  document.title=tab.name+' · Study Desk';view.focus();scheduleState();
}
function renderTabs(){
  $('document-tabs').innerHTML=tabs.map(tab=>`<div class="doc-tab" role="tab" tabindex="0" aria-selected="${tab.id===active}" data-tab="${tab.id}" title="${escape(tab.savedName||'Unsaved '+tab.name)}"><span class="file-glyph ${tab.language==='python'?'python':''}">${tab.language==='python'?'PY':'SQL'}</span><span class="tab-name">${escape(tab.name)}</span>${tab.dirty?'<span class="dirty-dot" title="File has unsaved changes"></span>':''}<button class="tab-close" data-close="${tab.id}" aria-label="Close ${escape(tab.name)}">${icon('close')}</button></div>`).join('')+`<button class="add-tab" id="new-tab" aria-label="New query" title="New SQL query">${icon('plus')}</button>`;
}
function updateRunLabel(){
  if(!view)return;const tab=activeTab(),selected=!view.state.selection.main.empty;
  $('run-label').textContent=tab?.language==='python'?'Run Python':selected?'Run selection':'Run query';
}
function scheduleState(){if(booting)return;clearTimeout(saveTimer);$('draft-status').textContent='Saving drafts…';saveTimer=setTimeout(persistState,1500);}
async function persistState(){
  if(savingState){stateQueued=true;return;}
  savingState=true;
  try{await call('state',{value:{version:1,theme:theme.id,layout,editorSize,tabs,active,history,editorHeight:document.documentElement.style.getPropertyValue('--editor-height')}});$('draft-status').textContent='Drafts saved to workspace';}
  catch(e){$('draft-status').textContent='Drafts not saved · use Save';toast(e.message);}
  finally{savingState=false;if(stateQueued){stateQueued=false;scheduleState();}}
}
async function refresh(){
  $('refresh').disabled=true;
  try{database=await call('bootstrap');$('connection-name').textContent=database.database;$('connection-detail').textContent='MySQL '+database.version.split('-')[0];$('connection-dot').classList.add('online');$('status-connection').textContent='MySQL · '+database.database;view.dispatch({effects:language.reconfigure(languageFor(activeTab()))});renderSidebar();}
  catch(error){$('connection-detail').textContent='Connection needs attention';$('connection-dot').classList.remove('online');$('side-content').innerHTML=`<div class="side-empty">${escape(error.message)}<br><a class="button outline" href="${remote?'./setup/':'/__study/'}">Open setup</a></div>`;throw error;}
  finally{$('refresh').disabled=false;}
}
function renderSidebar(){
  const filter=$('side-filter').value.toLowerCase();
  $('side-filter').placeholder=sideView==='database'?'Filter tables…':sideView==='files'?'Filter files…':'Search query history…';
  $('sidebar-title').textContent={database:'DATABASE EXPLORER',files:'WORKSPACE FILES',history:'QUERY HISTORY'}[sideView];
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===sideView));
  let html='';
  if(sideView==='database'){
    const tables=database.tables.filter(t=>t.name.toLowerCase().includes(filter));
    html=`<div class="side-section"><span>TABLES & VIEWS</span><div style="display:flex;align-items:center;gap:4px"><span class="count-badge">${tables.length}</span><button class="icon-button" data-create-table title="Create table" aria-label="Create table">${icon('plus')}</button></div></div>`;
    html+=tables.map(t=>`<div class="tree-row ${currentTable?.name===t.name?'selected':''}"><button class="caret ${expanded.has(t.name)?'open':''}" data-expand="${escape(t.name)}" aria-label="Show columns for ${escape(t.name)}" aria-expanded="${expanded.has(t.name)}">${icon('right')}</button><span class="table-icon">${icon('table')}</span><button class="tree-name" data-table="${escape(t.name)}" title="Browse ${escape(t.name)}">${escape(t.name)}</button><button class="icon-button" data-select-table="${escape(t.name)}" title="Write SELECT query" aria-label="Write SELECT for ${escape(t.name)}">${icon('code')}</button></div>${expanded.has(t.name)?`<div class="tree-columns">${t.columns.map(c=>`<div class="tree-column" title="${escape(c.name+' · '+c.type+(c.nullable==='YES'?' · nullable':''))}"><span class="${c.keyKind==='PRI'?'key-icon':''}">${icon(c.keyKind==='PRI'?'key':'column')}</span><span>${escape(c.name)}</span><span class="column-type">${escape(c.type)}</span></div>`).join('')}</div>`:''}`).join('');
    if(!tables.length)html+=`<div class="side-empty">${database.tables.length?'No matching tables.':'A fresh database. A blank canvas.<br>Create a table in SQL, or try the practice dataset.'}${!database.tables.length?'<button class="button outline" data-demo>Open practice script</button>':''}</div>`;
  }else if(sideView==='files'){
    html=`<div class="side-section"><span>COURSEWORK</span><button class="icon-button" data-new-file title="New file" aria-label="New file">${icon('plus')}</button></div>`;
    html+=database.files.filter(f=>f.toLowerCase().includes(filter)).map(f=>`<button class="tree-row" style="width:100%;text-align:left" data-file="${escape(f)}"><span class="file-glyph ${f.endsWith('.py')?'python':''}">${f.endsWith('.py')?'PY':f.endsWith('.sql')?'SQL':'TXT'}</span><span class="tree-name">${escape(f)}</span></button>`).join('');
    html+=`<div class="side-empty">Files saved here are shared with the full code editor.<br><button class="button outline" data-python>${icon('python')} Python + MySQL example</button><button class="button ghost" data-import>${icon('upload')} Open a local SQL / Python file</button></div>`;
  }else{
    const runs=history.filter(h=>h.sql.toLowerCase().includes(filter));
    html=`<div class="history-actions"><span>Last ${history.length} runs</span><button data-clear-history>Clear history</button></div>`;
    html+=runs.map(h=>`<button class="history-card" data-history="${h.id}"><code>${escape(h.sql)}</code><div><span class="${h.error?'history-error':'tiny-dot'}">${h.error?'Error':''}</span><span>${new Date(h.time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span><span>· ${h.elapsed||0} ms</span><span>· ${h.language==='python'?'Python':'SQL'}</span></div></button>`).join('');
    if(!runs.length)html+='<div class="side-empty">Your runs will appear here. Click one to reopen its code. It will not run until you choose Run.</div>';
  }
  $('side-content').innerHTML=html;
}
async function openFile(name){
  const existing=tabs.find(t=>t.savedName===name);if(existing){switchTab(existing.id);return;}
  const data=await call('read',{name});
  const tab=newTab(data.text,name.endsWith('.py')?'python':'sql',name.split('/').at(-1));
  if(tab){tab.savedName=name;tab.savedText=data.text;tab.dirty=false;renderTabs();$('document-status').textContent=name;scheduleState();}
}
function showModal(title,description,content,after){
  $('modal-content').innerHTML=`<div class="modal-head"><div><h2>${escape(title)}</h2><p>${escape(description)}</p></div><button class="icon-button" data-dismiss aria-label="Close dialog">${icon('close')}</button></div><div class="modal-body">${content}</div>`;
  if(!$('modal').open)$('modal').showModal();if(after)after();
}
function closeModal(){$('modal').close();view?.focus();}
async function saveDocument(){
  const tab=activeTab();if(!tab)return false;
  tab.text=view.state.doc.toString();
  if(tab.savedName){await saveAs(tab,tab.savedName);return true;}
  showSaveDialog(tab);return false;
}
async function saveAs(tab,name,createOnly=false){
  await call('save',{name,text:tab.text,createOnly,...(name===tab.savedName?{expectedText:tab.savedText}:{})});tab.savedName=name;tab.name=name.split('/').at(-1);tab.savedText=tab.text;tab.dirty=false;renderTabs();
  if(tab.id===active)$('document-status').textContent=name;
  if(!database.files.includes(name))database.files.push(name);database.files.sort();renderSidebar();scheduleState();toast('Saved '+name+' to coursework.');
}
function showSaveDialog(tab,afterSave){
  showModal('Save to coursework','Your file will also appear in the full code editor.',`<form id="save-form"><label class="field-label" for="file-name">File name</label><input class="field-input" id="file-name" value="${escape(tab.name)}" required maxlength="180"><p class="field-note">Use .sql for SQL or .py for Python. Subfolders are welcome.</p><p class="field-error" id="save-error" hidden></p><div class="modal-actions"><button class="button outline" type="button" data-dismiss>Cancel</button><button class="button primary" type="submit">${icon('save')}Save file</button></div></form>`,()=>{
    $('file-name').focus();$('file-name').select();$('save-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;
      try{const name=$('file-name').value.trim();if(tab.language==='python'&&!name.endsWith('.py'))throw Error('Python files need a .py extension.');await saveAs(tab,name,true);closeModal();if(afterSave)await afterSave();}
      catch(error){$('save-error').hidden=false;$('save-error').textContent=error.message;}finally{button.disabled=false;}};
  });
}
function showAppearance(){
  showModal('Make yourself at home.','20 looks. Five layouts. One workspace that feels like yours.',`
    <h3>Layout & feel</h3><div class="layout-options">${layouts.map(l=>`<button class="layout-option ${l.id===layout?'active':''}" data-layout-choice="${l.id}" title="${escape(l.note)}">${escape(l.name)}</button>`).join('')}</div>
    <h3>Choose your look <span style="font-weight:400;letter-spacing:0;text-transform:none">· each includes its own default layout</span></h3><div class="theme-grid">${themes.map(t=>`<button class="theme-card ${t.id===theme.id?'active':''}" data-theme-choice="${t.id}" aria-label="${escape(t.name)}" aria-pressed="${t.id===theme.id}" style="--preview-bg:${t.colors.bg};--preview-side:${t.colors.side};--preview-editor:${t.colors.editor};--preview-accent:${t.colors.accent};--preview-text:${t.colors.text};--preview-radius:${t.layout==='studio'?'5px':'1px'}"><span class="theme-preview"><span class="mini-side"><i></i><i></i><i></i><i></i></span><span class="mini-main"><span class="mini-code"><i></i><i></i></span><span class="mini-results"><i></i><i></i><i></i></span></span></span><span class="theme-name">${escape(t.name)}<span class="theme-check">${t.id===theme.id?'✓':''}</span></span><span class="theme-note">${escape(t.note)}</span></button>`).join('')}</div>
    <div class="appearance-bottom"><span>Preview instantly. Your choice follows this workspace.</span><label>Editor size <select id="font-size">${[11,12,13,14,15,16,18,20].map(n=>`<option ${n===editorSize?'selected':''}>${n}</option>`).join('')}</select></label></div><div class="modal-actions"><button class="button primary" data-dismiss>Looks good ${icon('check')}</button></div>`,()=>{
    $('font-size').onchange=()=>{editorSize=Number($('font-size').value);view.dispatch({effects:fontSize.reconfigure(EditorView.theme({'&':{fontSize:editorSize+'px'}}))});scheduleState();};
  });
}
function showHelp(){
  showModal('A little guidance. A lot of possibility.','SQL comes first. Python connects to the same real MySQL database.',`
  <div class="shortcut-list">${[['Run statement or selection','⌘ / Ctrl Enter'],['Run whole script','⌘ / Ctrl Shift Enter'],['Save file','⌘ / Ctrl S'],['Find in editor','⌘ / Ctrl F'],['Command menu','⌘ / Ctrl K'],['Completion','Ctrl Space']].map(([name,key])=>`<div class="shortcut-row"><span>${name}</span><kbd>${key}</kbd></div>`).join('')}</div>
  <div class="help-grid"><div class="help-card"><h3>SQL that stays out of your way</h3><p>Click a table to browse its rows. Expand its arrow to see columns. Use the table’s code button to write a SELECT. Run uses your selection, or the statement at your cursor.</p><p>Results show up to 500 rows per statement. Table browsing pages through 100 rows at a time. CSV exports contain the displayed rows.</p></div><div class="help-card"><h3>Changes are real</h3><p>Auto-commit is on. INSERT, UPDATE, DELETE and DDL change the real database. Earlier statements can stay committed if a later one fails.</p><p>Each run starts a new connection. Keep <code>START TRANSACTION</code> and <code>COMMIT</code> in the same script. Unfinished transactions roll back when the run ends. MySQL DDL can commit implicitly.</p></div><div class="help-card"><h3>Python, with your database</h3><p>Choose the Python + MySQL example in Files. Save it, then Run Python. It uses the same database credentials through environment variables, never hard-coded passwords.</p><p>${remote?'The browser runner is noninteractive. Breakpoints and terminals are available in the local code editor on your home PC.':'Open Code editor for breakpoints, terminals and larger projects.'} Python is installed; other runtimes and database drivers need administrator setup.</p></div><div class="help-card"><h3>Drafts, files, and your device</h3><p>Tabs, history and appearance are saved to this workspace. Save writes a real coursework file shared with the full editor. File imports accept SQL and Python text; importing does not execute it.</p><p>Runs stop after 35 seconds. Stop cancels the active run; it cannot undo earlier auto-committed changes. Export your work before deleting the Codespace.</p></div></div><div class="modal-actions"><button class="button outline" id="help-demo">Open practice script</button><button class="button primary" data-dismiss>Got it</button></div>`,()=>{$('help-demo').onclick=()=>{closeModal();newTab(demo,'sql','practice-data.sql');};});
}
function createTable(){
  const types=['INT','BIGINT','VARCHAR(100)','VARCHAR(255)','TEXT','DECIMAL(10,2)','DATE','DATETIME','BOOLEAN'];
  const row=(name,type,key=false)=>`<div class="designer-row"><input class="field-input" data-field-name value="${escape(name)}" placeholder="column_name" aria-label="Column name"><select class="field-input" data-field-type aria-label="Column type">${types.map(t=>`<option ${t===type?'selected':''}>${t}</option>`).join('')}</select><label class="field-note"><input type="checkbox" data-field-null ${key?'':'checked'}>NULL</label><button class="icon-button" type="button" data-remove-field aria-label="Remove column">${icon('close')}</button></div>`;
  showModal('A new table. Your structure.','Build the structure, then review the generated MySQL before running it.',`<label class="field-label" for="new-table-name">Table name</label><input class="field-input" id="new-table-name" placeholder="e.g. books" maxlength="64"><p class="field-note">An auto-incrementing integer primary key named id is included.</p><div id="designer-fields" style="margin-top:20px">${row('name','VARCHAR(100)')}${row('created_at','DATETIME')}</div><button class="button outline" id="add-field" style="margin-top:12px">${icon('plus')}Add column</button><p class="field-error" id="designer-error" hidden></p><div class="modal-actions"><button class="button outline" data-dismiss>Cancel</button><button class="button primary" id="review-create-table">Review SQL ${icon('arrow')}</button></div>`,()=>{
    $('new-table-name').focus();$('add-field').onclick=()=>$('designer-fields').insertAdjacentHTML('beforeend',row('','VARCHAR(100)'));
    $('designer-fields').onclick=e=>{const remove=e.target.closest('[data-remove-field]');if(remove)remove.closest('.designer-row').remove();};
    $('review-create-table').onclick=()=>{try{
      const name=$('new-table-name').value.trim();if(!name||name.length>64)throw Error('Choose a table name of up to 64 characters.');
      const fields=Array.from($('designer-fields').children).map(r=>({name:r.querySelector('[data-field-name]').value.trim(),type:r.querySelector('[data-field-type]').value,nullable:r.querySelector('[data-field-null]').checked}));
      if(fields.some(f=>!f.name||f.name.length>64)||new Set(['id',...fields.map(f=>f.name.toLowerCase())]).size!==fields.length+1)throw Error('Give each column a unique name. The name id is already used.');
      const q=n=>'`'+n.replaceAll('`','``')+'`';
      const script='CREATE TABLE '+q(name)+' (\n    `id` INT AUTO_INCREMENT PRIMARY KEY'+fields.map(f=>',\n    '+q(f.name)+' '+f.type+(f.nullable?' NULL':' NOT NULL')).join('')+'\n);\n\nSELECT * FROM '+q(name)+';\n';
      closeModal();newTab(script,'sql','create-'+name+'.sql');toast('Review your table, then choose Run whole script to create it.');
    }catch(error){$('designer-error').hidden=false;$('designer-error').textContent=error.message;}};
  });
}
function showCommands(){
  const commands=[['New SQL query','plus',()=>newTab()],['Python + MySQL example','python',()=>newTab(pythonExample,'python','database.py')],['Run statement or selection','play',()=>run('smart')],['Run whole script','play',()=>run('all')],['Format SQL','format',formatDocument],['Save current file','save',saveDocument],['Open local SQL / Python file','upload',importFile],['Appearance · 20 looks','palette',showAppearance],['Refresh database and files','refresh',refresh],['Practice dataset script','database',()=>newTab(demo,'sql','practice-data.sql')],['Help and keyboard shortcuts','help',showHelp],['Full code editor','code',()=>location.assign('/?folder=/home/coder/coursework')]];
  showModal('Jump to anything.','A shortcut to the things you do most.',`<input class="field-input" id="command-filter" placeholder="Search commands or tables…" aria-label="Search commands"><div class="command-list" id="command-list"></div>`,()=>{
    const render=()=>{const term=$('command-filter').value.toLowerCase();const items=(remote?commands.filter(c=>c[0]!=='Full code editor'):commands).concat(database.tables.map(t=>['Browse '+t.name,'table',()=>browseTable(t.name)]));$('command-list').replaceChildren(...items.filter(c=>c[0].toLowerCase().includes(term)).map(([title,glyph,action])=>{const b=document.createElement('button');b.className='command-item';b.innerHTML=icon(glyph)+`<span>${escape(title)}</span>`;b.onclick=()=>{closeModal();Promise.resolve(action()).catch(e=>toast(e.message));};return b;}));};
    $('command-filter').oninput=render;$('command-filter').onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();$('command-list').querySelector('button')?.focus();}if(e.key==='Enter'){$('command-list').querySelector('button')?.click();}};render();$('command-filter').focus();
  });
}
function formatDocument(){
  if(activeTab()?.language!=='sql'){toast('Formatting is available for SQL.');return;}
  const sel=view.state.selection.main,text=sel.empty?view.state.doc.toString():view.state.sliceDoc(sel.from,sel.to);
  try{const formatted=formatSQL(text,{language:'mysql',keywordCase:'upper',tabWidth:4});view.dispatch({changes:{from:sel.empty?0:sel.from,to:sel.empty?view.state.doc.length:sel.to,insert:formatted}});toast('SQL formatted. Undo is available in the editor.');}
  catch(error){toast('This SQL could not be formatted. Your code has been kept as it was.');}
}
function codeFor(scope){
  const text=view.state.doc.toString(),sel=view.state.selection.main;
  if(scope==='all')return text;
  if(!sel.empty)return view.state.sliceDoc(sel.from,sel.to);
  if(scope==='selected')throw Error('Select the SQL you want to run first.');
  return currentStatement(text,sel.head).text;
}
async function run(scope='smart',explain=false){
  if(runId){toast('A run is in progress. Stop it or wait for it to finish.');return;}
  const tab=activeTab();if(!tab)return;
  if(tab.language==='python'){
    if(!tab.savedName){tab.text=view.state.doc.toString();showSaveDialog(tab,()=>run('all'));return;}
    await saveAs(tab,tab.savedName);
  }
  let text=tab.language==='python'?tab.text:codeFor(scope);
  if(!text.trim()){toast('Write a query first.');return;}
  if(explain){
    const stripped=text.replace(/^\s*(?:(?:--[^\n]*|#[^\n]*)\n|\/\*[\s\S]*?\*\/)\s*/g,'').trim();
    if(!/^(SELECT|WITH)\b/i.test(stripped)||statements(text).length!==1){toast('Explain works on one SELECT or WITH query. Select a single query first.');return;}
    text='EXPLAIN FORMAT=JSON '+text.replace(/;\s*$/,'');
  }
  tableRequest++;currentTable=null;resultSets=[];resultError=null;output=null;sourceLabel=tab.name;resultElapsed=0;
  setTask(tab.language==='python'?'Running Python…':'Running SQL…');$('run').disabled=true;$('stop').hidden=false;$('run-options').disabled=true;
  $('result-title').textContent=tab.language==='python'?'Python output':'Running query';$('result-tabs').hidden=true;$('result-subbar').hidden=true;$('result-count').hidden=true;$('execution-meta').textContent='';
  $('copy-results').disabled=true;$('export').disabled=true;
  $('result-content').innerHTML=`<div class="running-state"><div class="spinner"></div><div><strong>${tab.language==='python'?'Python is running.':'Asking your database…'}</strong><p>You can keep editing. Runs have a 35-second limit.</p></div></div>`;
  runningSince=Date.now();
  try{
    const response=await api('run',tab.language==='python'?{op:'python',name:tab.savedName}:{op:'execute',sql:text});runId=response.id;
    const captured={text,language:tab.language,time:Date.now(),id:id()};
    const poll=async()=>{
      try{
        const job=await api('job',{id:runId});
        if(job.state==='running'){$('execution-meta').textContent=((Date.now()-runningSince)/1000).toFixed(1)+' s';pollTimer=setTimeout(poll,400);return;}
        const result=job.result||{};resultSets=result.results||[];resultIndex=0;resultError=result.error||null;output=tab.language==='python'?(result.output||''):null;resultElapsed=result.elapsed||Date.now()-runningSince;resultRolledBack=!!result.rolledBack;
        captured.error=!!resultError;captured.elapsed=resultElapsed;history.unshift({...captured,sql:captured.text.slice(0,20000),truncated:captured.text.length>20000});delete history[0].text;history=history.slice(0,30);scheduleState();
        finishRun();renderResults(result.rolledBack);renderSidebar();
        if(!resultError&&tab.language==='sql')refresh().catch(()=>{});
      }catch(error){finishRun();resultError=error.message;renderResults();}
    };
    poll();
  }catch(error){finishRun();resultError=error.message;renderResults();}
}
function finishRun(){runId=null;clearTimeout(pollTimer);$('run').disabled=false;$('stop').hidden=true;$('run-options').disabled=activeTab()?.language==='python';setTask(resultError?'Run finished with an error':'Ready',!!resultError);}
function errorHTML(message){return `<div class="query-error"><strong>${icon('error')}Something to look at</strong><pre>${escape(message)}</pre><p>Check the statement and try again. Any earlier auto-committed changes may still be present.</p></div>`;}
function renderResults(rolledBack=resultRolledBack){
  currentTable=null;selectedCell=null;$('result-subbar').hidden=true;
  $('result-title').textContent=output!==null?'Python output':resultError&&!resultSets.length?'Query error':'Results';
  $('execution-meta').textContent=sourceLabel?resultElapsed.toLocaleString()+' ms':'';
  $('result-count').hidden=!resultSets.length;$('result-count').textContent=resultSets.length;
  $('result-tabs').hidden=resultSets.length<2;
  $('result-tabs').innerHTML=resultSets.map((r,i)=>`<button class="result-tab" role="tab" aria-selected="${i===resultIndex}" data-result="${i}"><span class="tiny-dot"></span>${i+1} · ${escape((r.statement||'Result').replace(/^\s*(?:--[^\n]*\n)*/,'').trim().split(/\s+/)[0].slice(0,15).toUpperCase())}${r.columns.length?' · '+r.rows.length+' rows':''}</button>`).join('');
  let html='';const result=resultSets[resultIndex];
  if(output!==null)html=`<pre class="output">${escape(output||(!resultError?'Python finished without printing output.':''))}</pre>`;
  else if(result?.columns.length){html=explainHTML(result)||tableHTML(result.columns,result.rows,false);$('result-footer').innerHTML=`<span>${result.rowCount??result.rows.length} rows${result.truncated?' · preview limited to '+(result.previewLimit||500)+' rows':''}</span><span>${result.warnings?result.warnings+' warning(s) · ':''}${escape(sourceLabel)} · ${resultElapsed} ms</span>`;}
  else if(result){html=`<div class="query-success"><span class="success-icon">${icon('check')}</span><div><strong>Statement completed.</strong><p>${Math.max(0,result.affected)} row${result.affected===1?'':'s'} affected${result.warnings?' · '+result.warnings+' warning(s)':''}.</p><p>Auto-commit is enabled. Explicit transactions follow MySQL rules.</p></div></div>`;}
  else if(!resultError)html='<div class="empty-state"><h1>A clean slate.</h1><p>Run a query to see its results.</p></div>';
  if(resultError)html+=errorHTML(resultError);
  if(rolledBack)html+='<div class="query-error"><strong>Unfinished transaction rolled back</strong><p>The script ended before COMMIT. Keep the whole transaction in one run. DDL may still have committed implicitly.</p></div>';
  $('result-content').innerHTML=html;
  $('copy-results').disabled=!(result?.columns.length||output!==null);$('export').disabled=!result?.columns.length;
  if(!result?.columns.length)$('result-footer').innerHTML=`<span>${resultError?'Finished with an error':output!==null?'Python · shared MySQL database':'Ready'}</span><span>${sourceLabel?escape(sourceLabel)+' · '+resultElapsed+' ms':'Real MySQL. Your own work.'}</span>`;
}
function explainHTML(result){
  if(result.columns.length!==1||result.columns[0].name!=='EXPLAIN'||!result.rows.length)return '';
  try{
    const plan=JSON.parse(result.rows[0][0]),tables=[];
    const scan=node=>{if(!node||typeof node!=='object')return;if(node.table_name)tables.push(node);for(const value of Object.values(node))if(typeof value==='object')scan(value);};scan(plan);
    const cost=plan.query_block?.cost_info?.query_cost;
    return `<div class="plan-view"><div class="plan-heading"><strong>Query plan</strong><span>Estimates from MySQL${cost?' · cost '+escape(cost):''} · not an actual execution measurement</span></div>${tables.map((t,i)=>`<div class="plan-step"><span class="plan-number">${i+1}</span><div><strong>${escape(t.table_name)}</strong><p>${escape(t.access_type==='ALL'?'Full table scan':t.access_type||'Access')}${t.key?' · index '+escape(t.key):''}</p></div><div class="plan-rows"><strong>${escape(t.rows_examined_per_scan??'—')}</strong><span>rows per scan</span></div></div>`).join('')}<details><summary>View full JSON plan</summary><pre class="output">${escape(JSON.stringify(plan,null,2))}</pre></details></div>`;
  }catch{return '';}
}
function inspectCell(row,column){
  const data=currentData();if(!data)return;
  const value=data.rows[row]?.[column];
  showModal(data.columns[column].name,'Result value · read only',`<textarea class="field-input" id="inspect-value" readonly>${escape(value===null?'NULL':value)}</textarea><p class="field-note">${escape(data.columns[column].type)}${value===null?' · SQL NULL':''}</p><div class="modal-actions"><button class="button primary" data-dismiss>Done</button></div>`,()=>{$('inspect-value').focus();$('inspect-value').select();});
}
function tableHTML(columns,rows,editable=false){
  return `<table class="data-table"><thead><tr><th class="row-number">#</th>${columns.map(c=>`<th>${editable?`<button class="sort-button" data-sort="${escape(c.name)}">`:''}${escape(c.name)}<span class="column-data-type">${escape(c.type)}</span>${editable?(tableSort===c.name?icon('chevron'):'')+'</button>':''}</th>`).join('')}</tr></thead><tbody>${rows.map((row,i)=>`<tr><td class="row-number">${(currentTable?tableOffset:0)+i+1}</td>${row.map((v,j)=>`<td tabindex="0" data-row="${i}" data-column="${j}" class="${/INT|DECIMAL|FLOAT|DOUBLE|NUMERIC/.test(columns[j].type)?'number ':''}${editable?'editable-cell':''}" title="${escape(v===null?'NULL':v)}${editable?' · double-click to edit':''}">${v===null?'<span class="null">NULL</span>':escape(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>${!rows.length?'<div class="side-empty">No rows match this query.</div>':''}`;
}
async function browseTable(name,options={}){
  if(runId){toast('Wait for the active run before browsing another table.');return;}
  const request=++tableRequest;
  if(currentTable?.name!==name){tableSort=null;tableDirection='ASC';tableSearch='';tableOffset=0;}
  if(options.offset!==undefined)tableOffset=options.offset;if(options.search!==undefined){tableSearch=options.search;tableOffset=0;}
  $('result-content').innerHTML='<div class="running-state"><div class="spinner"></div><div>Opening table…</div></div>';
  const result=await call('table',{table:name,limit:100,offset:tableOffset,search:tableSearch,sort:tableSort,direction:tableDirection});
  if(request!==tableRequest)return;
  currentTable={name,...result,mode:'data'};resultError=null;output=null;resultSets=[];resultIndex=0;selectedCell=null;
  $('result-title').textContent=name;$('result-count').hidden=false;$('result-count').textContent=result.total.toLocaleString();$('execution-meta').textContent='Table browser';$('result-tabs').hidden=true;
  const canEdit=result.table.kind==='BASE TABLE'&&result.table.columns.some(c=>c.keyKind==='PRI');
  $('result-subbar').hidden=false;$('result-subbar').innerHTML=`<button class="button outline" id="data-view">${icon('table')}Data</button><button class="button ghost" id="structure-view">${icon('column')}Structure</button><input type="search" id="table-search" placeholder="Search rows…" aria-label="Search table rows" value="${escape(tableSearch)}"><button class="icon-button" id="search-table" title="Search table" aria-label="Search table">${icon('search')}</button><span style="margin-left:auto"></span><button class="icon-button" id="previous-page" title="Previous 100 rows" aria-label="Previous page" ${tableOffset===0?'disabled':''}>${icon('right')}</button><span>${result.total?tableOffset+1:0}–${Math.min(tableOffset+result.rows.length,result.total)} of ${result.total.toLocaleString()}</span><button class="icon-button" id="next-page" title="Next 100 rows" aria-label="Next page" ${tableOffset+result.rows.length>=result.total?'disabled':''}>${icon('right')}</button>`;
  $('previous-page').style.transform='rotate(180deg)';
  $('result-content').innerHTML=tableHTML(result.columns,result.rows,canEdit);
  $('result-footer').innerHTML=`<span>${canEdit?'Double-click a cell to edit · primary key identifies the row':'Read-only grid · use SQL to make changes'}${result.truncated?' · large values limited this preview':result.total>100?' · 100 rows per page':''}</span><span>${escape(name)} · ${result.table.columns.length} columns</span>`;
  $('copy-results').disabled=false;$('export').disabled=false;
  $('table-search').onkeydown=e=>{if(e.key==='Enter')browseTable(name,{search:$('table-search').value}).catch(e=>toast(e.message));};
  $('search-table').onclick=()=>browseTable(name,{search:$('table-search').value}).catch(e=>toast(e.message));
  $('previous-page').onclick=()=>browseTable(name,{offset:Math.max(0,tableOffset-100)}).catch(e=>toast(e.message));
  $('next-page').onclick=()=>browseTable(name,{offset:tableOffset+result.rows.length}).catch(e=>toast(e.message));
  $('data-view').onclick=()=>browseTable(name).catch(e=>toast(e.message));
  $('structure-view').onclick=()=>showStructure(result.table);
  renderSidebar();$('sidebar').classList.remove('sidebar-open');setTask('Browsing '+name);
}
function showStructure(table){
  currentTable.mode='structure';
  $('result-content').innerHTML=tableHTML([{name:'Column',type:''},{name:'Type',type:''},{name:'Nullable',type:''},{name:'Key',type:''},{name:'Default',type:''},{name:'Extra',type:''}],table.columns.map(c=>[c.name,c.type,c.nullable,c.keyKind,c.defaultValue,c.extra]));
  if(table.relations.length)$('result-content').insertAdjacentHTML('beforeend','<div class="side-empty">'+table.relations.map(r=>`${escape(r.columnName)} → ${escape(r.targetTable)}.${escape(r.targetColumn)}`).join('<br>')+'</div>');
  $('result-footer').innerHTML='<span>Table structure · '+table.columns.length+' columns</span><span>'+escape(table.name)+'</span>';
  $('copy-results').disabled=true;$('export').disabled=true;
}
function editCell(row,column){
  const t=currentTable;if(!t||t.mode==='structure')return;
  const field=t.table.columns[column];const primary=t.table.columns.filter(c=>c.keyKind==='PRI');
  if(!primary.length||t.table.kind!=='BASE TABLE'||field.extra.includes('GENERATED')){toast('Use SQL to change this value. Grid editing needs a primary key and a writable column.');return;}
  const original=t.rows[row][column];const keys=Object.fromEntries(primary.map(c=>[c.name,t.rows[row][t.columns.findIndex(f=>f.name===c.name)]]));
  showModal('Edit '+field.name,`${t.name} · ${Object.entries(keys).map(([k,v])=>k+' = '+v).join(', ')}`,`<form id="edit-cell-form"><label class="field-label" for="cell-value">Value · ${escape(field.type)}</label><textarea class="field-input" id="cell-value" ${original===null?'disabled':''}>${escape(original??'')}</textarea><label class="field-note" style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="cell-null" ${original===null?'checked':''} ${field.nullable!=='YES'?'disabled':''}>Set to NULL ${field.nullable!=='YES'?'(this column is required)':''}</label><p class="field-note">Saving updates one row in MySQL immediately. A concurrent change will be detected.</p><p class="field-error" id="cell-error" hidden></p><div class="modal-actions"><button class="button outline" type="button" data-dismiss>Cancel</button><button class="button primary" type="submit">Save change</button></div></form>`,()=>{
    $('cell-null').onchange=()=>$('cell-value').disabled=$('cell-null').checked;
    $('edit-cell-form').onsubmit=async e=>{e.preventDefault();const value=$('cell-null').checked?null:$('cell-value').value;
      if((original===null&&value===null)||(original!==null&&String(original)===value)){closeModal();return;}
      e.submitter.disabled=true;
      try{await call('update',{table:t.name,column:field.name,keys,original,value});closeModal();await browseTable(t.name);toast('One row updated.');}
      catch(error){$('cell-error').hidden=false;$('cell-error').textContent=error.message;e.submitter.disabled=false;}
    };
  });
}
function currentData(){if(currentTable)return currentTable;return resultSets[resultIndex];}
function csvCell(value){const s=value===null?'':String(value);return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;}
function download(text,name,type='text/plain'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
function exportCSV(){const data=currentData();if(!data)return;const csv=[data.columns.map(c=>csvCell(c.name)).join(','),...data.rows.map(r=>r.map(csvCell).join(','))].join('\r\n');download(csv,(currentTable?.name||'query-results')+'.csv','text/csv;charset=utf-8');toast('Exported '+data.rows.length+' displayed rows.');}
async function copyResults(){const data=currentData();const text=output!==null?output:data?[data.columns.map(c=>c.name).join('\t'),...data.rows.map(r=>r.map(v=>v===null?'NULL':String(v)).join('\t'))].join('\n'):'';try{await navigator.clipboard.writeText(text);toast('Displayed results copied.');}catch{showModal('Copy results','Select and copy the text below.',`<textarea class="field-input" id="copy-text">${escape(text)}</textarea><div class="modal-actions"><button class="button primary" data-dismiss>Done</button></div>`,()=>{$('copy-text').focus();$('copy-text').select();});}}
function importFile(){
  const input=document.createElement('input');input.type='file';input.accept='.sql,.py,.txt';input.onchange=async()=>{const file=input.files[0];if(!file)return;if(file.size>1024*1024){toast('Open files up to 1 MB here. Use the full code editor for larger files.');return;}newTab(await file.text(),file.name.endsWith('.py')?'python':'sql',file.name);toast('Opened '+file.name+'. Review the code before running it.');};input.click();
}

on('run','click',()=>run());on('first-run','click',()=>run('all'));on('format','click',formatDocument);on('save','click',saveDocument);on('explain','click',()=>run('smart',true));
on('appearance','click',showAppearance);on('appearance-small','click',showAppearance);on('theme-status','click',showAppearance);on('commands','click',showCommands);on('help','click',showHelp);on('refresh','click',refresh);
on('side-filter','input',renderSidebar);on('export','click',exportCSV);on('copy-results','click',copyResults);
on('focus','click',()=>document.body.classList.toggle('focus-mode'));
on('toggle-sidebar','click',()=>$('sidebar').classList.toggle('sidebar-open'));on('close-sidebar','click',()=>$('sidebar').classList.remove('sidebar-open'));
on('language-switch','click',()=>{const tab=activeTab();tab.language=tab.language==='sql'?'python':'sql';switchTab(tab.id);});
on('stop','click',async()=>{if(runId){$('stop').disabled=true;try{await api('stop',{id:runId});setTask('Stopping…');}finally{$('stop').disabled=false;}}});
on('clear-results','click',()=>{if(runId){toast('Stop the current run first.');return;}resultSets=[];resultError=null;currentTable=null;output=null;sourceLabel='';renderResults();renderSidebar();});
on('run-options','click',()=>{const menu=$('run-menu'),rect=$('run-options').getBoundingClientRect();menu.hidden=!menu.hidden;menu.style.top=(rect.bottom+5)+'px';menu.style.left=Math.min(rect.left-110,innerWidth-350)+'px';if(parseInt(menu.style.left)<8)menu.style.left='8px';});
document.addEventListener('click',async event=>{
  const target=event.target.closest('button,[data-tab]');if(!target){if(!event.target.closest('#run-menu'))$('run-menu').hidden=true;return;}
  try{
    if(target.hasAttribute('data-dismiss'))closeModal();
    else if(target.dataset.themeChoice){applyTheme(themes.find(t=>t.id===target.dataset.themeChoice));showAppearance();}
    else if(target.dataset.layoutChoice){applyTheme(theme,target.dataset.layoutChoice);showAppearance();}
    else if(target.dataset.view){sideView=target.dataset.view;$('side-filter').value='';renderSidebar();}
    else if(target.dataset.tab)switchTab(target.dataset.tab);
    else if(target.dataset.close){const tab=tabs.find(t=>t.id===target.dataset.close);if(tab.dirty){showModal('Close this tab?','Your latest changes have not been saved to a coursework file.',`<p class="field-note">${escape(tab.name)}</p><div class="modal-actions"><button class="button outline" data-dismiss>Keep editing</button><button class="button outline" id="discard-tab">Discard changes</button><button class="button primary" id="save-close-tab">Save & close</button></div>`,()=>{$('discard-tab').onclick=()=>{closeModal();closeTab(tab.id);};$('save-close-tab').onclick=async()=>{switchTab(tab.id);closeModal();if(tab.savedName){await saveAs(tab,tab.savedName);closeTab(tab.id);}else showSaveDialog(tab,()=>closeTab(tab.id));};});}else closeTab(tab.id);}
    else if(target.id==='new-tab'||target.hasAttribute('data-new-file'))newTab();
    else if(target.dataset.expand){const name=target.dataset.expand;expanded.has(name)?expanded.delete(name):expanded.add(name);renderSidebar();}
    else if(target.dataset.table)await browseTable(target.dataset.table);
    else if(target.dataset.selectTable){const name=target.dataset.selectTable;newTab('SELECT *\nFROM `'+name.replaceAll('`','``')+'`\nLIMIT 100;','sql',name+'.sql');}
    else if(target.dataset.file)await openFile(target.dataset.file);
    else if(target.hasAttribute('data-python'))newTab(pythonExample,'python','database.py');
    else if(target.hasAttribute('data-create-table'))createTable();
    else if(target.hasAttribute('data-import'))importFile();
    else if(target.hasAttribute('data-demo'))newTab(demo,'sql','practice-data.sql');
    else if(target.dataset.history){const item=history.find(h=>h.id===target.dataset.history);if(item.truncated){toast('This history preview is shortened. Reopen the saved script for its full text.');return;}newTab(item.sql,item.language,item.language==='python'?'history.py':'history.sql');}
    else if(target.hasAttribute('data-clear-history')){history=[];renderSidebar();scheduleState();}
    else if(target.dataset.run){$('run-menu').hidden=true;await run(target.dataset.run);}
    else if(target.dataset.result!==undefined){resultIndex=Number(target.dataset.result);renderResults();}
    else if(target.dataset.sort&&currentTable){tableDirection=tableSort===target.dataset.sort&&tableDirection==='ASC'?'DESC':'ASC';tableSort=target.dataset.sort;await browseTable(currentTable.name);}
  }catch(error){toast(error.message);}
});
function closeTab(identifier){const index=tabs.findIndex(t=>t.id===identifier);tabs=tabs.filter(t=>t.id!==identifier);if(!tabs.length)newTab();else if(active===identifier)switchTab(tabs[Math.max(0,index-1)].id);else renderTabs();scheduleState();}
$('document-tabs').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.hasAttribute('data-tab')){e.preventDefault();switchTab(e.target.dataset.tab);}});
$('result-content').addEventListener('click',e=>{const cell=e.target.closest('td[data-row]');if(!cell)return;selectedCell?.classList.remove('selected-cell');selectedCell=cell;cell.classList.add('selected-cell');});
$('result-content').addEventListener('dblclick',e=>{const cell=e.target.closest('td[data-row]');if(!cell)return;if(currentTable&&cell.classList.contains('editable-cell'))editCell(Number(cell.dataset.row),Number(cell.dataset.column));else if(currentTable?.mode!=='structure')inspectCell(Number(cell.dataset.row),Number(cell.dataset.column));});
$('result-content').addEventListener('keydown',async e=>{const cell=e.target.closest('td[data-row]');if(!cell)return;if(e.key==='Enter'&&currentTable){e.preventDefault();editCell(Number(cell.dataset.row),Number(cell.dataset.column));}if((e.ctrlKey||e.metaKey)&&e.key==='c'){try{await navigator.clipboard.writeText(cell.textContent);toast('Cell copied.');}catch{toast('Use the Copy results button to copy the full grid.');}}});
document.addEventListener('keydown',e=>{if(e.defaultPrevented||(remote&&remote.panel.open))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();showCommands();}if(e.key==='Escape')$('run-menu').hidden=true;});
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal();});
const splitter=$('splitter');let dragging=false;
splitter.addEventListener('pointerdown',e=>{dragging=true;splitter.setPointerCapture(e.pointerId);splitter.classList.add('dragging');});
splitter.addEventListener('pointermove',e=>{if(!dragging)return;const rect=$('editor').parentElement.getBoundingClientRect(),main=document.querySelector('.main-pane').getBoundingClientRect();const height=Math.max(130,Math.min(e.clientY-rect.top,main.height-220));document.documentElement.style.setProperty('--editor-height',height+'px');});
splitter.addEventListener('pointerup',()=>{dragging=false;splitter.classList.remove('dragging');scheduleState();});
splitter.addEventListener('keydown',e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();const height=document.querySelector('.editor-pane').offsetHeight+(e.key==='ArrowUp'?-20:20);document.documentElement.style.setProperty('--editor-height',Math.max(130,Math.min(height,document.querySelector('.main-pane').offsetHeight-220))+'px');scheduleState();}});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'&&!booting){clearTimeout(saveTimer);persistState();}});
window.addEventListener('beforeunload',e=>{if(tabs.some(t=>t.dirty)&&$('draft-status').textContent!=='Drafts saved to workspace'){e.preventDefault();e.returnValue='';}});

async function boot(){
  makeEditor();let saved=null;try{const stored=localStorage.getItem('study-theme');theme=themes.find(t=>t.id===stored)||themes[0];}catch{}
  applyTheme(theme,theme.layout,false);
  try{
    if(remote){
      document.querySelector('.code-link').hidden=true;
      const button=document.createElement('button');button.className='button ghost';button.textContent='Sign out';button.onclick=()=>remote.signOut().catch(e=>toast(e.message));document.querySelector('.top-actions').append(button);
      $('connection-detail').textContent='Waiting for home PC';setTask('Connecting to home PC…');
      await remote.connect();
    }
    const statePromise=call('state').catch(()=>({value:null}));await refresh();saved=(await statePromise).value;
    if(saved?.version===1&&Array.isArray(saved.tabs)&&saved.tabs.length){
      tabs=saved.tabs.filter(t=>typeof t.id==='string'&&typeof t.text==='string'&&['sql','python'].includes(t.language)).slice(0,12);
      history=Array.isArray(saved.history)?saved.history.filter(h=>typeof h.sql==='string').slice(0,30):[];
      theme=themes.find(t=>t.id===saved.theme)||theme;layout=saved.layout;editorSize=[11,12,13,14,15,16,18,20].includes(saved.editorSize)?saved.editorSize:13;
      applyTheme(theme,layout,false);view.dispatch({effects:fontSize.reconfigure(EditorView.theme({'&':{fontSize:editorSize+'px'}}))});
      if(/^\d{3,4}px$/.test(saved.editorHeight||''))document.documentElement.style.setProperty('--editor-height',saved.editorHeight);
    }
    booting=false;
    if(tabs.length)switchTab(tabs.some(t=>t.id===saved?.active)?saved.active:tabs[0].id);else newTab();
    renderSidebar();$('draft-status').textContent='Drafts saved to workspace';setTask('Ready');
  }catch(error){booting=false;newTab();setTask('Connection needs attention',true);toast(error.message);}
}
if(!config.redirecting){if(window.self===window.top)boot();else location.replace(remote?new URL('./standalone.html',location.href):'/__study/browser');}
