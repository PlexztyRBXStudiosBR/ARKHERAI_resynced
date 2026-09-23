/* ARKHER — painel da estação de jobs no Cérebro */
'use strict';
(function () {
  if (typeof document === 'undefined' || typeof ArkherStation === 'undefined') return;
  const pane = document.querySelector('#v-cerebro .pane');
  if (!pane || document.getElementById('arkher-station-card')) return;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const card = el('div', 'card');
  card.id = 'arkher-station-card';
  const title = el('h3');
  title.innerHTML = '<svg class="ico"><use href="#i-cpu"/></svg>Estação de jobs e promoção';
  card.appendChild(title);
  card.appendChild(el('p', null,
    'Telemetria real de workers autorizados, experimentos e checkpoints. O painel não inicia máquinas nem promove modelo sozinho: a atualização é sempre manual.'));

  const metrics = el('div', 'row');
  metrics.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:7px;margin:10px 0';
  const metricNodes = {};
  [
    ['workers', 'workers'], ['queuedJobs', 'jobs na fila'], ['activeJobs', 'jobs ativos'],
    ['totalRuns', 'experimentos'], ['candidates', 'candidatos'], ['experiences', 'experiências'],
  ].forEach(([key, label]) => {
    const box = el('div', 'stat');
    const a = el('span', null, label);
    const b = el('b', null, '0');
    box.append(a, b); metrics.appendChild(box); metricNodes[key] = b;
  });
  card.appendChild(metrics);

  const active = el('div', 'hint');
  active.style.cssText = 'margin:8px 0;padding:8px;border:1px solid var(--lin,#2a2a2a);border-radius:8px';
  card.appendChild(active);

  const actions = el('div', 'row');
  const refresh = el('button', 'ghost', 'Atualizar estado');
  const syncStation = el('button', 'ghost', 'Sincronizar estação');
  const autoEvaluate = el('button', 'ghost', 'Executar avaliação independente');
  const evaluate = el('button', 'ghost', 'Registrar avaliação');
  const promote = el('button', 'pri', 'Atualizar modelo');
  const rollback = el('button', 'ghost', 'Rollback');
  const dispatchJobs = el('button', 'ghost', 'Enviar jobs ao worker');
  const reconcileJobs = el('button', 'ghost', 'Reconciliar jobs');
  actions.append(refresh, syncStation, dispatchJobs, reconcileJobs, autoEvaluate, evaluate, promote, rollback);
  card.appendChild(actions);

  const candidateLabel = el('label', null, 'Experimento para avaliar ou promover manualmente');
  const candidateSelect = document.createElement('select');
  candidateSelect.style.width = '100%';
  candidateLabel.appendChild(candidateSelect);
  card.appendChild(candidateLabel);

  const runsTitle = el('h4', null, 'Experimentos e checkpoints');
  runsTitle.style.margin = '14px 0 5px';
  card.appendChild(runsTitle);
  const runs = el('div', 'hint');
  runs.style.cssText = 'max-height:260px;overflow:auto;white-space:pre-wrap';
  card.appendChild(runs);

  const logTitle = el('h4', null, 'Últimas mudanças');
  logTitle.style.margin = '14px 0 5px';
  card.appendChild(logTitle);
  const log = el('div', 'hint');
  log.style.cssText = 'max-height:160px;overflow:auto;white-space:pre-wrap';
  card.appendChild(log);
  pane.insertBefore(card, pane.firstChild);

  function time(v) {
    if (!v) return '—';
    try { return new Date(v).toLocaleString(); } catch (e) { return String(v); }
  }
  function candidateText(r) {
    const e = r.evaluation || {};
    const score = e.score !== undefined ? ' · score ' + e.score : '';
    return r.name + ' · ' + r.status + score + ' · ' + r.id;
  }
  function render(s) {
    const m = s.metrics || {};
    Object.keys(metricNodes).forEach(k => { metricNodes[k].textContent = String(m[k] || 0); });
    active.textContent = 'Modelo ativo: ' + ((s.activeModel && (s.activeModel.version || s.activeModel.name)) || 'nenhum')
      + ' · última atualização: ' + time(s.updatedAt);

    candidateSelect.textContent = '';
    const empty = document.createElement('option');
    empty.value = ''; empty.textContent = m.candidates ? 'selecione um candidato' : 'nenhum candidato avaliado';
    candidateSelect.appendChild(empty);
    (s.runs || []).filter(r => ['trained', 'candidate', 'evaluated'].includes(r.status)).slice().reverse().forEach(r => {
      const o = document.createElement('option'); o.value = r.id; o.textContent = candidateText(r); candidateSelect.appendChild(o);
    });
    const selectedRun = (s.runs || []).find(r => r.id === candidateSelect.value);
    promote.disabled = !(selectedRun && ['candidate', 'evaluated'].includes(selectedRun.status)
      && selectedRun.evaluation && selectedRun.evaluation.pass === true);
    evaluate.disabled = !(selectedRun && ['trained', 'candidate', 'evaluated'].includes(selectedRun.status));
    autoEvaluate.disabled = !(selectedRun && ['trained', 'candidate', 'evaluated'].includes(selectedRun.status)
      && Array.isArray(selectedRun.artifacts) && selectedRun.artifacts.length);

    runs.textContent = '';
    const list = (s.runs || []).slice().reverse();
    if (!list.length) runs.textContent = 'Nenhum experimento registrado. Workers podem usar ArkherStation.createRun(), checkpoint(), event() e evaluate().';
    list.forEach(r => {
      const d = el('div', null,
        r.name + ' · ' + r.status + '\n'
        + 'base: ' + (r.base || '—') + ' · criado: ' + time(r.createdAt) + '\n'
        + 'checkpoints: ' + ((r.checkpoints || []).length) + ' · métricas: ' + JSON.stringify(r.metrics || {}));
      d.style.padding = '6px 0'; runs.appendChild(d);
    });

    log.textContent = '';
    const changes = (s.changelog || []).slice().reverse().slice(0, 20);
    if (!changes.length) log.textContent = 'Nenhuma promoção, avaliação ou rollback registrado.';
    changes.forEach(c => log.appendChild(el('div', null,
      time(c.at) + ' · ' + c.type + (c.runId ? ' · ' + c.runId : '')
      + (c.to ? ' → ' + c.to : '') + (c.reason ? ' · ' + c.reason : ''))));
  }

  candidateSelect.onchange = () => {
    const r = ArkherStation.snapshot().runs.find(x => x.id === candidateSelect.value);
    promote.disabled = !(r && ['candidate', 'evaluated'].includes(r.status) && r.evaluation && r.evaluation.pass === true);
    evaluate.disabled = !(r && ['trained', 'candidate', 'evaluated'].includes(r.status));
    autoEvaluate.disabled = !(r && ['trained', 'candidate', 'evaluated'].includes(r.status)
      && Array.isArray(r.artifacts) && r.artifacts.length);
  };
  refresh.onclick = () => render(ArkherStation.refresh());
  syncStation.onclick = async () => {
    syncStation.disabled = true;
    try {
      const s = await ArkherStation.sincronizar();
      active.textContent = 'Estação sincronizada com o time: ' + (s.metrics && s.metrics.totalRuns || 0) + ' experimento(s).';
      render(s);
    } catch (e) { active.textContent = 'Sincronização indisponível: ' + (e.message || e); }
    finally { syncStation.disabled = false; }
  };
  function workerBase() {
    try { return String(LS.get('arkher_agent', '') || LS.get('arkher_kaggle', '') || '').replace(/\/+$/, ''); }
    catch (e) { return ''; }
  }
  dispatchJobs.onclick = async () => {
    const base = workerBase();
    if (!base) { active.textContent = 'Configure a URL do worker em Config antes de enviar jobs.'; return; }
    const fila = ArkherStation.snapshot().jobs.filter(j => j.status === 'queued');
    if (!fila.length) { active.textContent = 'Não há jobs locais aguardando despacho.'; return; }
    dispatchJobs.disabled = true;
    let ok = 0, falhas = 0;
    try {
      for (const job of fila) {
        try { await ArkherStation.dispatch(job.id, base); ok++; }
        catch (e) { falhas++; active.textContent = 'Job ' + job.id + ': ' + (e.message || e); }
      }
      active.textContent = ok + ' job(s) enviados ao worker autorizado'
        + (falhas ? ' · ' + falhas + ' falha(s)' : '')
        + '. O worker só ficará concluído após lease, heartbeat e confirmação.';
      render(ArkherStation.snapshot());
    } finally { dispatchJobs.disabled = false; }
  };
  reconcileJobs.onclick = async () => {
    const base = workerBase();
    if (!base) { active.textContent = 'Configure a URL do worker em Config antes de reconciliar.'; return; }
    reconcileJobs.disabled = true;
    try {
      const s = await ArkherStation.reconcile(base, { limit: 200 });
      const ativos = (s.jobs || []).filter(j => ['queued', 'claimed', 'running', 'dispatched'].includes(j.status)).length;
      active.textContent = 'Jobs reconciliados: ' + (s.jobs || []).length + ' local(is) · ' + ativos + ' ainda ativo(s).';
      render(s);
    } catch (e) { active.textContent = 'Reconciliação indisponível: ' + (e.message || e); }
    finally { reconcileJobs.disabled = false; }
  };
  autoEvaluate.onclick = async () => {
    const id = candidateSelect.value;
    if (!id || typeof ArkherEvaluator === 'undefined') { active.textContent = 'Selecione um experimento com artifact e carregue o avaliador.'; return; }
    autoEvaluate.disabled = true;
    active.textContent = 'Executando casos independentes no candidato…';
    try {
      const out = await ArkherEvaluator.evaluateRun(id, { onProgress: ev => {
        if (ev.type === 'case_start') active.textContent = 'Avaliação: ' + ev.id + '…';
        if (ev.type === 'case_done') active.textContent = 'Avaliação: ' + ev.result.id + ' → ' + (ev.result.ok ? 'passou' : 'falhou');
      } });
      active.textContent = 'Avaliação concluída: ' + out.passed + '/' + out.total + ' · score ' + out.score.toFixed(2)
        + (out.pass ? ' · candidato aprovado' : ' · candidato reprovado');
    } catch (e) { active.textContent = 'Avaliação falhou: ' + (e.message || e); }
    finally { render(ArkherStation.snapshot()); }
  };
  evaluate.onclick = () => {
    const id = candidateSelect.value;
    if (!id) { active.textContent = 'Escolha um experimento treinado antes de avaliar.'; return; }
    const score = window.prompt ? window.prompt('Score independente (0 a 1):', '0.8') : '0.8';
    if (score === null) return;
    const n = Number(score);
    if (!Number.isFinite(n) || n < 0 || n > 1) { active.textContent = 'Score inválido: use um número entre 0 e 1.'; return; }
    const pass = n >= 0.7 && (!window.confirm || window.confirm('A avaliação passou nos testes independentes?\n\nOK = promover a candidato · Cancelar = rejeitar')); 
    const r = ArkherStation.evaluate(id, { pass, score: n, method: 'avaliação manual no Cérebro', at: new Date().toISOString() });
    active.textContent = r ? (pass ? 'Avaliação registrada: candidato pronto para promoção manual.' : 'Avaliação registrada: candidato rejeitado.') : 'Experimento inválido.';
    render(ArkherStation.snapshot());
  };
  promote.onclick = () => {
    const id = candidateSelect.value;
    if (!id) { active.textContent = 'Escolha um candidato avaliado antes de atualizar o modelo.'; return; }
    if (!window.confirm || window.confirm('Promover este candidato como modelo ativo?')) {
      const r = ArkherStation.promote(id, 'botão Atualizar modelo no Cérebro');
      if (!r) active.textContent = 'Promoção não realizada: candidato inválido ou já promovido.';
      render(ArkherStation.snapshot());
    }
  };
  rollback.onclick = () => {
    if (!window.confirm || window.confirm('Voltar para o modelo anterior?')) {
      const r = ArkherStation.rollback('botão Rollback no Cérebro');
      active.textContent = r ? 'Rollback concluído.' : 'Não há modelo anterior para rollback.';
      render(ArkherStation.snapshot());
    }
  };
  ArkherStation.subscribe(render);
  if (window.addEventListener) window.addEventListener('storage', e => {
    if (e.key === 'arkher_station_v1') render(ArkherStation.refresh());
  });
  render(ArkherStation.snapshot());
})();
