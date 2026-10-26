"""Gera data/sinistros.json -> interpretacao_prf_piaui: conclusões já calculadas (em texto) sobre
os dados da PRF para o assistente citar. Rode depois de scripts/importar_prf.py.
Uso: python scripts/interpretar_prf.py"""
import csv, collections, datetime, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'data', 'prf_acidentes_pi.csv')
JS = os.path.join(ROOT, 'data', 'sinistros.json')

rows = list(csv.DictReader(open(CSV, encoding='utf-8', newline='')))
for r in rows:
    for c in ['pessoas', 'mortos', 'feridos_leves', 'feridos_graves', 'ilesos', 'veiculos']:
        r[c] = int(r[c])
    r['ano'] = int(r['data_inversa'][:4])
    r['mes'] = int(r['data_inversa'][5:7])
    r['dia'] = r['data_inversa'][5:]  # MM-DD
    r['hora'] = int(r['horario'][:2])
    r['km_f'] = float(r['km']) if r['km'] not in ('', 'NA') else None
N = len(rows)
TOTAL_MORTOS = sum(r['mortos'] for r in rows)

# ---------------------------------------------------------------- helpers
def pc(x, casas=1):
    return f'{x:.{casas}f}'.replace('.', ',') + '%'

def num(x):
    return f'{x:,}'.replace(',', '.')

def dec(x, casas=1):
    return f'{x:.{casas}f}'.replace('.', ',')

def mud(v):
    return ('alta de ' if v > 0 else 'queda de ' if v < 0 else 'variação de ') + dec(abs(v)) + '%'

def share(a, b):
    return 100 * a / b if b else 0.0

def stats(rs):
    n = len(rs)
    m = sum(r['mortos'] for r in rs)
    g = sum(r['feridos_graves'] for r in rs)
    return {'ocorrencias': n, 'mortos': m, 'feridos_graves': g,
            'mortos_por_100_ocorrencias': round(100 * m / n, 1) if n else None}

def grp(key, rs=None):
    g = collections.defaultdict(list)
    for r in (rs if rs is not None else rows):
        g[key(r)].append(r)
    return g

def top(g, by, n=3, minimo=0):
    its = [(k, stats(v)) for k, v in g.items() if len(v) >= minimo]
    its.sort(key=lambda kv: (-(kv[1][by] if kv[1][by] is not None else -1), -kv[1]['ocorrencias'], str(kv[0])))
    return its[:n]

ACENTOS = {'PARNAIBA': 'Parnaíba', 'LOBAO': 'Lobão', 'PIAUI': 'Piauí', 'JOSE': 'José', 'JOAO': 'João',
           'GONCALO': 'Gonçalo', 'CONCEICAO': 'Conceição', 'LUIS': 'Luís', 'SAO ': 'São '}
SMALL = {'Do', 'Da', 'De', 'Dos', 'Das'}

def bonito(nome):
    s = nome
    marks = []
    for k, v in ACENTOS.items():
        s = s.replace(k, '\0' + v + '\0')
    out = ''.join(c if c in ACENTOS.values() else c.title() for c in s.split('\0'))
    return ' '.join(w.lower() if w in SMALL else w for w in out.split(' '))

def lista(itens):
    itens = list(itens)
    if len(itens) <= 1:
        return ''.join(itens)
    return ', '.join(itens[:-1]) + ' e ' + itens[-1]

FONTE = 'Dados da PRF: só rodovias federais (BRs) no Piauí, não incluem vias estaduais nem urbanas.'
geral = stats(rows)
let_geral = geral['mortos_por_100_ocorrencias']

# ---------------------------------------------------------------- visão geral
DATAS = sorted(r['data_inversa'] for r in rows)
DMIN, DMAX = DATAS[0], DATAS[-1]
def br_data(s):
    return f'{s[8:10]}/{s[5:7]}/{s[:4]}'
