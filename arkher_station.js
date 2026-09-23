/* ============================================================
   ARKHER STATION — jobs, workers, telemetria e promoção manual

   Esta estação é um ledger local seguro por padrão. Ela não inicia treino,
   não usa máquinas remotas sem autorização e não promete GPU disponível.
   Workers autorizados podem publicar eventos por ArkherStation.event().
   ============================================================ */
'use strict';
if (typeof LS === 'undefined' && typeof require !== 'undefined') globalThis.LS = require('./core.js').LS;

const ArkherStation = (() => {
  const KEY = 'arkher_station_v1';
  const MAX_EVENTS = 500;
  const MAX_RUNS = 80;
  const MAX_JOBS = 200;
  const MAX_CHANGELOG = 120;
  const listeners = [];

  function id(prefix) {
    return prefix + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }
  function now() { return new Date().toISOString(); }
  function clone(v) { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } }
  function redactText(v) {
    return String(v || '')
      .replace(/(bearer\s+)[A-Za-z0-9._~+/=-]+/ig, '$1[REDACTED]')
      .replace(/((?:api[_-]?key|token|secret|password|senha)\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s;]+)/ig, '$1[REDACTED]')
      .replace(/\b(?:sk|ghp|hf|xai)_[A-Za-z0-9_-]{12,}/g, '[REDACTED]');
  }
  function safe(v, depth) {
    depth = depth || 0;
    if (depth > 4) return '[limite]';
    if (v === null || v === undefined || typeof v === 'number' || typeof v === 'boolean') return v;
    if (typeof v === 'string') return redactText(v).slice(0, 1200);
    if (Array.isArray(v)) return v.slice(0, 30).map(x => safe(x, depth + 1));
    if (typeof v === 'object') {
      const out = {};
      Object.keys(v).slice(0, 60).forEach(k => {
        if (/(token|secret|password|senha|api.?key|authorization|cookie|private.?key)/i.test(k)) return;
        out[k] = safe(v[k], depth + 1);
      });
      return out;
    }
    return String(v).slice(0, 1200);
  }
  function fresh() {
    return {
      version: '0.1.0',
      activeModel: null,
      previousModel: null,
      workers: {},
      jobs: [],
      runs: [],
      events: [],
      experiences: [],
      changelog: [],
      updatedAt: now(),
    };
  }
  function load() {
    const raw = LS.get(KEY, null);
    const s = Object.assign(fresh(), raw && typeof raw === 'object' ? raw : {});
    s.workers = s.workers && typeof s.workers === 'object' ? s.workers : {};
    ['jobs', 'runs', 'events', 'experiences', 'changelog'].forEach(k => { if (!Array.isArray(s[k])) s[k] = []; });
    return s;
  }
  let state = load();

  function save() {
    state.updatedAt = now();
    LS.set(KEY, state);
    const snap = snapshot();
    listeners.slice().forEach(fn => { try { fn(snap); } catch (e) {} });
    return snap;
  }
  function snapshot() {
    const s = clone(state) || fresh();
    const candidates = s.runs.filter(r => ['candidate', 'evaluated'].includes(r.status));
    s.metrics = {
      workers: Object.keys(s.workers).length,
      workersOnline: Object.values(s.workers).filter(w => w.status === 'online').length,
      queuedJobs: s.jobs.filter(j => j.status === 'queued').length,
      activeJobs: s.jobs.filter(j => ['claimed', 'running'].includes(j.status)).length,
      totalRuns: s.runs.length,
      candidates: candidates.length,
      experiences: s.experiences.length,
      events: s.events.length,
      activeModel: s.activeModel && (s.activeModel.version || s.activeModel.id) || 'nenhum',
      updatedAt: s.updatedAt,
    };
    return s;
  }
  function trim() {
    if (state.events.length > MAX_EVENTS) state.events = state.events.slice(-MAX_EVENTS);
    if (state.runs.length > MAX_RUNS) state.runs = state.runs.slice(-MAX_RUNS);
    if (state.jobs.length > MAX_JOBS) state.jobs = state.jobs.slice(-MAX_JOBS);
    if (state.experiences.length > MAX_EVENTS) state.experiences = state.experiences.slice(-MAX_EVENTS);
    if (state.changelog.length > MAX_CHANGELOG) state.changelog = state.changelog.slice(-MAX_CHANGELOG);
  }

  /* O Cérebro pode colocar um job no agente autorizado, mas não assume que
     isso significa execução. O worker só confirma depois de fazer o trabalho
     e devolver o resultado observado. O token vai apenas no cabeçalho HTTP;
     nunca entra no job, no ledger ou no retorno da estação. */
  function remoteBase(base) {
    let u = base;
    if (u && typeof u === 'object') u = u.base || u.url;
    if (!u) { try { u = LS.get('arkher_agent', '') || LS.get('arkher_kaggle', ''); } catch (e) {} }
    return String(u || '').replace(/\/+$/, '');
  }
  function remoteHeaders(extra) {
    const h = Object.assign({ 'Content-Type': 'application/json' }, extra || {});
    try {
      const token = String(LS.get('arkher_agent_token', '') || '').trim();
      if (token) h.Authorization = 'Bearer ' + token;
    } catch (e) {}
    return h;
  }
  async function remoteJson(url, init) {
    if (typeof fetch !== 'function') throw new Error('fetch indisponível para falar com o worker');
    const r = await fetch(url, init);
    let body = {};
    try { body = await r.json(); } catch (e) { body = {}; }
    if (!r.ok || body.ok === false) throw new Error(body.err || ('HTTP ' + r.status));
    return body;
  }
  function jobForRemote(job) {
    return safe({ id: job.id, kind: job.kind, priority: job.priority, requestedBy: job.requestedBy,
      runId: job.runId, payload: job.payload || {} });
  }

  const api = {
    VERSION: '0.1.0',
    snapshot,
    subscribe(fn) { if (typeof fn === 'function') { listeners.push(fn); return () => { const i = listeners.indexOf(fn); if (i >= 0) listeners.splice(i, 1); }; } return () => {}; },
    refresh() { state = load(); return save(); },
    exportar() {
      const out = clone(state) || fresh();
      delete out.metrics;
      return out;
    },
    importar(remote) {
      if (!remote || typeof remote !== 'object') return snapshot();
      const mergeById = (key, limit) => {
        const local = new Map((state[key] || []).map(x => [x.id || (x.at + '|' + x.type + '|' + x.runId), x]));
        for (const x of (remote[key] || [])) {
          const idv = x.id || (x.at + '|' + x.type + '|' + x.runId);
          const old = local.get(idv);
          if (!old || String(x.updatedAt || x.at || '') > String(old.updatedAt || old.at || '')) local.set(idv, safe(x));
        }
        state[key] = Array.from(local.values()).sort((a, b) => String(a.at || a.createdAt || '').localeCompare(String(b.at || b.createdAt || ''))).slice(-(limit || 500));
      };
      const workers = Object.assign({}, remote.workers || {});
      Object.keys(workers).forEach(k => { if (!state.workers[k] || String(workers[k].lastSeen || '') > String(state.workers[k].lastSeen || '')) state.workers[k] = safe(workers[k]); });
      ['runs', 'events', 'experiences', 'changelog'].forEach(k => mergeById(k, k === 'runs' ? MAX_RUNS : k === 'changelog' ? MAX_CHANGELOG : MAX_EVENTS));
      const localLast = (state.changelog || []).slice().reverse().find(x => ['promotion', 'rollback'].includes(x.type));
      const remoteLast = (remote.changelog || []).slice().reverse().find(x => ['promotion', 'rollback'].includes(x.type));
      if (remoteLast && (!localLast || String(remoteLast.at) > String(localLast.at))) {
        state.activeModel = clone(remote.activeModel || null);
        state.previousModel = clone(remote.previousModel || null);
      }
      trim();
      return save();
    },
    async sincronizar() {
      if (typeof Sync === 'undefined' || !Sync.ligado || !Sync.ligado()) throw new Error('Sync não está ligado');
      const chave = 'arkher_station_shared_v1';
      const remoto = await Sync.get(chave, null);
      if (remoto) this.importar(remoto);
      await Sync.set(chave, this.exportar());
      return snapshot();
    },

    registerWorker(info) {
      info = info || {};
      const wid = String(info.id || id('worker')).slice(0, 100);
      state.workers[wid] = Object.assign({}, state.workers[wid] || {}, safe({
        id: wid,
        name: info.name || wid,
        kind: info.kind || 'local',
        capabilities: info.capabilities || [],
        status: info.status || 'online',
        /* autorização é opt-in explícito; descobrir um worker não concede
           permissão para consumir jobs nem publicar candidatos. */
        authorized: info.authorized === true,
        lastSeen: now(),
        meta: info.meta || {},
      }));
      return save().workers[wid];
    },
    heartbeat(workerId, patch) {
      const w = state.workers[String(workerId)];
      if (!w) return null;
      Object.assign(w, safe(patch || {}), { lastSeen: now(), status: (patch && patch.status) || 'online' });
      return save().workers[String(workerId)];
    },
    removeWorker(workerId) { delete state.workers[String(workerId)]; return save(); },

    enqueue(spec) {
      spec = spec || {};
      const job = safe({
        id: spec.id || id('job'),
        kind: spec.kind || 'experiment',
        status: 'queued',
        createdAt: now(),
        priority: Number(spec.priority || 0),
        requestedBy: spec.requestedBy || 'user',
        runId: spec.runId || null,
        payload: spec.payload || {},
      });
      state.jobs.push(job);
      trim();
      save();
      return clone(job);
    },
    claim(jobId, workerId) {
      const job = state.jobs.find(j => j.id === jobId);
      const worker = state.workers[String(workerId)];
      if (!job || job.status !== 'queued' || !worker || worker.authorized === false) return null;
      Object.assign(job, { status: 'claimed', workerId: String(workerId), claimedAt: now() });
      save();
      return clone(job);
    },
    next(workerId, kinds) {
      const worker = state.workers[String(workerId)];
      if (!worker || worker.authorized === false) return null;
      const allowed = Array.isArray(kinds) && kinds.length ? kinds : null;
      const job = state.jobs.filter(j => j.status === 'queued' && (!allowed || allowed.includes(j.kind)))
        .sort((a, b) => (b.priority || 0) - (a.priority || 0) || String(a.createdAt).localeCompare(String(b.createdAt)))[0];
      return job ? this.claim(job.id, workerId) : null;
    },
    complete(jobId, result, status) {
      const job = state.jobs.find(j => j.id === jobId);
      if (!job) return null;
      Object.assign(job, { status: status || 'completed', finishedAt: now(), result: safe(result || {}) });
      save();
      return clone(job);
    },

    /* Coloca um job local na fila persistida do agente. O endpoint só aceita
       metadados e payload sanitizado; a execução continua sendo confirmada
       pelo lease/heartbeat/complete do worker. */
    async dispatch(jobId, base, options) {
      options = options || {};
      const job = state.jobs.find(j => j.id === jobId);
      if (!job) throw new Error('job local não existe: ' + jobId);
      const u = remoteBase(base);
      if (!u) throw new Error('sem URL do worker autorizado');
      const body = { job: jobForRemote(job) };
      if (options.workerId) body.workerId = String(options.workerId).slice(0, 120);
      const data = await remoteJson(u + '/station/job', {
        method: 'POST', headers: remoteHeaders(), body: JSON.stringify(body),
      });
      const remote = data.job || data.item || {};
      Object.assign(job, safe({ status: 'dispatched', remoteId: remote.id || job.id,
        remoteWorkerId: remote.workerId || body.workerId || null, dispatchedAt: now(),
        leaseUntil: remote.leaseUntil || null }));
      save();
      return clone(remote);
    },
    async reconcile(base, options) {
      options = options || {};
      const u = remoteBase(base);
      if (!u) throw new Error('sem URL do worker autorizado');
      const qs = options.limit ? ('?limit=' + encodeURIComponent(Math.max(1, Math.min(500, options.limit)))) : '';
      const data = await remoteJson(u + '/station/jobs' + qs, { headers: remoteHeaders() });
      const remotes = Array.isArray(data.items) ? data.items : [];
      let changed = false;
      const byId = new Map(remotes.map(x => [String(x.id), x]));
      state.jobs.forEach(job => {
        const r = byId.get(String(job.remoteId || job.id));
        if (!r) return;
        const patch = { status: r.status, remoteId: r.id || job.remoteId || job.id,
          workerId: r.workerId || job.workerId || null, leaseUntil: r.leaseUntil || null,
          attempts: r.attempts, lastHeartbeat: r.lastHeartbeat, finishedAt: r.finishedAt };
        if (r.result !== undefined) patch.result = r.result;
        Object.assign(job, safe(patch));
        const runId = r.runId || job.runId;
        const run = runId && state.runs.find(x => x.id === runId);
        if (run) {
          if (r.status === 'failed') run.status = 'failed';
          else if (r.status === 'completed' && ['queued', 'running', 'dispatched'].includes(run.status)) run.status = 'completed';
          if (r.result && r.result.metrics) run.metrics = Object.assign(run.metrics || {}, safe(r.result.metrics));
          if (r.result && Array.isArray(r.result.artifacts)) run.artifacts = safe(r.result.artifacts);
          run.updatedAt = now();
          state.events.push(safe({ id: id('evt'), at: now(), type: 'remote_job_reconciled',
            jobId: r.id, runId, state: r.status, verified: r.result && r.result.verified === true }));
        }
        changed = true;
      });
      if (changed) { trim(); save(); }
      return snapshot();
    },
    async heartbeatRemote(jobId, leaseToken, base, patch) {
      patch = patch || {};
      const u = remoteBase(base);
      if (!u) throw new Error('sem URL do worker autorizado');
      const data = await remoteJson(u + '/station/job/heartbeat', {
        method: 'POST', headers: remoteHeaders(), body: JSON.stringify(Object.assign({
          jobId, leaseToken,
        }, patch)),
      });
      const job = state.jobs.find(j => j.id === jobId || j.remoteId === jobId);
      if (job) { Object.assign(job, safe({ status: data.job && data.job.status || 'running',
        leaseUntil: data.job && data.job.leaseUntil || null, lastHeartbeat: now() })); save(); }
      return data.job || data;
    },
    async remoteJobs(base, options) {
      options = options || {};
      const u = remoteBase(base);
      if (!u) throw new Error('sem URL do worker autorizado');
      const qs = options.status ? '?status=' + encodeURIComponent(options.status) : '';
      const data = await remoteJson(u + '/station/jobs' + qs, { headers: remoteHeaders() });
      return Array.isArray(data.items) ? data.items : [];
    },

    createRun(spec) {
      spec = spec || {};
      const run = safe({
        id: spec.id || id('run'),
        name: spec.name || 'experiência ARKHER',
        kind: spec.kind || 'adapter',
        base: spec.base || 'modelo-base',
        status: 'queued',
        createdAt: now(),
        updatedAt: now(),
        metrics: {},
        checkpoints: [],
        artifacts: [],
        evaluation: null,
        notes: spec.notes || '',
      });
      state.runs.push(run);
      trim();
      save();
      return clone(run);
    },
    updateRun(runId, patch) {
      patch = patch || {};
      if (patch.workerId && (!state.workers[String(patch.workerId)] || state.workers[String(patch.workerId)].authorized !== true)) return null;
      const run = state.runs.find(r => r.id === runId);
      if (!run) return null;
      Object.assign(run, safe(patch), { updatedAt: now() });
      save();
      return clone(run);
    },
    checkpoint(runId, data) {
      data = data || {};
      if (data.workerId && (!state.workers[String(data.workerId)] || state.workers[String(data.workerId)].authorized !== true)) return null;
      const run = state.runs.find(r => r.id === runId);
      if (!run) return null;
      run.checkpoints = Array.isArray(run.checkpoints) ? run.checkpoints : [];
      const cp = safe(Object.assign({ at: now() }, data));
      run.checkpoints.push(cp);
      state.events.push(safe({ id: id('evt'), at: now(), type: 'checkpoint', runId, workerId: data.workerId || '',
        progress: data.progress, metrics: data.metrics || {}, message: data.message || '' }));
      run.status = 'running';
      run.updatedAt = now();
      trim();
      save();
      return clone(run);
    },
    evaluate(runId, evaluation) {
      evaluation = evaluation || {};
      if (evaluation.workerId && (!state.workers[String(evaluation.workerId)] || state.workers[String(evaluation.workerId)].authorized !== true)) return null;
      const run = state.runs.find(r => r.id === runId);
      if (!run) return null;
      run.evaluation = safe(evaluation);
      run.status = run.evaluation.pass === false ? 'rejected' : 'candidate';
      run.updatedAt = now();
      state.changelog.push({ at: now(), type: 'evaluation', runId, status: run.status, evaluation: run.evaluation });
      trim();
      save();
      return clone(run);
    },
    promote(runId, reason) {
      const run = state.runs.find(r => r.id === runId);
      /* Promoção é uma operação de produção: um treino concluído sem
         avaliação independente continua sendo apenas "trained". */
      if (!run || !['candidate', 'evaluated'].includes(run.status)
          || !run.evaluation || run.evaluation.pass !== true) return null;
      const old = state.activeModel;
      state.previousModel = old ? clone(old) : state.previousModel;
      const primeiroArtefato = Array.isArray(run.artifacts) && run.artifacts[0];
      const referenciaArtefato = primeiroArtefato && typeof primeiroArtefato === 'object'
        ? (primeiroArtefato.path || primeiroArtefato.name || run.id)
        : (primeiroArtefato || run.id);
      state.activeModel = safe({ id: run.id, version: run.id, name: run.name, base: run.base,
        model: referenciaArtefato, promotedAt: now() });
      run.status = 'promoted';
      run.updatedAt = now();
      state.changelog.push({ at: now(), type: 'promotion', runId, from: old && old.version || null, to: run.id, reason: String(reason || 'promoção manual').slice(0, 300) });
      trim();
      save();
      return clone(state.activeModel);
    },
    rollback(reason) {
      if (!state.previousModel) return null;
      const current = state.activeModel;
      state.activeModel = clone(state.previousModel);
      state.previousModel = current ? clone(current) : null;
      state.changelog.push({ at: now(), type: 'rollback', from: current && current.version || null, to: state.activeModel && state.activeModel.version || null, reason: String(reason || 'rollback manual').slice(0, 300) });
      save();
      return clone(state.activeModel);
    },

    event(evt) {
      evt = evt || {};
      if (evt.workerId) {
        const worker = state.workers[String(evt.workerId)];
        if (!worker || worker.authorized !== true) return null;
      }
      const ev = safe(Object.assign({ id: id('evt'), at: now(), type: 'telemetry' }, evt));
      state.events.push(ev);
      if (ev.workerId && state.workers[ev.workerId]) Object.assign(state.workers[ev.workerId], { lastSeen: ev.at, status: ev.status || 'online' });
      if (ev.runId) {
        const run = state.runs.find(r => r.id === ev.runId);
        if (run) {
          run.updatedAt = now();
          if (ev.state) run.status = ev.state;
          if (ev.metrics) run.metrics = Object.assign(run.metrics || {}, ev.metrics);
          if (ev.checkpoint) { run.checkpoints = run.checkpoints || []; run.checkpoints.push(ev.checkpoint); }
        }
      }
      trim();
      save();
      return clone(ev);
    },
    experience(exp) {
      state.experiences.push(safe(Object.assign({ id: id('exp'), at: now() }, exp || {})));
      trim();
      save();
      return clone(state.experiences[state.experiences.length - 1]);
    },
    changelog() { return clone(state.changelog) || []; },
    reset() { state = fresh(); return save(); },
  };
  return api;
})();

if (typeof window !== 'undefined') window.ArkherStation = ArkherStation;
if (typeof module !== 'undefined' && module.exports) module.exports = { ArkherStation };
