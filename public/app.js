import { EngineAdapter } from './engine-adapter.js';
const $ = id => document.getElementById(id);
const engine = new EngineAdapter($('gameCanvas'), message => setStatus(message));
const settingsIds=['nickname','volume','touchMode','preset','scale','fps','filter'];
const defaults={nickname:'Jogador',volume:'85',touchMode:'auto',preset:'balanced',scale:'2',fps:'30',filter:'linear'};
const settings={...defaults};
for(const key of settingsIds) { const saved=localStorage.getItem(`stor-pes6:${key}`); if(saved!==null)settings[key]=saved; $(key).value=settings[key]; }
function setStatus(message){$('runStatus').textContent=message;}
function showInfo(message){$('stageInfo').textContent=message;}
const useCoarse = () => window.matchMedia('(pointer: coarse)').matches;
function touchVisible(){return settings.touchMode==='on'||(settings.touchMode==='auto'&&useCoarse());}
function updateTouch(){const visible=touchVisible();$('touchPad').classList.toggle('visible',visible);$('touchToggle').textContent=visible?'◉ Ocultar touch':'◉ Mostrar touch';}
function collect(){return {audio:{volume:Number(settings.volume)/100},render:{scale:Number(settings.scale),fps:Number(settings.fps),filter:settings.filter,preset:settings.preset}};}
function updateGraphics(){ $('volumeOutput').textContent=`${settings.volume}%`; $('graphicsSummary').textContent=`Perfil ${settings.preset} • ${settings.scale}x • ${settings.fps} FPS`; engine.configure(collect()); }
function choosePreset(value){if(value==='low'){settings.scale='1';settings.fps='30';settings.filter='nearest';}else if(value==='balanced'){settings.scale='2';settings.fps='30';settings.filter='linear';}else{settings.scale='3';settings.fps='60';settings.filter='linear';} for(const key of ['scale','fps','filter']) {$(key).value=settings[key]; localStorage.setItem(`stor-pes6:${key}`,settings[key]);}}
for(const key of settingsIds)$(key).addEventListener('input',()=>{settings[key]=$(key).value;localStorage.setItem(`stor-pes6:${key}`,settings[key]);if(key==='preset')choosePreset(settings.preset);if(key==='touchMode')updateTouch();updateGraphics();});
updateTouch();updateGraphics();
window.matchMedia('(pointer: coarse)').addEventListener?.('change',updateTouch);
for(const tab of document.querySelectorAll('[data-tab]'))tab.addEventListener('click',()=>{
  for(const btn of document.querySelectorAll('[data-tab]'))btn.classList.toggle('active',btn===tab);
  for(const panel of document.querySelectorAll('[data-panel]'))panel.hidden=panel.dataset.panel!==tab.dataset.tab;
  if(tab.dataset.tab==='online')refreshRooms();
});
async function checkEngine(){const ready=await engine.available();$('engineFlag').textContent=ready?'Módulo encontrado':'Aguardando WebAssembly';setStatus(ready?'Motor detectado; pronto para testar':'Launcher ativo • motor ainda ausente');return ready;}
$('startGame').addEventListener('click',async()=>{
  $('startGame').disabled=true;
  try{
    await engine.start(collect()); $('stage').classList.add('playing');$('engineFlag').textContent='Motor carregado';setStatus('Motor iniciado');
  }catch(e){showInfo(e.message);setStatus('O jogo ainda não está disponível');}
  finally{$('startGame').disabled=false;}
});
checkEngine();
$('goFullscreen').addEventListener('click',async()=>{const el=$('stage');if(document.fullscreenElement)await document.exitFullscreen();else await el.requestFullscreen?.();});
$('touchToggle').addEventListener('click',()=>{$('touchMode').value=touchVisible()?'off':'on';$('touchMode').dispatchEvent(new Event('input'));});
$('controlHelp').addEventListener('click',()=>$('helpDialog').showModal());
$('closeHelp').addEventListener('click',()=>$('helpDialog').close());

