// Runtime bridge. Independently compiled, authorized engine code belongs in /public/runtime/.
// Your runtime module must export `createRuntime({canvas, settings, onStatus})`.
// Its result must have `input(action, pressed)` and optional `stop()`, `configure(settings)`.
export class EngineAdapter {
  constructor(canvas,onStatus) { this.canvas=canvas; this.onStatus=onStatus; this.runtime=null; }
  async available() {
    try {
      const response=await fetch('/runtime/runtime.js',{method:'HEAD',cache:'no-store'});
      return response.ok;
    } catch { return false; }
  }
  async start(settings) {
    if(this.runtime)return;
    if(!await this.available()) throw new Error('Motor WASM não instalado. Consulte docs/BUILD_ENGINE.md no GitHub.');
    const engine=await import('/runtime/runtime.js');
    if(typeof engine.createRuntime!=='function')throw new Error('O arquivo runtime.js precisa exportar createRuntime().');
    const runtime=await engine.createRuntime({canvas:this.canvas,settings,onStatus:this.onStatus});
    if(!runtime || typeof runtime.input!=='function')throw new Error('Runtime inválido: faltou input(action,pressed).');
    this.runtime=runtime;
  }
  input(action,pressed) { this.runtime?.input(action,pressed); }
  configure(settings) { this.runtime?.configure?.(settings); }
  stop() { this.runtime?.stop?.(); this.runtime=null; }
}
