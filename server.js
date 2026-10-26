// Servidor sem dependências (Node 18+): serve o painel e repassa as chamadas de IA ao
// Gemini/OpenRouter usando as chaves do arquivo .env (ou de variáveis de ambiente, como no Railway).
// Uso: node server.js
const http = require('http');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const ROOT = __dirname;

// Em hospedagens (Render, Railway etc.) as variáveis já vêm do ambiente e o servidor precisa ouvir em 0.0.0.0.
// A plataforma fornece PORT antes de o servidor iniciar; no seu computador PORT só aparece depois de ler o .env.
const NA_NUVEM = !!(process.env.RENDER || process.env.RAILWAY_ENVIRONMENT || process.env.RAILWAY_PROJECT_ID
  || process.env.NODE_ENV === 'production' || process.env.PORT);

// Lê o .env (linhas CHAVE=valor, # comentários); variáveis já definidas no ambiente têm prioridade.
function loadEnv(){
  let txt = '';
  try{ txt = fs.readFileSync(path.join(ROOT, '.env'), 'utf8'); }
  catch(_){
    if(!NA_NUVEM) console.warn('Aviso: arquivo .env não encontrado (copie .env.example para .env).');
    return;
  }
  for(const line of txt.split(/\r?\n/)){
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if(!m || line.trim().startsWith('#')) continue;
    const valor = m[2].replace(/^(['"])(.*)\1$/, '$2');
    if(!(m[1] in process.env)) process.env[m[1]] = valor;
  }
}
loadEnv();

const PORT = Number(process.env.PORT) || 8000;
// Fora da nuvem só aceita conexões da própria máquina, para ninguém na rede gastar suas chaves.
const HOST = process.env.HOST || (NA_NUVEM ? '0.0.0.0' : '127.0.0.1');
const GEMINI_KEY = (process.env.GEMINI_API_KEY || '').trim();
const OPENROUTER_KEY = (process.env.OPENROUTER_API_KEY || '').trim();
const MAX_BODY = 300 * 1024;
const MAX_TOKENS = 8192;   // teto de saída (inclui os tokens de raciocínio)
const NIVEIS_RACIOCINIO = ['minimal', 'low', 'medium', 'high'];

// Limites de uso (só valem quando o servidor está exposto: nuvem ou HOST diferente de 127.0.0.1).
const LIMITAR = HOST !== '127.0.0.1';
const LIMITE_IP_HORA = Number(process.env.LIMITE_IP_POR_HORA) || 40;   // chamadas de IA por IP por hora
const LIMITE_DIA = Number(process.env.LIMITE_TOTAL_POR_DIA) || 800;    // chamadas de IA por dia, somando todos

const TIPOS = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8'
};

function sendJson(res, status, obj, extra = {}){
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', ...extra });
  res.end(JSON.stringify(obj));
}

function readBody(req){
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => {
      size += c.length;
      if(size > MAX_BODY){ reject(new Error('corpo grande demais')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

/* ---------------------------------------------------------------- limite de uso */
const usoPorIp = new Map();   // ip -> instantes das chamadas na última hora
let diaAtual = '';
let usoDoDia = 0;

// Atrás do proxy da hospedagem o IP real vem em X-Forwarded-For; o último valor é o que o proxy anexou.
function ipDoCliente(req){
  const xff = String(req.headers['x-forwarded-for'] || '').split(',').map(s => s.trim()).filter(Boolean);
  return xff.length ? xff[xff.length - 1] : req.socket.remoteAddress;
}

// Devolve uma mensagem se o limite foi atingido; senão registra a chamada e devolve null.
function verificarLimite(req){
  if(!LIMITAR) return null;
  const agora = Date.now();
  const hoje = new Date().toISOString().slice(0, 10);
  if(hoje !== diaAtual){ diaAtual = hoje; usoDoDia = 0; }
  if(usoDoDia >= LIMITE_DIA) return 'O limite diário de uso da IA foi atingido. Tente amanhã ou use as perguntas prontas.';
  const ip = ipDoCliente(req);
  const marcas = (usoPorIp.get(ip) || []).filter(t => agora - t < 3600e3);
  if(marcas.length >= LIMITE_IP_HORA) return 'Você atingiu o limite de consultas à IA por hora. Tente mais tarde ou use as perguntas prontas.';
  marcas.push(agora);
  usoPorIp.set(ip, marcas);
  usoDoDia++;
  return null;
}
setInterval(() => {
  const agora = Date.now();
  for(const [ip, marcas] of usoPorIp){
    const recentes = marcas.filter(t => agora - t < 3600e3);
    if(recentes.length) usoPorIp.set(ip, recentes); else usoPorIp.delete(ip);
  }
}, 10 * 60 * 1000).unref();

/* ---------------------------------------------------------------- proxy de IA */
// Valida e limita o corpo antes de gastar a chave: só modelos gratuitos do OpenRouter, saída limitada.
function prepararCorpo(rota, bruto){
  let j;
  try{ j = JSON.parse(bruto); }catch(_){ return { erro: 'JSON inválido' }; }
  if(!j || typeof j !== 'object') return { erro: 'corpo inválido' };
  if(rota === 'gemini'){
    j.generationConfig = j.generationConfig || {};
    j.generationConfig.maxOutputTokens = Math.min(Number(j.generationConfig.maxOutputTokens) || 2048, MAX_TOKENS);
    const tc = j.generationConfig.thinkingConfig;
    if(tc && typeof tc === 'object'){
      delete tc.thinkingBudget;                                  // nada de orçamentos livres
      if(!NIVEIS_RACIOCINIO.includes(tc.thinkingLevel)) delete tc.thinkingLevel;
    }
  }else{
    if(typeof j.model !== 'string' || !/^[\w.\/-]+:free$/.test(j.model)) return { erro: 'só modelos gratuitos (sufixo :free) são permitidos' };
    j.max_tokens = Math.min(Number(j.max_tokens) || 2048, MAX_TOKENS);
    if(j.reasoning && typeof j.reasoning === 'object'){
      delete j.reasoning.max_tokens;
      if(!['low', 'medium', 'high'].includes(j.reasoning.effort)) delete j.reasoning.effort;
    }else{
      delete j.reasoning;
    }
  }
  return { corpo: JSON.stringify(j) };
}

// Cota diária esgotada: lembra até quando e deixa de chamar o provedor (a cota é por modelo no Gemini).
const esgotadoAte = {};   // 'gemini:MODELO' | 'openrouter' -> instante (ms) em que a cota deve voltar

function segundosRestantes(chave){
  return Math.max(0, Math.ceil(((esgotadoAte[chave] || 0) - Date.now()) / 1000));
}

// Lê do erro do provedor quanto tempo falta para liberar ("retryDelay": "44574s" ou "retry in 12h12m54s").
function segundosDeEspera(texto, cabecalho){
  let m = texto.match(/"retryDelay"\s*:\s*"([\d.]+)s"/);
  if(m) return Math.ceil(Number(m[1]));
  m = texto.match(/retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?/i);
  if(m && (m[1] || m[2] || m[3])) return Math.ceil((Number(m[1]) || 0) * 3600 + (Number(m[2]) || 0) * 60 + (Number(m[3]) || 0));
  return Number(cabecalho) || 0;
}

// Repassa o corpo ao provedor e devolve status e corpo; se a cota diária acabou, avisa com x-esgotado.
async function proxy(res, url, headers, body, chave){
  let up;
  try{
    up = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body });
  }catch(err){
    return sendJson(res, 502, { error: { message: 'servidor não conseguiu falar com o provedor (' + err.message + ')' } });
  }
  const extra = {};
  const ra = up.headers.get('retry-after');
  if(ra) extra['retry-after'] = ra;
  const buf = Buffer.from(await up.arrayBuffer());
  if(up.status === 429){
    const texto = buf.toString('utf8');
    const seg = segundosDeEspera(texto, ra);
    if(seg >= 600 || /per ?day|perday|daily|por dia/i.test(texto)){
      const espera = Math.min(seg || 6 * 3600, 24 * 3600);
      esgotadoAte[chave] = Date.now() + espera * 1000;
      extra['x-esgotado'] = '1';
      extra['retry-after'] = String(espera);
      console.log(`Cota diária esgotada em ${chave}; sem novas chamadas por ${Math.round(espera / 60)} min`);
    }
  }
  res.writeHead(up.status, { 'content-type': up.headers.get('content-type') || 'application/json', ...extra });
  res.end(buf);
}

async function handleApi(req, res, url){
  if(req.method === 'GET' && url.pathname === '/api/config'){
    // esgotado: segundos até a cota diária voltar, por provedor/modelo (só os que estão esgotados agora)
    const esgotado = {};
    for(const k of Object.keys(esgotadoAte)){ const s = segundosRestantes(k); if(s > 0) esgotado[k] = s; }
    return sendJson(res, 200, { gemini: !!GEMINI_KEY, openrouter: !!OPENROUTER_KEY && !esgotado.openrouter, esgotado });
  }
  if(req.method !== 'POST') return sendJson(res, 405, { error: { message: 'método não permitido' } });

  const rota = url.pathname === '/api/gemini' ? 'gemini' : url.pathname === '/api/openrouter' ? 'openrouter' : null;
  if(!rota) return sendJson(res, 404, { error: { message: 'rota não encontrada' } });
  if(rota === 'gemini' && !GEMINI_KEY) return sendJson(res, 503, { error: { message: 'GEMINI_API_KEY não configurada' } });
  if(rota === 'openrouter' && !OPENROUTER_KEY) return sendJson(res, 503, { error: { message: 'OPENROUTER_API_KEY não configurada' } });

  let bruto;
  try{ bruto = await readBody(req); }
  catch(err){ return sendJson(res, 413, { error: { message: err.message } }); }
  const prep = prepararCorpo(rota, bruto);
  if(prep.erro) return sendJson(res, 400, { error: { message: prep.erro } });

  let model = '';
  if(rota === 'gemini'){
    model = url.searchParams.get('model') || '';
    if(!/^gemini-[A-Za-z0-9._-]+$/.test(model)) return sendJson(res, 400, { error: { message: 'modelo inválido' } });
  }

  // cota diária já esgotada: responde sem chamar o provedor e sem gastar o limite de uso do visitante
  const chave = rota === 'gemini' ? 'gemini:' + model : 'openrouter';
  const falta = segundosRestantes(chave);
  if(falta > 0){
    return sendJson(res, 429, { error: { message: 'cota diária gratuita esgotada neste provedor' } },
      { 'x-esgotado': '1', 'retry-after': String(falta) });
  }

  const limite = verificarLimite(req);
  if(limite) return sendJson(res, 429, { error: { message: limite } }, { 'x-limite': '1', 'retry-after': '3600' });

  if(rota === 'gemini'){
    return proxy(res, `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
      { 'x-goog-api-key': GEMINI_KEY }, prep.corpo, chave);
  }
  return proxy(res, 'https://openrouter.ai/api/v1/chat/completions',
    { 'Authorization': 'Bearer ' + OPENROUTER_KEY }, prep.corpo, chave);
}

/* ---------------------------------------------------------------- arquivos estáticos */
const cache = new Map();   // arquivo -> { mtimeMs, buf, gz }

// Só serve os arquivos do painel; .env, server.js e .git nunca saem daqui.
function serveStatic(req, res, pathname){
  let rel;
  try{ rel = decodeURIComponent(pathname); }catch(_){ rel = ''; }
  if(rel === '/') rel = '/index.html';
  const permitido = ['/index.html', '/script.js', '/style.css'].includes(rel) || /^\/data\/[\w.-]+\.json$/.test(rel);
  const arquivo = path.join(ROOT, rel);
  if(!permitido || !arquivo.startsWith(ROOT + path.sep)){
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    return res.end('Não encontrado');
  }
  fs.stat(arquivo, (err, info) => {
    if(err){ res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }); return res.end('Não encontrado'); }
    let ent = cache.get(arquivo);
    if(!ent || ent.mtimeMs !== info.mtimeMs){
      let buf;
      try{ buf = fs.readFileSync(arquivo); }catch(_){ res.writeHead(404); return res.end(); }
      ent = { mtimeMs: info.mtimeMs, buf, gz: zlib.gzipSync(buf) };
      cache.set(arquivo, ent);
    }
    const cabecalhos = {
      'content-type': TIPOS[path.extname(arquivo)] || 'application/octet-stream',
      'cache-control': 'public, max-age=300',
      'vary': 'accept-encoding'
    };
    const gzip = /\bgzip\b/.test(req.headers['accept-encoding'] || '');
    if(gzip) cabecalhos['content-encoding'] = 'gzip';
    res.writeHead(200, cabecalhos);
    res.end(req.method === 'HEAD' ? undefined : (gzip ? ent.gz : ent.buf));
  });
}

http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if(url.pathname === '/healthz'){ res.writeHead(200, { 'content-type': 'text/plain' }); return res.end('ok'); }
  if(url.pathname.startsWith('/api/')) return handleApi(req, res, url).catch(err => sendJson(res, 500, { error: { message: err.message } }));
  if(req.method !== 'GET' && req.method !== 'HEAD'){ res.writeHead(405); return res.end(); }
  serveStatic(req, res, url.pathname);
}).listen(PORT, HOST, () => {
  console.log(`Servidor em http://${HOST === '127.0.0.1' ? 'localhost' : HOST}:${PORT}${NA_NUVEM ? ' (modo nuvem)' : ''}`);
  console.log(`Gemini: ${GEMINI_KEY ? 'chave carregada' : 'sem chave'} | OpenRouter: ${OPENROUTER_KEY ? 'chave carregada' : 'sem chave'}`);
  if(LIMITAR) console.log(`Limites de IA: ${LIMITE_IP_HORA}/hora por IP, ${LIMITE_DIA}/dia no total`);
});
