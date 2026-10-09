#!/usr/bin/env node
// Offline-only metadata probe. Does not decrypt, modify, upload or distribute game data.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export function readSfo(file) {
  const data=fs.readFileSync(file);
  if(data.length<20 || data.toString("latin1",0,4)!=="\0PSF") throw new Error("Assinatura PARAM.SFO inválida");
  const keyBase=data.readUInt32LE(8), valueBase=data.readUInt32LE(12), count=data.readUInt32LE(16);
  if(count>500 || 20+count*16>data.length || keyBase>=data.length || valueBase>=data.length) throw new Error("Tabela PARAM.SFO inválida");
  const found={};
  for(let i=0;i<count;i++){
    const offset=20+i*16, keyPos=keyBase+data.readUInt16LE(offset), type=data[offset+3];
    const length=data.readUInt32LE(offset+4), valPos=valueBase+data.readUInt32LE(offset+12);
    if(keyPos>=data.length || valPos>data.length || length>data.length-valPos) throw new Error("Índice PARAM.SFO inválido");
    const end=data.indexOf(0,keyPos);
    if(end<0) throw new Error("Chave PARAM.SFO inválida");
    const key=data.toString("utf8",keyPos,end);
    found[key]=type===4 && length>=4 ? data.readUInt32LE(valPos) :
      type===2 ? data.toString("utf8",valPos,valPos+length).replace(/\0.*$/s,"") :
      data.subarray(valPos,valPos+length).toString("hex");
  }
  return found;
}
export function probeExecutable(file) {
  if(!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) return {present:false};
  const handle=fs.openSync(file,"r"), head=Buffer.alloc(4);
  try { fs.readSync(handle,head,0,4,0); } finally { fs.closeSync(handle); }
  let kind="desconhecido";
  if(head.toString("latin1")==="~PSP") kind="PSP criptografado (~PSP)";
  if(head.equals(Buffer.from([127,69,76,70]))) kind="ELF descriptografado";
  if(head.equals(Buffer.alloc(4))) kind="início preenchido por zeros";
  return {present:true,bytes:fs.statSync(file).size,kind,signature:head.toString("hex")};
}
export function inspect(options) {
  const game=options.dir ? path.join(options.dir,"PSP_GAME") : null;
  const eboot=options.eboot || (game && path.join(game,"SYSDIR","EBOOT.BIN"));
  const boot=options.boot || (game && path.join(game,"SYSDIR","BOOT.BIN"));
  const param=options.param || (game && path.join(game,"PARAM.SFO"));
  if(!eboot && !boot && !param) throw new Error("Informe --dir ou arquivos individuais");
  const metadata=param && fs.existsSync(param) ? readSfo(param) : {};
  const executables={eboot:probeExecutable(eboot),boot:probeExecutable(boot)};
  const assets=[];
  const userdir=game && path.join(game,"USRDIR");
  if(userdir && fs.existsSync(userdir)) {
    for(const name of fs.readdirSync(userdir).sort()){
      const p=path.join(userdir,name);
      if(fs.statSync(p).isFile()) assets.push({name,bytes:fs.statSync(p).size});
    }
  }
  const warnings=[];
  if(executables.eboot.kind?.startsWith("PSP criptografado")) warnings.push("EBOOT criptografado: o recompilador requer um ELF obtido legalmente com ferramenta compatível.");
  if(!executables.eboot.present) warnings.push("EBOOT.BIN não encontrado.");
  if(!assets.length) warnings.push("Diretório USRDIR não disponível nesta análise.");
  return {
    identity:{title:metadata.TITLE||null,disc_id:metadata.DISC_ID||null,disc_version:metadata.DISC_VERSION||null,system_version:metadata.PSP_SYSTEM_VER||null},
    executables,assets,ready_for_recompiler:executables.eboot.kind==="ELF descriptografado",warnings
  };
}
function cli(args){
  if(args.includes("--help") || args.includes("-h")){
    process.stdout.write("Uso: node scripts/inspect-psp.mjs --dir /caminho/PES6\nOu: --eboot arquivo --boot arquivo --param arquivo\n");return;
  }
  const opts={};
  for(let i=0;i<args.length;i++){
    const key=args[i];
    if(!["--dir","--eboot","--boot","--param"].includes(key)) throw new Error("Argumento desconhecido: "+key);
    const value=args[++i];
    if(!value || value.startsWith("--")) throw new Error("Falta valor para "+key);
    opts[key.slice(2)]=path.resolve(value);
  }
  console.log(JSON.stringify(inspect(opts),null,2));
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  try{cli(process.argv.slice(2));}catch(e){console.error("Erro: "+e.message);process.exitCode=1;}
}
