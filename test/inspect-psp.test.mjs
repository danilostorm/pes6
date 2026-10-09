import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { inspect, readSfo, probeExecutable } from "../scripts/inspect-psp.mjs";

function makeSfo(){
  const keys=Buffer.from("TITLE\0DISC_ID\0");
  const values=[Buffer.from("Pro Evolution Soccer 6\0"),Buffer.from("ULES00476\0")];
  const keyBase=52, valueBase=keyBase+keys.length;
  const buffer=Buffer.alloc(valueBase+values[0].length+values[1].length);
  buffer.write("\0PSF",0,"latin1");
  buffer.writeUInt32LE(257,4);buffer.writeUInt32LE(keyBase,8);
  buffer.writeUInt32LE(valueBase,12);buffer.writeUInt32LE(2,16);
  let keyOffset=0,valueOffset=0;
  for(let i=0;i<2;i++){
    const at=20+i*16;
    buffer.writeUInt16LE(keyOffset,at);buffer.writeUInt8(2,at+3);
    buffer.writeUInt32LE(values[i].length,at+4);buffer.writeUInt32LE(values[i].length,at+8);
    buffer.writeUInt32LE(valueOffset,at+12);
    values[i].copy(buffer,valueBase+valueOffset);
    keyOffset+=i===0?6:8;valueOffset+=values[i].length;
  }
  keys.copy(buffer,keyBase);
  return buffer;
}

test("identifica PES 6 e EBOOT criptografado sem processar os dados do jogo",()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"pes6-check-"));
  try{
    const p=path.join(root,"PSP_GAME");
    fs.mkdirSync(path.join(p,"SYSDIR"),{recursive:true});
    fs.mkdirSync(path.join(p,"USRDIR"));
    fs.writeFileSync(path.join(p,"PARAM.SFO"),makeSfo());
    fs.writeFileSync(path.join(p,"SYSDIR","EBOOT.BIN"),Buffer.from("~PSP"));
    fs.writeFileSync(path.join(p,"USRDIR","0_text.afs"),Buffer.alloc(8));
    const report=inspect({dir:root});
    assert.equal(report.identity.title,"Pro Evolution Soccer 6");
    assert.equal(report.identity.disc_id,"ULES00476");
    assert.equal(report.ready_for_recompiler,false);
    assert.match(report.executables.eboot.kind,/criptografado/);
    assert.equal(report.assets.length,1);
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test("reconhece executável ELF sem afirmar que o jogo é jogável",()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"psp-elf-"));
  try{
    const file=path.join(root,"EBOOT.BIN");
    fs.writeFileSync(file,Buffer.from([127,69,76,70]));
    assert.equal(probeExecutable(file).kind,"ELF descriptografado");
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});

test("recusa PARAM.SFO inválido",()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"psp-bad-"));
  try{
    const file=path.join(root,"PARAM.SFO");
    fs.writeFileSync(file,"invalid");
    assert.throws(()=>readSfo(file),/inválida/);
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});
