/* ============================================================
   ARKHER GUARD — camada final de segurança e qualidade

   O guard não substitui a política do provedor. Ele fica depois da
   resposta para evitar que o app entregue segredos, instruções de dano
   real ou uma resposta vazia como se fosse sucesso.

   Princípio: permitir conteúdo legal e útil por padrão; bloquear somente
   sinais fortes de abuso real; marcar código para teste em vez de fingir
   que ele funcionou.
   ============================================================ */
'use strict';
if (typeof LS === 'undefined' && typeof require !== 'undefined') globalThis.LS = require('./core.js').LS;

const Guard = {
  VERSION: '0.1.0',
  KEY: 'arkher_guard_v1',

  _cfg() {
    const d = LS.get(this.KEY, null);
    return Object.assign({ ligado: true, redigirSegredos: true, exigirTesteParaCodigo: true }, d || {});
  },
  configurar(patch) { const n = Object.assign(this._cfg(), patch || {}); LS.set(this.KEY, n); return n; },
  config() { return this._cfg(); },

  /* Padrões de alta confiança. Não bloqueamos palavras sensíveis isoladas:
     contexto e autorização importam, especialmente em game dev. */
  BLOQUEIOS: [
    { id: 'credenciais', re: /(roubar|furtar|exfiltrar|dump(?:ar)?|capturar)\s+(?:senha|token|cookie|credencial|sess[aã]o)/i },
    { id: 'invasao', re: /(bypass|contornar|quebrar|invadir)\s+.{0,30}(2fa|autentica[cç][aã]o|senha|conta|login)/i },
    { id: 'malware', re: /(ransomware|keylogger|reverse\s*shell|persist[êe]ncia\s+maliciosa|desativar\s+(?:o\s+)?antiv[ií]rus|roubar\s+arquivos)/i },
    { id: 'dano-fisico', re: /(fabricar|fabrique|construir|construa|montar|monte|detonar)\s+.{0,35}(bomba|explosivo|arma\s+qu[ií]mica|veneno\s+letal)/i },
    { id: 'abuso-infantil', re: /(material|imagem|vídeo|video|conteúdo|conteudo).{0,35}(sexual|íntimo|intimo).{0,25}(menor|criança|crianca|infantil)/i },
    { id: 'fraude', re: /(clonar|falsificar|forjar)\s+.{0,30}(documento|identidade|assinatura|comprovante)\s+.{0,30}(enganar|fraudar|v[ií]tima)/i },
  ],
  ROBLOX_ABUSO: /(executor|injector|injetar|bypass\s+(?:de\s+)?anti.?cheat|dupe\s+robux|roubar\s+robux|exploit\s+em\s+jogo\s+de\s+terceiro|trapacear\s+em\s+jogo\s+público|publico)/i,
  ROBLOX_AUTORIZADO: /(meu\s+jogo|meu\s+place|roblox\s+studio|servidor\s+privado|ambiente\s+de\s+teste|autorizad|laborat[oó]rio|sandbox|local)/i,
  AUTORIZADO: /(meu|minha|pr[oó]pri[ao]|laborat[oó]rio|sandbox|ambiente\s+de\s+teste|pentest|ctf|servidor\s+privado|autorizad|pesquisa\s+de\s+seguran[cç]a|defensiv|simula[cç][aã]o|detec[cç][aã]o|an[aá]lise)/i,

  SEGREDOS: [
    { id: 'private-key', re: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g, repl: '[CHAVE PRIVADA REDIGIDA]' },
    { id: 'openai', re: /\bsk-[A-Za-z0-9_-]{20,}\b/g, repl: '[TOKEN REDIGIDO]' },
    { id: 'anthropic', re: /\bsk-ant-[A-Za-z0-9_-]{12,}\b/g, repl: '[TOKEN REDIGIDO]' },
    { id: 'google', re: /\bAIza[0-9A-Za-z_-]{20,}\b/g, repl: '[TOKEN REDIGIDO]' },
    { id: 'github', re: /\b(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, repl: '[TOKEN REDIGIDO]' },
    { id: 'hf', re: /\bhf_[A-Za-z0-9]{10,}\b/g, repl: '[TOKEN REDIGIDO]' },
    { id: 'generic-bearer', re: /\bBearer\s+[A-Za-z0-9._-]{20,}\b/gi, repl: 'Bearer [TOKEN REDIGIDO]' },
  ],

  _texto(input) {
    if (Array.isArray(input)) return input.map(x => x && x.content ? this._texto(x.content) : '').join('\n');
    if (input && typeof input === 'object') return JSON.stringify(input);
    return String(input || '');
  },

  sanear(text) {
    let out = String(text || '');
    const encontrados = [];
    if (!this._cfg().redigirSegredos) return { text: out, redigidos: encontrados };
    for (const s of this.SEGREDOS) {
      const antes = out;
      out = out.replace(s.re, s.repl);
      if (out !== antes) encontrados.push(s.id);
    }
    return { text: out, redigidos: Array.from(new Set(encontrados)) };
  },

  classificar(input, contexto) {
    const t = (this._texto(input) + '\n' + this._texto(contexto)).slice(0, 50000);
    const riscos = [];
    for (const p of this.BLOQUEIOS) if (p.re.test(t)) riscos.push(p.id);
    /* Executor/injeção é permitido apenas quando há contexto explícito de
       projeto próprio/teste; caso contrário é uma tentativa de abuso. */
    if (this.ROBLOX_ABUSO.test(t) && !this.ROBLOX_AUTORIZADO.test(t)) riscos.push('roblox-nao-autorizado');
    const gameContext = /(jogo|game|roblox|unity|unreal|godot|blender|fic[cç][aã]o|hist[oó]ria)/i.test(t);
    const realHarm = /(vida\s+real|pessoa\s+real|terceiro|conta\s+alheia|sistema\s+real|fora\s+do\s+jogo)/i.test(t);
    let unicos = Array.from(new Set(riscos));
    /* Conteúdo de jogo/ficção não vira automaticamente dano real. Mantemos
       credenciais e abuso de terceiros bloqueados, mesmo quando alguém cita
       um game para tentar mascarar o objetivo. */
    if (gameContext && !realHarm) unicos = unicos.filter(x => !['dano-fisico', 'fraude', 'malware'].includes(x));
    const autorizado = this.AUTORIZADO.test(t);
    const revisaveis = ['credenciais', 'invasao', 'malware', 'roblox-nao-autorizado'];
    /* Laboratório, CTF, pentest e software próprio não devem virar uma
       recusa genérica. Ainda ficam marcados como revisão para o chamador
       poder exigir confirmação/teste antes de executar. Dano físico, CSAM
       e fraude nunca ganham esta exceção textual. */
    if (unicos.length && autorizado && unicos.every(x => revisaveis.includes(x))) {
      return { nivel: 'revisar', riscos: unicos, autorizado: true };
    }
    return { nivel: unicos.length ? 'bloquear' : 'permitir', riscos: unicos, autorizado };
  },

  _codigo(text) {
    return /```|\b(function|class|def|import|require|const|local|extends|using)\b|\.lua\b|\.luau\b|\.py\b|\.blend\b/i.test(String(text || ''));
  },

  /* O modelo não ganha permissão para executar um comando só por ter
     produzido JSON. Ações destrutivas ou que parecem exfiltração precisam
     de contexto explícito de máquina própria/teste; pedidos legítimos de
     game dev, build e automação continuam passando. */
  autorizarFerramenta(call, contexto) {
    const c = call || {};
    const args = c.args || {};
    const raw = JSON.stringify(args) + '\n' + String(contexto || '');
    const cmd = String(args.cmd || args.comando || args.script || args.conteudo || '');
    const perigoso = /(rm\s+-rf\s+[/~]|Remove-Item\b[^\n]{0,180}-Recurse|format\s+[a-z]:|del\s+[/\\][sS]|shutdown\s+[/\\]s|net\s+user\b[^\n]*(?:add|\/active)|reg\s+delete\b|reverse\s*shell|keylogger|ransomware|curl\b[^\n]*(?:\/etc\/passwd|shadow)|wget\b[^\n]*(?:\/etc\/passwd|shadow)|powershell\s+-(?:enc|e)\b)/i.test(cmd + '\n' + raw);
    const autorizado = /(meu|minha|pr[oó]pri[ao]|local|sandbox|vm|servidor\s+privado|ambiente\s+de\s+teste|autorizad|projeto\s+pr[oó]prio|jogo\s+pr[oó]prio)/i.test(String(contexto || ''));
    if (perigoso && !autorizado) return { ok: false, reason: 'comando de alto risco sem contexto explícito de ambiente próprio/teste' };
    if (/(token|senha|cookie|credencial|private key|api.?key)/i.test(raw) && /(exfil|roub|enviar|publicar|upload|curl|wget|post)/i.test(raw)) {
      return { ok: false, reason: 'possível envio ou exfiltração de segredo' };
    }
    return { ok: true, reason: '' };
  },

  verificar(input, output, meta) {
    const cfg = this._cfg();
    const texto = String(output || '');
    const classe = this.classificar(input, texto);
    const limpo = this.sanear(texto);
    const avisos = [];
    if (!texto.trim()) avisos.push('resposta-vazia');
    if (classe.nivel === 'revisar') avisos.push('revisao-autorizada');
    if (limpo.redigidos.length) avisos.push('segredo-redigido');
    if (this._codigo(texto) && cfg.exigirTesteParaCodigo) avisos.push('codigo-nao-testado');
    const bloqueado = cfg.ligado && classe.nivel === 'bloquear';
    return {
      ok: !bloqueado && !!limpo.text.trim(),
      action: bloqueado ? 'block' : (limpo.redigidos.length ? 'redact' : 'deliver'),
      text: bloqueado ? this.alternativa(classe.riscos) : limpo.text,
      riscos: classe.riscos,
      avisos,
      redigidos: limpo.redigidos,
      precisaTeste: avisos.includes('codigo-nao-testado'),
      modelo: meta && meta.model || '',
      version: this.VERSION,
    };
  },

  alternativa(riscos) {
    if ((riscos || []).includes('roblox-nao-autorizado')) {
      return 'Não ajudo a criar executor, injeção ou bypass para prejudicar jogos de terceiros. Posso ajudar com Luau no seu próprio jogo, Roblox Studio, servidor privado, testes de anti-cheat ou um plugin autorizado.';
    }
    return 'Não posso fornecer instruções para dano real, invasão, roubo de credenciais ou fraude. Posso ajudar com uma alternativa defensiva, autorizada ou em ambiente de laboratório.';
  },

  /* eventos pequenos e sem texto de usuário: úteis para o dashboard sem criar
     um histórico de dados pessoais. */
  evento(verdict, extra) {
    const v = verdict || {};
    return Object.assign({ at: Date.now(), action: v.action || 'unknown', riscos: v.riscos || [], avisos: v.avisos || [] }, extra || {});
  },
};

if (typeof window !== 'undefined') window.Guard = Guard;
if (typeof module !== 'undefined' && module.exports) module.exports = { Guard };