TODOS_ANOS = sorted({r['ano'] for r in rows})
ANO_PARCIAL = int(DMAX[:4]) if DMAX[5:] < '12-31' else None
anos_cheios = [y for y in TODOS_ANOS if y != ANO_PARCIAL]
A0, A1 = anos_cheios[0], anos_cheios[-1]
NCHEIOS = len(anos_cheios)
por_ano = {y: stats([r for r in rows if r['ano'] == y]) for y in TODOS_ANOS}
media_ocorr = sum(por_ano[y]['ocorrencias'] for y in anos_cheios) / NCHEIOS
media_mortos = sum(por_ano[y]['mortos'] for y in anos_cheios) / NCHEIOS
com_fatais = sum(1 for r in rows if r['classificacao_acidente'] == 'Com Vítimas Fatais')
com_feridos = sum(1 for r in rows if r['classificacao_acidente'] == 'Com Vítimas Feridas')
visao_geral = {
    'resumo': (f'Entre {br_data(DMIN)} e {br_data(DMAX)} a PRF registrou {num(N)} acidentes em rodovias federais do Piauí, '
               f'com {num(TOTAL_MORTOS)} mortos e {num(geral["feridos_graves"])} feridos graves. '
               f'Nos anos completos ({A0} a {A1}) a média é de {num(round(media_ocorr))} acidentes e {num(round(media_mortos))} mortos por ano. '
               f'{pc(share(com_fatais, N))} dos acidentes tiveram morte e {pc(share(com_feridos, N))} tiveram feridos sem mortes. '
               f'Há cerca de {dec(let_geral)} mortos para cada 100 acidentes. {FONTE}'),
    'numeros': {'ocorrencias': N, 'mortos': TOTAL_MORTOS, 'feridos_graves': geral['feridos_graves'],
                'media_anual_ocorrencias_anos_completos': round(media_ocorr), 'media_anual_mortos_anos_completos': round(media_mortos),
                'pct_ocorrencias_com_mortes': round(share(com_fatais, N), 1), 'mortos_por_100_ocorrencias': let_geral}
}

# ---------------------------------------------------------------- evolução
def var(a, b):
    return round(100 * (b - a) / a, 1) if a else None

o20, o25 = por_ano[A0]['ocorrencias'], por_ano[A1]['ocorrencias']
m20, m25 = por_ano[A0]['mortos'], por_ano[A1]['mortos']
o24, m24 = por_ano[A1 - 1]['ocorrencias'], por_ano[A1 - 1]['mortos']
pico_o = max(anos_cheios, key=lambda y: por_ano[y]['ocorrencias'])
pico_m = max(anos_cheios, key=lambda y: por_ano[y]['mortos'])
menor_m = min(anos_cheios, key=lambda y: por_ano[y]['mortos'])
serie = '; '.join(f'{y}: {num(por_ano[y]["ocorrencias"])} acidentes e {por_ano[y]["mortos"]} mortos' for y in anos_cheios)
FIM = DMAX[5:]
mesmo_periodo = lambda y: [r for r in rows if r['ano'] == y and r['dia'] <= FIM]
if ANO_PARCIAL:
    p25, p26 = stats(mesmo_periodo(ANO_PARCIAL - 1)), stats(mesmo_periodo(ANO_PARCIAL))
evolucao = {
    'pergunta_exemplo': 'Como evoluiu o número de acidentes e de mortos nas rodovias federais do Piauí?',
    'resumo': (f'Série anual (PRF): {serie}. De {A0} a {A1} os acidentes tiveram {mud(var(o20, o25))} ({num(o20)} para {num(o25)}) '
               f'e os mortos tiveram {mud(var(m20, m25))} ({m20} para {m25}). '
               f'O ano com mais acidentes foi {pico_o} ({num(por_ano[pico_o]["ocorrencias"])}) e o com mais mortos foi {pico_m} ({por_ano[pico_m]["mortos"]}); '
               f'o com menos mortos foi {menor_m} ({por_ano[menor_m]["mortos"]}). De {A1 - 1} para {A1} os acidentes tiveram {mud(var(o24, o25))} e os mortos {mud(var(m24, m25))}. '
               f'{FONTE}'),
    'numeros': {'variacao_ocorrencias_primeiro_ultimo_ano_completo_pct': var(o20, o25), 'variacao_mortos_primeiro_ultimo_ano_completo_pct': var(m20, m25),
                'variacao_ocorrencias_ultimos_dois_anos_completos_pct': var(o24, o25), 'variacao_mortos_ultimos_dois_anos_completos_pct': var(m24, m25),
                'ano_pico_ocorrencias': pico_o, 'ano_pico_mortos': pico_m}
}
ano_parcial = None if not ANO_PARCIAL else {
    'pergunta_exemplo': f'E {ANO_PARCIAL}, está melhor ou pior que {ANO_PARCIAL - 1}?',
    'resumo': (f'{ANO_PARCIAL} é parcial (até {br_data(DMAX)}): {num(p26["ocorrencias"])} acidentes e {p26["mortos"]} mortos. No mesmo período de {ANO_PARCIAL - 1} (01/01 a {FIM[3:]}/{FIM[:2]}) '
               f'foram {num(p25["ocorrencias"])} acidentes e {p25["mortos"]} mortos, ou seja, {mud(var(p25["ocorrencias"], p26["ocorrencias"]))} nos acidentes '
               f'e {mud(var(p25["mortos"], p26["mortos"]))} nos mortos. Não compare {ANO_PARCIAL} inteiro com anos completos. {FONTE}'),
    'numeros': {'mesmo_periodo_ano_anterior': p25, 'ano_parcial': p26,
                'variacao_ocorrencias_pct': var(p25['ocorrencias'], p26['ocorrencias']), 'variacao_mortos_pct': var(p25['mortos'], p26['mortos'])}
}

