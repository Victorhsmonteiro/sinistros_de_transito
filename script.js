/* =========================================================
   Perguntas sugeridas
========================================================= */
const SUGGESTED_QUESTIONS = [
  "Onde acontecem mais acidentes no Piauí?",
  "Qual a importância de usar capacete nas motos?",
  "Qual a diferença de mortalidade nos acidentes usando cinto de segurança?",
  "Como evoluiu o número de óbitos nos últimos anos?",
  "Quais tipos de veículo mais se envolvem em sinistros?"
];

const MODEL = "gemini-3.6-flash";
let dataset = null;

/* =========================================================
   Carregamento dos dados
========================================================= */
async function loadData(){
  try{
    const res = await fetch('data/sinistros.json');
    if(!res.ok) throw new Error('HTTP ' + res.status);
    dataset = await res.json();
    renderVivaKpis();
    renderKpis();
    renderLocais();
  }catch(err){
    const erro = '<div class="rounded-[var(--radius)] border px-4 py-4 kpi-danger">' +
      '<p class="mb-1.5 text-[13px] font-medium text-danger-soft">Erro ao carregar dados</p>' +
      '<p class="text-[14px] font-semibold tracking-tight text-danger-soft">Sirva os arquivos com um servidor local (ex: python3 -m http.server) — abrir o HTML direto do disco bloqueia o fetch do JSON.</p></div>';
    document.getElementById('vivaGrid').innerHTML = erro;
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('locaisBody').innerHTML =
      '<tr><td colspan="5" class="px-2.5 py-3 text-[13px] text-danger-soft">Não foi possível carregar data/sinistros.json.</td></tr>';
  }
}

function pctFmt(v){ return v == null ? '—' : Math.round(v * 1000) / 10 + '%'; }

function kpiCard(c){
  const tone = c.danger ? 'kpi-danger' : 'kpi-amber';
  const labelTone = c.danger ? 'text-danger-soft' : 'text-amber';
  const valueTone = c.danger ? 'text-danger-soft' : '';
  return `
    <div class="rounded-[var(--radius)] border px-4 py-4 ${tone}">
      <p class="mb-1.5 text-[13px] font-medium ${labelTone}">${c.label}</p>
      <p class="text-[26px] font-extrabold tracking-tight tabular ${valueTone}">${c.value}${c.unit ? `<span class="ml-0.5 text-sm font-medium text-muted-foreground">${c.unit}</span>` : ''}</p>
    </div>`;
}

/* =========================================================
   Dashboard: perfil VIVA 2014 (dados reais nacionais)
========================================================= */
function renderVivaKpis(){
  const ev = dataset.evento;
  const at = dataset.atendimento_evolucao;
  const amostra = dataset.fonte_dados_viva_2014.amostra_total;
  const cards = [
    { label: 'Motociclistas sem capacete (atendidos)', value: pctFmt(ev.uso_capacete.nao.total_pct), danger:true },
    { label: 'Envolveram consumo de álcool', value: pctFmt(ev.consumo_alcool.sim.total_pct), danger:true },
    { label: 'Evoluíram para internação hospitalar', value: pctFmt(at.evolucao.internacao_hospitalar.total_pct) },
    { label: 'Evoluíram para óbito (na amostra)', value: pctFmt(at.evolucao.obito_outros.total_pct), danger:true },
    { label: 'Faixa etária mais atingida', value: '20–39 anos' },
    { label: 'Tamanho da amostra', value: amostra.toLocaleString('pt-BR'), unit:'atendimentos' }
  ];
  document.getElementById('vivaGrid').innerHTML = cards.map(kpiCard).join('');
}

/* =========================================================
   Dashboard: morbidade hospitalar Piauí 2010-2023 (dados reais)
========================================================= */
function renderKpis(){
  const e = dataset.estudo_morbidade_piaui_2010_2023;
  const cards = [
    { label: 'Internações por acidente (2010–2023)', value: e.total_internacoes_periodo.toLocaleString('pt-BR') },
    { label: 'Taxa média de internação', value: e.taxa_internacao_hospitalar_100mil_hab.geral.valor, unit:'/100 mil hab.', danger:true },
    { label: 'Óbitos hospitalares no período', value: e.letalidade_hospitalar_pct.obitos_hospitalares_totais_periodo.toLocaleString('pt-BR'), danger:true },
    { label: 'Letalidade hospitalar', value: e.letalidade_hospitalar_pct.geral.valor + '%' },
    { label: 'Permanência média internado', value: e.permanencia_media_dias.geral.valor, unit:'dias' },
    { label: 'Ano com mais internações', value: e.ano_com_mais_internacoes.ano, unit: `(${e.ano_com_mais_internacoes.internacoes.toLocaleString('pt-BR')} casos)` }
  ];
  document.getElementById('kpiGrid').innerHTML = cards.map(kpiCard).join('');
}

