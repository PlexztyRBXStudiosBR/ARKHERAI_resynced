/* ============================================================
   ARKHER STATION BRIDGE — espelho operacional no worker autorizado

   O ledger principal continua no Cérebro/Sync. Este bridge envia ao agente
   autorizado apenas eventos operacionais resumidos, sem prompts, mensagens,
   tokens ou conteúdo de arquivos. Se o worker estiver offline, a UI continua
   funcionando e a telemetria local permanece no station ledger.
   ============================================================ */
'use strict';
(function () {
  if (typeof window === 'undefined' || typeof ArkherStation === 'undefined') return;
  const Bridge = { VERSION: '0.1.0', fila: 0, ultimo: '', erro: '' };
  const seen = new Set();
  const queue = [];
  let busy = false;

  function base() {
    try { return String(LS.get('arkher_agent', '') || LS.get('arkher_kaggle', '') || '').replace(/\/+$/, ''); }
    catch (e) { return ''; }
  }
  function operacional(ev) {
    const type = String(ev && ev.type || '');
    return /^(train_|ingest_|tool_|provider_error|guard_|checkpoint$|response$|request_start$)/.test(type);
  }
  function resumir(ev) {
    const allow = ['id', 'at', 'type', 'runId', 'jobId', 'workerId', 'state', 'status', 'src', 'model', 'task',
      'step', 'progress', 'outputSize', 'verified', 'gastouSaldo'];
    const out = {};
    allow.forEach(k => { if (ev && ['string', 'number', 'boolean'].includes(typeof ev[k])) out[k] = ev[k]; });
    if (ev && ev.metrics && typeof ev.metrics === 'object') {
      out.metrics = {};
      Object.keys(ev.metrics).slice(0, 30).forEach(k => {
        if (['number', 'boolean'].includes(typeof ev.metrics[k])) out.metrics[k] = ev.metrics[k];
      });
    }
    if (ev && ev.error) out.error = String(ev.error).slice(0, 300);
    if (ev && ev.reason) out.reason = String(ev.reason).slice(0, 240);
    return out;
  }
  async function enviar(ev) {
    const u = base();
    if (!u || !ev) return false;
    try {
      const r = await fetch(u + '/station/event', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: ev }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      Bridge.ultimo = new Date().toISOString(); Bridge.erro = '';
      return true;
    } catch (e) { Bridge.erro = String(e.message || e).slice(0, 160); return false; }
  }
  async function drenar() {
    if (busy || !queue.length || !base()) return;
    busy = true;
    const ev = queue.shift(); Bridge.fila = queue.length;
    const ok = await enviar(ev);
    if (!ok && queue.length < 40) queue.unshift(ev); // tenta de novo quando voltar
    Bridge.fila = queue.length;
    busy = false;
    if (queue.length) setTimeout(drenar, ok ? 0 : 3000);
  }
  const unsubscribe = ArkherStation.subscribe(s => {
    const ev = s && s.events && s.events[s.events.length - 1];
    if (!ev || !ev.id || seen.has(ev.id) || !operacional(ev)) return;
    seen.add(ev.id);
    if (seen.size > 1000) seen.delete(seen.values().next().value);
    queue.push(resumir(ev));
    if (queue.length > 40) queue.shift();
    Bridge.fila = queue.length;
    drenar();
  });
  Bridge.parar = () => { try { unsubscribe(); } catch (e) {} queue.length = 0; Bridge.fila = 0; };
  Bridge.status = () => ({ fila: Bridge.fila, ultimo: Bridge.ultimo, erro: Bridge.erro, base: !!base() });
  window.ArkherStationBridge = Bridge;
})();
