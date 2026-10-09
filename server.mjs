import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public');
const roomTTL = 15 * 60_000;
const memberTTL = 90_000;
const rooms = new Map();
const types = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json', '.wasm':'application/wasm', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.ico':'image/x-icon', '.pak':'application/octet-stream' };
const commonHeaders = {
  'Cross-Origin-Opener-Policy':'same-origin',
  'Cross-Origin-Embedder-Policy':'require-corp',
  'Cross-Origin-Resource-Policy':'same-origin',
  'X-Content-Type-Options':'nosniff',
  'Referrer-Policy':'no-referrer',
  'Cache-Control':'no-store'
};
const send = (res, status, payload) => {
  res.writeHead(status, { ...commonHeaders, 'Content-Type':'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
};
const fail = (res, status, message) => send(res, status, { error:message });
const publicRoom = r => ({ id:r.id, name:r.name, capacity:r.capacity, count:r.members.size, created:r.created });
function validateText(str, max) { return typeof str === 'string' ? str.trim().slice(0, max) : ''; }
function broadcast(room, type, data, excludedId = '') {
  const event = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const [id, member] of room.members) if (id !== excludedId && member.stream && !member.stream.destroyed) member.stream.write(event);
}
function roster(room) { return [...room.members.values()].map(m=>({ id:m.id, name:m.name })); }
function notify(room) { broadcast(room, 'roster', { members:roster(room) }); }
function staleCleanup() {
  const now = Date.now();
  for (const [key,room] of rooms) {
    for (const [id,m] of room.members) {
      if (now - m.lastSeen > memberTTL) { m.stream?.end(); room.members.delete(id); }
    }
    if (!room.members.size && now - room.lastActive > roomTTL) rooms.delete(key);
    else notify(room);
  }
}
async function readJson(req) {
  let input = '';
  for await (const chunk of req) {
    input += chunk.toString('utf8');
    if (input.length > 16_384) throw new Error('Requisição muito grande');
  }
  try { return input ? JSON.parse(input) : {}; }
  catch { throw new Error('JSON inválido'); }
}
function auth(room, body) {
  const member = room.members.get(body?.memberId);
  if (!member || body?.token !== member.token) return null;
  member.lastSeen = Date.now(); room.lastActive = Date.now();
  return member;
}
async function api(req, res, u) {
  const pieces = u.pathname.split('/').filter(Boolean);
  if (req.method === 'GET' && u.pathname === '/api/health') return send(res, 200, { ok:true, rooms:rooms.size, runtime:fs.existsSync(path.join(dir,'runtime','runtime.js')) });
  if (u.pathname === '/api/rooms' && req.method === 'GET') return send(res, 200, { rooms:[...rooms.values()].map(publicRoom) });
  let body = {};
  if (!['GET','HEAD'].includes(req.method)) {
    try { body = await readJson(req); } catch(e) { return fail(res, 400, e.message); }
  }
  if (u.pathname === '/api/rooms' && req.method === 'POST') {
    const name = validateText(body.name, 40);
    if (!name) return fail(res,400,'Informe o nome da sala');
    const room = { id:crypto.randomUUID(), name, capacity:2, created:Date.now(), lastActive:Date.now(), members:new Map(), messages:[] };
    rooms.set(room.id,room); return send(res,201,{ room:publicRoom(room) });
  }
  if (pieces[0] !== 'api' || pieces[1] !== 'rooms' || pieces.length !== 4) return fail(res,404,'Rota não encontrada');
  const room = rooms.get(pieces[2]);
  if (!room) return fail(res,404,'Sala não encontrada');
  const action = pieces[3];
  if (action === 'join' && req.method === 'POST') {
    const name = validateText(body.name, 24);
    if (!name) return fail(res,400,'Informe seu apelido');
    if (room.members.size >= room.capacity) return fail(res,409,'Sala cheia');
    const member = { id:crypto.randomUUID(), token:crypto.randomBytes(24).toString('hex'), name, stream:null, lastSeen:Date.now() };
    room.members.set(member.id,member); room.lastActive=Date.now(); notify(room);
    return send(res,200,{ room:publicRoom(room), memberId:member.id, token:member.token, members:roster(room), messages:room.messages });
  }
  if (action === 'events' && req.method === 'GET') {
    const member = auth(room, {memberId:u.searchParams.get('memberId'),token:u.searchParams.get('token')});
    if (!member) return fail(res,403,'Participante inválido');
    res.writeHead(200, { ...commonHeaders, 'Content-Type':'text/event-stream', 'Connection':'keep-alive', 'Cache-Control':'no-cache' });
    member.stream?.end(); member.stream=res;
    res.write(`event: ready\ndata: ${JSON.stringify({members:roster(room), messages:room.messages})}\n\n`);
    req.on('close',()=>{ if(member.stream===res) member.stream=null; });
    return;
  }
  const member=auth(room,body);
  if (!member) return fail(res,403,'Participante inválido');
  if (action==='heartbeat' && req.method==='POST') return send(res,200,{ok:true});
  if (action==='leave' && req.method==='POST') { member.stream?.end(); room.members.delete(member.id); notify(room); return send(res,200,{ok:true}); }
  if (action==='chat' && req.method==='POST') {
    const message=validateText(body.message,500);
    if (!message) return fail(res,400,'Mensagem vazia');
    const item={id:crypto.randomUUID(), name:member.name, message, at:Date.now()};
    room.messages.push(item); if(room.messages.length>40) room.messages.shift();
    broadcast(room,'chat',item); return send(res,200,{ok:true});
  }
  if (action==='signal' && req.method==='POST') {
    // Reserved signaling transport. Does not implement PES6 netplay.
    const target=room.members.get(body.to);
    const signal=body.signal;
    if (!target || typeof signal!=='object' || signal===null || JSON.stringify(signal).length>10_000) return fail(res,400,'Sinal inválido');
    if (target.stream && !target.stream.destroyed) target.stream.write(`event: signal\ndata: ${JSON.stringify({from:member.id, signal})}\n\n`);
    return send(res,200,{ok:true});
  }
  return fail(res,404,'Rota não encontrada');
}
async function serve(req,res,u) {
  let p;
  try { p=decodeURIComponent(u.pathname); } catch { return fail(res,400,'URL inválida'); }
  if (p.includes('\0') || p.split('/').includes('..')) return fail(res,403,'Caminho proibido');
  let absolute=path.resolve(dir, `.${p==='/'?'/index.html':p}`);
  if (!absolute.startsWith(dir+path.sep)) return fail(res,403,'Caminho proibido');
  let stat;
  try { stat=await fs.promises.stat(absolute); } catch { return fail(res,404,'Arquivo não encontrado'); }
  if (!stat.isFile()) return fail(res,404,'Arquivo não encontrado');
  const type=types[path.extname(absolute)] || 'application/octet-stream';
  let from=0,to=stat.size-1,status=200;
  const range=req.headers.range;
  if (range && /^bytes=\d*-\d*$/.test(range)) {
    const [a,b]=range.slice(6).split('-');
    if (!a && !b) return fail(res,416,'Range inválido');
    if (!a) { from=Math.max(0,stat.size-Number(b)); }
    else { from=Number(a); to=b?Math.min(Number(b),stat.size-1):stat.size-1; }
    if (from>=stat.size || to<from) return fail(res,416,'Range fora do arquivo');
    status=206;
  }
  res.writeHead(status,{ ...commonHeaders,'Content-Type':type,'Accept-Ranges':'bytes','Content-Length':to-from+1,...(status===206?{'Content-Range':`bytes ${from}-${to}/${stat.size}`}:{}) });
  if(req.method==='HEAD') return res.end();
  fs.createReadStream(absolute,{start:from,end:to}).pipe(res);
}
export function createAppServer() {
  const server=http.createServer((req,res)=>{
    let u;try{u=new URL(req.url,'http://localhost');}catch{return fail(res,400,'URL inválida');}
    Promise.resolve(u.pathname.startsWith('/api/') ? api(req,res,u) : serve(req,res,u)).catch(e=>{console.error(e);if(!res.headersSent)fail(res,500,'Erro interno'); else res.destroy();});
  });
  const cleanup=setInterval(staleCleanup,30_000); cleanup.unref();
  server.on('close',()=>clearInterval(cleanup));
  return server;
}
if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const port=Number(process.env.PORT)||8787;
  const host=process.env.HOST||'0.0.0.0';
  createAppServer().listen(port,host,()=>console.log(`PES6 Web launcher: http://${host}:${port}`));
}