# ---------------------------------------------------------------- rodovias
g_br = grp(lambda r: r['br'])
br_ocorr = top(g_br, 'ocorrencias', 3)
br_mortos = top(g_br, 'mortos', 3)
br_let = top({k: v for k, v in g_br.items() if k != '0'}, 'mortos_por_100_ocorrencias', 3, minimo=100)
fmt_br = lambda k, s: f'BR-{k} ({num(s["ocorrencias"])} acidentes, {s["mortos"]} mortos)'
outras_let = [k for k, _ in br_let if k not in [x for x, _ in br_ocorr]]
rodovias = {
    'pergunta_exemplo': 'Qual a rodovia federal mais perigosa do Piauí?',
    'resumo': (f'Em volume de acidentes lideram {lista(fmt_br(k, s) for k, s in br_ocorr)}. ' + ('As mesmas três lideram também em número de mortos. ' if [k for k, _ in br_ocorr] == [k for k, _ in br_mortos] else f'Em número de mortos: {lista(fmt_br(k, s) for k, s in br_mortos)}. ') +
               f'Em gravidade (mortos por 100 acidentes, só BRs com 100 ou mais acidentes): '
               f'{lista(f"BR-{k} ({dec(s["mortos_por_100_ocorrencias"])})" for k, s in br_let)}, contra {dec(let_geral)} na média. '
               + (f'A gravidade não acompanha o volume: {lista("BR-" + k for k in outras_let)} {"aparecem" if len(outras_let) > 1 else "aparece"} entre as mais letais por acidente sem estar entre as mais movimentadas. ' if outras_let else '')
               + FONTE),
    'numeros': {'por_br': {f'BR-{k}': stats(v) for k, v in sorted(g_br.items(), key=lambda kv: -len(kv[1])) if k != '0'}}
}

# ---------------------------------------------------------------- municípios
g_mun = grp(lambda r: r['municipio'])
mun_o = top(g_mun, 'ocorrencias', 5)
mun_m = top(g_mun, 'mortos', 5)
ter = stats(g_mun['TERESINA'])
municipios = {
    'pergunta_exemplo': 'Quais municípios têm mais acidentes e mais mortes nas rodovias federais?',
    'resumo': (f'Mais acidentes: {lista(f"{bonito(k)} ({num(s["ocorrencias"])})" for k, s in mun_o)}. '
               f'Mais mortos: {lista(f"{bonito(k)} ({s["mortos"]})" for k, s in mun_m)}. '
               f'Teresina concentra {pc(share(ter["ocorrencias"], N))} dos acidentes e {pc(share(ter["mortos"], TOTAL_MORTOS))} dos mortos das BRs do estado, '
               f'com gravidade {"menor" if ter["mortos_por_100_ocorrencias"] < let_geral else "maior"} ({dec(ter["mortos_por_100_ocorrencias"])} mortos por 100 acidentes) que a média ({dec(let_geral)}). Os dados são só das BRs que passam pelo município. {FONTE}'),
    'numeros': {'teresina': ter, 'pct_ocorrencias_teresina': round(share(ter['ocorrencias'], N), 1),
                'pct_mortos_teresina': round(share(ter['mortos'], TOTAL_MORTOS), 1)}
}

