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
   O mapa e os rankings da PRF usam data/mapa_prf.json e data/malha_pi.json
   (gerados por scripts/gerar_territorios.py), carregados em paralelo.
========================================================= */
const fetchJson = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject(new Error(url + ': HTTP ' + r.status)));
const prfPromise = fetchJson('data/mapa_prf.json');
const malhaPromise = fetchJson('data/malha_pi.json');
prfPromise.catch(() => {}); malhaPromise.catch(() => {});   // o erro é tratado onde cada um é usado

async function loadData(){
  try{
    const res = await fetch('data/sinistros.json');
    if(!res.ok) throw new Error('HTTP ' + res.status);
    dataset = await res.json();
  }catch(err){
    const erro = '<div class="rounded-[var(--radius)] border px-4 py-4 kpi-danger">' +
      '<p class="mb-1.5 text-[13px] font-medium text-danger-soft">Erro ao carregar dados</p>' +
      '<p class="text-[14px] font-semibold tracking-tight text-danger-soft">Inicie o servidor local com "node server.js" e abra http://localhost:8000 — abrir o HTML direto do disco bloqueia o fetch do JSON.</p></div>';
    document.getElementById('vivaGrid').innerHTML = erro;
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('locaisBody').innerHTML =
      '<tr><td colspan="7" class="px-2.5 py-3 text-[13px] text-danger-soft">Não foi possível carregar data/sinistros.json.</td></tr>';
    document.getElementById('planoCard').innerHTML = '<p class="text-[13px] text-danger-soft">Não foi possível carregar data/sinistros.json.</p>';
    document.getElementById('mapaStatus').textContent = 'Não foi possível carregar os dados do mapa.';
    return;
  }
  renderVivaKpis();
  renderKpis();
  iniciarRanking();
  iniciarPlanos();
  iniciarMapa();
  bancoPromise.then(apresentarAreasCriticas);   // depois das sugestões, para a mensagem não ficar acima delas
}

function pctFmt(v){ return v == null ? '—' : Math.round(v * 1000) / 10 + '%'; }

// Número no formato brasileiro (1.234,5); null vira travessão.
function fmt(v, casas = 0){
  return v == null || Number.isNaN(v) ? '—'
    : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}
// Compara textos pelo código dos caracteres, como o sorted() do Python nos scripts (mantém a mesma ordem de empate).
const cmpTexto = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

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
// Faixa com maior total_n em perfil_demografico.faixa_etaria ("20_a_39_anos" -> "20–39 anos").
function faixaMaisAtingida(){
  const faixas = Object.entries(dataset.perfil_demografico.faixa_etaria);
  const [chave] = faixas.reduce((a, b) => (b[1].total_n > a[1].total_n ? b : a));
  const m = chave.match(/^(\d+)_a_(\d+)_anos$/);
  if(m) return `${m[1]}–${m[2]} anos`;
  const mais = chave.match(/^(\d+)_anos_ou_mais$/);
  return mais ? `${mais[1]}+ anos` : chave.replace(/_/g, ' ');
}