const NOMES_REGIAO = {
  carnaubais: 'Carnaubais', chapada_das_mangabeiras: 'Chapada das Mangabeiras', cocais: 'Cocais',
  entre_rios: 'Entre Rios', planicie_litoranea: 'Planície Litorânea', serra_da_capivara: 'Serra da Capivara',
  tabuleiros_do_alto_parnaiba: 'Tabuleiros do Alto Parnaíba', vale_do_caninde: 'Vale do Canindé',
  vale_do_rio_guaribas: 'Vale do Rio Guaribas', vale_do_sambito: 'Vale do Sambito',
  vale_dos_rios_piaui_e_itaueiras: 'Vale dos Rios Piauí e Itaueiras', chapada_vale_do_rio_itaim: 'Chapada Vale do Rio Itaim'
};
const MACRORREGIAO_DA_REGIAO = {
  carnaubais: 'Meio-Norte', cocais: 'Meio-Norte', entre_rios: 'Meio-Norte', vale_do_sambito: 'Meio-Norte',
  vale_do_caninde: 'Semiárido', vale_do_rio_guaribas: 'Semiárido', serra_da_capivara: 'Semiárido',
  chapada_das_mangabeiras: 'Semiárido',
  planicie_litoranea: 'Litoral', chapada_vale_do_rio_itaim: 'Litoral',
  tabuleiros_do_alto_parnaiba: 'Cerrado', vale_dos_rios_piaui_e_itaueiras: 'Cerrado'
};

// Mapeia o rótulo textual da tendência para um rótulo curto + a cor da célula.
function tendenciaInfo(tendencia){
  const t = (tendencia || '').toLowerCase();
  if(t.startsWith('cresc')) return { label: 'alta', cls: 'text-danger' };
  if(t.startsWith('decresc')) return { label: 'queda', cls: 'text-success' };
  return { label: 'estável', cls: 'text-muted-foreground' };
}

function renderLocais(){
  const porRegiao = dataset.estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab.por_regiao_de_saude;
  const linhas = Object.entries(porRegiao)
    .map(([chave, dados]) => ({ chave, ...dados }))
    .sort((a, b) => b.valor - a.valor);
  const body = document.getElementById('locaisBody');
  body.innerHTML = linhas.map((l, i) => {
    const t = tendenciaInfo(l.tendencia);
    return `
      <tr>
        <td class="border-b border-border px-2.5 py-2.5 last:border-none">
          <span class="inline-flex h-5 w-5 items-center justify-center rounded bg-panel-2 text-xs font-bold text-amber">${i + 1}</span>
        </td>
        <td class="border-b border-border px-2.5 py-2.5">${NOMES_REGIAO[l.chave] || l.chave}</td>
        <td class="border-b border-border px-2.5 py-2.5 text-muted-foreground">${MACRORREGIAO_DA_REGIAO[l.chave] || '—'}</td>
        <td class="tabular cell-danger border-b border-border px-2.5 py-2.5 text-right font-semibold text-danger-soft">${l.valor}</td>
        <td class="border-b border-border px-2.5 py-2.5 ${t.cls}">${t.label}</td>
      </tr>`;
  }).join('');
}

function renderSuggestions(){
  const wrap = document.getElementById('suggestions');
  wrap.innerHTML = SUGGESTED_QUESTIONS.map(q =>
    `<button type="button" class="rounded-full border border-border bg-panel-2 px-2.5 py-1.5 text-[12.5px] text-muted-foreground transition-colors hover:border-amber-dim hover:text-foreground" data-q="${q.replace(/"/g,'&quot;')}">${q}</button>`
  ).join('');
  wrap.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => askQuestion(btn.dataset.q));
  });
}

/* =========================================================
   Busca: resolve um caminho tipo "evento.uso_capacete" dentro
   do dataset, devolvendo o objeto correspondente.
========================================================= */
function resolvePath(path){
  return path.split('.').reduce((obj, key) => (obj && key in obj) ? obj[key] : undefined, dataset);
}