# ---------------------------------------------------------------- trechos críticos (janela de 5 km)
def seg(r):
    return None if (r['km_f'] is None or r['br'] == '0') else (r['br'], int(r['km_f'] // 5) * 5)
g_seg = {k: v for k, v in grp(seg).items() if k is not None}
seg_o = sorted(g_seg.items(), key=lambda kv: (-len(kv[1]), -sum(r['mortos'] for r in kv[1]), kv[0]))
seg_m = sorted(g_seg.items(), key=lambda kv: (-sum(r['mortos'] for r in kv[1]), -len(kv[1]), kv[0]))
def seg_txt(kv):
    k, v = kv
    s = stats(v)
    mun = bonito(collections.Counter(r['municipio'] for r in v).most_common(1)[0][0])
    return f'BR-{k[0]} km {k[1]} a {k[1] + 5} ({mun}: {num(s["ocorrencias"])} acidentes, {s["mortos"]} mortos)'
top10 = sum(len(v) for _, v in seg_o[:10])
ter10 = sum(1 for _, v in seg_o[:10] if collections.Counter(r['municipio'] for r in v).most_common(1)[0][0] == 'TERESINA')
trechos = {
    'pergunta_exemplo': 'Onde (que trecho ou km) acontecem mais acidentes e mais mortes?',
    'resumo': (f'Trechos com mais acidentes (janelas de 5 km): {"; ".join(seg_txt(kv) for kv in seg_o[:5])}. '
               f'Trechos com mais mortos: {"; ".join(seg_txt(kv) for kv in seg_m[:5])}. '
               f'Os 10 trechos mais movimentados concentram {pc(share(top10, N))} de todos os acidentes; {ter10} desses 10 trechos ficam em Teresina. {FONTE}'),
    'numeros': {'pct_ocorrencias_nos_10_trechos_mais_movimentados': round(share(top10, N), 1)}
}

# ---------------------------------------------------------------- causas
g_causa = grp(lambda r: r['causa_acidente'])
c_o = top(g_causa, 'ocorrencias', 5)
c_m = top(g_causa, 'mortos', 5)
c_let = top(g_causa, 'mortos_por_100_ocorrencias', 3, minimo=50)
alc = stats(g_causa.get('Ingestão de álcool pelo condutor', []))
vel = stats(g_causa.get('Velocidade Incompatível', []))
anim = stats(g_causa.get('Animais na Pista', []))
dorm = stats(g_causa.get('Condutor Dormindo', []))
causas = {
    'pergunta_exemplo': 'Quais as principais causas dos acidentes nas rodovias federais do Piauí?',
    'resumo': (f'Causas mais frequentes: {lista(f"{k.lower()} ({num(s["ocorrencias"])}, {pc(share(s["ocorrencias"], N))})" for k, s in c_o)}. '
               f'Causas com mais mortos: {lista(f"{k.lower()} ({s["mortos"]})" for k, s in c_m)}. '
               f'Mais letais por acidente (causas com 50 ou mais acidentes): {lista(f"{k.lower()} ({dec(s["mortos_por_100_ocorrencias"])} mortos por 100)" for k, s in c_let)}. Atenção: em 2020 a PRF usava categorias de causa mais genéricas (ex.: desobediência às normas de trânsito pelo condutor, 242 acidentes só em 2020), então compare causas entre anos com cautela. {FONTE}'),
    'numeros': {'alcool_condutor': alc, 'velocidade_incompativel': vel, 'animais_na_pista': anim, 'condutor_dormindo': dorm}
}
alcool = {
    'pergunta_exemplo': 'O álcool contribui para os acidentes?',
    'resumo': (f'A ingestão de álcool pelo condutor foi a causa de {num(alc["ocorrencias"])} acidentes ({pc(share(alc["ocorrencias"], N))} do total) e de {alc["mortos"]} mortos '
               f'({pc(share(alc["mortos"], TOTAL_MORTOS))} do total), com {dec(alc["mortos_por_100_ocorrencias"])} mortos por 100 acidentes, contra {dec(let_geral)} na média. '
               f'Só conta quando a PRF registrou o álcool como causa. {FONTE}'),
    'numeros': {'alcool_condutor': alc, 'pct_ocorrencias': round(share(alc['ocorrencias'], N), 1), 'pct_mortos': round(share(alc['mortos'], TOTAL_MORTOS), 1)}
}

# ---------------------------------------------------------------- tipos de acidente
g_tipo = grp(lambda r: r['tipo_acidente'])
t_o = top(g_tipo, 'ocorrencias', 4)
t_m = top(g_tipo, 'mortos', 4)
t_let = top(g_tipo, 'mortos_por_100_ocorrencias', 3, minimo=50)
tipos = {
    'pergunta_exemplo': 'Quais os tipos de acidente mais comuns e mais letais?',
    'resumo': (f'Mais comuns: {lista(f"{k.lower()} ({num(s["ocorrencias"])})" for k, s in t_o)}. Com mais mortos: {lista(f"{k.lower()} ({s["mortos"]})" for k, s in t_m)}. '
               f'Mais letais por acidente (tipos com 50 ou mais acidentes): {lista(f"{k.lower()} ({dec(s["mortos_por_100_ocorrencias"])} mortos por 100)" for k, s in t_let)}. '
               f'A PRF não informa o tipo de veículo neste arquivo, então não dá para separar motos de carros. {FONTE}'),
    'numeros': {}
}

# ---------------------------------------------------------------- horário
g_h = grp(lambda r: r['hora'])
h_o = top(g_h, 'ocorrencias', 3)
h_m = top(g_h, 'mortos', 3)
def per(r):
    h = r['hora']
    return 'madrugada' if h < 6 else 'manhã' if h < 12 else 'tarde' if h < 18 else 'noite'
g_p = grp(per)
ps = {k: stats(v) for k, v in g_p.items()}
noite_mad_m = ps['noite']['mortos'] + ps['madrugada']['mortos']
noite_mad_o = ps['noite']['ocorrencias'] + ps['madrugada']['ocorrencias']
horario = {
    'pergunta_exemplo': 'Em que horário acontecem mais acidentes e mais mortes?',
    'resumo': (f'Mais acidentes por hora: {lista(f"{k:02d}h ({num(s["ocorrencias"])})" for k, s in h_o)}. Mais mortos por hora: {lista(f"{k:02d}h ({s["mortos"]})" for k, s in h_m)}. '
               f'Por período: ' + '; '.join(f'{p} {num(ps[p]["ocorrencias"])} acidentes, {ps[p]["mortos"]} mortos, {dec(ps[p]["mortos_por_100_ocorrencias"])} mortos por 100 acidentes' for p in ['madrugada', 'manhã', 'tarde', 'noite']) +
               f'. A noite e a madrugada (18h às 5h59) reúnem {pc(share(noite_mad_o, N))} dos acidentes, mas {pc(share(noite_mad_m, TOTAL_MORTOS))} dos mortos; '
               f'o período mais letal por acidente é a {max(ps, key=lambda p: ps[p]["mortos_por_100_ocorrencias"])}. {FONTE}'),
    'numeros': {'por_periodo': ps, 'pct_ocorrencias_noite_madrugada': round(share(noite_mad_o, N), 1), 'pct_mortos_noite_madrugada': round(share(noite_mad_m, TOTAL_MORTOS), 1)}
}

# ---------------------------------------------------------------- dia da semana
g_d = grp(lambda r: r['dia_semana'])
ds = {k: stats(v) for k, v in g_d.items()}
fds = ['sábado', 'domingo']
fds_o = sum(ds[k]['ocorrencias'] for k in fds)
fds_m = sum(ds[k]['mortos'] for k in fds)
d_o = top(g_d, 'ocorrencias', 3)
d_m = top(g_d, 'mortos', 3)
dia_semana = {
    'pergunta_exemplo': 'Quais dias da semana têm mais acidentes? E fim de semana?',
    'resumo': (f'Mais acidentes: {lista(f"{k} ({num(s["ocorrencias"])})" for k, s in d_o)}. Mais mortos: {lista(f"{k} ({s["mortos"]})" for k, s in d_m)}. '
               f'Sábado e domingo concentram {pc(share(fds_o, N))} dos acidentes e {pc(share(fds_m, TOTAL_MORTOS))} dos mortos (dois dos sete dias seriam 28,6%). {FONTE}'),
    'numeros': {'por_dia': ds, 'pct_ocorrencias_fim_de_semana': round(share(fds_o, N), 1), 'pct_mortos_fim_de_semana': round(share(fds_m, TOTAL_MORTOS), 1)}
}

# ---------------------------------------------------------------- mês (anos completos)
NOMES_MES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
cheios = [r for r in rows if r['ano'] in anos_cheios]
g_m = grp(lambda r: r['mes'], cheios)
m_o = top(g_m, 'ocorrencias', 3)
m_menos = sorted(((k, stats(v)) for k, v in g_m.items()), key=lambda kv: kv[1]['ocorrencias'])[:2]
m_mort = top(g_m, 'mortos', 3)
mes = {
    'pergunta_exemplo': 'Em quais meses acontecem mais acidentes?',
    'resumo': (f'Somando os anos completos ({A0} a {A1}), os meses com mais acidentes são {lista(f"{NOMES_MES[k - 1]} ({num(s["ocorrencias"])})" for k, s in m_o)}; '
               f'os com mais mortos são {lista(f"{NOMES_MES[k - 1]} ({s["mortos"]})" for k, s in m_mort)}; os com menos acidentes são {lista(f"{NOMES_MES[k - 1]} ({num(s["ocorrencias"])})" for k, s in m_menos)}. {FONTE}'),
    'numeros': {NOMES_MES[k - 1]: stats(v) for k, v in sorted(g_m.items())}
}

# ---------------------------------------------------------------- clima, urbano/rural, pista
g_cl = grp(lambda r: r['condicao_metereologica'])
cs = {k: stats(v) for k, v in g_cl.items()}
chuva = [cs[k] for k in ('Chuva', 'Garoa/Chuvisco') if k in cs]
ch_o = sum(s['ocorrencias'] for s in chuva)
ch_m = sum(s['mortos'] for s in chuva)
clima = {
    'pergunta_exemplo': 'A chuva aumenta os acidentes?',
    'resumo': (f'A maioria dos acidentes ocorre com tempo bom: céu claro {pc(share(cs["Céu Claro"]["ocorrencias"], N))}, sol {pc(share(cs["Sol"]["ocorrencias"], N))}, nublado {pc(share(cs["Nublado"]["ocorrencias"], N))}. '
               f'Chuva e garoa somam {num(ch_o)} acidentes ({pc(share(ch_o, N))}) e {ch_m} mortos, com {dec(100 * ch_m / ch_o)} mortos por 100 acidentes (média {dec(let_geral)}). '
               f'Isso mostra que o clima não é a principal causa; mas não dá para afirmar que a chuva é mais perigosa sem comparar com o volume de tráfego. {FONTE}'),
    'numeros': {'por_condicao': cs}
}
urb = stats([r for r in rows if r['uso_solo'] == 'Sim'])
rur = stats([r for r in rows if r['uso_solo'] == 'Não'])
urbano_rural = {
    'pergunta_exemplo': 'Os acidentes são mais urbanos ou rurais?',
    'resumo': (f'Em trechos com predominância de construções (urbano) foram {num(urb["ocorrencias"])} acidentes ({pc(share(urb["ocorrencias"], N))}) e {urb["mortos"]} mortos, '
               f'{dec(urb["mortos_por_100_ocorrencias"])} mortos por 100 acidentes. Em trechos sem construções (rural) foram {num(rur["ocorrencias"])} acidentes e {rur["mortos"]} mortos '
               f'({pc(share(rur["mortos"], TOTAL_MORTOS))} do total), {dec(rur["mortos_por_100_ocorrencias"])} mortos por 100 acidentes. Os acidentes rurais são bem mais letais. {FONTE}'),
    'numeros': {'urbano': urb, 'rural': rur}
}
g_pista = grp(lambda r: r['tipo_pista'])
pi = {k: stats(v) for k, v in g_pista.items()}
curva = stats([r for r in rows if 'Curva' in r['tracado_via']])
pista_tracado = {
    'pergunta_exemplo': 'Pista simples é mais perigosa que pista dupla?',
    'resumo': ('Por tipo de pista: ' + '; '.join(f'{k.lower()} {num(s["ocorrencias"])} acidentes, {s["mortos"]} mortos, {dec(s["mortos_por_100_ocorrencias"])} mortos por 100 acidentes' for k, s in sorted(pi.items(), key=lambda kv: -kv[1]['ocorrencias'])) +
               f'. Pista simples concentra {pc(share(pi["Simples"]["mortos"], TOTAL_MORTOS))} dos mortos. Em curvas: {num(curva["ocorrencias"])} acidentes ({pc(share(curva["ocorrencias"], N))}) e {curva["mortos"]} mortos, {dec(curva["mortos_por_100_ocorrencias"])} por 100 acidentes. {FONTE}'),
    'numeros': {'por_tipo_pista': pi, 'curvas': curva}
}

# ---------------------------------------------------------------- perfil por rodovia (para responder "por que a BR-X é letal?")
def _noite(r):
    return r['hora'] >= 18 or r['hora'] < 6


def _tem(rs, f):
    return share(sum(1 for r in rs if f(r)), len(rs)) if rs else 0.0


def _cmp(v, ref):
    return 'acima da média' if v > ref + 3 else 'abaixo da média' if v < ref - 3 else 'próximo da média'


REF = {
    'rural': _tem(rows, lambda r: r['uso_solo'] == 'Não'),
    'simples': _tem(rows, lambda r: r['tipo_pista'] == 'Simples'),
    'noite': _tem(rows, _noite),
    'frontal': _tem(rows, lambda r: r['tipo_acidente'] == 'Colisão frontal'),
    'contramao': _tem(rows, lambda r: r['causa_acidente'] == 'Transitar na contramão'),
}
perfil_por_br = {}
for br, rs in sorted(g_br.items(), key=lambda kv: -len(kv[1])):
    if br == '0' or len(rs) < 100:
        continue
    s_ = stats(rs)
    v = {
        'rural': _tem(rs, lambda r: r['uso_solo'] == 'Não'),
        'simples': _tem(rs, lambda r: r['tipo_pista'] == 'Simples'),
        'noite': _tem(rs, _noite),
        'frontal': _tem(rs, lambda r: r['tipo_acidente'] == 'Colisão frontal'),
        'contramao': _tem(rs, lambda r: r['causa_acidente'] == 'Transitar na contramão'),
    }
    por_tipo = sorted(((k, stats(x)) for k, x in grp(lambda r: r['tipo_acidente'], rs).items()), key=lambda kv: (-kv[1]['mortos'], kv[0]))[:2]
    por_causa = sorted(((k, stats(x)) for k, x in grp(lambda r: r['causa_acidente'], rs).items()), key=lambda kv: (-kv[1]['mortos'], kv[0]))[:2]
    segs = {k: x for k, x in grp(seg, rs).items() if k is not None}
    top_seg = sorted(segs.items(), key=lambda kv: (-sum(r['mortos'] for r in kv[1]), -len(kv[1]), kv[0]))[:2]
    seg_txt_ = '; '.join(
        f'km {k[1]} ao {k[1] + 5} ({bonito(collections.Counter(r["municipio"] for r in x).most_common(1)[0][0])}: {stats(x)["ocorrencias"]} acidentes, {stats(x)["mortos"]} mortos)'
        for k, x in top_seg)
    perfil_por_br['BR-' + br] = {
        'resumo': (f'BR-{br}: {num(s_["ocorrencias"])} acidentes e {s_["mortos"]} mortos, {dec(s_["mortos_por_100_ocorrencias"])} mortos por 100 acidentes (média das BRs do Piauí: {dec(let_geral)}). '
                   f'Fatores associados, comparando com a média das BRs do estado: trechos rurais em {pc(v["rural"])} dos acidentes ({_cmp(v["rural"], REF["rural"])}, média {pc(REF["rural"])}); '
                   f'pista simples em {pc(v["simples"])} ({_cmp(v["simples"], REF["simples"])}, média {pc(REF["simples"])}); '
                   f'acidentes entre 18h e 5h59 em {pc(v["noite"])} ({_cmp(v["noite"], REF["noite"])}, média {pc(REF["noite"])}); '
                   f'colisões frontais em {pc(v["frontal"])} ({_cmp(v["frontal"], REF["frontal"])}, média {pc(REF["frontal"])}); '
                   f'contramão em {pc(v["contramao"])} ({_cmp(v["contramao"], REF["contramao"])}, média {pc(REF["contramao"])}). '
                   f'Tipos que mais matam na rodovia: {lista(f"{k.lower()} ({x["mortos"]} mortos, {pc(share(x["mortos"], s_["mortos"]))} dos mortos da BR)" for k, x in por_tipo)}. '
                   f'Causas que mais matam: {lista(f"{k.lower()} ({x["mortos"]} mortos)" for k, x in por_causa)}. '
                   f'Trechos com mais mortos: {seg_txt_}. '
                   'Isto mostra associação e não prova causa: os dados da PRF não incluem volume de tráfego, velocidade praticada nem tempo de chegada do socorro. ' + FONTE),
        'numeros': {'acidentes': s_['ocorrencias'], 'mortos': s_['mortos'], 'mortos_por_100_acidentes': s_['mortos_por_100_ocorrencias'],
                    'pct_rural': round(v['rural'], 1), 'pct_pista_simples': round(v['simples'], 1), 'pct_noite_madrugada': round(v['noite'], 1),
                    'pct_colisao_frontal': round(v['frontal'], 1), 'pct_contramao': round(v['contramao'], 1)},
    }

TEMAS_EXTRA = {'ano_parcial': ano_parcial} if ano_parcial else {}
interp = {
    'como_usar': ('Conclusões JÁ CALCULADAS a partir das ' + num(N) + f' ocorrências da PRF no Piauí ({br_data(DMIN)} a {br_data(DMAX)}). Para perguntas sobre acidentes em rodovias, prefira estes textos "resumo" e cite os números exatos deles. '
                  'Gravidade = mortos por 100 acidentes. Sempre diga que são dados da PRF em rodovias federais. Não some nem compare com internações (SIH/SUS) ou óbitos (SIM).'),
    'visao_geral': visao_geral,
    'perfil_por_br': perfil_por_br,
    'temas': {
        'evolucao': evolucao, 'rodovias': rodovias, 'municipios': municipios, 'trechos': trechos,
        'causas': causas, 'alcool': alcool, 'tipos': tipos, 'horario': horario, 'dia_semana': dia_semana, 'mes': mes,
        'clima': clima, 'urbano_rural': urbano_rural, 'pista_tracado': pista_tracado, **TEMAS_EXTRA
    }
}

# ---------------------------------------------------------------- JSON + índice
raw = open(JS, encoding='utf-8', newline='').read()
d = json.loads(raw)
d.pop('interpretacao_prf_piaui', None)
new = {}
for k, v in d.items():
    new[k] = v
    if k == 'dados_prf_piaui':
        new['interpretacao_prf_piaui'] = interp
d = new

ix = d['indice_busca']
for _k in ix:
    ix[_k] = [_p for _p in ix[_k] if not _p.startswith('interpretacao_prf_piaui.')]
I = 'interpretacao_prf_piaui.'
T = I + 'temas.'
def add(palavra, paths):
    cur = ix.setdefault(palavra, [])
    for p in paths:
        if p not in cur:
            cur.insert(0, p) if p.startswith(I) else cur.append(p)

add('prf', [I + 'visao_geral'])
add('ocorrencia', [I + 'visao_geral', T + 'evolucao'])
add('ano', [T + 'evolucao'])
add('morte', [T + 'evolucao'])
add('obito', [T + 'evolucao'])
add('evolucao', [T + 'evolucao'])
add('serie temporal', [T + 'evolucao'])
add('tendencia', [T + 'evolucao'])
add('aument', [T + 'evolucao'])
add('diminu', [T + 'evolucao'])
add('cresc', [T + 'evolucao'])
if ANO_PARCIAL:
    add(str(ANO_PARCIAL), [T + 'ano_parcial'])
    add('parcial', [T + 'ano_parcial'])
add('onde', [T + 'trechos', T + 'municipios', T + 'rodovias'])
add('local', [T + 'trechos', T + 'municipios', T + 'rodovias'])
add('rodovia', [T + 'rodovias', T + 'trechos', I + 'perfil_por_br'])
add('br', [T + 'rodovias', T + 'trechos', I + 'perfil_por_br'])
add('km', [T + 'trechos'])
add('trecho', [T + 'trechos'])
add('critico', [T + 'trechos', T + 'municipios'])
add('perigos', [T + 'rodovias', T + 'trechos', I + 'perfil_por_br'])
add('municipio', [T + 'municipios'])
add('capital', [T + 'municipios'])
add('teresina', [T + 'municipios'])
add('cidade', [T + 'municipios'])
add('causa', [T + 'causas'])
add('velocidade', [T + 'causas'])
add('dormindo', [T + 'causas'])
add('sono', [T + 'causas'])
add('animal', [T + 'causas', T + 'tipos'])
add('alcool', [T + 'alcool'])
add('bebid', [T + 'alcool'])
add('colisao', [T + 'tipos'])
add('atropelamento', [T + 'tipos'])
add('tipo de acidente', [T + 'tipos'])
add('capotamento', [T + 'tipos'])
add('tombamento', [T + 'tipos'])
add('horario', [T + 'horario'])
add('hora', [T + 'horario'])
add('noite', [T + 'horario'])
add('madrugada', [T + 'horario'])
add('dia da semana', [T + 'dia_semana'])
add('fim de semana', [T + 'dia_semana'])
add('sabado', [T + 'dia_semana'])
add('domingo', [T + 'dia_semana'])
add('mes', [T + 'mes'])
add('sazonal', [T + 'mes'])
add('chuva', [T + 'clima'])
add('clima', [T + 'clima'])
add('urbano', [T + 'urbano_rural'])
add('rural', [T + 'urbano_rural'])
add('pista', [T + 'pista_tracado'])
add('curva', [T + 'pista_tracado'])
add('letalidade', [T + 'rodovias', I + 'perfil_por_br'])
add('mortalidade', [T + 'evolucao'])

d['indice_busca'] = ix
d['metadata']['ultima_atualizacao'] = datetime.date.today().isoformat() + ' (dados_prf_piaui, interpretacao_prf_piaui e apresentacao_ufpi_morbimortalidade_brasil_2016_2025)'
open(JS, 'w', encoding='utf-8', newline='').write(json.dumps(d, ensure_ascii=False, indent=2))

for nome, t in interp['temas'].items():
    print('==', nome); print(t['resumo']); print()
print('==', 'visao_geral'); print(visao_geral['resumo'])
