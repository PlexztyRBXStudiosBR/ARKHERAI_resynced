/* ============================================================
   ARKHER TASK — classificador e plano de trabalho

   O ARKHER continua geral. Este módulo só dá prioridade e método às
   tarefas de código, engines, game dev e criação técnica, sem obrigar
   toda pergunta casual a passar por um pipeline pesado.
   ============================================================ */
'use strict';

const ArkherTask = {
  VERSION: '0.1.0',

  detect(input) {
    const t = Array.isArray(input)
      ? input.map(m => m && m.content || '').join('\n')
      : String(input || '');
    const s = t.toLowerCase();
    const tags = [];
    const add = (id, re) => { if (re.test(s) && !tags.includes(id)) tags.push(id); };
    add('roblox', /roblox|luau|remoteevent|roblox\s+studio|rojo|wally/);
    add('blender', /blender|\.blend|modelagem|malha 3d|mesh|uv map|rig|rigging/);
    add('cascadeur', /cascadeur|anima[cç][aã]o|motion capture|mocap|esqueleto/);
    add('unity', /unity|c#/);
    add('unreal', /unreal|ue5|blueprint|niagara|umg/);
    add('godot', /godot|gdscript/);
    add('game', /jogo|game|engine|motor gr[aá]fico|playtest|build|asset|shader|npc/);
    add('code', /c[oó]digo|script|programa|debug|erro|api|fun[cç][aã]o|classe|compile|compilar/);
    add('research', /pesquis|fonte|documenta[cç][aã]o|artigo|refer[eê]ncia|verifique|atual/);
    add('visual', /imagem|v[ií]deo|textura|render|visual|refer[eê]ncia visual|3d/);
    add('build', /build|deploy|publicar|empacotar|instalar depend[eê]ncia|ci\/cd/);

    let id = 'general';
    if (tags.some(x => ['roblox', 'blender', 'cascadeur', 'unity', 'unreal', 'godot', 'game'].includes(x))) id = 'game-dev';
    else if (tags.includes('code') || tags.includes('build')) id = 'engineering';
    else if (tags.includes('visual')) id = 'creative-tech';
    else if (tags.includes('research')) id = 'research';

    const stage = id === 'game-dev' || id === 'engineering' ? 'code' : id === 'creative-tech' ? 'visao' : 'chat';
    return {
      id,
      tags,
      stage,
      prioridade: id === 'game-dev' ? 'alta' : id === 'engineering' ? 'alta' : 'normal',
      verificar: id === 'game-dev' || id === 'engineering' || id === 'creative-tech',
      pesquisar: tags.includes('research') || id === 'game-dev',
      usarFerramentas: id !== 'general',
    };
  },

  plano(task, objetivo) {
    const t = task || this.detect(objetivo);
    if (t.id === 'game-dev' || t.id === 'engineering') {
      return [
        { id: 'entender', nome: 'Entender requisitos e ambiente', obrigatorio: true },
        { id: 'pesquisar', nome: 'Consultar documentação e memória relevante', obrigatorio: !!t.pesquisar },
        { id: 'planejar', nome: 'Planejar arquivos, dependências e passos', obrigatorio: true },
        { id: 'executar', nome: 'Escrever/alterar e executar no ambiente autorizado', obrigatorio: true },
        { id: 'diagnosticar', nome: 'Ler saída, logs e erros reais', obrigatorio: true },
        { id: 'corrigir', nome: 'Corrigir e repetir até atingir o limite', obrigatorio: true },
        { id: 'entregar', nome: 'Entregar artefatos, testes e limitações', obrigatorio: true },
      ].filter(x => x.obrigatorio);
    }
    if (t.id === 'creative-tech') return [
      { id: 'referencias', nome: 'Organizar referências e restrições' },
      { id: 'gerar', nome: 'Gerar no programa especializado' },
      { id: 'avaliar', nome: 'Renderizar e comparar versões' },
      { id: 'exportar', nome: 'Exportar no formato pedido e validar' },
    ];
    return [{ id: 'responder', nome: 'Responder diretamente' }];
  },

  contexto(task, objetivo) {
    const t = task || this.detect(objetivo);
    if (t.id === 'general') return '';
    return [
      'MODO DE TRABALHO ARKHER: ' + t.id,
      'Tags: ' + t.tags.join(', '),
      'Quando houver código ou arquivo, não diga que testou sem executar.',
      t.usarFerramentas ? 'MODO TOOL-FIRST: pesquisar quando necessário, executar, observar o resultado, testar, corrigir e só então entregar.' : '',
      t.verificar ? 'Prefira executar, renderizar, compilar ou validar antes de afirmar que está pronto.' : '',
      t.pesquisar ? 'Use documentação/fonte e registre a origem quando a informação for atual ou específica.' : '',
      'Se faltar acesso ao ambiente, diga exatamente o que não foi executado e entregue o próximo passo.',
    ].filter(Boolean).join('\n');
  },

  resumo(t) { return t ? t.id + ' · ' + (t.tags || []).join(', ') : 'general'; },
};

if (typeof window !== 'undefined') window.ArkherTask = ArkherTask;
if (typeof module !== 'undefined' && module.exports) module.exports = { ArkherTask };
