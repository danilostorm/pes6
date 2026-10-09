# Integrar o motor de jogo (ainda não implementado)

O launcher **não contém o jogo PES 6**, nem um emulador/recompilação pronta. A presença do motor é testada por um `HEAD /runtime/runtime.js`. O botão de iniciar não simula uma partida.

## Caminho técnico recomendado

1. Estudar [snuri00/psp-web-recomp](https://github.com/snuri00/psp-web-recomp) (MIT) e seus `scripts/setup.sh`, `scripts/port.sh`, `profile/host`, `profile/renderer`.
2. Usar apenas uma cópia de jogo e arquivos que você tenha direito de processar. As ferramentas em geral exigem ISO próprio, decriptação do EBOOT e Emscripten. **Portar um novo jogo não é garantido:** chamadas HLE, GPU, áudio, timing e rede ad-hoc precisam de engenharia específica.
3. Gerar e testar um build específico de PES 6 **fora deste repositório público**. Não colocar no GitHub executáveis traduzidos, arquivos comerciais ou patches com conteúdo protegido sem autorização.
4. Encapsular o build num `runtime.js` próprio no diretório `public/runtime/`, junto com seus arquivos de runtime (ou montar volume no Docker).
5. Adaptar as APIs do motor a este contrato:

```js
// public/runtime/runtime.js (EXEMPLO DE CONTRATO; NÃO EXECUTA PES6 SOZINHO)
export async function createRuntime({ canvas, settings, onStatus }) {
  // Carregar seus próprios arquivos WASM/JS aqui, conectar ao canvas e boot real.
  // Exemplo conceitual: const core = await loadYourCompiledGame(canvas, settings);
  // Substituir com uma implementação real específica do seu build.
  throw new Error('Ainda é necessário implementar a ponte real do seu motor');
  // return {
  //   input(action, pressed) { core.setButton(action, pressed); },
  //   configure(nextSettings) { core.applySettings(nextSettings); },
  //   stop() { core.shutdown(); }
  // };
}
```

As ações possíveis são `up`, `down`, `left`, `right`, `cross`, `circle`, `square`, `triangle`, `L`, `R`, `select`, `start`. Devem ser conectadas à fila interna de leitura de controles da recompilação; apenas emitir eventos `KeyboardEvent` não resolve a entrada de um motor WASM.

## Online

`server.mjs` implementa **lobby, chat, presença e um canal experimental de sinalização** (`/signal`). Isso **não é netplay**. Para partidas reais, será necessário adaptar a camada `sceNetAdhoc`/comunicação original do jogo, aplicar sincronização de quadros/pacotes, controle de atraso e opcionalmente criar um relay UDP/WebRTC. Não reutilizar o servidor do site de referência.

## Cabeçalhos e CDN

O servidor fornece COOP `same-origin`, COEP `require-corp` e HTTP Range para builds WASM que dependem de `SharedArrayBuffer` e carregamento parcial. Assets externos precisam obedecer a CORP/CORS e ser compatíveis com isolamento. Exponha em HTTPS em produção e teste em navegadores reais de desktop e celular.

## Próximas provas de conceito

- Primeiro boot real com ISO próprio e logs HLE
- Teste de áudio sem falhas, texturas WebGL2, 30 e 60 FPS medidos no hardware-alvo
- Saves PSP integrados ao armazenamento do motor
- Multiplayer local (múltiplos gamepads) e netplay via ad-hoc (não disponíveis nesta versão)