// Use one action bus for keyboard, pointer and Gamepad API. Never synthesize untrusted keyboard events.
const keyToAction={ArrowUp:'up',KeyW:'up',ArrowDown:'down',KeyS:'down',ArrowLeft:'left',KeyA:'left',ArrowRight:'right',KeyD:'right',KeyJ:'cross',Enter:'cross',KeyK:'circle',Escape:'circle',KeyU:'square',KeyI:'triangle',KeyQ:'L',KeyE:'R',Space:'start',Backspace:'select'};
const sourceStates=new Map();
function input(source, action, down) {
  const key=`${source}:${action}`;
  if(sourceStates.get(key)===down)return;
  if(down)sourceStates.set(key,true);else sourceStates.delete(key);
  const active=[...sourceStates.keys()].some(k=>k.endsWith(`:${action}`));
  engine.input(action,active);
  $('inputTest').textContent=`Última entrada: ${action.toUpperCase()} ${down?'pressionado':'solto'} (${source})`;
  for(const btn of document.querySelectorAll('[data-control]'))if(btn.dataset.control===action)btn.classList.toggle('pressed',active);
}
function releaseAll(){const keys=[...sourceStates.keys()];for(const item of keys){const p=item.lastIndexOf(':');input(item.slice(0,p),item.slice(p+1),false);}}
for(const eventName of ['keydown','keyup'])window.addEventListener(eventName,e=>{
  if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)||$('helpDialog').open)return;
  const action=keyToAction[e.code]; if(!action)return;
  e.preventDefault(); if(e.repeat)return;
  input('keyboard',action,eventName==='keydown');
});
window.addEventListener('blur',releaseAll);
for(const btn of document.querySelectorAll('[data-control]')){
  btn.addEventListener('pointerdown',e=>{e.preventDefault();btn.setPointerCapture(e.pointerId);input(`touch${e.pointerId}`,btn.dataset.control,true);});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])btn.addEventListener(name,e=>input(`touch${e.pointerId}`,btn.dataset.control,false));
}
const padKeys={0:'cross',1:'circle',2:'square',3:'triangle',4:'L',5:'R',8:'select',9:'start',12:'up',13:'down',14:'left',15:'right'};
function pollPads(){
  const pads=navigator.getGamepads?.()||[];
  for(let p=0;p<4;p++){
    const pad=pads[p];const source=`gamepad${p}`;
    if(!pad){for(const action of new Set(Object.values(padKeys)))input(source,action,false);continue;}
    const states=new Set(pad.buttons.flatMap((b,i)=>b.pressed&&padKeys[i]?[padKeys[i]]:[]));
    const x=pad.axes[0]||0,y=pad.axes[1]||0;
    if(x<-.45)states.add('left');if(x>.45)states.add('right');if(y<-.45)states.add('up');if(y>.45)states.add('down');
    for(const action of new Set(Object.values(padKeys)))input(source,action,states.has(action));
  }
  requestAnimationFrame(pollPads);
}
requestAnimationFrame(pollPads);