function renderVivaKpis(){
  const ev = dataset.evento;
  const at = dataset.atendimento_evolucao;
  const amostra = dataset.fonte_dados_viva_2014.amostra_total;
  const cards = [
    { label: 'Motociclistas sem capacete (atendidos)', value: pctFmt(ev.uso_capacete.nao.total_pct), danger:true },
    { label: 'Envolveram consumo de álcool', value: pctFmt(ev.consumo_alcool.sim.total_pct), danger:true },
    { label: 'Evoluíram para internação hospitalar', value: pctFmt(at.evolucao.internacao_hospitalar.total_pct) },
    { label: 'Evoluíram para óbito (na amostra)', value: pctFmt(at.evolucao.obito_outros.total_pct), danger:true },
    { label: 'Faixa etária mais atingida', value: faixaMaisAtingida() },
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

/* =========================================================
   PRF: agregação das ocorrências de data/mapa_prf.json
   Cada ponto: [lat, lon, ano, br, km_trecho, mortos, feridos_graves, município].
   Mesmas regras de scripts/gerar_territorios.py (trecho = BR + janela de 5 km).
========================================================= */
const chaveTrecho = p => (p[3] === 0 || p[4] == null) ? null : p[3] + '|' + p[4];

function agregarPrf(prf, pontos, chaveDe){
  const antes = new Set(prf.janelas.antes), depois = new Set(prf.janelas.depois);
  const grupos = new Map();
  for(const p of pontos){
    const k = chaveDe(p);
    if(k == null) continue;
    let a = grupos.get(k);
    if(!a){ a = { chave: k, n: 0, m: 0, fg: 0, nAntes: 0, nDepois: 0, lat: 0, lon: 0, muns: new Map() }; grupos.set(k, a); }
    a.n++; a.m += p[5]; a.fg += p[6]; a.lat += p[0]; a.lon += p[1];
    if(antes.has(p[2])) a.nAntes++;
    if(depois.has(p[2])) a.nDepois++;
    a.muns.set(p[7], (a.muns.get(p[7]) || 0) + 1);
  }
  for(const a of grupos.values()){
    a.l = 100 * a.m / a.n;
    a.var = a.nAntes ? 100 * (a.nDepois - a.nAntes) / a.nAntes : null;
    a.lat /= a.n; a.lon /= a.n;
    // município mais frequente; no empate fica o que apareceu primeiro, como no Counter.most_common do Python
    let melhor = null, max = 0;
    for(const [mun, c] of a.muns) if(c > max){ max = c; melhor = mun; }
    a.municipio = prf.municipios[melhor];
    delete a.muns;
  }
  return [...grupos.values()];
}

function trechosPrf(prf, pontos){
  return agregarPrf(prf, pontos, chaveTrecho).map(a => {
    const [br, km] = a.chave.split('|').map(Number);
    return { ...a, br, km, nome: `BR-${br}, km ${km} a ${km + 5}` };
  });
}
const cmpTrecho = (a, b) => cmpTexto(String(a.br), String(b.br)) || a.km - b.km;

/* =========================================================
   Ranking de prioridades: regiões de saúde (SIH/SUS) e municípios e trechos das BRs (PRF).
   Clicar numa linha abre o plano de ação do território (no trecho, o do município).
========================================================= */
const TH = 'border-b border-border px-2.5 py-2 text-[11px] font-bold uppercase tracking-[0.08em] text-faint';
const TD = 'border-b border-border px-2.5 py-2.5';
const FONTE_SIH = 'SIH/SUS 2010–2023 (Bastos et al., Rev Bras Epidemiol 2026); médias e tendências por região de saúde';
const LIMITE_RANKING = 20;

function badgePrioridade(nivel, prefixo = ''){
  if(!nivel) return '<span class="text-faint">—</span>';
  const cls = nivel === 'alta' ? 'badge badge-alta' : nivel === 'média' ? 'badge badge-media' : 'badge';
  return `<span class="${cls}">${prefixo}${nivel}</span>`;
}

function planosDe(tipo){
  return ((dataset && dataset.planos_por_territorio) || {})[tipo] || {};
}
const nivelDe = (tipo, chave) => planosDe(tipo)[chave] ? planosDe(tipo)[chave].prioridade.nivel : null;

// Cada tipo: colunas (num = casas decimais; tela = HTML próprio; soCsv = só no arquivo), critérios de ordem,
// nota de fonte e o plano ligado à linha.
const RANKINGS = {
  regioes: {
    titulo: 'Regiões de saúde (SIH/SUS)',
    criterios: {
      taxa: { rotulo: 'Maior taxa de internação', coluna: 'taxa', ordem: (a, b) => b.taxa - a.taxa },
      crescimento: { rotulo: 'Maior crescimento (VPA)', coluna: 'vpa', ordem: (a, b) => b.vpa - a.vpa },
      letalidade: { rotulo: 'Pior letalidade hospitalar', coluna: 'letal', ordem: (a, b) => b.letal - a.letal }
    },
    colunas: [
      { id: 'nome', titulo: 'Região de saúde' },
      { id: 'macro', titulo: 'Macrorregião', classe: 'text-muted-foreground' },
      { id: 'taxa', titulo: 'Taxa /100 mil hab.', num: 1 },
      { id: 'vpa', titulo: 'VPA % ao ano', num: 2, tela: l => `${fmt(l.vpa, 2)} <span class="${tendenciaInfo(l.tendTaxa).cls}">${tendenciaInfo(l.tendTaxa).label}</span>` },
      { id: 'tendTaxa', titulo: 'Tendência da taxa', soCsv: true },
      { id: 'letal', titulo: 'Letalidade %', num: 1 },
      { id: 'prioridade', titulo: 'Prioridade', tela: l => badgePrioridade(l.prioridade) }
    ],
    linhas(){
      const e = dataset.estudo_morbidade_piaui_2010_2023;
      const tx = e.taxa_internacao_hospitalar_100mil_hab.por_regiao_de_saude;
      const lt = e.letalidade_hospitalar_pct.por_regiao_de_saude;
      return Object.keys(tx).map(chave => ({
        chave, nome: NOMES_REGIAO[chave] || chave, macro: MACRORREGIAO_DA_REGIAO[chave] || '—',
        taxa: tx[chave].valor, vpa: tx[chave].vpa_pct, tendTaxa: tx[chave].tendencia,
        letal: lt[chave] ? lt[chave].valor : null, prioridade: nivelDe('regioes_de_saude', chave)
      }));
    },
    nota: () => `Fonte: ${FONTE_SIH}. VPA = variação percentual anual da taxa de internação.`,
    plano: l => ({ tipo: 'regioes_de_saude', chave: l.chave })
  },
  municipios: {
    titulo: 'Municípios nas rodovias federais (PRF)',
    criterios: {
      mortos: { rotulo: 'Mais mortos', coluna: 'm', ordem: (a, b) => b.m - a.m || b.n - a.n || cmpTexto(a.nome, b.nome) },
      ocorrencias: { rotulo: 'Mais ocorrências', coluna: 'n', ordem: (a, b) => b.n - a.n || b.m - a.m || cmpTexto(a.nome, b.nome) },
      gravidade: { rotulo: 'Maior gravidade (mortos por 100)', coluna: 'l', minimo: 'municipio',
                   ordem: (a, b) => b.l - a.l || b.m - a.m || cmpTexto(a.nome, b.nome) },
      crescimento: { rotulo: 'Maior crescimento das ocorrências', coluna: 'var', minimo: 'municipio', filtro: l => l.var != null,
                     ordem: (a, b) => b.var - a.var || b.m - a.m || cmpTexto(a.nome, b.nome) }
    },
    colunas: [
      { id: 'nome', titulo: 'Município' },
      { id: 'n', titulo: 'Ocorrências', num: 0 },
      { id: 'm', titulo: 'Mortos', num: 0 },
      { id: 'l', titulo: 'Mortos /100 ocorr.', num: 1 },
      { id: 'var', titulo: 'Variação % ocorr.', num: 1, tela: l => l.var == null ? '—' : (l.var > 0 ? '+' : '') + fmt(l.var, 1) },
      { id: 'prioridade', titulo: 'Prioridade', tela: l => badgePrioridade(l.prioridade) }
    ],
    async linhas(){
      const prf = await prfPromise;
      return agregarPrf(prf, prf.pontos, p => p[7]).map(a => {
        const nome = prf.municipios[a.chave];
        return { ...a, nome, prioridade: nivelDe('municipios', nome) };
      });
    },
    nota: (c, prf) => `Fonte: ${prf.fonte}. Só rodovias federais; óbitos e internações em todas as vias estão em "Municípios — óbitos e internações". ` +
      `Variação = ocorrências de ${janelaTxt(prf.janelas.depois)} contra ${janelaTxt(prf.janelas.antes)}. ` +
      (c.minimo ? `Este critério só considera municípios com ${prf.minimos.municipio} ou mais ocorrências. ` : '') +
      'Prioridade só para municípios com plano de ação.',
    plano: l => ({ tipo: 'municipios', chave: l.nome })
  },
  trechos: {
    titulo: 'Trechos de 5 km das rodovias federais (PRF)',
    criterios: {
      mortos: { rotulo: 'Mais mortos', coluna: 'm', ordem: (a, b) => b.m - a.m || b.n - a.n || cmpTrecho(a, b) },
      ocorrencias: { rotulo: 'Mais ocorrências', coluna: 'n', ordem: (a, b) => b.n - a.n || b.m - a.m || cmpTrecho(a, b) },
      gravidade: { rotulo: 'Maior gravidade (mortos por 100)', coluna: 'l', minimo: 'trecho', ordem: (a, b) => b.l - a.l || b.m - a.m || cmpTrecho(a, b) }
    },
    colunas: [
      { id: 'nome', titulo: 'Trecho' },
      { id: 'municipio', titulo: 'Município', classe: 'text-muted-foreground' },
      { id: 'n', titulo: 'Ocorrências', num: 0 },
      { id: 'm', titulo: 'Mortos', num: 0 },
      { id: 'fg', titulo: 'Feridos graves', num: 0 },
      { id: 'l', titulo: 'Mortos /100 ocorr.', num: 1 }
    ],
    async linhas(){
      const prf = await prfPromise;
      return trechosPrf(prf, prf.pontos);
    },
    nota: (c, prf) => `Fonte: ${prf.fonte}. Trecho = BR + janela de 5 km; município é o mais frequente no trecho. ` +
      (c.minimo ? `Este critério só considera trechos com ${prf.minimos.trecho} ou mais ocorrências. ` : '') +
      'Clique num trecho para abrir o plano do município, se houver.',
    plano: l => ({ tipo: 'municipios', chave: l.municipio })
  }
};

// Óbitos (SIM) e internações (SIH) de residentes, todas as vias: os mesmos números das cores do mapa (atencao_territorial).
const ORDEM_COR = { vermelho: 0, laranja: 1, amarelo: 2 };
const badgeCor = nivel => `<span class="badge ${nivel === 'vermelho' ? 'badge-alta' : nivel === 'laranja' ? 'badge-media' : ''}">${nivel}</span>`;
const colunasSaude = primeira => [
  primeira,
  { id: 'obitos', titulo: 'Óbitos', num: 0 },
  { id: 'taxa_obitos', titulo: 'Óbitos /100 mil/ano', num: 1 },
  { id: 'internacoes', titulo: 'Internações', num: 0 },
  { id: 'taxa_internacoes', titulo: 'Intern. /100 mil/ano', num: 1 },
  { id: 'nivel', titulo: 'Mapa', tela: l => badgeCor(l.nivel) }
];
const criteriosSaude = municipal => ({
  atencao: { rotulo: 'Nível de atenção (cor do mapa)', coluna: 'nivel', ordem: (a, b) => ORDEM_COR[a.nivel] - ORDEM_COR[b.nivel] || b.taxa_obitos - a.taxa_obitos },
  taxa_obitos: { rotulo: 'Maior taxa de óbitos', coluna: 'taxa_obitos', ordem: (a, b) => b.taxa_obitos - a.taxa_obitos,
                 filtro: municipal ? l => l.obitos >= 10 : null },
  obitos: { rotulo: 'Mais óbitos', coluna: 'obitos', ordem: (a, b) => b.obitos - a.obitos || cmpTexto(a.nome, b.nome) },
  taxa_internacoes: { rotulo: 'Maior taxa de internações', coluna: 'taxa_internacoes', ordem: (a, b) => b.taxa_internacoes - a.taxa_internacoes,
                      filtro: municipal ? l => l.internacoes >= 30 : null }
});
const notaSaude = c => {
  const at = dataset.atencao_territorial;
  return `Fonte: ${at.fonte}. Óbitos e internações contados pelo município de residência, em todas as vias. ${at.metodo}` +
    (c.filtro ? ' Este critério só considera municípios com casos suficientes (10 óbitos ou 30 internações).' : '');
};
Object.assign(RANKINGS, {
  saude_regioes: {
    titulo: 'Regiões de saúde — óbitos e internações (SIM e SIH)',
    criterios: criteriosSaude(false),
    colunas: colunasSaude({ id: 'nome', titulo: 'Região de saúde' }).concat([{ id: 'pct_via_publica', titulo: '% mortes na via', num: 1 }]),
    linhas: () => Object.entries(dataset.atencao_territorial.regioes).map(([chave, r]) => ({ ...r, chave })),
    nota: notaSaude,
    plano: l => ({ tipo: 'regioes_de_saude', chave: l.chave })
  },
  saude_municipios: {
    titulo: 'Municípios — óbitos e internações (SIM e SIH)',
    criterios: criteriosSaude(true),
    colunas: (cols => { cols.splice(1, 0, { id: 'regiao', titulo: 'Região de saúde', classe: 'text-muted-foreground' }); return cols; })(colunasSaude({ id: 'nome', titulo: 'Município' })),
    linhas: () => Object.entries(dataset.atencao_territorial.municipios).map(([nome, a]) => ({ ...a, nome })),
    nota: notaSaude,
    plano: l => ({ tipo: 'municipios', chave: l.nome })
  }
});

function janelaTxt(anos){ return anos.length > 1 ? `${anos[0]}–${anos[anos.length - 1]}` : String(anos[0]); }

const rk = { tipo: 'regioes', criterio: 'taxa', linhas: [], todas: false, versao: 0, prf: null };

function preencherCriterios(){
  const sel = document.getElementById('rkCriterio');
  sel.innerHTML = Object.entries(RANKINGS[rk.tipo].criterios)
    .map(([k, c]) => `<option value="${k}">${c.rotulo}</option>`).join('');
  sel.value = rk.criterio;
}

function iniciarRanking(){
  const tipo = document.getElementById('rkTipo');
  const crit = document.getElementById('rkCriterio');
  tipo.addEventListener('change', () => {
    rk.tipo = tipo.value;
    rk.criterio = Object.keys(RANKINGS[rk.tipo].criterios)[0];
    rk.todas = false;
    preencherCriterios();
    renderRanking();
  });
  crit.addEventListener('change', () => { rk.criterio = crit.value; rk.todas = false; renderRanking(); });
  document.getElementById('rkCsv').addEventListener('click', exportarRankingCsv);
  document.getElementById('rkPdf').addEventListener('click', imprimirRanking);
  const body = document.getElementById('locaisBody');
  const abrir = tr => {
    if(tr.dataset.mais){ rk.todas = true; renderRanking(); return; }
    const alvo = RANKINGS[rk.tipo].plano(rk.linhas[tr.dataset.i]);
    abrirPlano(alvo.tipo, alvo.chave);
  };
  body.addEventListener('click', e => { const tr = e.target.closest('tr[data-i], tr[data-mais]'); if(tr) abrir(tr); });
  body.addEventListener('keydown', e => {
    const tr = e.target.closest('tr[data-i], tr[data-mais]');
    if(tr && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); abrir(tr); }
  });
  preencherCriterios();
  renderRanking();
}

async function renderRanking(){
  const def = RANKINGS[rk.tipo];
  const c = def.criterios[rk.criterio];
  const versao = ++rk.versao;   // descarta respostas atrasadas se o usuário trocar o filtro no meio da carga
  const body = document.getElementById('locaisBody');
  const ncol = def.colunas.filter(col => !col.soCsv).length + 1;
  document.getElementById('rkHead').innerHTML = `<tr><th class="w-9 ${TH}"></th>` + def.colunas.filter(col => !col.soCsv)
    .map(col => `<th class="${TH} ${col.num != null ? 'text-right' : 'text-left'}">${col.titulo}</th>`).join('') + '</tr>';
  body.innerHTML = `<tr><td colspan="${ncol}" class="px-2.5 py-3 text-[13px] text-faint">Carregando dados...</td></tr>`;
  let linhas, prf = null;
  try{
    linhas = await def.linhas();
    if(rk.tipo === 'municipios' || rk.tipo === 'trechos') prf = await prfPromise;
  }catch(err){
    if(versao !== rk.versao) return;
    body.innerHTML = `<tr><td colspan="${ncol}" class="px-2.5 py-3 text-[13px] text-danger-soft">Não foi possível carregar data/mapa_prf.json (rode scripts/gerar_territorios.py).</td></tr>`;
    return;
  }
  if(versao !== rk.versao) return;
  if(c.minimo) linhas = linhas.filter(l => l.n >= prf.minimos[c.minimo]);
  if(rk.tipo.startsWith('saude') && !dataset.atencao_territorial) linhas = [];
  if(c.filtro) linhas = linhas.filter(c.filtro);
  linhas.sort(c.ordem);
  rk.linhas = linhas;
  rk.prf = prf;
  const visiveis = rk.todas ? linhas : linhas.slice(0, LIMITE_RANKING);
  body.innerHTML = visiveis.map((l, i) => {
    const alvo = def.plano(l);
    const temPlano = !!planosDe(alvo.tipo)[alvo.chave];
    const celulas = def.colunas.filter(col => !col.soCsv).map(col => {
      const valor = col.tela ? col.tela(l) : col.num != null ? fmt(l[col.id], col.num) : escapeHtml(l[col.id] == null ? '—' : l[col.id]);
      const destaque = col.id === c.coluna ? 'cell-danger font-semibold text-danger-soft' : (col.classe || '');
      return `<td class="${TD} ${col.num != null ? 'tabular text-right' : ''} ${destaque}">${valor}</td>`;
    }).join('');
    return `
      <tr class="${temPlano ? 'rk-linha' : 'rk-sem-plano'}" data-i="${i}"${temPlano ? ' tabindex="0" title="Abrir o plano de ação"' : ''}>
        <td class="${TD}"><span class="inline-flex h-5 w-5 items-center justify-center rounded bg-panel-2 text-xs font-bold text-amber">${i + 1}</span></td>${celulas}
      </tr>`;
  }).join('') + (linhas.length > visiveis.length
    ? `<tr class="rk-linha" data-mais="1" tabindex="0"><td colspan="${ncol}" class="${TD} text-center text-amber">Mostrar todos (${linhas.length})</td></tr>`
    : '');
  if(!linhas.length) body.innerHTML = `<tr><td colspan="${ncol}" class="px-2.5 py-3 text-[13px] text-faint">Nenhum território neste critério.</td></tr>`;
  document.getElementById('rkNota').textContent = def.nota(c, prf);
}

/* Exportação: CSV (separador ";" e vírgula decimal, abre direto no Excel em português) e PDF pela impressão do navegador. */
function baixarArquivo(nome, conteudo, tipo){
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
  const a = document.createElement('a');
  a.href = url; a.download = nome;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvCampo(v){
  const s = String(v == null ? '' : v);
  return /[";\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function exportarRankingCsv(){
  const def = RANKINGS[rk.tipo];
  const cab = ['posicao', ...def.colunas.map(col => col.titulo)];
  const linhas = rk.linhas.map((l, i) => [i + 1, ...def.colunas.map(col =>
    col.num != null && l[col.id] != null ? l[col.id].toFixed(col.num).replace('.', ',') : l[col.id])]);
  const csv = '﻿' + [cab, ...linhas].map(r => r.map(csvCampo).join(';')).join('\r\n') + '\r\n';
  baixarArquivo(`ranking_${rk.tipo}_${rk.criterio}.csv`, csv, 'text/csv;charset=utf-8');
}

const CSS_IMPRESSAO = `
  body { font: 13px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1a1a1a; margin: 24px; }
  h1 { font-size: 20px; margin: 0 0 4px; } h3 { font-size: 18px; margin: 0; } h4 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; margin: 16px 0 6px; }
  .meta, .nota, .plano-fonte, .acao-meta, .plano-limites { color: #555; font-size: 11.5px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th, td { border-bottom: 1px solid #ccc; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { font-size: 10.5px; text-transform: uppercase; color: #555; } .n { text-align: right; }
  .badge { border: 1px solid #999; border-radius: 10px; padding: 0 6px; font-size: 10.5px; text-transform: uppercase; }
  .plano-topo { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  ul { padding-left: 18px; } li { margin-bottom: 4px; } .eixo { font-weight: 600; }
  .acima { font-weight: 600; } .plano-limites { border-top: 1px solid #ccc; margin-top: 16px; padding-top: 8px; }
  @page { margin: 14mm; }`;

function imprimir(titulo, corpo){
  const w = window.open('', '_blank');
  if(!w){ alert('O navegador bloqueou a janela de impressão. Permita pop-ups desta página para salvar em PDF.'); return; }
  const gerado = `Observatório de sinistros de trânsito do Piauí (Infotrânsito, UFPI) — gerado em ${new Date().toLocaleDateString('pt-BR')}`;
  w.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${escapeHtml(titulo)}</title>` +
    `<style>${CSS_IMPRESSAO}</style></head><body>${corpo}<p class="meta">${gerado}</p>` +
    '<script>window.onload = () => { window.focus(); window.print(); };<\/script></body></html>');
  w.document.close();
}

function imprimirRanking(){
  const def = RANKINGS[rk.tipo];
  const c = def.criterios[rk.criterio];
  const cols = def.colunas.filter(col => !col.soCsv);
  const linhas = rk.linhas.map((l, i) => '<tr><td>' + (i + 1) + '</td>' + cols.map(col => {
    const v = col.id === 'prioridade' ? (l.prioridade || '—') : col.id === 'nivel' ? l.nivel : col.id === 'vpa' ? `${fmt(l.vpa, 2)} (${tendenciaInfo(l.tendTaxa).label})`
      : col.num != null ? fmt(l[col.id], col.num) : escapeHtml(l[col.id] == null ? '—' : l[col.id]);
    return `<td class="${col.num != null ? 'n' : ''}">${v}</td>`;
  }).join('') + '</tr>').join('');
  imprimir(`Ranking — ${def.titulo}`,
    `<h1>Ranking de prioridades — ${escapeHtml(def.titulo)}</h1><p class="meta">Ordenado por: ${escapeHtml(c.rotulo)} · ${rk.linhas.length} territórios</p>` +
    `<table><thead><tr><th>#</th>${cols.map(col => `<th class="${col.num != null ? 'n' : ''}">${col.titulo}</th>`).join('')}</tr></thead><tbody>${linhas}</tbody></table>` +
    `<p class="nota">${escapeHtml(def.nota(c, rk.prf))}</p>`);
}

/* =========================================================
   Plano de ação por território (planos_por_territorio, gerado por scripts/gerar_territorios.py)
========================================================= */
const NIVEIS = ['alta', 'média', 'monitorar'];
const ORDEM_EIXOS = ['fiscalização', 'engenharia', 'educação e comunicação', 'atendimento às vítimas', 'articulação', 'dados e gestão'];
let planoAtual = null;

function preencherTerritorios(tipo, selecionado){
  const planos = planosDe(tipo);
  const sel = document.getElementById('plTerritorio');
  sel.innerHTML = NIVEIS.map(n => {
    const itens = Object.entries(planos).filter(([, p]) => p.prioridade.nivel === n);
    return itens.length
      ? `<optgroup label="Prioridade ${n}">${itens.map(([k, p]) => `<option value="${escapeHtml(k)}">${escapeHtml(p.nome)}</option>`).join('')}</optgroup>`
      : '';
  }).join('');
  if(selecionado && planos[selecionado]) sel.value = selecionado;
}

function iniciarPlanos(){
  const card = document.getElementById('planoCard');
  if(!dataset.planos_por_territorio){
    card.innerHTML = '<p class="text-[13px] text-faint">Os planos por território ainda não foram gerados. Rode python scripts/gerar_territorios.py.</p>';
    return;
  }
  const tipo = document.getElementById('plTipo');
  tipo.addEventListener('change', () => { preencherTerritorios(tipo.value); renderPlano(); });
  document.getElementById('plTerritorio').addEventListener('change', renderPlano);
  document.getElementById('plChat').addEventListener('click', discutirNoChat);
  document.getElementById('plPdf').addEventListener('click', () => {
    if(planoAtual) imprimir(`Plano de ação — ${planoAtual.p.nome}`, htmlDoPlano(planoAtual.p, planoAtual.tipo));
  });
  preencherTerritorios(tipo.value);
  renderPlano();
}

// Abre o plano de um território (vindo do ranking ou do mapa); devolve false se ele não tem plano.
function abrirPlano(tipo, chave){
  if(!planosDe(tipo)[chave]) return false;
  document.getElementById('plTipo').value = tipo;
  preencherTerritorios(tipo, chave);
  renderPlano();
  document.getElementById('planoSec').scrollIntoView({ behavior: 'smooth', block: 'start' });
  return true;
}

function renderPlano(){
  const tipo = document.getElementById('plTipo').value;
  const chave = document.getElementById('plTerritorio').value;
  const p = planosDe(tipo)[chave];
  const card = document.getElementById('planoCard');
  if(!p){ card.innerHTML = '<p class="text-[13px] text-faint">Nenhum plano para este território.</p>'; planoAtual = null; return; }
  planoAtual = { tipo, chave, p };
  card.innerHTML = htmlDoPlano(p, tipo);
}

function htmlDoPlano(p, tipo){
  const pt = dataset.planos_por_territorio;
  const e = escapeHtml;
  const bloco = (titulo, html) => `<div class="plano-bloco"><h4>${titulo}</h4>${html}</div>`;
  const lista = itens => `<ul>${itens.join('')}</ul>`;
  const acoes = [...p.acoes].sort((a, b) => ORDEM_EIXOS.indexOf(a.eixo) - ORDEM_EIXOS.indexOf(b.eixo));
  const fatores = p.fatores ? bloco('Fatores comparados com a média do estado',
    '<div class="overflow-x-auto"><table class="fatores"><thead><tr><th>Fator</th><th class="n">No território</th><th class="n">Estado</th><th class="n">Mortos</th><th>Situação</th></tr></thead><tbody>' +
    p.fatores.map(f => {
      const cls = f.situacao.startsWith('acima') ? 'acima' : f.situacao.startsWith('abaixo') ? 'abaixo' : 'text-muted-foreground';
      return `<tr><td>${e(f.fator)}</td><td class="n">${fmt(f.pct_acidentes, 1)}%</td><td class="n">${fmt(pt.fatores_media_estado_pct[f.fator], 1)}%</td>` +
        `<td class="n">${fmt(f.mortos)}</td><td class="${cls}">${e(f.situacao)}</td></tr>`;
    }).join('') + `</tbody></table></div><p class="nota">${e(pt.regra_dos_fatores)}</p>`) : '';
  const locais = p.locais_prioritarios && p.locais_prioritarios.length
    ? bloco('Trechos prioritários', lista(p.locais_prioritarios.map(t => `<li>${e(t)}</li>`))) : '';
  const at = dataset.atencao_territorial;
  const limites = (tipo === 'regioes_de_saude' ? pt.limites.regioes_de_saude : p.fatores ? pt.limites.prf : '') + (p.atencao && at ? ' ' + at.limites : '');
  const chavesPacote = (p.atencao && p.atencao.pacote && p.atencao.pacote.length ? p.atencao.pacote : p.pacote) || [];
  const pacote = chavesPacote.length && at ? bloco('Medidas para áreas em vermelho e laranja', lista(chavesPacote.map(k => {
    const m = at.pacote_de_medidas[k];
    return `<li><span class="eixo">[${e(m.titulo.toLowerCase())}]</span> ${e(m.acoes.join(' '))}<span class="acao-meta">${e(at.pacote_de_medidas.origem)} · quem executa: ${e(m.quem.join(', '))}</span></li>`;
  })) + (chavesPacote.includes('gestao_velocidade') ? `<p class="nota">${e(at.pacote_de_medidas.gestao_velocidade.observacao)}</p>` : '')) : '';
  const mapaCor = p.atencao ? `<p class="text-[13px]">Mapa (${e(at ? at.periodo.replace('-', '–') : '')}): ${badgeCor(p.atencao.nivel)} ${e(p.atencao.rotulo)}` +
    (p.atencao.nivel !== 'amarelo' ? ` · onde agir primeiro: ${e(p.atencao.onde_agir)}` : '') + '</p>' : '';
  const viaVermelha = p.municipios_em_vermelho_no_trajeto
    ? `<p class="text-[13px]">Municípios em vermelho no trajeto: ${e(p.municipios_em_vermelho_no_trajeto.join(', '))}.</p>` : '';
  return `
    <div class="plano-topo">
      <h3>${e(p.nome)}</h3>${badgePrioridade(p.prioridade.nivel, 'prioridade ')}
      <span class="text-[13px] text-muted-foreground">${e(p.tipo)}${p.macrorregiao ? ' · macrorregião ' + e(p.macrorregiao) : ''}</span>
    </div>
    <p class="plano-fonte">Fonte: ${e(p.fonte)}</p>
    <ul class="plano-motivos">${p.prioridade.motivos.map(m => `<li>${e(m)}</li>`).join('')}</ul>
    ${mapaCor}${viaVermelha}
    <div class="plano-grid">
      <div>${bloco('Diagnóstico', `<p>${e(p.diagnostico)}</p>`)}${fatores}${locais}</div>
      <div>
        ${acoes.length ? bloco('Ações propostas', lista(acoes.map(a =>
          `<li><span class="eixo">[${e(a.eixo)}]</span> ${e(a.acao)}<span class="acao-meta">${e(a.origem)} · por quê: ${e(a.por_que)}</span></li>`))) : ''}
        ${pacote}
        ${bloco('Metas', lista(p.metas.map(m => `<li>${e(m.meta)}<span class="acao-meta">${e(m.origem)}</span></li>`)))}
        ${bloco('Indicadores para acompanhar', `<p>${p.indicadores.map(e).join('; ')}.</p>`)}
        ${bloco('Quem envolver', `<p>${p.quem_envolver.map(e).join(', ')}.</p>`)}
      </div>
    </div>
    <p class="plano-limites">${e(limites)} Origem das ações: "proposta técnica" = ${e(pt.origens['proposta técnica'])}; "recomendação dos autores" = ${e(pt.origens['recomendação dos autores'])}. Metas da ONU: ${e(pt.origens['referência: meta da ONU para 2030'])}.</p>`;
}

function discutirNoChat(){
  if(!planoAtual) return;
  const input = document.getElementById('askInput');
  input.value = `Quais ações do plano de ${planoAtual.p.nome} priorizar primeiro e por quê?`;
  input.scrollIntoView({ behavior: 'smooth', block: 'center' });
  input.focus({ preventScroll: true });
}

/* =========================================================
   Mapa interativo em <canvas>, sem bibliotecas externas
   Municípios (IBGE, data/malha_pi.json) coloridos por óbitos e internações (atencao_territorial: SIM e SIH),
   rodovias federais e estaduais (OpenStreetMap, data/vias_pi.json) e ocorrências da PRF (data/mapa_prf.json).
   Roda do mouse, botões ou dois dedos aproximam; arrastar move. Clicar numa área ou rodovia sugere um plano no chat.
========================================================= */
const viasPromise = fetchJson('data/vias_pi.json');
viasPromise.catch(() => {});
const TOP_TRECHOS_MAPA = 10;
const ZOOM_MAX = 14;
const COR_ATENCAO = ['vermelho', 'laranja', 'amarelo'];
const QUEBRAS_RAZAO = [0.8, 1, 1.2, 1.5];   // taxa da área dividida pela do estado
const mapa = {
  prf: null, malha: null, vias: null, at: null,
  filtro: { ano: 'todos', br: 'todas', exibir: 'todas', criterio: 'm', cor: 'atencao', area: 'regioes',
            federais: true, estaduais: true, trechos: true, pontos: false },
  limites: null, geo: null, dpr: 1, largura: 0, vista: { z: 1, x: 0, y: 0 },
  muns: [], linhas: [], rotulosVia: [], cores: null, preenchimento: [], quebrasObitos: null, regiaoPorNome: {},
  filtrados: [], porMunicipio: new Map(), trechos: [], rotulos: [], hover: null, ativo: null, quadro: 0
};

// O canvas de navegadores mais antigos não entende oklch(): nesse caso usa um equivalente aproximado em hex.
function coresDoTema(){
  const css = getComputedStyle(document.documentElement);
  const teste = document.createElement('canvas').getContext('2d');
  const cor = (nome, reserva) => {
    const valor = css.getPropertyValue(nome).trim();
    teste.fillStyle = '#010203';
    teste.fillStyle = valor;
    return valor && teste.fillStyle !== '#010203' ? valor : reserva;
  };
  return {
    municipio: cor('--panel-2', '#2b2f35'), limite: cor('--faint', '#757b84'), painel: cor('--panel', '#25282d'),
    fundo: cor('--background', '#1e2125'), texto: cor('--foreground', '#ebe6da'),
    ponto: cor('--amber-dim', '#8f6c2e'), fatal: cor('--danger', '#c0583f'), amber: cor('--amber', '#eaa93f'),
    escala: ['--mapa-1', '--mapa-2', '--mapa-3', '--mapa-4', '--mapa-5'].map((v, i) => cor(v, ['#363c45', '#6b6a3f', '#a8874a', '#c06a3e', '#b84434'][i])),
    vermelho: cor('--atencao-vermelho', '#b84434'), laranja: cor('--atencao-laranja', '#d08a43'), amarelo: cor('--atencao-amarelo', '#76704a'),
    federal: cor('--via-federal', '#f1cf72'), estadual: cor('--via-estadual', '#dcdfe4')
  };
}

async function iniciarMapa(){
  const status = document.getElementById('mapaStatus');
  try{
    [mapa.prf, mapa.malha, mapa.vias] = await Promise.all([prfPromise, malhaPromise, viasPromise]);
  }catch(err){
    status.textContent = 'Não foi possível carregar o mapa (data/mapa_prf.json, data/malha_pi.json, data/vias_pi.json). ' +
      'Rode python scripts/importar_saude_vias.py e python scripts/gerar_territorios.py.';
    return;
  }
  mapa.at = dataset.atencao_territorial || null;
  status.remove();
  mapa.cores = coresDoTema();
  if(mapa.at) for(const [k, r] of Object.entries(mapa.at.regioes)) mapa.regiaoPorNome[r.nome] = k;

  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for(const m of mapa.malha.municipios) for(const anel of m.aneis) for(let i = 0; i < anel.length; i += 2){
    minLon = Math.min(minLon, anel[i]); maxLon = Math.max(maxLon, anel[i]);
    minLat = Math.min(minLat, anel[i + 1]); maxLat = Math.max(maxLat, anel[i + 1]);
  }
  mapa.limites = { minLon, maxLon, minLat, maxLat, k: Math.cos((minLat + maxLat) / 2 * Math.PI / 180) };
  mapa.muns = mapa.malha.municipios.map(m => {
    const a = mapa.at ? mapa.at.municipios[m.nome] || null : null;
    return { nome: m.nome, aneis: m.aneis, a, regiao: a ? mapa.regiaoPorNome[a.regiao] : null };
  });
  for(const [ref, r] of Object.entries(mapa.vias.rodovias)){
    for(const l of r.linhas) mapa.linhas.push({ ref, tipo: r.tipo, s: l.s, c: l.c });
  }

  // controles das camadas de saúde e das rodovias
  const ligar = (id, fn) => document.getElementById(id).addEventListener('change', fn);
  ligar('mapaCor', e => { mapa.filtro.cor = e.target.value; colorirAreas(); desenharMapa(); });
  ligar('mapaArea', e => { mapa.filtro.area = e.target.value; colorirAreas(); renderFocos(); desenharMapa(); });
  for(const [id, campo] of [['lyFederais', 'federais'], ['lyEstaduais', 'estaduais'], ['lyTrechos', 'trechos'], ['lyPontos', 'pontos']]){
    ligar(id, e => { mapa.filtro[campo] = e.target.checked; desenharMapa(); });
  }
  // controles da PRF (ano, BR, ocorrências e critério dos trechos)
  const prf = mapa.prf;
  document.getElementById('mapaAno').innerHTML = `<option value="todos">${janelaTxt(prf.anos)}</option>` +
    prf.anos.map(a => `<option value="${a}">${a}${a === prf.ano_parcial ? ' (parcial)' : ''}</option>`).join('');
  const porBr = new Map();
  for(const p of prf.pontos) porBr.set(p[3], (porBr.get(p[3]) || 0) + 1);
  document.getElementById('mapaBr').innerHTML = '<option value="todas">todas</option>' +
    [...porBr].sort((a, b) => b[1] - a[1])
      .map(([br, n]) => `<option value="${br}">${br ? 'BR-' + br : 'sem BR identificada'} (${fmt(n)})</option>`).join('');
  for(const [id, campo] of [['mapaAno', 'ano'], ['mapaBr', 'br'], ['mapaExibir', 'exibir'], ['mapaCriterio', 'criterio']]){
    ligar(id, e => { mapa.filtro[campo] = e.target.value; mapa.ativo = null; atualizarPrf(); });
  }
  document.getElementById('mapaTrechos').addEventListener('click', e => {
    const b = e.target.closest('button[data-i]');
    if(b) ativarTrecho(Number(b.dataset.i));
  });
  document.getElementById('mapaFocos').addEventListener('click', e => {
    const b = e.target.closest('button[data-chave]');
    if(!b) return;
    enquadrarArea(b.dataset.tipo, b.dataset.chave);
    sugerirNoChat(b.dataset.tipo, b.dataset.chave);
  });
  document.getElementById('zoomMais').addEventListener('click', () => zoomEm(mapa.geo.W / 2, mapa.geo.H / 2, 1.6));
  document.getElementById('zoomMenos').addEventListener('click', () => zoomEm(mapa.geo.W / 2, mapa.geo.H / 2, 1 / 1.6));
  document.getElementById('zoomInicio').addEventListener('click', () => { mapa.vista = { z: 1, x: 0, y: 0 }; aplicarVista(); });
  if(mapa.at){
    document.getElementById('mapaFonte').textContent = `Cores: ${mapa.at.fonte}. ${mapa.at.metodo} ${mapa.at.limites}`;
  }
  ligarGestos(document.getElementById('mapaCanvas'));
  new ResizeObserver(() => requestAnimationFrame(() => {
    const canvas = document.getElementById('mapaCanvas');
    if(canvas.clientWidth && canvas.clientWidth !== mapa.largura){ projetarMapa(); desenharMapa(); }
  })).observe(document.getElementById('mapaWrap'));
  projetarMapa();
  colorirAreas();
  renderFocos();
  atualizarPrf();
}

// Projeção equiretangular com correção de longitude pela latitude média (suficiente na escala de um estado).
// Os caminhos ficam em "coordenadas base" (zoom 1); zoom e arrasto só mudam a transformação do desenho.
function projetarMapa(){
  const canvas = document.getElementById('mapaCanvas');
  const L = mapa.limites;
  const larguraGeo = (L.maxLon - L.minLon) * L.k, alturaGeo = L.maxLat - L.minLat;
  const W = canvas.clientWidth;
  const H = Math.min(Math.round(W * alturaGeo / larguraGeo), 720);
  const pad = 6;
  const s = Math.min((W - 2 * pad) / larguraGeo, (H - 2 * pad) / alturaGeo);
  const ox = (W - larguraGeo * s) / 2, oy = (H - alturaGeo * s) / 2;
  const g = mapa.geo = { W, H, x: lon => ox + (lon - L.minLon) * L.k * s, y: lat => oy + (L.maxLat - lat) * s };
  mapa.largura = W;
  mapa.dpr = window.devicePixelRatio || 1;
  mapa.vista = { z: 1, x: 0, y: 0 };
  canvas.style.touchAction = 'pan-y';
  canvas.style.height = H + 'px';
  canvas.width = Math.round(W * mapa.dpr);
  canvas.height = Math.round(H * mapa.dpr);
  for(const m of mapa.muns){
    m.path = new Path2D();
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, sx = 0, sy = 0, n = 0;
    m.aneis.forEach((anel, j) => {
      for(let i = 0; i < anel.length; i += 2){
        const X = g.x(anel[i]), Y = g.y(anel[i + 1]);
        if(i) m.path.lineTo(X, Y); else m.path.moveTo(X, Y);
        x0 = Math.min(x0, X); x1 = Math.max(x1, X); y0 = Math.min(y0, Y); y1 = Math.max(y1, Y);
        if(j === 0){ sx += X; sy += Y; n++; }
      }
      m.path.closePath();
    });
    Object.assign(m, { caixa: [x0, y0, x1, y1], cx: sx / n, cy: sy / n });
  }
  const maisLonga = {};
  for(const l of mapa.linhas){
    l.xy = new Float32Array(l.c.length);
    l.path = new Path2D();
    for(let i = 0; i < l.c.length; i += 2){
      const X = l.xy[i] = g.x(l.c[i]), Y = l.xy[i + 1] = g.y(l.c[i + 1]);
      if(i) l.path.lineTo(X, Y); else l.path.moveTo(X, Y);
    }
    if(!maisLonga[l.ref] || l.c.length > maisLonga[l.ref].c.length) maisLonga[l.ref] = l;
  }
  // rótulo de cada rodovia no meio da sua linha mais longa
  mapa.rotulosVia = Object.values(maisLonga).map(l => {
    const i = Math.floor(l.c.length / 4) * 2;
    return { ref: l.ref.split('/')[0], tipo: l.tipo, x: l.xy[i], y: l.xy[i + 1] };
  });
}

/* ---------- cores das áreas */
function valorDaArea(m){
  const f = mapa.filtro, at = mapa.at;
  if(!at || !m.a) return null;
  const a = f.area === 'regioes' ? at.regioes[m.regiao] : m.a;
  return { a, chave: f.area === 'regioes' ? m.regiao : m.nome };
}

function quebrasQuantis(valores){
  const v = [...valores].sort((x, y) => x - y);
  const q = [0.2, 0.4, 0.6, 0.8].map(p => Math.round(v[Math.min(v.length - 1, Math.floor(p * v.length))]));
  for(let i = 0; i < q.length; i++) q[i] = Math.max(q[i], i ? q[i - 1] + 1 : 1);   // faixas sempre crescentes
  return q;
}

function colorirAreas(){
  const f = mapa.filtro, c = mapa.cores, at = mapa.at;
  if(!at){ mapa.preenchimento = mapa.muns.map(() => c.municipio); renderLegenda(); return; }
  const fontes = f.area === 'regioes' ? Object.values(at.regioes) : Object.values(at.municipios);
  mapa.quebrasObitos = quebrasQuantis(fontes.map(a => a.obitos));
  const classe = (v, quebras) => quebras.findIndex(q => v < q) === -1 ? 4 : quebras.findIndex(q => v < q);
  mapa.preenchimento = mapa.muns.map(m => {
    const va = valorDaArea(m);
    if(!va) return c.municipio;
    const a = va.a, municipal = f.area === 'municipios';
    if(f.cor === 'atencao') return c[a.nivel];
    if(f.cor === 'obitos') return c.escala[classe(a.obitos, mapa.quebrasObitos)];
    if(f.cor === 'taxa_obitos'){
      if(municipal && a.obitos < 10) return c.municipio;
      return c.escala[classe(a.taxa_obitos / at.estado.taxa_obitos, QUEBRAS_RAZAO)];
    }
    if(municipal && a.internacoes < 30) return c.municipio;
    return c.escala[classe(a.taxa_internacoes / at.estado.taxa_internacoes, QUEBRAS_RAZAO)];
  });
  renderLegenda();
}

function renderLegenda(){
  const f = mapa.filtro, c = mapa.cores, at = mapa.at, el = document.getElementById('mapaLegenda');
  if(!at){ el.innerHTML = '<span class="text-faint">Sem dados de óbitos e internações (rode scripts/importar_saude_vias.py).</span>'; return; }
  const item = (cor, txt) => `<span class="item"><i style="background:${cor}"></i>${txt}</span>`;
  const periodo = at.periodo.replace('-', '–');
  let html;
  if(f.cor === 'atencao'){
    html = `<span class="titulo">Nível de atenção (${periodo})</span>` +
      item(c.vermelho, 'vermelho: atenção máxima') + item(c.laranja, 'laranja: atenção alta') + item(c.amarelo, 'amarelo: abaixo da média do estado');
  }else if(f.cor === 'obitos'){
    const q = mapa.quebrasObitos;
    const faixas = [`menos de ${fmt(q[0])}`, `${fmt(q[0])} a ${fmt(q[1] - 1)}`, `${fmt(q[1])} a ${fmt(q[2] - 1)}`, `${fmt(q[2])} a ${fmt(q[3] - 1)}`, `${fmt(q[3])} ou mais`];
    html = `<span class="titulo">Óbitos de residentes, ${periodo}</span>` + faixas.map((t, i) => item(c.escala[i], t)).join('');
  }else{
    const ob = f.cor === 'taxa_obitos';
    const ref = ob ? at.estado.taxa_obitos : at.estado.taxa_internacoes;
    const faixas = ['menos de 0,8× o estado', '0,8× a 1×', '1× a 1,2×', '1,2× a 1,5×', '1,5× ou mais'];
    html = `<span class="titulo">${ob ? 'Óbitos' : 'Internações'} por 100 mil hab./ano (estado: ${fmt(ref, 1)})</span>` +
      faixas.map((t, i) => item(c.escala[i], t)).join('') +
      (f.area === 'municipios' ? item(c.municipio, ob ? 'menos de 10 óbitos (taxa instável)' : 'menos de 30 internações') : '');
  }
  el.innerHTML = html;
}

function renderFocos(){
  const el = document.getElementById('mapaFocos'), at = mapa.at;
  if(!at){ el.innerHTML = ''; return; }
  const btn = (tipo, chave, rotulo) => `<button type="button" data-tipo="${tipo}" data-chave="${escapeHtml(chave)}" title="Ver no mapa e receber o plano no chat">${escapeHtml(rotulo)}</button>`;
  el.innerHTML = mapa.filtro.area === 'regioes'
    ? Object.entries(at.regioes).filter(([, r]) => r.nivel === 'vermelho').map(([k, r]) => btn('regiao', k, r.nome)).join('')
    : at.prioritarios.municipios_vermelhos_com_mais_obitos.slice(0, 12).map(x => btn('municipio', x.municipio, x.municipio)).join('');
}

/* ---------- PRF: filtros, trechos e resumo */
function atualizarPrf(){
  const prf = mapa.prf, f = mapa.filtro;
  mapa.filtrados = prf.pontos.filter(p => (f.ano === 'todos' || p[2] === Number(f.ano)) && (f.br === 'todas' || p[3] === Number(f.br)));
  mapa.porMunicipio = new Map(agregarPrf(prf, mapa.filtrados, p => p[7]).map(a => [prf.municipios[a.chave], a]));
  mapa.trechos = trechosPrf(prf, mapa.filtrados)
    .sort(f.criterio === 'm' ? RANKINGS.trechos.criterios.mortos.ordem : RANKINGS.trechos.criterios.ocorrencias.ordem)
    .slice(0, TOP_TRECHOS_MAPA);
  desenharMapa();
  const n = mapa.filtrados.length, m = mapa.filtrados.reduce((s, p) => s + p[5], 0);
  const recorte = (f.ano === 'todos' ? ` de ${janelaTxt(prf.anos)}` : ` em ${f.ano}${Number(f.ano) === prf.ano_parcial ? ' (ano parcial)' : ''}`) +
    (f.br === 'todas' ? '' : f.br === '0' ? ', sem BR identificada' : ` na BR-${f.br}`);
  document.getElementById('mapaResumo').textContent = `${fmt(n)} ocorrências e ${fmt(m)} mortos${recorte}` +
    (n ? ` (${fmt(100 * m / n, 1)} mortos por 100 ocorrências).` : '.') + ` Fonte: ${prf.fonte}.`;
  document.getElementById('mapaTrechos').innerHTML = mapa.trechos.map((t, i) => `
    <li><button type="button" data-i="${i}" class="${mapa.ativo === i ? 'ativo' : ''}">
      <span class="num-badge">${i + 1}</span>
      <span>${t.nome}<span class="sub">${escapeHtml(t.municipio)} · ${f.criterio === 'm' ? fmt(t.n) + ' ocorrências' : fmt(t.m) + ' mortos'}</span></span>
      <span class="valor">${f.criterio === 'm' ? fmt(t.m) + ' mortos' : fmt(t.n) + ' ocorr.'}</span>
    </button></li>`).join('') || '<li class="text-[13px] text-faint">Nenhum trecho com ocorrências neste filtro.</li>';
}

/* ---------- desenho */
const paraTela = (bx, by) => [bx * mapa.vista.z + mapa.vista.x, by * mapa.vista.z + mapa.vista.y];

function desenharMapa(){
  if(mapa.quadro) return;   // agrupa vários pedidos no mesmo quadro de animação
  mapa.quadro = requestAnimationFrame(() => { mapa.quadro = 0; desenharAgora(); });
}

function desenharAgora(){
  const canvas = document.getElementById('mapaCanvas');
  if(!mapa.geo) return;
  const ctx = canvas.getContext('2d'), c = mapa.cores, f = mapa.filtro, { z, x, y } = mapa.vista, dpr = mapa.dpr, g = mapa.geo;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(dpr * z, 0, 0, dpr * z, dpr * x, dpr * y);

  // 1. áreas coloridas e limites (em "regiões", os limites municipais ficam bem fracos)
  mapa.muns.forEach((m, i) => { ctx.fillStyle = mapa.preenchimento[i]; ctx.fill(m.path, 'evenodd'); });
  ctx.lineWidth = 0.7 / z;
  ctx.strokeStyle = c.fundo;
  ctx.globalAlpha = f.area === 'regioes' ? 0.25 : 0.7;
  for(const m of mapa.muns) ctx.stroke(m.path);
  ctx.globalAlpha = 1;
  const h = mapa.hover;
  if(h && h.tipo === 'area'){
    ctx.lineWidth = 2 / z; ctx.strokeStyle = c.amber;
    for(const m of mapa.muns) if(f.area === 'regioes' ? m.regiao === h.chave : m.nome === h.chave) ctx.stroke(m.path);
  }

  // 2. rodovias: contorno escuro e linha clara; estaduais finas (tracejadas quando não pavimentadas), federais grossas
  const fatorTela = Math.min(1, Math.max(0.55, g.W / 750));   // mapa estreito (celular): linhas mais finas
  const larg = k => k * fatorTela * Math.min(1 + 0.25 * (z - 1), 3) / z;
  const tracar = (tipo, cor, largura) => {
    for(const passo of ['contorno', 'linha']){
      for(const l of mapa.linhas){
        if(l.tipo !== tipo) continue;
        ctx.strokeStyle = passo === 'contorno' ? c.fundo : (h && h.tipo === 'via' && h.ref === l.ref ? c.amber : cor);
        ctx.lineWidth = larg(passo === 'contorno' ? largura + 1.6 : largura);
        ctx.globalAlpha = passo === 'contorno' ? 0.55 : 0.95;
        ctx.setLineDash(passo === 'linha' && l.s === 'n' ? [4 / z, 3 / z] : []);
        ctx.stroke(l.path);
      }
    }
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  };
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  if(f.estaduais) tracar('estadual', c.estadual, 0.9);
  if(f.federais) tracar('federal', c.federal, 2);

  // 3. ocorrências da PRF
  if(f.pontos){
    const r = 1.4 / z;
    if(f.exibir === 'todas'){
      ctx.globalAlpha = 0.5; ctx.fillStyle = c.ponto; ctx.beginPath();
      for(const p of mapa.filtrados) if(!p[5]){ const X = g.x(p[1]), Y = g.y(p[0]); ctx.moveTo(X + r, Y); ctx.arc(X, Y, r, 0, 2 * Math.PI); }
      ctx.fill();
    }
    ctx.globalAlpha = 0.8; ctx.fillStyle = c.fatal;
    for(const p of mapa.filtrados) if(p[5]){ ctx.beginPath(); ctx.arc(g.x(p[1]), g.y(p[0]), (1.8 + 1.1 * Math.sqrt(p[5])) / z, 0, 2 * Math.PI); ctx.fill(); }
    ctx.globalAlpha = 1;
  }

  // 4. rótulos na tela (sem zoom): rodovias e municípios conforme a aproximação, e trechos críticos
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const dentro = (X, Y) => X > -20 && Y > -20 && X < g.W + 20 && Y < g.H + 20;
  const halo = (txt, X, Y, cor, fonte) => {
    ctx.font = fonte; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineWidth = 3; ctx.strokeStyle = c.fundo; ctx.strokeText(txt, X, Y);
    ctx.fillStyle = cor; ctx.fillText(txt, X, Y);
  };
  // um rótulo só entra se não encostar nos já desenhados (rodovias federais primeiro, depois municípios em vermelho)
  const ocupados = [];
  const rotular = (txt, X, Y, cor, fonte) => {
    ctx.font = fonte;
    const w = ctx.measureText(txt).width / 2 + 3, hh = 8;
    if(!dentro(X, Y) || ocupados.some(o => Math.abs(o[0] - X) < o[2] + w && Math.abs(o[1] - Y) < hh * 2)) return;
    ocupados.push([X, Y, w]);
    halo(txt, X, Y, cor, fonte);
  };
  if(z >= 1.6){
    for(const r of mapa.rotulosVia){
      if((r.tipo === 'federal' && !f.federais) || (r.tipo === 'estadual' && (!f.estaduais || z < 3))) continue;
      const [X, Y] = paraTela(r.x, r.y);
      rotular(r.ref, X, Y, r.tipo === 'federal' ? c.federal : c.estadual, `700 ${r.tipo === 'federal' ? 11 : 10}px system-ui, sans-serif`);
    }
  }
  if(z >= 2.2){
    const ordem = [...mapa.muns].sort((a, b) => ((b.a && b.a.nivel === 'vermelho') - (a.a && a.a.nivel === 'vermelho')) || ((b.a ? b.a.obitos : 0) - (a.a ? a.a.obitos : 0)));
    for(const m of ordem){
      const verm = m.a && m.a.nivel === 'vermelho';
      if(z < 3.5 && !verm) continue;
      const [X, Y] = paraTela(m.cx, m.cy);
      rotular(m.nome, X, Y, verm ? '#fff' : c.texto, `${verm ? 600 : 400} 11px system-ui, sans-serif`);
    }
  }
  mapa.rotulos = [];
  if(f.trechos){
    posicionarRotulos();
    mapa.trechos.forEach((t, i) => { if(mapa.rotulos[i].visivel) desenharTrecho(ctx, i, (h && h.tipo === 'trecho' ? h.i : mapa.ativo) === i); });
  }
}

// Trechos vizinhos se sobrepõem: afasta o número em espiral (na tela) e liga ao ponto com uma linha.
function posicionarRotulos(){
  const g = mapa.geo;
  mapa.rotulos = [];
  for(const t of mapa.trechos){
    const [x0, y0] = paraTela(g.x(t.lon), g.y(t.lat));
    if(x0 < 0 || y0 < 0 || x0 > g.W || y0 > g.H){ mapa.rotulos.push({ x: -99, y: -99, x0, y0, visivel: false }); continue; }   // fora da vista
    let x = x0, y = y0;
    for(let k = 1; k < 80 && mapa.rotulos.some(r => r.visivel && Math.hypot(r.x - x, r.y - y) < 21); k++){
      const r = 16 + 2.2 * k, ang = k * 0.8;
      x = Math.min(Math.max(x0 + r * Math.cos(ang), 11), g.W - 11);
      y = Math.min(Math.max(y0 + r * Math.sin(ang), 11), g.H - 11);
    }
    mapa.rotulos.push({ x, y, x0, y0, visivel: true });
  }
}

function desenharTrecho(ctx, i, destaque){
  const c = mapa.cores, r = mapa.rotulos[i];
  if(Math.hypot(r.x - r.x0, r.y - r.y0) > 1){
    ctx.strokeStyle = c.amber; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(r.x0, r.y0); ctx.lineTo(r.x, r.y); ctx.stroke();
    ctx.fillStyle = c.amber;
    ctx.beginPath(); ctx.arc(r.x0, r.y0, 2, 0, 2 * Math.PI); ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(r.x, r.y, destaque ? 11 : 9, 0, 2 * Math.PI);
  ctx.fillStyle = c.painel; ctx.fill();
  ctx.lineWidth = destaque ? 3 : 2; ctx.strokeStyle = c.amber; ctx.stroke();
  ctx.fillStyle = c.amber;
  ctx.font = '700 10px system-ui, sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(String(i + 1), r.x, r.y + 0.5);
}

/* ---------- zoom e arrasto */
function limitarVista(){
  const v = mapa.vista, g = mapa.geo;
  v.z = Math.min(Math.max(v.z, 1), ZOOM_MAX);
  v.x = Math.min(0, Math.max(g.W - g.W * v.z, v.x));
  v.y = Math.min(0, Math.max(g.H - g.H * v.z, v.y));
}

function aplicarVista(){
  limitarVista();
  // sem zoom, arrastar na vertical rola a página (celular); com zoom, arrastar move o mapa
  document.getElementById('mapaCanvas').style.touchAction = mapa.vista.z > 1 ? 'none' : 'pan-y';
  esconderDica();
  desenharMapa();
}

function zoomEm(px, py, fator){
  const v = mapa.vista;
  const z1 = Math.min(Math.max(v.z * fator, 1), ZOOM_MAX);
  v.x = px - (px - v.x) * (z1 / v.z);
  v.y = py - (py - v.y) * (z1 / v.z);
  v.z = z1;
  aplicarVista();
}

function enquadrarArea(tipo, chave){
  const ms = mapa.muns.filter(m => tipo === 'regiao' ? m.regiao === chave : m.nome === chave);
  if(!ms.length) return;
  const x0 = Math.min(...ms.map(m => m.caixa[0])), y0 = Math.min(...ms.map(m => m.caixa[1]));
  const x1 = Math.max(...ms.map(m => m.caixa[2])), y1 = Math.max(...ms.map(m => m.caixa[3]));
  const g = mapa.geo;
  const z = Math.min(Math.max(Math.min(g.W / ((x1 - x0) * 1.4), g.H / ((y1 - y0) * 1.4)), 1), 8);
  mapa.vista = { z, x: g.W / 2 - (x0 + x1) / 2 * z, y: g.H / 2 - (y0 + y1) / 2 * z };
  mapa.hover = { tipo: 'area', chave };
  aplicarVista();
}

function ligarGestos(canvas){
  const ponteiros = new Map();
  let arrasto = null, pinca = null;
  const pos = e => [e.offsetX, e.offsetY];
  canvas.addEventListener('wheel', e => {
    if(mapa.vista.z <= 1 && e.deltaY > 0) return;   // já no estado inteiro: deixa a página rolar
    e.preventDefault();
    zoomEm(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0018));
  }, { passive: false });
  canvas.addEventListener('pointerdown', e => {
    ponteiros.set(e.pointerId, pos(e));
    if(ponteiros.size === 1){
      arrasto = { x0: e.offsetX, y0: e.offsetY, vx: mapa.vista.x, vy: mapa.vista.y, moveu: false };
    }else if(ponteiros.size === 2){
      const [a, b] = [...ponteiros.values()];
      pinca = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: mapa.vista.z };
      arrasto = null;
    }
    if(e.pointerType !== 'mouse' || e.button === 0) canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', e => {
    if(ponteiros.has(e.pointerId)) ponteiros.set(e.pointerId, pos(e));
    if(pinca && ponteiros.size === 2){
      const [a, b] = [...ponteiros.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomEm((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (pinca.z * d / pinca.d) / mapa.vista.z);
      return;
    }
    if(arrasto && ponteiros.size === 1){
      const dx = e.offsetX - arrasto.x0, dy = e.offsetY - arrasto.y0;
      if(!arrasto.moveu && Math.hypot(dx, dy) > 4 && mapa.vista.z > 1){ arrasto.moveu = true; canvas.classList.add('arrastando'); }
      if(arrasto.moveu){
        mapa.vista.x = arrasto.vx + dx; mapa.vista.y = arrasto.vy + dy;
        limitarVista(); esconderDica(); desenharMapa();
      }
      return;
    }
    if(e.pointerType === 'mouse') passarMouse(e.offsetX, e.offsetY, false);
  });
  const soltar = e => {
    const clique = arrasto && !arrasto.moveu && ponteiros.size === 1;
    ponteiros.delete(e.pointerId);
    if(ponteiros.size < 2) pinca = null;
    if(clique && e.type === 'pointerup') passarMouse(e.offsetX, e.offsetY, true);
    if(!ponteiros.size){ arrasto = null; canvas.classList.remove('arrastando'); }
  };
  canvas.addEventListener('pointerup', soltar);
  canvas.addEventListener('pointercancel', soltar);
  canvas.addEventListener('pointerleave', e => { if(e.pointerType === 'mouse'){ mapa.hover = null; esconderDica(); desenharMapa(); } });
}

/* ---------- o que está sob o mouse */
const testeArea = document.createElement('canvas').getContext('2d');

function distSegmento(px, py, ax, ay, bx, by){
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}

function alvoNoPonto(x, y){
  const f = mapa.filtro, { z } = mapa.vista;
  const i = mapa.rotulos.findIndex(r => r.visivel && Math.hypot(r.x - x, r.y - y) <= 11);
  if(i >= 0) return { tipo: 'trecho', i };
  const bx = (x - mapa.vista.x) / z, by = (y - mapa.vista.y) / z;
  // no estado inteiro as rodovias se cruzam nas sedes dos municípios: só ficam clicáveis com o mapa aproximado
  if((f.federais || f.estaduais) && z >= 1.6){
    let melhor = null, dmin = z < 3 ? 3.5 : 5;
    for(const l of mapa.linhas){
      if((l.tipo === 'federal' && !f.federais) || (l.tipo === 'estadual' && !f.estaduais)) continue;
      for(let k = 2; k < l.xy.length; k += 2){
        const d = distSegmento(bx, by, l.xy[k - 2], l.xy[k - 1], l.xy[k], l.xy[k + 1]) * z;
        if(d < dmin || (melhor && d === dmin && l.tipo === 'federal')){ dmin = d; melhor = l; }
      }
    }
    if(melhor) return { tipo: 'via', ref: melhor.ref, linha: melhor };
  }
  const m = mapa.muns.find(m => bx >= m.caixa[0] && bx <= m.caixa[2] && by >= m.caixa[1] && by <= m.caixa[3] &&
    testeArea.isPointInPath(m.path, bx, by, 'evenodd'));
  if(!m) return null;
  return { tipo: 'area', chave: f.area === 'regioes' ? m.regiao : m.nome, municipio: m.nome };
}

function passarMouse(x, y, clique){
  if(!mapa.geo) return;
  const canvas = document.getElementById('mapaCanvas');
  const alvo = alvoNoPonto(x, y);
  const chaveAlvo = a => a ? a.tipo + '|' + (a.chave || a.ref || a.i) : '';
  if(chaveAlvo(alvo) !== chaveAlvo(mapa.hover)){ mapa.hover = alvo; desenharMapa(); }
  canvas.style.cursor = alvo ? 'pointer' : mapa.vista.z > 1 ? 'grab' : 'default';
  if(!alvo){ esconderDica(); return; }
  mostrarDica(alvo, x + canvas.offsetLeft, y + canvas.offsetTop);
  if(!clique) return;
  if(alvo.tipo === 'trecho') ativarTrecho(alvo.i);
  else if(alvo.tipo === 'via') sugerirViaNoChat(alvo.ref);
  else if(alvo.chave) sugerirNoChat(mapa.filtro.area === 'regioes' ? 'regiao' : 'municipio', alvo.chave);
}

function linhaAtencao(a){
  const at = mapa.at;
  return `<span class="sub">${a.nivel === 'vermelho' ? 'vermelho: atenção máxima' : a.nivel === 'laranja' ? 'laranja: atenção alta' : 'amarelo: abaixo da média do estado'}</span><br>` +
    `${fmt(a.obitos)} óbitos (${fmt(a.taxa_obitos, 1)} por 100 mil/ano; estado ${fmt(at.estado.taxa_obitos, 1)})<br>` +
    `${fmt(a.internacoes)} internações (${fmt(a.taxa_internacoes, 1)} por 100 mil/ano; estado ${fmt(at.estado.taxa_internacoes, 1)})`;
}

function mostrarDica(alvo, x, y){
  const tip = document.getElementById('mapaTip'), at = mapa.at, e = escapeHtml;
  let html;
  if(alvo.tipo === 'trecho'){
    const t = mapa.trechos[alvo.i];
    html = `<b>${alvo.i + 1}. ${t.nome}</b><br>${e(t.municipio)}<br>${fmt(t.n)} ocorrências · ${fmt(t.m)} mortos · ${fmt(t.fg)} feridos graves (PRF)`;
  }else if(alvo.tipo === 'via'){
    const l = alvo.linha;
    const verm = at ? Object.entries(at.municipios).filter(([, a]) => a.nivel === 'vermelho' &&
      alvo.ref.split('/').some(r => a.rodovias_federais.includes(r) || a.rodovias_estaduais.includes(r))).length : 0;
    html = `<b>${e(alvo.ref.replace(/\//g, ' / '))}</b> · rodovia ${l.tipo}<br><span class="sub">superfície: ${e(mapa.vias.superficie[l.s] || 'não informada')}</span>` +
      (verm ? `<br>passa por ${verm} município${verm > 1 ? 's' : ''} em vermelho` : '') + '<br><span class="sub">clique para um plano sugerido no chat</span>';
  }else if(at){
    if(mapa.filtro.area === 'regioes'){
      const r = at.regioes[alvo.chave];
      html = `<b>${e(r.nome)}</b> · região de saúde<br>${linhaAtencao(r)}` +
        (r.pct_via_publica != null ? `<br>${fmt(r.pct_via_publica, 1)}% das mortes na via pública` : '') +
        `<br><span class="sub">${e(alvo.municipio)} · clique para o plano no chat</span>`;
    }else{
      const a = at.municipios[alvo.chave];
      const p = mapa.porMunicipio.get(alvo.chave);
      html = `<b>${e(alvo.chave)}</b> · ${e(a.regiao)}<br>${linhaAtencao(a)}` +
        (p ? `<br>PRF (filtro): ${fmt(p.n)} ocorrências, ${fmt(p.m)} mortos nas BRs` : '') +
        '<br><span class="sub">clique para o plano no chat</span>';
    }
  }else{
    html = `<b>${e(alvo.municipio)}</b>`;
  }
  tip.innerHTML = html;
  tip.hidden = false;
  const wrap = document.getElementById('mapaWrap');
  tip.style.left = Math.max(8, Math.min(x + 14, wrap.clientWidth - tip.offsetWidth - 8)) + 'px';
  tip.style.top = Math.max(8, Math.min(y + 14, wrap.clientHeight - tip.offsetHeight - 8)) + 'px';
}

function esconderDica(){ document.getElementById('mapaTip').hidden = true; }

function ativarTrecho(i){
  mapa.ativo = mapa.ativo === i ? null : i;
  document.querySelectorAll('#mapaTrechos button').forEach(b => b.classList.toggle('ativo', Number(b.dataset.i) === mapa.ativo));
  desenharMapa();
}

/* =========================================================
   Sugestões de plano no chat, sem IA: montadas de atencao_territorial e dos planos por território.
   Cada uma oferece abrir o plano completo ou pedir à IA um plano detalhado.
========================================================= */
const ORDEM_PACOTE = ['gestao_velocidade', 'infraestrutura', 'fiscalizacao_eletronica', 'educacao'];

function rodapeSugestao(fonte){
  return `<span class="mt-2 block border-t border-border pt-1.5 text-[10.5px] text-faint">Fonte: ${escapeHtml(fonte)} · medidas: diretriz do projeto, são propostas · sugestão pronta, sem IA</span>`;
}

function botoesSugestao(planoTipo, planoChave, pergunta){
  return '<span class="acoes-chat">' +
    (planoTipo && planosDe(planoTipo)[planoChave] ? `<button type="button" data-acao="plano" data-tipo="${planoTipo}" data-chave="${escapeHtml(planoChave)}">Ver plano completo</button>` : '') +
    `<button type="button" data-acao="ia" data-pergunta="${escapeHtml(pergunta)}">Pedir à IA um plano detalhado</button></span>`;
}

function listaPacote(chaves, adaptar){
  const pac = dataset.atencao_territorial.pacote_de_medidas;
  return '<ul>' + chaves.map(k => `<li><b>${escapeHtml(pac[k].titulo)}:</b> ${escapeHtml(adaptar ? adaptar(k, pac[k]) : pac[k].acoes.slice(0, 2).join(' '))}</li>`).join('') + '</ul>';
}

function sugerirNoChat(tipo, chave){
  const at = dataset.atencao_territorial;
  if(!at) return;
  const a = tipo === 'regiao' ? at.regioes[chave] : at.municipios[chave];
  if(!a) return;
  const e = escapeHtml, nome = tipo === 'regiao' ? a.nome : chave;
  const planoTipo = tipo === 'regiao' ? 'regioes_de_saude' : 'municipios';
  const plano = planosDe(planoTipo)[chave];
  const onde = plano && plano.atencao ? plano.atencao.onde_agir
    : (a.rodovias_federais || []).concat(a.rodovias_estaduais || []).length
      ? 'rodovias no município: ' + (a.rodovias_federais || []).concat(a.rodovias_estaduais || []).join(', ') + '.' : '';
  const tipoTxt = tipo === 'regiao' ? 'região de saúde' : 'município';
  let html = `<div class="sugestao"><b>Plano sugerido — ${e(nome)}</b> (${tipoTxt}) · <span class="cor-${a.nivel}">${a.nivel}</span><br>` +
    `${fmt(a.obitos)} óbitos e ${fmt(a.internacoes)} internações de residentes por acidentes de transporte em ${e(at.periodo.replace('-', '–'))}` +
    ` (${fmt(a.taxa_obitos, 1)} óbitos e ${fmt(a.taxa_internacoes, 1)} internações por 100 mil hab./ano; estado: ${fmt(at.estado.taxa_obitos, 1)} e ${fmt(at.estado.taxa_internacoes, 1)}).`;
  if(a.nivel === 'amarelo'){
    html += '<br>Não está entre as áreas em vermelho ou laranja. Sugestão: manter o acompanhamento anual dos óbitos e internações e as campanhas educativas.';
  }else{
    html += `<br>Por quê: ${e((a.motivos || []).join('; '))}.` + (onde ? `<br>Onde agir primeiro: ${e(onde)}` : '') +
      listaPacote(ORDEM_PACOTE) + `<span class="text-[12px] text-muted-foreground">${e(at.pacote_de_medidas.gestao_velocidade.observacao)}</span>`;
  }
  const pergunta = `Monte um plano de ação para ${nome} (${tipoTxt}, ${a.nivel} no mapa) com gestão de velocidade, infraestrutura viária, fiscalização eletrônica e educação, dizendo onde agir primeiro.`;
  appendMessage('ai', html + botoesSugestao(planoTipo, chave, pergunta) + '</div>' + rodapeSugestao(at.fonte));
  levarAoChat();
}

function sugerirViaNoChat(ref){
  const at = dataset.atencao_territorial;
  if(!at) return;
  const e = escapeHtml, refs = ref.split('/'), federal = refs.some(r => r.startsWith('BR'));
  const passa = Object.entries(at.municipios).filter(([, a]) => refs.some(r => a.rodovias_federais.includes(r) || a.rodovias_estaduais.includes(r)));
  const verm = passa.filter(([, a]) => a.nivel === 'vermelho').sort((x, y) => y[1].obitos - x[1].obitos).map(([n]) => n);
  const lar = passa.filter(([, a]) => a.nivel === 'laranja').map(([n]) => n);
  const brNum = refs.filter(r => r.startsWith('BR')).map(r => Number(r.slice(3)));
  const pts = mapa.prf ? mapa.prf.pontos.filter(p => brNum.includes(p[3])) : [];
  const orgao = federal ? 'DNIT e PRF' : 'DER-PI';
  let html = `<div class="sugestao"><b>Plano sugerido — ${e(refs.join(' / '))}</b> (rodovia ${federal ? 'federal' : 'estadual'})<br>` +
    `Passa por ${passa.length} município${passa.length === 1 ? '' : 's'}: ${verm.length} em vermelho${verm.length ? ' (' + e(verm.slice(0, 6).join(', ')) + (verm.length > 6 ? '...' : '') + ')' : ''} e ${lar.length} em laranja.`;
  html += federal && pts.length
    ? ` Nas BRs da rodovia, a PRF registrou ${fmt(pts.length)} ocorrência${pts.length === 1 ? '' : 's'} e ${fmt(pts.reduce((s, p) => s + p[5], 0))} mortos (${e(mapa.prf.periodo)}).`
    : ' A base não tem sinistros georreferenciados nas rodovias estaduais; a prioridade vem dos óbitos e internações dos municípios que ela corta.';
  html += listaPacote(['gestao_velocidade', 'fiscalizacao_eletronica', 'infraestrutura', 'educacao'], (k, p) =>
    k === 'gestao_velocidade' ? `Nas travessias urbanas${verm.length ? ' de ' + verm.slice(0, 3).join(', ') : ''}, baixar a velocidade com sinalização, redutores e controle de acessos (${orgao}); nas ruas urbanas, 50 km/h em arteriais e 30 km/h em vias locais (prefeituras).`
    : k === 'fiscalizacao_eletronica' ? `Radares fixos e lombadas eletrônicas nos acessos urbanos e nos trechos com mais óbitos (${orgao}).`
    : k === 'infraestrutura' ? `Faixas de pedestres elevadas, calçadas e iluminação nas travessias urbanas da rodovia (${orgao} com as prefeituras).`
    : p.acoes[0]);
  const plano = planosDe('rodovias')[refs.find(r => planosDe('rodovias')[r])];
  const pergunta = `Monte um plano de ação para a rodovia ${refs[0]}, que passa por municípios em vermelho como ${verm.slice(0, 3).join(', ') || 'os do trajeto'}, com gestão de velocidade e fiscalização eletrônica.`;
  appendMessage('ai', html + botoesSugestao(plano ? 'rodovias' : null, plano ? plano.nome : null, pergunta) + '</div>' +
    rodapeSugestao(at.fonte + (federal ? '; ' + mapa.prf.fonte : '') + '; traçado: OpenStreetMap'));
  levarAoChat();
}

// Mostra a mensagem nova sem tirar o mapa da tela, quando cabe; no celular rola até o chat.
function levarAoChat(){
  const log = document.getElementById('log');
  const caixa = log.getBoundingClientRect();
  if(caixa.top > window.innerHeight || caixa.bottom < 0) log.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Mensagem inicial do chat: as regiões em vermelho, com atalho para a sugestão de cada uma.
function apresentarAreasCriticas(){
  const at = dataset && dataset.atencao_territorial;
  if(!at) return;
  const verm = Object.entries(at.regioes).filter(([, r]) => r.nivel === 'vermelho');
  if(!verm.length) return;
  appendMessage('ai', `<div class="sugestao"><b>Áreas que pedem mais atenção</b><br>Regiões de saúde em vermelho no mapa (óbitos e internações de residentes, ${escapeHtml(at.periodo.replace('-', '–'))}). ` +
    'Escolha uma para ver o plano sugerido, ou clique em qualquer área ou rodovia do mapa.<span class="acoes-chat">' +
    verm.map(([k, r]) => `<button type="button" data-acao="sugerir" data-tipo="regiao" data-chave="${k}">${escapeHtml(r.nome)}</button>`).join('') +
    '</span></div>' + rodapeSugestao(at.fonte));
}

document.getElementById('log').addEventListener('click', e => {
  const b = e.target.closest('button[data-acao]');
  if(!b) return;
  if(b.dataset.acao === 'plano') abrirPlano(b.dataset.tipo, b.dataset.chave);
  else if(b.dataset.acao === 'ia') askQuestion(b.dataset.pergunta);
  else if(b.dataset.acao === 'sugerir'){
    if(mapa.geo){ document.getElementById('mapaArea').value = 'regioes'; mapa.filtro.area = 'regioes'; colorirAreas(); renderFocos(); enquadrarArea('regiao', b.dataset.chave); }
    sugerirNoChat(b.dataset.tipo, b.dataset.chave);
  }
});

/* =========================================================
   Perguntas rápidas: banco de respostas prontas (data/perguntas.json)
   Mostra uma pergunta de cada seção, sorteadas a cada carga da página.
========================================================= */
const MIN_SUGESTOES = 6;
const VISTAS_KEY = 'infotransito:vistas';
const CHIP = 'rounded-full border border-border bg-panel-2 px-2.5 py-1.5 text-[12.5px] transition-colors hover:border-amber-dim hover:text-foreground';
let banco = [];

const bancoPromise = fetch('data/perguntas.json')
  .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
  .then(lista => { banco = lista; return lista; })
  .catch(() => []);

function chaveDePergunta(texto){
  return normalize(texto).trim().replace(/[?!.\s]+$/, '');
}

// Pergunta digitada igual (sem acento/pontuação) a uma pronta: responde sem gastar a API.
function acharPronta(question){
  const n = chaveDePergunta(question);
  return banco.find(b => chaveDePergunta(b.pergunta) === n) || null;
}

function lerVistas(){
  try{ return JSON.parse(localStorage.getItem(VISTAS_KEY)) || []; }catch(_){ return []; }
}
function gravarVistas(ids){
  try{ localStorage.setItem(VISTAS_KEY, JSON.stringify(ids)); }catch(_){ /* sem armazenamento */ }
}

// Uma pergunta por seção (evitando as do último sorteio), completando até o mínimo, em ordem aleatória.
function escolherSugestoes(){
  const vistas = new Set(lerVistas());
  const porSecao = new Map();
  const elegiveis = banco.filter(b => b.chip !== false);
  elegiveis.forEach(b => {
    if(!porSecao.has(b.secao)) porSecao.set(b.secao, []);
    porSecao.get(b.secao).push(b);
  });
  const sorteia = arr => arr[Math.floor(Math.random() * arr.length)];
  const escolhidas = [];
  for(const itens of porSecao.values()){
    const novas = itens.filter(b => !vistas.has(b.id));
    const base = novas.length ? novas : itens;
    // perguntas gerais (destaque) saem na maioria das vezes; as de detalhe (por BR, ano, faixa...) variam o resto
    const fortes = base.filter(b => b.destaque);
    escolhidas.push(sorteia(fortes.length && Math.random() < 0.75 ? fortes : base));
  }
  const resto = elegiveis.filter(b => !escolhidas.includes(b) && !vistas.has(b.id));
  while(escolhidas.length < MIN_SUGESTOES && resto.length){
    escolhidas.push(resto.splice(Math.floor(Math.random() * resto.length), 1)[0]);
  }
  for(let i = escolhidas.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [escolhidas[i], escolhidas[j]] = [escolhidas[j], escolhidas[i]];
  }
  gravarVistas(escolhidas.map(b => b.id));
  return escolhidas;
}

function mostrarPronta(b){
  appendMessage('user', escapeHtml(b.pergunta));
  const temFonte = b.fonte && !['metadata', 'index.html'].includes(b.fonte);
  appendMessage('ai', respostaHtml(b.resposta, false, (temFonte ? 'Fonte: ' + escapeHtml(b.fonte) + ' · ' : '') + 'resposta pronta, sem IA'));
}

async function renderSuggestions(){
  const wrap = document.getElementById('suggestions');
  await bancoPromise;
  if(!banco.length){
    // sem o banco (arquivo ausente): volta às perguntas fixas, respondidas pela IA
    wrap.innerHTML = SUGGESTED_QUESTIONS.map(q =>
      `<button type="button" class="${CHIP} text-muted-foreground" data-ia="1" data-q="${escapeHtml(q)}">${escapeHtml(q)}</button>`
    ).join('');
    wrap.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => askQuestion(btn.dataset.q)));
    return;
  }
  wrap.innerHTML = escolherSugestoes().map(b =>
    `<button type="button" class="${CHIP} text-muted-foreground" data-id="${b.id}" title="${escapeHtml(b.secao)}">${escapeHtml(b.pergunta)}</button>`
  ).join('') +
    `<button type="button" class="${CHIP} text-amber" data-outras="1" title="Mostrar outras perguntas">↻ Outras perguntas</button>`;
  wrap.querySelectorAll('button[data-id]').forEach(btn => {
    btn.addEventListener('click', () => mostrarPronta(banco.find(b => String(b.id) === btn.dataset.id)));
  });
  wrap.querySelector('button[data-outras]').addEventListener('click', renderSuggestions);
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

// A palavra deve começar numa fronteira de palavra ("capacete" casa "capacetes", mas "cid" não casa
// "acidentes"). Termos curtos (até 3 letras: cid, ano, cor...) exigem palavra inteira, com plural opcional.
function casaPalavra(q, palavra){
  const p = palavra.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = palavra.length <= 3 ? new RegExp('\\b' + p + '(s|es)?\\b') : new RegExp('\\b' + p);
  return re.test(q);
}

// Pedidos de plano de ação ou de medidas: levam os planos já montados (planos_de_acao) dos assuntos citados.
const INTENCAO_PLANO = /\b(planos?|acao|acoes|medidas?|combat\w*|reduzir|prevenir|prevencao|evitar|estrategias?|solucao|solucoes|politicas? publicas?|o que fazer|deve fazer|devemos fazer|ser feito|como melhorar|enfrent\w*|mitig\w*|prioridades?|priorizar|intervencao|intervencoes|recomend\w*|propostas?)\b/;
const TEMAS_PLANO = [
  [/alcool|bebid|lei seca|embriag|fim de semana|sabado|domingo/, ['alcool_fim_de_semana']],
  [/noite|noturn|madrugada|escuro|iluminac/, ['noite_madrugada']],
  [/pedestre|atropel|calcada|travessia/, ['pedestres']],
  [/contramao|frontal|ultrapass/, ['colisao_frontal_contramao']],
  [/animal|gado|boi\b|cavalo/, ['animais_na_pista']],
  [/sono|dormindo|fadiga|cansa|atencao|distracao|celular|reacao/, ['atencao_fadiga']],
  [/moto|capacete|motofrete|aplicativo|entregador/, ['motociclistas']],
  [/samu|resgate|socorro|atendimento|trauma|hospital|pre-hospitalar/, ['atendimento_pre_hospitalar']],
  [/teresina|capital|urban/, ['teresina_urbano']],
  [/rural|pista simples|interior|curva|mais letal|mais perigos/, ['pista_simples_rural', 'brs_mais_letais']],
  [/dados|subnotific|informac|registro|monitor/, ['dados_monitoramento']]
];
const TEMAS_PLANO_GERAIS = ['pista_simples_rural', 'noite_madrugada', 'colisao_frontal_contramao', 'pedestres'];

// Devolve os caminhos dos planos a incluir, ou null se a pergunta não pede plano.
// Com um território citado (que já tem plano próprio), os temas gerais e o plano integrado não entram.
function caminhosDePlano(q, comTerritorio){
  if(!INTENCAO_PLANO.test(q) || !dataset.planos_de_acao) return null;
  const temas = new Set();
  TEMAS_PLANO.forEach(([re, chaves]) => { if(re.test(q)) chaves.forEach(c => temas.add(c)); });
  if(!comTerritorio){
    if(!temas.size) TEMAS_PLANO_GERAIS.forEach(c => temas.add(c));
    temas.add('plano_integrado');
  }
  return [...temas].map(c => 'planos_de_acao.temas.' + c).concat([
    'planos_de_acao.limite_da_inferencia',
    'estudo_morbidade_piaui_2010_2023.recomendacoes',
    'apresentacao_ufpi_morbimortalidade_brasil_2016_2025.recomendacoes_dos_autores'
  ]);
}

// Perguntas de decisão ("quais 10 municípios priorizar?", "onde investir?"): levam os rankings prontos.
const TERRITORIO = 'planos_por_territorio.';
const ATENCAO = 'atencao_territorial.';
const INTENCAO_DECISAO = /\b(prioriz\w*|prioridades?|ranking|onde (investir|focar|agir|atuar|comecar)|por onde comecar|quais (os |as )?\d+|top \d+|mais critic\w*)\b/;
const PEDE_PLANO = /\b(planos?|acao|acoes|medidas?)\b/;
const PARTES_PRIORIZACAO = [
  [/regi(ao|oes)|regional/, 'regioes_de_saude'], [/municip|cidade/, 'municipios_prf'],
  [/trecho|\bkm\b/, 'trechos_prf'], [/\bbrs?\b|rodovia|estrada/, 'rodovias_prf']
];

function caminhosDeDecisao(q){
  if(!INTENCAO_DECISAO.test(q) || !dataset.planos_por_territorio) return null;
  const partes = PARTES_PRIORIZACAO.filter(([re]) => re.test(q)).map(([, k]) => k);
  const P = TERRITORIO + 'priorizacao.';
  return [TERRITORIO + 'criterios_de_prioridade', P + 'lista_recomendada']
    .concat((partes.length ? partes : PARTES_PRIORIZACAO.map(([, k]) => k)).map(k => P + k));
}

// Monta um contexto sob medida para a pergunta, usando o índice de busca do JSON.
// Se nenhuma palavra-chave bater, cai no fallback de enviar uma visão geral.
function buildContextForQuestion(question){
  const q = normalize(question);
  const indice = dataset.indice_busca || {};
  const pathsEncontrados = new Set();
  const palavrasEncontradas = [];

  const achados = Object.entries(indice).filter(([palavra]) => casaPalavra(q, normalize(palavra)));
  const comTerritorio = achados.some(([, paths]) => paths.some(p => p.startsWith(TERRITORIO)));
  // "quais ações do plano de Teresina priorizar?" é sobre o plano do território, não sobre o ranking
  const decisaoPaths = comTerritorio && PEDE_PLANO.test(q) ? null : caminhosDeDecisao(q);
  // pedido de priorização sem pedir plano/ações: responde com o ranking, não com o formato de plano
  const planoPaths = decisaoPaths && !PEDE_PLANO.test(q) ? null : caminhosDePlano(q, comTerritorio);
  if(planoPaths){
    palavrasEncontradas.push('plano de ação');
    planoPaths.forEach(p => pathsEncontrados.add(p));
  }
  if(decisaoPaths){
    palavrasEncontradas.push('priorização');
    decisaoPaths.forEach(p => pathsEncontrados.add(p));
  }

  for(const [palavra, paths] of achados){
    palavrasEncontradas.push(palavra);
    // em pedidos de plano ou de priorização, só entram as interpretações prontas e os planos por território;
    // as tabelas brutas inflariam o contexto
    paths.filter(p => !(planoPaths || decisaoPaths) || p.startsWith('interpretacao_prf_piaui.') || p.startsWith(TERRITORIO) || p.startsWith(ATENCAO))
      .forEach(p => pathsEncontrados.add(p));
  }
  // planos por território usam rótulos curtos de origem e a média do estado por fator, explicados no topo da seção
  if([...pathsEncontrados].some(p => p.startsWith(TERRITORIO + 'regioes_de_saude.') || p.startsWith(TERRITORIO + 'rodovias.') || p.startsWith(TERRITORIO + 'municipios.'))){
    ['origens', 'fatores_media_estado_pct', 'limites'].forEach(k => pathsEncontrados.add(TERRITORIO + k));
  }
  // um caminho cujo "pai" já está no contexto só repetiria dados
  for(const p of [...pathsEncontrados]){
    if([...pathsEncontrados].some(outro => p !== outro && p.startsWith(outro + '.'))) pathsEncontrados.delete(p);
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
    // fallback: nenhuma palavra-chave reconhecida, envia uma visão geral (a base inteira ficou grande demais)
    contexto = {
      resumo_geral: resumoGeral,
      'dados_prf_piaui.fonte': resolvePath('dados_prf_piaui.fonte'),
      'dados_prf_piaui.por_ano': resolvePath('dados_prf_piaui.por_ano'),
      'dados_prf_piaui.por_rodovia': resolvePath('dados_prf_piaui.por_rodovia'),
      'apresentacao_ufpi_morbimortalidade_brasil_2016_2025.piaui': resolvePath('apresentacao_ufpi_morbimortalidade_brasil_2016_2025.piaui')
    };
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

// Escapa texto vindo do usuário ou do modelo antes de entrar em innerHTML.
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
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

let busy = false;
function setBusy(b){
  busy = b;
  document.getElementById('askBtn').disabled = b;
  document.querySelectorAll('#suggestions button[data-ia]').forEach(btn => { btn.disabled = b; });
}

/* =========================================================
   Provedores de IA: Gemini (principal) e OpenRouter (reserva)
========================================================= */
const OPENROUTER_MODELS = [
  "google/gemma-4-26b-a4b-it:free",
  "nvidia/nemotron-3-super-120b-a12b:free",
  "nvidia/nemotron-3.5-lightning:free"
];
/* Quanto a IA "pensa": perguntas simples usam o perfil rápido; pedidos de plano de ação e perguntas analíticas
   (por que, compare, explique...) usam o analítico, com mais raciocínio e mais espaço de saída. Os tokens de
   raciocínio contam no limite de saída, então o analítico precisa de um limite maior. Ajuste os números aqui. */
const PERFIS_IA = {
  rapido:   { nome: 'rápido',   pensar: 'low',  efforts: 'low',  maxTokens: 2048 },
  // 'efforts' vale para os modelos do OpenRouter, que gastam muitos tokens raciocinando e podem não sobrar texto
  // (motivo: length); por isso o analítico usa 'medium' lá, enquanto o Gemini usa 'high'.
  analitico: { nome: 'analítico', pensar: 'high', efforts: 'medium', maxTokens: 8192 }
};
const INTENCAO_ANALISE = /\b(por que|porque|explic\w*|analis\w*|compar\w*|relacion\w*|correlac\w*|motivos?|diferenca entre|o que explica|tendencia)\b/;

function perfilDaPergunta(question){
  const q = normalize(question);
  return (INTENCAO_PLANO.test(q) || INTENCAO_ANALISE.test(q)) ? PERFIS_IA.analitico : PERFIS_IA.rapido;
}

// Quais provedores têm chave e quais estão com a cota diária esgotada (o servidor nunca envia a chave).
// Consultado a cada pergunta, para parar de tentar um provedor assim que o servidor souber que a cota acabou.
function carregarConfig(){
  return fetch('/api/config')
    .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
    .catch(() => ({ gemini: false, openrouter: false, esgotado: {}, erro: true }));
}

function formatarEspera(seg){
  const h = Math.floor(seg / 3600), m = Math.ceil((seg % 3600) / 60);
  return h ? `${h}h${String(m).padStart(2, '0')}` : `${m} min`;
}

function apiError(msg, status, retryAfter){
  const e = new Error(msg);
  e.status = status;           // undefined = falha de rede
  e.retryAfter = retryAfter;   // segundos, se a API informou
  return e;
}

// 429 e 5xx (tráfego alto) e falhas de rede valem nova tentativa; 400/401/403 não.
function isRetriable(e){
  if(e.limite || e.esgotado) return false;   // limite de uso ou cota diária: repetir não adianta
  return e.status === undefined || e.status === 429 || (e.status >= 500 && e.status <= 504);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function postJson(url, headers, body){
  let res;
  try{
    res = await fetch(url, {
      method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body),
      signal: AbortSignal.timeout ? AbortSignal.timeout(180000) : undefined   // raciocínio longo pode levar mais de 1 minuto
    });
  }catch(err){
    throw apiError(err.name === 'TimeoutError' ? 'tempo esgotado esperando a resposta' : 'falha de conexão (' + err.message + ')', undefined);
  }
  let data = null;
  try{ data = await res.json(); }catch(_){ /* corpo não-JSON: tratado abaixo */ }
  if(!res.ok){
    const msg = (data && data.error && data.error.message) ? data.error.message : ('erro HTTP ' + res.status);
    const err = apiError(msg, res.status, Number(res.headers.get('retry-after')) || undefined);
    err.limite = res.headers.get('x-limite') === '1';
    err.esgotado = res.headers.get('x-esgotado') === '1';
    throw err;
  }
  if(!data) throw apiError('resposta que não é JSON válido (HTTP ' + res.status + ')', 0);
  return data;
}

// As chaves ficam no .env do servidor (server.js); o navegador só chama /api/*.
async function callGemini(systemPrompt, question, perfil){
  const data = await postJson(
    `/api/gemini?model=${encodeURIComponent(MODEL)}`,
    {},
    {
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents: [{ role: 'user', parts: [{ text: question }] }],
      generationConfig: { maxOutputTokens: perfil.maxTokens, thinkingConfig: { thinkingLevel: perfil.pensar } }
    }
  );
  const candidate = (data.candidates || [])[0];
  const parts = candidate && candidate.content && candidate.content.parts;
  const text = parts && parts.length ? parts.map(p => p.text || '').join('') : null;
  if(!text) throw apiError('sem texto (motivo: ' + (candidate ? candidate.finishReason : 'sem candidatos') + ')', 0);
  return { text, cortada: candidate.finishReason === 'MAX_TOKENS' };
}

async function callOpenRouter(model, systemPrompt, question, perfil){
  const data = await postJson(
    '/api/openrouter',
    {},
    {
      model,
      messages: [{ role: 'system', content: systemPrompt }, { role: 'user', content: question }],
      max_tokens: perfil.maxTokens,
      reasoning: { effort: perfil.efforts }
    }
  );
  if(data.error) throw apiError(data.error.message || 'erro do provedor', data.error.code);
  const choice = (data.choices || [])[0];
  const text = choice && choice.message && choice.message.content;
  if(!text){
    const motivo = choice ? choice.finish_reason : 'sem choices';
    throw apiError(motivo === 'length' ? 'o modelo gastou todo o limite de tokens raciocinando e não escreveu a resposta' : 'sem texto (motivo: ' + motivo + ')', 0);
  }
  return { text, cortada: choice.finish_reason === 'length' };
}

// Mensagem curta e legível por provedor (os erros originais costumam trazer links e parágrafos inteiros).
function resumirErro(p, e){
  if(e.limite) return e.message;
  if(e.esgotado) return p.nome + ': cota diária gratuita esgotada' + (e.retryAfter ? ' (volta em cerca de ' + formatarEspera(e.retryAfter) + ')' : '');
  const curto = String(e.message).replace(/https?:\/\/\S+/g, '').split(/\n|\. /)[0].trim().slice(0, 160);
  return p.nome + ': ' + curto;
}

// Tenta cada provedor em ordem; em erro de tráfego, repete uma vez após uma espera curta.
async function askProviders(providers, onStatus){
  const falhas = [];
  for(let i = 0; i < providers.length; i++){
    const p = providers[i];
    if(i > 0) onStatus('Tentando ' + p.nome + '...');
    for(let tentativa = 0; tentativa < 2; tentativa++){
      try{
        return { ...(await p.call()), nome: p.nome };
      }catch(e){
        if(isRetriable(e) && tentativa === 0){
          onStatus(p.nome + ' ocupado, tentando de novo...');
          await sleep(Math.min((e.retryAfter || 1) * 1000, 5000) + Math.random() * 500);
          continue;
        }
        falhas.push(resumirErro(p, e));
        if(e.limite) i = providers.length;   // o limite vale para todos os modelos: para aqui
        break;
      }
    }
  }
  const erro = new Error(falhas.join('\n'));
  erro.falhas = falhas;
  throw erro;
}

/* Cache das respostas (pergunta normalizada -> texto), só no navegador do visitante. */
const CACHE_PREFIX = 'infotransito:v3:';   // mude a versão quando o prompt ou os dados mudarem, para não servir respostas antigas
function cacheGet(question){
  try{ return JSON.parse(localStorage.getItem(CACHE_PREFIX + normalize(question).trim())); }catch(_){ return null; }
}
function cacheSet(question, valor){
  try{ localStorage.setItem(CACHE_PREFIX + normalize(question).trim(), JSON.stringify(valor)); }catch(_){ /* sem armazenamento */ }
}

function respostaHtml(text, cortada, rodape){
  const avisoCorte = cortada
    ? '<br><br><em>(resposta cortada por limite de tokens — tente uma pergunta mais específica)</em>'
    : '';
  const corpo = escapeHtml(limparMarkdown(text)).replace(/\n/g,'<br>') + avisoCorte;
  if(!rodape) return corpo;
  const tag = `<span class="mt-2 block border-t border-border pt-1.5 text-[10.5px] text-faint">${rodape}</span>`;
  return corpo + '<br>' + tag;
}

async function askQuestion(question){
  if(!question || !question.trim()) return;
  const pronta = acharPronta(question);
  if(pronta){
    mostrarPronta(pronta);
    return;
  }
  if(busy) return;

  const emCache = cacheGet(question);
  if(emCache){
    appendMessage('user', escapeHtml(question));
    appendMessage('ai', respostaHtml(emCache.text, false, 'Resposta em cache (' + escapeHtml(emCache.nome) + ')'));
    return;
  }
  const cfg = await carregarConfig();
  const esgotadoGemini = (cfg.esgotado || {})['gemini:' + MODEL] || 0;
  const usaGemini = cfg.gemini && !esgotadoGemini;
  if(!usaGemini && !cfg.openrouter){
    const volta = Math.max(esgotadoGemini, (cfg.esgotado || {}).openrouter || 0);
    appendMessage('ai', cfg.erro
      ? 'Não foi possível falar com o servidor local. Inicie-o com "node server.js" e abra http://localhost:8000.'
      : volta
        ? 'As cotas diárias gratuitas das IAs acabaram (voltam em cerca de ' + formatarEspera(volta) + '). As perguntas rápidas continuam funcionando.'
        : 'Nenhuma chave de API configurada. Preencha GEMINI_API_KEY e/ou OPENROUTER_API_KEY no arquivo .env e reinicie o servidor.',
      'error');
    return;
  }
  if(!dataset){
    appendMessage('ai', 'Os dados ainda não foram carregados. Verifique se o arquivo data/sinistros.json está acessível.', 'error');
    return;
  }
  setBusy(true);
  appendMessage('user', escapeHtml(question));
  const loadingEl = appendMessage('ai', 'Buscando os dados relevantes e analisando...', 'loading');

  const { contexto, palavrasEncontradas } = buildContextForQuestion(question);

  const systemPrompt =
    "Você é um assistente de análise de segurança viária do Piauí. " +
    "Responda SOMENTE com base nos dados JSON fornecidos abaixo (um recorte relevante da base completa).\n\n" +
    "REGRAS DE ESTILO (siga sempre, sem exceção):\n" +
    "- Seja curto e objetivo: no máximo 3-4 frases, ou até 4 linhas se precisar listar números (exceto nos " +
    "pedidos de plano de ação, descritos mais abaixo).\n" +
    "- Responda SOMENTE o que foi perguntado. Não acrescente contexto, curiosidades ou recomendações que não " +
    "foram pedidas, mesmo que estejam disponíveis nos dados.\n" +
    "- Não use markdown: nada de asterisco, hashtag, negrito ou itálico. Escreva em texto simples.\n" +
    "- Se precisar listar itens, use quebra de linha com um travessão (\"- \") no início de cada item, nunca " +
    "asterisco.\n" +
    "- Sempre siga este formato: (1) uma frase direta respondendo a pergunta, (2) opcionalmente, até 3 números " +
    "de apoio que fundamentam a resposta, (3) se usar um dado nacional (VIVA 2014 ou a apresentação da UFPI sobre o " +
    "Brasil), termine com uma frase curta avisando que aquele número é nacional, não do Piauí.\n" +
    "- Em TODA resposta (inclusive planos e rankings), a última linha deve começar com 'Fonte:' e citar a fonte e o " +
    "período de cada dado usado, por exemplo 'Fonte: PRF, só rodovias federais, 01/01/2020 a 31/08/2026' ou " +
    "'Fonte: SIH/SUS, Bastos et al. 2026, 2010-2023'. Com mais de uma fonte, separe por ponto e vírgula. Use os " +
    "campos 'fonte' e 'periodo' dos dados; não invente período.\n\n" +
    "PEDIDOS DE PLANO DE AÇÃO (quando a pergunta pedir plano, medidas, ações, estratégia ou como reduzir/combater/" +
    "evitar acidentes): use a seção 'planos_de_acao' (diagnóstico já calculado, locais prioritários, ações, " +
    "indicadores, quem envolver) junto com os demais dados. Estas regras substituem o limite de 3-4 frases: responda " +
    "em até 12 linhas de texto simples, nesta ordem: (1) 'Diagnóstico:' com os 2 ou 3 números mais relevantes e o " +
    "local, horário ou grupo prioritário; (2) 'Ações:' com até 5 itens iniciados por '- ', cada um dizendo o que " +
    "fazer, onde (trecho, município ou horário que aparece nos dados) e o eixo entre colchetes ([fiscalização], " +
    "[engenharia], [educação], [atendimento] ou [dados]); (3) 'Acompanhar:' com 2 ou 3 indicadores; (4) uma frase " +
    "final dizendo que as ações são propostas a partir dos dados, que não medem a eficácia das medidas. Marque com " +
    "'(recomendação dos autores)' as ações que vêm dos estudos. Não invente números, trechos, programas nem " +
    "resultados esperados; o que não estiver nos dados é sugestão e deve ser dito como sugestão. Se faltar dado " +
    "para um plano (por exemplo, tipo de veículo na PRF), diga isso. " +
    "Se a pergunta citar um território que tem plano em 'planos_por_territorio' (região de saúde, rodovia ou " +
    "município), use esse plano em vez dos temas gerais: comece com 'Prioridade:' (nível e o principal motivo) e " +
    "inclua 'Metas:' com até 2 metas do plano, dizendo se cada uma é referência da ONU ou proposta técnica.\n\n" +
    "PERGUNTAS DE PRIORIZAÇÃO (quais N municípios, regiões, trechos ou rodovias priorizar; onde investir; por onde " +
    "começar): use 'priorizacao', 'lista_recomendada' e 'criterios_de_prioridade'. Estas regras substituem o limite " +
    "de 3-4 frases: (1) uma frase dizendo o critério usado; (2) a lista em ordem, um item por linha com '- ', cada um " +
    "com o número que justifica a posição (mortos, gravidade ou taxa) e o nível de prioridade; se N não for dito, use " +
    "10 (ou todos, se houver menos); (3) uma frase citando quem se destaca em outro ranking (gravidade ou " +
    "crescimento) e ficou fora da lista; (4) avise que municípios, trechos e rodovias vêm da PRF e cobrem só " +
    "rodovias federais (para todas as vias, use óbitos e internações de 'atencao_territorial'). Não invente critério, não combine fontes " +
    "diferentes num mesmo ranking e diga que o nível de prioridade é uma proposta de critério.\n\n" +
    "FONTES DOS DADOS (não confunda uma com a outra):\n" +
    "(1) 'fonte_dados_viva_2014', 'evento', 'perfil_demografico' e 'atendimento_evolucao' vêm de uma pesquisa " +
    "NACIONAL (VIVA 2014, capitais + DF, ano de 2014) sobre motociclistas atendidos em emergência — não são " +
    "específicos do Piauí. " +
    "(2) 'estudo_morbidade_piaui_2010_2023' contém dados REAIS e ESPECÍFICOS do Piauí " +
    "(SIH/SUS, artigo científico Rev Bras Epidemiol 2026), cobrindo 2010 a 2023 — use como fonte primária " +
    "para perguntas sobre o Piauí especificamente. " +
    "ATENÇÃO: 'piaui_dados_locais' contém apenas registros FICTÍCIOS de exemplo, NÃO são dados reais. " +
    "Nunca cite esses registros como fatos (rodovias, km, municípios, vítimas); se a pergunta depender deles, " +
    "diga que não há dados reais de sinistros individuais na base. " +
    "(3) 'dados_tabnet_piaui_teresina' é uma consulta bruta do TABNET/DATASUS (SIH/SUS), também REAL e " +
    "ESPECÍFICA do Piauí, mas com série mais longa (2009 a 2026, sendo 2026 parcial) e recorte adicional só " +
    "do município de Teresina; os totais dela NÃO batem exatamente com os de 'estudo_morbidade_piaui_2010_2023' " +
    "porque a metodologia e o período são diferentes — se usar essa fonte, avise que é uma consulta bruta e " +
    "não o artigo científico. " +
    "(4) 'dados_prf_piaui' são REAIS e ESPECÍFICOS do Piauí (Polícia Rodoviária Federal, ocorrências, 2020 a " +
    "31/08/2026, sendo 2026 parcial), mas cobrem SOMENTE rodovias federais (BRs): não representam vias " +
    "estaduais nem urbanas. Conte ocorrências e vítimas (mortos, feridos) como registros da PRF; não compare " +
    "nem some esses totais com os de internações (SIH/SUS) ou de óbitos (SIM), pois a metodologia é outra. " +
    "Para locais críticos, use 'trechos_criticos_*' e 'municipios_*' e diga que se trata de rodovias federais. " +
    "A seção 'interpretacao_prf_piaui' traz conclusões JÁ CALCULADAS (campo 'resumo' de cada tema): quando ela " +
    "cobrir a pergunta, baseie a resposta nela e cite os números exatamente como estão escritos, sem recalcular. " +
    "(5) 'apresentacao_ufpi_morbimortalidade_brasil_2016_2025' traz resultados NACIONAIS de uma apresentação da " +
    "UFPI (internações 2016-2025, óbitos 2015-2024); só a seção 'piaui' é específica do Piauí (ex.: coeficiente " +
    "de mortalidade de 34,4 por 100 mil hab. em 2024, o 2º maior do país). Ao citar números das demais seções, " +
    "avise que são nacionais. " +
    "(6) 'planos_por_territorio' traz planos JÁ MONTADOS por região de saúde (calculados de (2)), por rodovia e por " +
    "município (calculados de (4), só rodovias federais) e rankings prontos em 'priorizacao'. Os níveis de prioridade " +
    "seguem 'criterios_de_prioridade'; as origens das ações e metas estão em 'origens' (a meta de 50% até 2030 é uma " +
    "referência externa da ONU, não um dado). Cite os números como estão escritos, sem recalcular. " +
    "(7) 'atencao_territorial' traz as CORES DO MAPA: óbitos (SIM) e internações (SIH/SUS) de RESIDENTES por acidentes de " +
    "transporte terrestre, 2020-2024, por região de saúde e município, em todas as vias (federais, estaduais e urbanas). " +
    "Vermelho = atenção máxima, laranja = atenção alta, amarelo = abaixo da média do estado; a regra está em 'metodo'. " +
    "São contados no município de residência da vítima, não no local do sinistro; rodovias estaduais aparecem só como " +
    "traçado (OpenStreetMap), sem sinistros georreferenciados.\n\n" +
    "ÁREAS EM VERMELHO OU LARANJA (perguntas sobre o mapa, áreas críticas, onde há mais óbitos ou plano para uma região ou " +
    "município em vermelho): use 'atencao_territorial'. Diga a cor e o motivo com os números (taxa e quantas vezes a do " +
    "estado). Para o plano, use as quatro frentes de 'pacote_de_medidas' (gestão de velocidade, infraestrutura viária, " +
    "fiscalização eletrônica, educação e conscientização), adaptadas ao lugar: cite os municípios e as rodovias federais e " +
    "estaduais de 'onde_agir' ou do município, e quem executa (prefeitura e órgão municipal de trânsito, STRANS só em " +
    "Teresina, DETRAN-PI, SAMU, DER-PI nas rodovias estaduais, DNIT e PRF nas BRs). Se muitas mortes ocorrem na via " +
    "pública ('pct_via_publica'), destaque o socorro rápido (SAMU). Lembre a observação do Código de Trânsito sobre 50 " +
    "km/h. Responda em até 14 linhas, uma frente por linha com '- ', e diga que as medidas são propostas.\n\n" +
    "PERGUNTAS DE \"POR QUE\" (motivo, o que explica, fatores): não responda apenas que os dados não informam o " +
    "motivo. Explique com os FATORES ASSOCIADOS que aparecem nos dados (por exemplo, em 'perfil_por_br': trechos " +
    "rurais, pista simples, horário, tipo de colisão, causas e trechos, sempre comparando com a média) e diga " +
    "claramente que isso é associação, não prova de causa. Só depois, em uma frase, cite o que os dados não medem " +
    "(volume de tráfego, velocidade, tempo de socorro, tipo de veículo). Use até 8 linhas de texto simples.\n\n" +
    "Se a pergunta não puder ser respondida com esses dados, diga isso em uma frase e pare — não tente " +
    "compensar com informação não solicitada.\n\n" +
    "DADOS:\n" + JSON.stringify(contexto);

  const perfil = perfilDaPergunta(question);
  if(perfil === PERFIS_IA.analitico) loadingEl.lastChild.textContent = 'Analisando com mais profundidade (pode levar cerca de um minuto)...';
  const providers = [];
  if(usaGemini) providers.push({ nome: 'Gemini', call: () => callGemini(systemPrompt, question, perfil) });
  if(cfg.openrouter) OPENROUTER_MODELS.forEach(m => providers.push({
    nome: m.replace(/:free$/, ''), call: () => callOpenRouter(m, systemPrompt, question, perfil)
  }));

  try{
    const r = await askProviders(providers, msg => { loadingEl.lastChild.textContent = msg; });
    loadingEl.remove();
    const busca = palavrasEncontradas.length
      ? 'Trechos usados na busca: ' + palavrasEncontradas.join(', ')
      : 'Nenhuma palavra-chave reconhecida — visão geral enviada';
    appendMessage('ai', respostaHtml(r.text, r.cortada, busca + ' · Modelo: ' + escapeHtml(r.nome)));
    if(!r.cortada) cacheSet(question, { text: r.text, nome: r.nome });
  }catch(err){
    loadingEl.remove();
    appendMessage('ai', 'Não foi possível obter resposta:<br>' + escapeHtml(err.message).replace(/\n/g,'<br>'), 'error');
  }finally{
    setBusy(false);
  }
}

document.getElementById('askForm').addEventListener('submit', (e) => {
  e.preventDefault();
  if(busy) return;
  const input = document.getElementById('askInput');
  const q = input.value;
  input.value = '';
  askQuestion(q);
});

renderSuggestions();
loadData();