function normalize(str){
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

// Monta um contexto sob medida para a pergunta, usando o índice de busca do JSON.
// Se nenhuma palavra-chave bater, cai no fallback de enviar tudo (evita respostas incompletas).
function buildContextForQuestion(question){
  const q = normalize(question);
  const indice = dataset.indice_busca || {};
  const pathsEncontrados = new Set();
  const palavrasEncontradas = [];

  for(const [palavra, paths] of Object.entries(indice)){
    if(q.includes(normalize(palavra))){
      palavrasEncontradas.push(palavra);
      paths.forEach(p => pathsEncontrados.add(p));
    }
  }

  // Sempre inclui um resumo geral leve, independente do que foi encontrado.
  const resumoGeral = {
    fonte_dados_viva_2014: dataset.fonte_dados_viva_2014,
    panorama_piaui: {
      fonte: dataset.estudo_morbidade_piaui_2010_2023.citacao,
      periodo: dataset.estudo_morbidade_piaui_2010_2023.periodo_estudado,
      total_internacoes: dataset.estudo_morbidade_piaui_2010_2023.total_internacoes_periodo,
      taxa_media_internacao: dataset.estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab.geral,
      letalidade_hospitalar: dataset.estudo_morbidade_piaui_2010_2023.letalidade_hospitalar_pct.geral
    }
  };

  let contexto;
  if(pathsEncontrados.size === 0){
    // fallback: nenhuma palavra-chave reconhecida, envia a base inteira
    contexto = dataset;
  }else{
    contexto = { resumo_geral: resumoGeral };
    pathsEncontrados.forEach(path => {
      contexto[path] = resolvePath(path);
    });
  }

  return { contexto, palavrasEncontradas };
}

/* =========================================================
   Chat
========================================================= */
// Remove marcações markdown que o modelo às vezes insere como texto literal
// (asterisco de negrito/itálico, hashtag de título, marcador de lista).
function limparMarkdown(text){
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')   // **negrito** -> negrito
    .replace(/\*(.+?)\*/g, '$1')       // *itálico* -> itálico
    .replace(/^#{1,6}\s*/gm, '')       // # Título -> Título
    .replace(/^[*•]\s+/gm, '- ');      // * item / • item -> - item
}

function appendMessage(role, text, extraClass){
  const log = document.getElementById('log');
  const empty = document.getElementById('emptyLog');
  if(empty) empty.remove();
  const div = document.createElement('div');
  const base = role === 'user'
    ? 'max-w-[88%] self-end rounded-lg border border-border bg-panel-2 px-3.5 py-2.5 text-sm leading-relaxed'
    : 'max-w-[88%] self-start rounded-lg border border-amber-dim px-3.5 py-2.5 text-sm leading-relaxed';
  div.className = base + (extraClass === 'error' ? ' border-danger text-danger-soft' : '') +
    (extraClass === 'loading' ? ' italic text-faint' : '');
  const tagText = role === 'user' ? 'você' : 'assistente';
  div.innerHTML = `<span class="mb-1 block text-[10px] uppercase tracking-[0.1em] text-faint">${tagText}</span>${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

async function askQuestion(question){
  if(!question || !question.trim()) return;
  const apiKey = document.getElementById('apiKey').value.trim();
  if(!apiKey){
    appendMessage('ai', 'Informe sua chave da API Gemini acima para o assistente poder responder.', 'error');
    return;
  }
  if(!dataset){
    appendMessage('ai', 'Os dados ainda não foram carregados. Verifique se o arquivo data/sinistros.json está acessível.', 'error');
    return;
  }
  appendMessage('user', question);
  const loadingEl = appendMessage('ai', 'Buscando os dados relevantes e analisando...', 'loading');

  const askBtn = document.getElementById('askBtn');
  askBtn.disabled = true;

  const { contexto, palavrasEncontradas } = buildContextForQuestion(question);

  const systemPrompt =
    "Você é um assistente de análise de segurança viária do Piauí. " +
    "Responda SOMENTE com base nos dados JSON fornecidos abaixo (um recorte relevante da base completa).\n\n" +
    "REGRAS DE ESTILO (siga sempre, sem exceção):\n" +
    "- Seja curto e objetivo: no máximo 3-4 frases, ou até 4 linhas se precisar listar números.\n" +
    "- Responda SOMENTE o que foi perguntado. Não acrescente contexto, curiosidades ou recomendações que não " +
    "foram pedidas, mesmo que estejam disponíveis nos dados.\n" +
    "- Não use markdown: nada de asterisco, hashtag, negrito ou itálico. Escreva em texto simples.\n" +
    "- Se precisar listar itens, use quebra de linha com um travessão (\"- \") no início de cada item, nunca " +
    "asterisco.\n" +
    "- Sempre siga este formato: (1) uma frase direta respondendo a pergunta, (2) opcionalmente, até 3 números " +
    "de apoio que fundamentam a resposta, (3) se usar o dado nacional VIVA 2014, termine com uma frase curta " +
    "avisando que aquele número é nacional, não do Piauí.\n\n" +
    "FONTES DOS DADOS (não confunda uma com a outra):\n" +
    "(1) 'fonte_dados_viva_2014', 'evento', 'perfil_demografico' e 'atendimento_evolucao' vêm de uma pesquisa " +
    "NACIONAL (VIVA 2014, capitais + DF, ano de 2014) sobre motociclistas atendidos em emergência — não são " +
    "específicos do Piauí. " +
    "(2) 'estudo_morbidade_piaui_2010_2023' e 'piaui_dados_locais' são dados REAIS e ESPECÍFICOS do Piauí " +
    "(SIH/SUS, artigo científico Rev Bras Epidemiol 2026), cobrindo 2010 a 2023 — use como fonte primária " +
    "para perguntas sobre o Piauí especificamente. " +
    "(3) 'dados_tabnet_piaui_teresina' é uma consulta bruta do TABNET/DATASUS (SIH/SUS), também REAL e " +
    "ESPECÍFICA do Piauí, mas com série mais longa (2009 a 2026, sendo 2026 parcial) e recorte adicional só " +
    "do município de Teresina; os totais dela NÃO batem exatamente com os de 'estudo_morbidade_piaui_2010_2023' " +
    "porque a metodologia e o período são diferentes — se usar essa fonte, avise que é uma consulta bruta e " +
    "não o artigo científico.\n\n" +
    "Se a pergunta não puder ser respondida com esses dados, diga isso em uma frase e pare — não tente " +
    "compensar com informação não solicitada.\n\n" +
    "DADOS:\n" + JSON.stringify(contexto);

  try{
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${encodeURIComponent(apiKey)}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: systemPrompt }] },
        contents: [{ role: 'user', parts: [{ text: question }] }],
        generationConfig: {
          maxOutputTokens: 2048,
          thinkingConfig: { thinkingLevel: "low" }
        }
      })
    });

    const data = await res.json();
    loadingEl.remove();

    if(!res.ok){
      const msg = (data && data.error && data.error.message) ? data.error.message : ('Erro HTTP ' + res.status);
      appendMessage('ai', 'Não foi possível obter resposta: ' + msg, 'error');
      return;
    }

    const candidate = (data.candidates || [])[0];
    const parts = candidate && candidate.content && candidate.content.parts;
    const text = parts && parts.length ? parts.map(p => p.text || '').join('') : null;

    if(!text){
      const reason = candidate ? candidate.finishReason : 'sem candidatos';
      appendMessage('ai', 'A API não retornou texto (motivo: ' + reason + ').', 'error');
      return;
    }

    const cortada = candidate.finishReason === 'MAX_TOKENS';
    const avisoCorte = cortada
      ? '<br><br><em>(resposta cortada por limite de tokens — tente uma pergunta mais específica)</em>'
      : '';
    const debugTag = palavrasEncontradas.length
      ? `<span class="mt-2 block border-t border-border pt-1.5 text-[10.5px] text-faint">Trechos usados na busca: ${palavrasEncontradas.join(', ')}</span>`
      : `<span class="mt-2 block border-t border-border pt-1.5 text-[10.5px] text-faint">Nenhuma palavra-chave reconhecida — base completa enviada</span>`;
    appendMessage('ai', limparMarkdown(text).replace(/\n/g,'<br>') + avisoCorte + '<br>' + debugTag);
  }catch(err){
    loadingEl.remove();
    appendMessage('ai', 'Falha de conexão com a API: ' + err.message, 'error');
  }finally{
    askBtn.disabled = false;
  }
}

document.getElementById('apiKey').addEventListener('input', (e) => {
  const status = document.getElementById('keyStatus');
  if(e.target.value.trim()){
    status.textContent = 'chave informada (só nesta sessão)';
    status.classList.remove('text-faint');
    status.classList.add('text-success');
  }else{
    status.textContent = 'não informada';
    status.classList.remove('text-success');
    status.classList.add('text-faint');
  }
});

document.getElementById('askForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const input = document.getElementById('askInput');
  const q = input.value;
  input.value = '';
  askQuestion(q);
});

renderSuggestions();
loadData();