const api=async(path,init={})=>{
  const response=await fetch(path,{...init,headers:{'Content-Type':'application/json',...(init.headers||{})}});
  const body=await response.json();if(!response.ok)throw new Error(body.error||'Falha na requisição');return body;
};
let membership=null;let stream=null;let heartbeat=null;
async function refreshRooms(){
  try{const data=await api('/api/rooms');$('serverStatus').classList.add('online');$('serverStatus').innerHTML='<i></i> Servidor online';$('roomsCount').textContent=`${data.rooms.length} salas`;
    const list=$('roomsList');list.replaceChildren();
    if(!data.rooms.length){const info=document.createElement('p');info.className='hint';info.textContent='Nenhuma sala ainda. Crie a primeira!';list.append(info);}
    for(const room of data.rooms){
      const row=document.createElement('div');row.className='room';const details=document.createElement('div');const title=document.createElement('b');title.textContent=room.name;
      const count=document.createElement('small');count.textContent=`${room.count}/${room.capacity} jogadores`;
      details.append(title,count);const button=document.createElement('button');button.className='ghost';button.textContent='Entrar';button.disabled=room.count>=room.capacity||!!membership;
      button.onclick=()=>joinRoom(room.id,room.name);row.append(details,button);list.append(row);
    }
  }catch(e){$('serverStatus').textContent='Servidor indisponível';$('roomsList').textContent=e.message;}
}
$('refreshRooms').addEventListener('click',refreshRooms);
$('newRoom').addEventListener('click',async()=>{const name=prompt('Nome da nova sala:',`Partida de ${settings.nickname}`);if(!name?.trim())return;try{const data=await api('/api/rooms',{method:'POST',body:JSON.stringify({name})});await joinRoom(data.room.id,data.room.name);}catch(e){alert(e.message);}});
async function joinRoom(id,title){
  if(membership){alert('Saia da sala atual antes de entrar em outra.');return;}
  try{
    const data=await api(`/api/rooms/${encodeURIComponent(id)}/join`,{method:'POST',body:JSON.stringify({name:settings.nickname||'Jogador'})});
    membership={id,title,memberId:data.memberId,token:data.token};$('roomTitle').textContent=title;$('currentRoom').hidden=false;$('chatMessages').replaceChildren();
    for(const item of data.messages)appendChat(item);
    updateMembers(data.members);
    const query=new URLSearchParams({memberId:membership.memberId,token:membership.token});
    stream=new EventSource(`/api/rooms/${encodeURIComponent(id)}/events?${query}`);
    stream.addEventListener('ready',e=>{const s=JSON.parse(e.data);updateMembers(s.members);});
    stream.addEventListener('roster',e=>updateMembers(JSON.parse(e.data).members));
    stream.addEventListener('chat',e=>appendChat(JSON.parse(e.data)));
    stream.onerror=()=>{$('members').textContent='Reconectando ao servidor...';};
    heartbeat=setInterval(()=>{if(membership)postRoom('heartbeat').catch(()=>{});},25000);
    await refreshRooms();
  }catch(e){alert(e.message);}
}
function updateMembers(members){$('members').textContent=`Participantes: ${members.map(m=>m.name).join(', ')||'nenhum'}`;}
function appendChat(item){const el=document.createElement('div');el.className='chat-item';const author=document.createElement('strong');author.textContent=`${item.name}: `;el.append(author,document.createTextNode(item.message));$('chatMessages').append(el);$('chatMessages').scrollTop=$('chatMessages').scrollHeight;}
const postRoom=(action,data={})=>api(`/api/rooms/${encodeURIComponent(membership.id)}/${action}`,{method:'POST',body:JSON.stringify({memberId:membership.memberId,token:membership.token,...data})});
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();if(!membership)return;const msg=$('chatInput').value.trim();if(!msg)return;try{await postRoom('chat',{message:msg});$('chatInput').value='';}catch(err){alert(err.message);}});
$('leaveRoom').addEventListener('click',leaveRoom);
async function leaveRoom(){if(!membership)return;const old=membership;stream?.close();clearInterval(heartbeat);try{await postRoom('leave');}catch{}membership=null;stream=null;$('currentRoom').hidden=true;refreshRooms();}
window.addEventListener('pagehide',()=>{if(membership)navigator.sendBeacon?.(`/api/rooms/${membership.id}/leave`,new Blob([JSON.stringify({memberId:membership.memberId,token:membership.token})],{type:'application/json'}));});
refreshRooms();

// Store user-selected files in IndexedDB; no claim they are automatically installed into a game.
const storeName='files';
function openDB(){return new Promise((resolve,reject)=>{const req=indexedDB.open('stor-pes6-files',1);req.onupgradeneeded=()=>req.result.createObjectStore(storeName,{keyPath:'name'});req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});}
async function withStore(mode,fn){const db=await openDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction(storeName,mode);const request=fn(tx.objectStore(storeName));request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});}finally{db.close();}}
async function refreshFiles(){const container=$('savedFiles');container.replaceChildren();try{const files=await withStore('readonly',s=>s.getAll());if(!files.length){const p=document.createElement('p');p.className='hint';p.textContent='Nenhum arquivo importado.';container.append(p);}for(const file of files){const row=document.createElement('div');row.className='saved-item';const name=document.createElement('span');name.textContent=`${file.name} • ${(file.blob.size/1024).toFixed(0)} KB`;const link=document.createElement('a');link.textContent='Baixar';link.href=URL.createObjectURL(file.blob);link.download=file.name;link.addEventListener('click',()=>setTimeout(()=>URL.revokeObjectURL(link.href),1500),{once:true});row.append(name,link);container.append(row);}}catch(e){container.textContent=`Armazenamento indisponível: ${e.message}`;}}
$('saveFiles').addEventListener('change',async e=>{for(const file of e.target.files){try{await withStore('readwrite',s=>s.put({name:file.name,blob:file}));}catch(err){alert(`Não foi possível salvar ${file.name}: ${err.message}`);}}e.target.value='';refreshFiles();});
$('clearFiles').addEventListener('click',async()=>{if(!confirm('Apagar os arquivos que você importou neste navegador?'))return;await withStore('readwrite',s=>s.clear());refreshFiles();});
refreshFiles();
