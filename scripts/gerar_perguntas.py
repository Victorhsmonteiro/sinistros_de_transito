"""Gera data/perguntas.json: banco de perguntas rápidas com respostas prontas (sem chamar IA).
Todos os números são calculados a partir de data/sinistros.json e data/prf_acidentes_pi.csv.
Rode por último: depois de importar_prf.py, interpretar_prf.py, gerar_planos.py e gerar_territorios.py.
Uso: python scripts/gerar_perguntas.py"""
import collections, csv, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, 'data', 'sinistros.json'), encoding='utf-8'))
ROWS = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'prf_acidentes_pi.csv'), encoding='utf-8', newline='')))

S_PRF = 'Rodovias federais (PRF)'
S_INT = 'Internações no Piauí (2010-2023)'
S_TAB = 'Internações e óbitos hospitalares (TABNET)'
S_VIVA = 'Motociclistas atendidos (VIVA 2014, nacional)'
S_BR = 'Brasil: internações e óbitos (UFPI)'
S_VG = 'Visão geral'
S_PLANO = 'Planos de ação'
S_CTX = 'Contexto, método e fontes'

QA = []


def q(secao, pergunta, resposta, fonte):
    QA.append({'secao': secao, 'pergunta': pergunta, 'resposta': resposta, 'fonte': fonte})


# ------------------------------------------------------------------ formatação
def dec(x, c=1):
    return f'{x:.{c}f}'.replace('.', ',')


def num(x):
    return f'{int(round(x)):,}'.replace(',', '.')


def pc(x, c=1):
    return dec(x, c) + '%'


def pct(a, b):
    return 100 * a / b if b else 0.0


def brl(x):
    inteiro, frac = f'{x:.2f}'.split('.')
    return f'{int(inteiro):,}'.replace(',', '.') + ',' + frac


def up1(t):
    return t[:1].upper() + t[1:]


def lista(itens):
    itens = list(itens)
    return ''.join(itens) if len(itens) <= 1 else ', '.join(itens[:-1]) + ' e ' + itens[-1]


def bonito(nome):
    ac = {'PARNAIBA': 'Parnaíba', 'LOBAO': 'Lobão', 'PIAUI': 'Piauí', 'JOSE': 'José', 'JOAO': 'João', 'GONCALO': 'Gonçalo',
          'CONCEICAO': 'Conceição', 'LUIS': 'Luís', 'SAO ': 'São '}
    s = nome
    for k, v in ac.items():
        s = s.replace(k, '\0' + v + '\0')
    out = ''.join(c if c in ac.values() else c.title() for c in s.split('\0'))
    return ' '.join(w.lower() if w in {'Do', 'Da', 'De', 'Dos', 'Das'} else w for w in out.split(' '))


# ------------------------------------------------------------------ PRF
for r in ROWS:
    for c in ['pessoas', 'mortos', 'feridos_leves', 'feridos_graves', 'ilesos', 'veiculos']:
        r[c] = int(r[c])
    r['ano'] = int(r['data_inversa'][:4])
    r['mes'] = int(r['data_inversa'][5:7])
    r['dia'] = r['data_inversa'][5:]
    r['hora'] = int(r['horario'][:2])
    r['km_f'] = float(r['km']) if r['km'] not in ('', 'NA') else None
N = len(ROWS)
DMIN, DMAX = min(r['data_inversa'] for r in ROWS), max(r['data_inversa'] for r in ROWS)
ANO_PARCIAL = int(DMAX[:4]) if DMAX[5:] < '12-31' else None
ANOS_CHEIOS = sorted({r['ano'] for r in ROWS} - {ANO_PARCIAL})
A0, A1 = ANOS_CHEIOS[0], ANOS_CHEIOS[-1]


def br_data(s):
    return f'{s[8:10]}/{s[5:7]}/{s[:4]}'


PERIODO = f'{br_data(DMIN)} a {br_data(DMAX)}'
FPRF = f'PRF, ocorrências em rodovias federais do Piauí, {PERIODO}'
AVISO_PRF = 'Dados da PRF: só rodovias federais, não incluem vias estaduais nem urbanas.'


def st(rs):
    n = len(rs)
    m = sum(r['mortos'] for r in rs)
    return {'n': n, 'm': m, 'g': sum(r['feridos_graves'] for r in rs), 'l': 100 * m / n if n else 0.0}


def grp(key, rs=None):
    g = collections.defaultdict(list)
    for r in (ROWS if rs is None else rs):
        g[key(r)].append(r)
    return g


TOT = st(ROWS)
LET = TOT['l']


def ranked(g, by, n=3, minimo=0):
    its = [(k, st(v)) for k, v in g.items() if len(v) >= minimo]
    its.sort(key=lambda kv: (-kv[1][by], -kv[1]['n'], str(kv[0])))
    return its[:n]


g_ano = grp(lambda r: r['ano'])
g_br = grp(lambda r: r['br'])
g_mun = grp(lambda r: r['municipio'])
g_causa = grp(lambda r: r['causa_acidente'])
g_tipo = grp(lambda r: r['tipo_acidente'])
g_dia = grp(lambda r: r['dia_semana'])
g_clima = grp(lambda r: r['condicao_metereologica'])
g_pista = grp(lambda r: r['tipo_pista'])
CHEIOS = [r for r in ROWS if r['ano'] in ANOS_CHEIOS]
g_mes = grp(lambda r: r['mes'], CHEIOS)
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def periodo(r):
    h = r['hora']
    return 'madrugada' if h < 6 else 'manhã' if h < 12 else 'tarde' if h < 18 else 'noite'


g_per = grp(periodo)
PER_TXT = {'madrugada': 'a madrugada (0h às 5h59)', 'manhã': 'a manhã (6h às 11h59)', 'tarde': 'a tarde (12h às 17h59)', 'noite': 'a noite (18h às 23h59)'}


def seg(r):
    return None if (r['km_f'] is None or r['br'] == '0') else (r['br'], int(r['km_f'] // 5) * 5)


g_seg = {k: v for k, v in grp(seg).items() if k is not None}


def seg_txt(k, v):
    s = st(v)
    mun = bonito(collections.Counter(r['municipio'] for r in v).most_common(1)[0][0])
    return f'BR-{k[0]} km {k[1]} ao {k[1] + 5} ({mun}: {num(s["n"])} acidentes, {s["m"]} mortos)'


# --- perguntas gerais PRF
q(S_PRF, 'Quantos acidentes a PRF registrou no Piauí?',
  f'A PRF registrou {num(N)} acidentes em rodovias federais do Piauí entre {br_data(DMIN)} e {br_data(DMAX)}, com {num(TOT["m"])} mortos e {num(TOT["g"])} feridos graves. {AVISO_PRF}', FPRF)

mm = [st(g_ano[y])['m'] for y in ANOS_CHEIOS]
q(S_PRF, 'Quantas pessoas morreram nas rodovias federais do Piauí?',
  f'Foram {num(TOT["m"])} mortos registrados pela PRF entre {br_data(DMIN)} e {br_data(DMAX)}. Nos anos completos ({A0} a {A1}) a média é de {num(sum(mm) / len(mm))} mortos por ano. {AVISO_PRF}', FPRF)

teresina = st(g_mun['TERESINA'])
q(S_PRF, 'Qual a taxa de mortes por acidente nas rodovias federais do Piauí?',
  f'Há cerca de {dec(LET)} mortos para cada 100 acidentes registrados pela PRF, e {pc(pct(sum(1 for r in ROWS if r["classificacao_acidente"] == "Com Vítimas Fatais"), N))} dos acidentes têm pelo menos uma morte. {AVISO_PRF}', FPRF)

mun5 = ranked(g_mun, 'n', 3)
seg5 = sorted(g_seg.items(), key=lambda kv: (-len(kv[1]), -sum(r['mortos'] for r in kv[1]), kv[0]))
reg = D['estudo_morbidade_piaui_2010_2023']['taxa_internacao_hospitalar_100mil_hab']['por_regiao_de_saude']
reg_top = max(reg.items(), key=lambda kv: kv[1]['valor'])
NOMES_REGIAO = {
    'carnaubais': 'Carnaubais', 'chapada_das_mangabeiras': 'Chapada das Mangabeiras', 'cocais': 'Cocais', 'entre_rios': 'Entre Rios',
    'planicie_litoranea': 'Planície Litorânea', 'serra_da_capivara': 'Serra da Capivara', 'tabuleiros_do_alto_parnaiba': 'Tabuleiros do Alto Parnaíba',
    'vale_do_caninde': 'Vale do Canindé', 'vale_do_rio_guaribas': 'Vale do Rio Guaribas', 'vale_do_sambito': 'Vale do Sambito',
    'vale_dos_rios_piaui_e_itaueiras': 'Vale dos Rios Piauí e Itaueiras', 'chapada_vale_do_rio_itaim': 'Chapada Vale do Rio Itaim'}
q(S_PRF, 'Onde acontecem mais acidentes no Piauí?',
  f'Nas rodovias federais, os acidentes se concentram em {lista(f"{bonito(k)} ({num(s["n"])})" for k, s in mun5)}; Teresina reúne {pc(pct(teresina["n"], N))} do total. '
  f'O trecho mais movimentado é {seg_txt(*seg5[0])}. Já nas internações hospitalares, a região de saúde com maior taxa é {NOMES_REGIAO[reg_top[0]]} ({dec(reg_top[1]["valor"])} por 100 mil hab.). {AVISO_PRF}',
  FPRF + '; SIH/SUS 2010-2023')

q(S_PRF, 'Quais são os trechos mais críticos das rodovias federais do Piauí?',
  f'Em número de acidentes (janelas de 5 km): {"; ".join(seg_txt(k, v) for k, v in seg5[:3])}. {AVISO_PRF}', FPRF)
seg_m = sorted(g_seg.items(), key=lambda kv: (-sum(r['mortos'] for r in kv[1]), -len(kv[1]), kv[0]))
q(S_PRF, 'Em que trechos das rodovias morre mais gente?',
  f'Os trechos com mais mortos são {"; ".join(seg_txt(k, v) for k, v in seg_m[:3])}. {AVISO_PRF}', FPRF)

br_o = ranked({k: v for k, v in g_br.items() if k != '0'}, 'n', 3)
q(S_PRF, 'Qual rodovia federal tem mais acidentes no Piauí?',
  f'A BR-{br_o[0][0]} lidera com {num(br_o[0][1]["n"])} acidentes e {br_o[0][1]["m"]} mortos, seguida da BR-{br_o[1][0]} ({num(br_o[1][1]["n"])}) e da BR-{br_o[2][0]} ({num(br_o[2][1]["n"])}). {AVISO_PRF}', FPRF)
br_l = ranked({k: v for k, v in g_br.items() if k != '0'}, 'l', 3, minimo=100)
q(S_PRF, 'Qual rodovia federal é mais letal por acidente?',
  f'Entre as BRs com 100 ou mais acidentes, as mais letais são {lista(f"a BR-{k} ({dec(s["l"])} mortos por 100 acidentes)" for k, s in br_l)}, contra {dec(LET)} na média do estado. {AVISO_PRF}', FPRF)

h_g = grp(lambda r: r['hora'])
h_top = ranked(h_g, 'n', 3)
nm_o = sum(st(g_per[p])['n'] for p in ('noite', 'madrugada'))
nm_m = sum(st(g_per[p])['m'] for p in ('noite', 'madrugada'))
q(S_PRF, 'Em que horário acontecem mais acidentes nas rodovias do Piauí?',
  f'Os horários com mais acidentes são {lista(f"{k:02d}h ({num(s["n"])})" for k, s in h_top)}. A noite e a madrugada (18h às 5h59) reúnem {pc(pct(nm_o, N))} dos acidentes, mas {pc(pct(nm_m, TOT["m"]))} dos mortos. {AVISO_PRF}', FPRF)
per_l = max(g_per, key=lambda p: st(g_per[p])['l'])
q(S_PRF, 'Qual é o período do dia mais perigoso nas rodovias federais?',
  f'{up1(PER_TXT[per_l])} é o período mais letal: {dec(st(g_per[per_l])["l"])} mortos por 100 acidentes, contra {dec(LET)} na média. Em volume, {PER_TXT[max(g_per, key=lambda p: st(g_per[p])["n"])]} tem mais acidentes. {AVISO_PRF}', FPRF)

c_o = ranked(g_causa, 'n', 3)
q(S_PRF, 'Quais as principais causas dos acidentes nas rodovias do Piauí?',
  f'As causas mais frequentes registradas pela PRF são {lista(f"{k.lower()} ({num(s["n"])}, {pc(pct(s["n"], N))})" for k, s in c_o)}. {AVISO_PRF}', FPRF)
c_m = ranked(g_causa, 'm', 3)
q(S_PRF, 'Que causas de acidente mais matam nas rodovias federais?',
  f'As causas com mais mortos são {lista(f"{k.lower()} ({s["m"]})" for k, s in c_m)}. {AVISO_PRF}', FPRF)
alc = st(g_causa['Ingestão de álcool pelo condutor'])
q(S_PRF, 'O álcool causa muitos acidentes nas rodovias federais do Piauí?',
  f'A ingestão de álcool pelo condutor foi registrada como causa de {num(alc["n"])} acidentes ({pc(pct(alc["n"], N))}) e {alc["m"]} mortos ({pc(pct(alc["m"], TOT["m"]))}). Só conta quando a PRF anotou o álcool como causa. {AVISO_PRF}', FPRF)

wk = sum(st(g_dia[d])['n'] for d in ('sábado', 'domingo'))
wk_m = sum(st(g_dia[d])['m'] for d in ('sábado', 'domingo'))
q(S_PRF, 'O fim de semana é mais perigoso nas rodovias do Piauí?',
  f'Sim: sábado e domingo concentram {pc(pct(wk, N))} dos acidentes e {pc(pct(wk_m, TOT["m"]))} dos mortos, enquanto dois dos sete dias seriam 28,6%. {AVISO_PRF}', FPRF)
d_m = ranked(g_dia, 'm', 3)
q(S_PRF, 'Em que dia da semana morre mais gente nas rodovias?',
  f'Os dias com mais mortos são {lista(f"{k} ({s["m"]})" for k, s in d_m)}. {AVISO_PRF}', FPRF)
d_n = ranked(g_dia, 'n', 3)
q(S_PRF, 'Qual dia da semana tem mais acidentes nas rodovias federais?',
  f'Os dias com mais acidentes são {lista(f"{k} ({num(s["n"])})" for k, s in d_n)}. {AVISO_PRF}', FPRF)

urb = st([r for r in ROWS if r['uso_solo'] == 'Sim'])
rur = st([r for r in ROWS if r['uso_solo'] == 'Não'])
q(S_PRF, 'Os acidentes são mais graves em área urbana ou rural?',
  f'Nos trechos sem construções (rural), há {dec(rur["l"])} mortos por 100 acidentes, contra {dec(urb["l"])} nos trechos com construções (urbano). Os trechos rurais respondem por {pc(pct(rur["m"], TOT["m"]))} dos mortos, apesar de terem menos acidentes. {AVISO_PRF}', FPRF)
ps = {k: st(v) for k, v in g_pista.items()}
q(S_PRF, 'A pista simples é mais perigosa que a pista dupla?',
  f'Sim. Pista simples: {num(ps["Simples"]["n"])} acidentes, {ps["Simples"]["m"]} mortos ({dec(ps["Simples"]["l"])} por 100 acidentes). Pista dupla: {num(ps["Dupla"]["n"])} acidentes, {ps["Dupla"]["m"]} mortos ({dec(ps["Dupla"]["l"])} por 100). A pista simples concentra {pc(pct(ps["Simples"]["m"], TOT["m"]))} dos mortos. {AVISO_PRF}', FPRF)
curva = st([r for r in ROWS if 'Curva' in r['tracado_via']])
q(S_PRF, 'Os acidentes em curva são mais graves?',
  f'Em curvas foram {num(curva["n"])} acidentes ({pc(pct(curva["n"], N))} do total) e {curva["m"]} mortos, com {dec(curva["l"])} mortos por 100 acidentes, contra {dec(LET)} na média. {AVISO_PRF}', FPRF)

chuva = st([r for r in ROWS if r['condicao_metereologica'] in ('Chuva', 'Garoa/Chuvisco')])
ceu = st(g_clima['Céu Claro'])
q(S_PRF, 'A chuva aumenta os acidentes nas rodovias do Piauí?',
  f'A maioria dos acidentes ocorre com céu claro ({pc(pct(ceu["n"], N))}). Chuva e garoa somam {num(chuva["n"])} acidentes ({pc(pct(chuva["n"], N))}) e {chuva["m"]} mortos, com {dec(chuva["l"])} mortos por 100 acidentes (média {dec(LET)}). Não há dados de tráfego para comparar o risco. {AVISO_PRF}', FPRF)

pa = {y: st(g_ano[y]) for y in sorted(g_ano)}
var = lambda a, b: 100 * (b - a) / a
mud = lambda v: ('alta de ' if v > 0 else 'queda de ') + dec(abs(v)) + '%'
q(S_PRF, 'Os acidentes nas rodovias federais do Piauí aumentaram nos últimos anos?',
  f'De {A0} a {A1}, os acidentes tiveram {mud(var(pa[A0]["n"], pa[A1]["n"]))} ({num(pa[A0]["n"])} para {num(pa[A1]["n"])}) e os mortos tiveram {mud(var(pa[A0]["m"], pa[A1]["m"]))} ({pa[A0]["m"]} para {pa[A1]["m"]}). De {A1 - 1} para {A1}, os acidentes tiveram {mud(var(pa[A1 - 1]["n"], pa[A1]["n"]))}. {AVISO_PRF}', FPRF)
pico_m = max(ANOS_CHEIOS, key=lambda y: pa[y]['m'])
q(S_PRF, 'Qual foi o ano com mais mortes nas rodovias federais do Piauí?',
  f'Entre os anos completos, {pico_m} teve mais mortos ({pa[pico_m]["m"]}), e o ano com menos mortos foi {min(ANOS_CHEIOS, key=lambda y: pa[y]["m"])} ({pa[min(ANOS_CHEIOS, key=lambda y: pa[y]["m"])]["m"]}). {AVISO_PRF}', FPRF)
if ANO_PARCIAL:
    fim = DMAX[5:]
    a_ant = st([r for r in g_ano[ANO_PARCIAL - 1] if r['dia'] <= fim])
    a_atu = pa[ANO_PARCIAL]
    q(S_PRF, f'{ANO_PARCIAL} está melhor ou pior que {ANO_PARCIAL - 1} nas rodovias federais?',
      f'{ANO_PARCIAL} é parcial (até {br_data(DMAX)}): {num(a_atu["n"])} acidentes e {a_atu["m"]} mortos. No mesmo período de {ANO_PARCIAL - 1} foram {num(a_ant["n"])} acidentes e {a_ant["m"]} mortos, ou seja, {mud(var(a_ant["n"], a_atu["n"]))} nos acidentes e {mud(var(a_ant["m"], a_atu["m"]))} nos mortos. {AVISO_PRF}', FPRF)

t_m = ranked(g_tipo, 'm', 3)
q(S_PRF, 'Que tipo de acidente mais mata nas rodovias federais?',
  f'Os tipos com mais mortos são {lista(f"{k.lower()} ({s["m"]})" for k, s in t_m)}. {AVISO_PRF}', FPRF)
t_l = ranked(g_tipo, 'l', 2, minimo=50)
q(S_PRF, 'Qual tipo de acidente é mais letal por ocorrência?',
  f'Entre os tipos com 50 ou mais acidentes, os mais letais são {lista(f"{k.lower()} ({dec(s["l"])} mortos por 100)" for k, s in t_l)}. {AVISO_PRF}', FPRF)
t_o = ranked(g_tipo, 'n', 3)
q(S_PRF, 'Quais os tipos de acidente mais comuns nas rodovias do Piauí?',
  f'Os mais comuns são {lista(f"{k.lower()} ({num(s["n"])})" for k, s in t_o)}. A PRF não informa o tipo de veículo neste arquivo, então não dá para separar motos de carros. {AVISO_PRF}', FPRF)
mes_o = ranked(g_mes, 'n', 3)
q(S_PRF, 'Em que meses acontecem mais acidentes nas rodovias do Piauí?',
  f'Somando os anos completos ({A0} a {A1}), os meses com mais acidentes são {lista(f"{MESES[k - 1]} ({num(s["n"])})" for k, s in mes_o)}. {AVISO_PRF}', FPRF)
q(S_PRF, 'Teresina concentra quantos por cento dos acidentes nas rodovias federais?',
  f'Teresina concentra {pc(pct(teresina["n"], N))} dos acidentes ({num(teresina["n"])}) e {pc(pct(teresina["m"], TOT["m"]))} dos mortos ({teresina["m"]}), com {dec(teresina["l"])} mortos por 100 acidentes, abaixo da média ({dec(LET)}). Só conta as BRs que passam pelo município. {AVISO_PRF}', FPRF)
q(S_PRF, 'Quantos feridos graves houve nos acidentes das rodovias federais do Piauí?',
  f'A PRF registrou {num(TOT["g"])} feridos graves entre {br_data(DMIN)} e {br_data(DMAX)}, além de {num(TOT["m"])} mortos. {AVISO_PRF}', FPRF)

atrop = st(g_tipo['Atropelamento de Pedestre'])
q(S_PRF, 'Quantos atropelamentos de pedestres ocorreram nas rodovias federais?',
  f'Foram {num(atrop["n"])} atropelamentos de pedestres e {atrop["m"]} mortos, com {dec(atrop["l"])} mortos por 100 ocorrências, um dos tipos mais letais. {AVISO_PRF}', FPRF)
fr = st(g_tipo['Colisão frontal'])
q(S_PRF, 'As colisões frontais são muito graves?',
  f'Sim. Foram {num(fr["n"])} colisões frontais com {fr["m"]} mortos, ou seja, {dec(fr["l"])} mortos por 100 acidentes, mais que o triplo da média do estado ({dec(LET)}). {AVISO_PRF}', FPRF)
an = st(g_causa['Animais na Pista'])
q(S_PRF, 'Animais na pista causam muitos acidentes?',
  f'Animais na pista foram causa de {num(an["n"])} acidentes ({pc(pct(an["n"], N))}) e {an["m"]} mortos. {AVISO_PRF}', FPRF)
dorm = st(g_causa['Condutor Dormindo'])
q(S_PRF, 'O sono do condutor causa acidentes graves?',
  f'Condutor dormindo foi a causa de {num(dorm["n"])} acidentes e {dorm["m"]} mortos ({dec(dorm["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)
vel = st(g_causa['Velocidade Incompatível'])
q(S_PRF, 'A velocidade incompatível causa muitos acidentes?',
  f'Velocidade incompatível aparece como causa de {num(vel["n"])} acidentes e {vel["m"]} mortos ({dec(vel["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)
contra = st(g_causa['Transitar na contramão'])
q(S_PRF, 'Transitar na contramão causa mortes nas rodovias do Piauí?',
  f'Sim: {num(contra["n"])} acidentes e {contra["m"]} mortos, com {dec(contra["l"])} mortos por 100 acidentes, um dos índices mais altos entre as causas. {AVISO_PRF}', FPRF)

# --- por BR
for br in ['343', '316', '135', '230', '407', '222', '402']:
    s = st(g_br[br])
    q(S_PRF, f'Quantos acidentes houve na BR-{br} no Piauí?',
      f'Na BR-{br} foram {num(s["n"])} acidentes, {s["m"]} mortos e {num(s["g"])} feridos graves, com {dec(s["l"])} mortos por 100 acidentes ({dec(LET)} na média do estado). {AVISO_PRF}', FPRF)
    vs = sorted([(k, v) for k, v in g_seg.items() if k[0] == br], key=lambda kv: (-len(kv[1]), kv[0]))
    if vs and len(vs[0][1]) >= 20:
        q(S_PRF, f'Qual o trecho mais crítico da BR-{br} no Piauí?',
          f'O trecho com mais acidentes da BR-{br} é {seg_txt(*vs[0])}. {AVISO_PRF}', FPRF)

# --- por que a BR é letal (perfil calculado em interpretar_prf.py)
PERFIL_BR = D['interpretacao_prf_piaui']['perfil_por_br']
for k, s_ in br_l:
    if 'BR-' + k in PERFIL_BR:
        q(S_PRF, f'Por que a BR-{k} é tão letal?', PERFIL_BR['BR-' + k]['resumo'], FPRF)

# --- por município
for mun in ['TERESINA', 'PICOS', 'PARNAIBA', 'FLORIANO', 'ALTOS', 'CAMPO MAIOR', 'PIRIPIRI', 'OEIRAS', 'BOM JESUS', 'DEMERVAL LOBAO']:
    s = st(g_mun[mun])
    brs = collections.Counter(r['br'] for r in g_mun[mun]).most_common(2)
    q(S_PRF, f'Quantos acidentes houve nas rodovias federais em {bonito(mun)}?',
      f'Em {bonito(mun)} foram {num(s["n"])} acidentes e {s["m"]} mortos nas BRs que passam pelo município ({dec(s["l"])} mortos por 100 acidentes); as rodovias com mais registros são {lista("BR-" + b for b, _ in brs)}. {AVISO_PRF}', FPRF)

# --- por ano
for y in sorted(g_ano):
    s = pa[y]
    extra = f' (ano parcial, até {br_data(DMAX)})' if y == ANO_PARCIAL else ''
    q(S_PRF, f'Quantos acidentes e mortes houve em {y} nas rodovias federais do Piauí?',
      f'Em {y}{extra} a PRF registrou {num(s["n"])} acidentes, {s["m"]} mortos e {num(s["g"])} feridos graves. {AVISO_PRF}', FPRF)

# --- por causa/tipo
for causa in [k for k, _ in ranked(g_causa, 'n', 8)][3:8]:
    s = st(g_causa[causa])
    q(S_PRF, f'Quantos acidentes foram causados por "{causa.lower()}"?',
      f'Essa causa aparece em {num(s["n"])} acidentes ({pc(pct(s["n"], N))}) e {s["m"]} mortos ({dec(s["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)
for tipo in [k for k, _ in ranked(g_tipo, 'n', 8)][3:8]:
    s = st(g_tipo[tipo])
    q(S_PRF, f'Quantos acidentes do tipo "{tipo.lower()}" ocorreram?',
      f'Foram {num(s["n"])} acidentes ({pc(pct(s["n"], N))}) e {s["m"]} mortos ({dec(s["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)

# --- por período, dia e clima
PER_Q = {'madrugada': 'na madrugada (0h às 5h59)', 'manhã': 'pela manhã (6h às 11h59)', 'tarde': 'à tarde (12h às 17h59)', 'noite': 'à noite (18h às 23h59)'}
for p in ('madrugada', 'manhã', 'tarde', 'noite'):
    s_ = st(g_per[p])
    q(S_PRF, f'Quantos acidentes ocorrem {PER_Q[p]} nas rodovias federais?',
      f'{up1(PER_Q[p])} foram {num(s_["n"])} acidentes ({pc(pct(s_["n"], N))}) e {s_["m"]} mortos ({pc(pct(s_["m"], TOT["m"]))}), com {dec(s_["l"])} mortos por 100 acidentes. {AVISO_PRF}', FPRF)
DIA_Q = {'segunda-feira': ('às segundas-feiras', 'Às segundas-feiras'), 'sexta-feira': ('às sextas-feiras', 'Às sextas-feiras'),
         'sábado': ('aos sábados', 'Aos sábados'), 'domingo': ('aos domingos', 'Aos domingos')}
for dia, (qtxt, atxt) in DIA_Q.items():
    s_ = st(g_dia[dia])
    q(S_PRF, f'Quantos acidentes ocorrem {qtxt} nas rodovias federais do Piauí?',
      f'{atxt} foram {num(s_["n"])} acidentes e {s_["m"]} mortos ({dec(s_["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)
for cl, rot in [('Nublado', 'com tempo nublado'), ('Sol', 'com sol')]:
    s_ = st(g_clima[cl])
    q(S_PRF, f'Quantos acidentes ocorrem {rot} nas rodovias federais?',
      f'{up1(rot)} foram {num(s_["n"])} acidentes ({pc(pct(s_["n"], N))}) e {s_["m"]} mortos ({dec(s_["l"])} por 100 acidentes). {AVISO_PRF}', FPRF)
for mes in (10, 12, 2):
    s = st(g_mes[mes])
    q(S_PRF, f'Quantos acidentes ocorrem em {MESES[mes - 1]} nas rodovias federais do Piauí?',
      f'Somando {A0} a {A1}, {MESES[mes - 1]} teve {num(s["n"])} acidentes e {s["m"]} mortos. {AVISO_PRF}', FPRF)

# ------------------------------------------------------------------ Internações Piauí (estudo)
E = D['estudo_morbidade_piaui_2010_2023']
TX = E['taxa_internacao_hospitalar_100mil_hab']
LT = E['letalidade_hospitalar_pct']
VM = E['valor_medio_internacao_reais']
PM = E['permanencia_media_dias']
FE = 'SIH/SUS 2010-2023 (Bastos et al., Rev Bras Epidemiol 2026)'
TEND = {'Crescente': 'crescente', 'Estável': 'estável', 'Decrescente': 'decrescente'}


def tend(x):
    return TEND.get(x['tendencia'], x['tendencia'].lower())


def vpa(x):
    return f'variação anual de {dec(x["vpa_pct"], 2)}%'


q(S_INT, 'Quantas internações por acidentes de trânsito houve no Piauí entre 2010 e 2023?',
  f'Foram {num(E["total_internacoes_periodo"])} internações no SUS por acidentes de transporte terrestre, com {num(E["letalidade_hospitalar_pct"]["obitos_hospitalares_totais_periodo"])} óbitos hospitalares. A taxa média é de {dec(TX["geral"]["valor"])} por 100 mil habitantes, em tendência {tend(TX["geral"])}.', FE)
q(S_INT, 'Qual foi o ano com mais internações por acidentes no Piauí?',
  f'Foi {E["ano_com_mais_internacoes"]["ano"]}, com {num(E["ano_com_mais_internacoes"]["internacoes"])} internações ({dec(E["ano_com_mais_internacoes"]["taxa_100mil"])} por 100 mil hab.). O menor foi {E["ano_com_menos_internacoes"]["ano"]}, com {num(E["ano_com_menos_internacoes"]["internacoes"])} ({dec(E["ano_com_menos_internacoes"]["taxa_100mil"])} por 100 mil).', FE)
q(S_INT, 'Qual a taxa de internação por acidentes de trânsito no Piauí?',
  f'A taxa média de 2010 a 2023 é de {dec(TX["geral"]["valor"])} internações por 100 mil habitantes, com {vpa(TX["geral"])} (IC95%: {dec(TX["geral"]["ic95_min"], 2)} a {dec(TX["geral"]["ic95_max"], 2)}), tendência {tend(TX["geral"])}.', FE)
q(S_INT, 'Qual a letalidade hospitalar dos acidentes de trânsito no Piauí?',
  f'A letalidade hospitalar média é de {dec(LT["geral"]["valor"])}% (tendência {tend(LT["geral"])}), com {num(LT["obitos_hospitalares_totais_periodo"])} óbitos hospitalares no período.', FE)
q(S_INT, 'Quanto tempo as vítimas ficam internadas no Piauí?',
  f'A permanência média é de {dec(PM["geral"]["valor"])} dias (tendência {tend(PM["geral"])}), somando {num(PM["total_dias_periodo"])} dias de internação no período.', FE)
q(S_INT, 'Quanto custa, em média, uma internação por acidente de trânsito no Piauí?',
  f'O valor médio é de R$ {brl(VM["geral"]["valor"])} por internação (R$ {brl(VM["valor_medio_corrigido_igpm_reais"])} corrigido pelo IGP-M); o total pago foi de R$ {dec(VM["valor_total_periodo_reais"] / 1e6)} milhões (R$ {dec(VM["valor_total_periodo_corrigido_igpm_reais"] / 1e6)} milhões corrigidos). O estudo avisa que não inclui verbas de estados e municípios.', FE)
q(S_INT, 'Qual a diferença da taxa de internação entre homens e mulheres no Piauí?',
  f'Homens: {dec(TX["por_sexo"]["masculino"]["valor"])} por 100 mil hab.; mulheres: {dec(TX["por_sexo"]["feminino"]["valor"])}. A taxa masculina é cerca de {dec(TX["por_sexo"]["masculino"]["valor"] / TX["por_sexo"]["feminino"]["valor"])} vezes a feminina.', FE)
q(S_INT, 'Qual a letalidade hospitalar entre homens e mulheres no Piauí?',
  f'Homens: {dec(LT["por_sexo"]["masculino"]["valor"])}%; mulheres: {dec(LT["por_sexo"]["feminino"]["valor"])}%.', FE)
FAIXA = {'0_a_9_anos': '0 a 9 anos', '10_a_19_anos': '10 a 19 anos', '20_a_39_anos': '20 a 39 anos', '40_a_59_anos': '40 a 59 anos', '60_anos_ou_mais': '60 anos ou mais'}
fa_top = max(TX['por_faixa_etaria'].items(), key=lambda kv: kv[1]['valor'])
q(S_INT, 'Qual faixa etária tem mais internações por acidentes no Piauí?',
  f'A faixa de {FAIXA[fa_top[0]]} tem a maior taxa: {dec(fa_top[1]["valor"])} por 100 mil hab. (tendência {tend(fa_top[1])}).', FE)
for k, v in TX['por_faixa_etaria'].items():
    q(S_INT, f'Qual a taxa de internação por acidentes entre pessoas de {FAIXA[k]} no Piauí?',
      f'É de {dec(v["valor"])} por 100 mil habitantes, com {vpa(v)} e tendência {tend(v)}. Letalidade hospitalar nessa faixa: {dec(LT["por_faixa_etaria"][k]["valor"])}%.', FE)
VIT = {'pedestre': 'pedestres', 'ciclista': 'ciclistas', 'motociclista': 'motociclistas', 'ocupante_de_veiculo': 'ocupantes de veículos', 'outros': 'outras vítimas'}
for k, v in TX['por_tipo_vitima'].items():
    q(S_INT, f'Qual a taxa de internação de {VIT[k]} no Piauí?',
      f'É de {dec(v["valor"])} por 100 mil habitantes (tendência {tend(v)}), com letalidade hospitalar de {dec(LT["por_tipo_vitima"][k]["valor"])}% e permanência média de {dec(PM["por_tipo_vitima"][k]["valor"])} dias.', FE)
mo, pe = TX['por_tipo_vitima']['motociclista']['valor'], TX['por_tipo_vitima']['pedestre']['valor']
q(S_INT, 'Os motociclistas se internam mais que os pedestres no Piauí?',
  f'Sim: a taxa de motociclistas ({dec(mo)} por 100 mil) é cerca de {dec(mo / pe, 0)} vezes a de pedestres ({dec(pe)}).', FE)
vit_l = max(LT['por_tipo_vitima'].items(), key=lambda kv: kv[1]['valor'])
q(S_INT, 'Que tipo de vítima tem maior letalidade hospitalar no Piauí?',
  f'{up1(VIT[vit_l[0]])} têm a maior letalidade hospitalar: {dec(vit_l[1]["valor"])}%, contra {dec(LT["geral"]["valor"])}% na média.', FE)
vit_c = max(VM['por_tipo_vitima'].items(), key=lambda kv: kv[1]['valor'])
q(S_INT, 'Que tipo de vítima gera a internação mais cara no Piauí?',
  f'{up1(VIT[vit_c[0]])}: R$ {brl(vit_c[1]["valor"])} por internação, contra R$ {brl(VM["geral"]["valor"])} na média.', FE)
MACRO = {'semiarido': 'Semiárido', 'meio_norte': 'Meio-Norte', 'litoral': 'Litoral', 'cerrado': 'Cerrado'}
for k, v in TX['por_macrorregiao'].items():
    q(S_INT, f'Qual a taxa de internação por acidentes na macrorregião {MACRO[k]}?',
      f'É de {dec(v["valor"])} por 100 mil habitantes (tendência {tend(v)}). Letalidade hospitalar: {dec(LT["por_macrorregiao"][k]["valor"])}%; permanência média: {dec(PM["por_macrorregiao"][k]["valor"])} dias; valor médio: R$ {brl(VM["por_macrorregiao"][k]["valor"])}.', FE)
ordem = sorted(TX['por_regiao_de_saude'].items(), key=lambda kv: -kv[1]['valor'])
for i, (k, v) in enumerate(ordem, 1):
    q(S_INT, f'Qual a taxa de internação por acidentes na região de saúde {NOMES_REGIAO[k]}?',
      f'É de {dec(v["valor"])} por 100 mil habitantes, a {i}ª maior entre as 12 regiões de saúde, com tendência {tend(v)} ({vpa(v)}). Letalidade hospitalar: {dec(LT["por_regiao_de_saude"][k]["valor"])}%.', FE)
q(S_INT, 'Quais regiões de saúde do Piauí têm as maiores taxas de internação?',
  f'As três maiores são {lista(f"{NOMES_REGIAO[k]} ({dec(v["valor"])})" for k, v in ordem[:3])} por 100 mil habitantes; a menor é {NOMES_REGIAO[ordem[-1][0]]} ({dec(ordem[-1][1]["valor"])}).', FE)
q(S_INT, 'Quais regiões de saúde do Piauí têm tendência crescente de internações?',
  f'Com tendência crescente: {lista(NOMES_REGIAO[k] for k, v in ordem if v["tendencia"] == "Crescente")}. Com queda: {lista(NOMES_REGIAO[k] for k, v in ordem if v["tendencia"] == "Decrescente")}.', FE)
mac_top = max(TX['por_macrorregiao'].items(), key=lambda kv: kv[1]['valor'])
q(S_INT, 'Qual macrorregião de saúde do Piauí tem a maior taxa de internação?',
  f'{MACRO[mac_top[0]]}, com {dec(mac_top[1]["valor"])} por 100 mil habitantes.', FE)
q(S_INT, 'Onde estão os aglomerados de municípios com mais internações no Piauí?',
  f'Análise espacial (LISA): 2010-2014, {E["analise_espacial"]["periodo_2010_2014"].lower()}; 2015-2019, {E["analise_espacial"]["periodo_2015_2019"].lower()}; 2020-2023, {E["analise_espacial"]["periodo_2020_2023"].lower()}.', FE)
q(S_INT, 'Quais os principais achados do estudo de internações no Piauí?',
  f'{E["principais_achados"][0]}. {E["principais_achados"][1]}. {E["principais_achados"][2]}.', FE)
q(S_INT, 'O que o estudo recomenda para reduzir os acidentes no Piauí?',
  ' '.join(x + '.' for x in E['recomendacoes']), FE)
q(S_INT, 'Quais são as limitações do estudo de internações no Piauí?',
  ' '.join(x + '.' for x in E['limitacoes_do_estudo'][:3]), FE)
C = E['contexto_estado_piaui']
q(S_INT, 'Quantos habitantes e municípios tem o Piauí?',
  f'O Piauí tem {num(C["populacao"])} habitantes ({C["ano_referencia_populacao"]}), {C["numero_municipios"]} municípios, {C["numero_regioes_de_saude"]} regiões de saúde e {C["numero_macrorregioes_de_saude"]} macrorregiões.', FE)
q(S_INT, 'Quantos domicílios do Piauí têm motocicleta?',
  f'{dec(C["domicilios_com_motocicleta_pct_2024"])}% dos domicílios em 2024 (cerca de 597 mil), a 2ª maior proporção do Brasil.', FE)
q(S_INT, 'O custo médio das internações por acidentes no Piauí está subindo?',
  f'A tendência do valor médio por internação é {tend(VM["geral"])} ({vpa(VM["geral"])}); o estudo indica que isso pode refletir defasagem da tabela de procedimentos do SUS e não redução real de custo.', FE)

# ------------------------------------------------------------------ TABNET
T = D['dados_tabnet_piaui_teresina']
P = T['piaui']
TE = T['teresina']
FT = f'TABNET/DATASUS (SIH/SUS), internações por local de internação, {T["periodo"]}'
CAT = {'V01-V09': 'pedestres', 'V10-V19': 'ciclistas', 'V20-V29': 'motociclistas', 'V30-V39': 'ocupantes de triciclo motorizado', 'V40-V49': 'ocupantes de automóvel',
       'V50-V59': 'ocupantes de caminhonete', 'V60-V69': 'ocupantes de veículo de transporte pesado', 'V70-V79': 'ocupantes de ônibus', 'V80-V89': 'outros acidentes de transporte terrestre'}
AVISO_TAB = 'Consulta do TABNET por local de internação; os totais não coincidem com os do artigo científico, que conta por residência.'
ia = P['internacoes_por_ano']
tot_p = ia['total_periodo']
anos = [int(k) for k in ia if k.isdigit()]
PARC_T = T.get('ano_parcial')
SERIE_T = f'{anos[0]} a {anos[-1]}' + (f' ({PARC_T} parcial)' if PARC_T else '')
q(S_TAB, 'Quantas internações por acidentes de transporte o TABNET registra no Piauí?',
  f'Foram {num(tot_p)} internações em hospitais do Piauí de {SERIE_T}, com {num(P["obitos_por_categoria"]["TOTAL_GERAL"])} óbitos hospitalares (letalidade de {dec(P["taxa_mortalidade_pct_por_categoria"]["TOTAL_GERAL"], 2)}%). {AVISO_TAB}', FT)
a_pico = max([a for a in anos if a != PARC_T], key=lambda a: ia[str(a)])
q(S_TAB, 'Qual ano teve mais internações por acidentes de transporte no TABNET do Piauí?',
  f'{a_pico}, com {num(ia[str(a_pico)])} internações. {AVISO_TAB}' + (f' O ano de {PARC_T} ainda é parcial.' if PARC_T else ''), FT)
for a in (2015, 2019, 2020, 2023, 2024, 2025):
    q(S_TAB, f'Quantas internações por acidentes de transporte houve no Piauí em {a} segundo o TABNET?',
      f'Foram {num(ia[str(a)])} internações em {a}. {AVISO_TAB}', FT)
q(S_TAB, 'As internações por acidentes caíram durante a pandemia no Piauí?',
  f'Pelo TABNET, as internações passaram de {num(ia["2019"])} em 2019 para {num(ia["2020"])} em 2020 e {num(ia["2021"])} em 2021, voltando a {num(ia["2023"])} em 2023. {AVISO_TAB}', FT)
cat_tot = {k: P['internacoes_por_categoria_e_ano'][k]['total_periodo'] for k in CAT}
for k in ('V20-V29', 'V01-V09', 'V40-V49', 'V10-V19'):
    q(S_TAB, f'Quantas internações de {CAT[k]} houve no Piauí segundo o TABNET?',
      f'Foram {num(cat_tot[k])} internações ({pc(pct(cat_tot[k], tot_p))} do total), com {num(P["obitos_por_categoria"].get(k, 0))} óbitos hospitalares e letalidade de {dec(P["taxa_mortalidade_pct_por_categoria"][k], 2)}%. {AVISO_TAB}', FT)
q(S_TAB, 'Que categoria de acidente de transporte tem mais internações no Piauí?',
  f'Motociclistas: {num(cat_tot["V20-V29"])} internações, {pc(pct(cat_tot["V20-V29"], tot_p))} do total. {AVISO_TAB}', FT)
q(S_TAB, 'Qual categoria tem a maior letalidade hospitalar no TABNET do Piauí?',
  f'Entre as categorias com dado, ocupantes de automóvel ({dec(P["taxa_mortalidade_pct_por_categoria"]["V40-V49"], 2)}%) e de veículo pesado ({dec(P["taxa_mortalidade_pct_por_categoria"]["V60-V69"], 2)}%) lideram; a média geral é {dec(P["taxa_mortalidade_pct_por_categoria"]["TOTAL_GERAL"], 2)}%. {AVISO_TAB}', FT)
q(S_TAB, 'Quantos motociclistas morreram internados no Piauí?',
  f'Foram {num(P["obitos_por_categoria"]["V20-V29"])} óbitos hospitalares de motociclistas, {pc(pct(P["obitos_por_categoria"]["V20-V29"], P["obitos_por_categoria"]["TOTAL_GERAL"]))} dos {num(P["obitos_por_categoria"]["TOTAL_GERAL"])} óbitos hospitalares por acidentes de transporte. {AVISO_TAB}', FT)
q(S_TAB, 'Qual o valor médio de uma AIH por acidente de transporte no Piauí?',
  f'O valor médio é de R$ {brl(P["valor_medio_aih_reais_por_categoria"]["TOTAL_GERAL"])}; para motociclistas, R$ {brl(P["valor_medio_aih_reais_por_categoria"]["V20-V29"])}. {AVISO_TAB}', FT)
q(S_TAB, 'Qual a permanência média de internação por acidente de transporte no Piauí pelo TABNET?',
  f'A média é de {dec(P["permanencia_media_dias_por_categoria"]["TOTAL_GERAL"])} dias; a maior é a de ocupantes de veículo pesado ({dec(P["permanencia_media_dias_por_categoria"]["V60-V69"])} dias). {AVISO_TAB}', FT)
sx = P['internacoes_por_sexo_e_categoria']['TOTAL_GERAL']
q(S_TAB, 'Quantas internações são de homens e de mulheres no TABNET do Piauí?',
  f'Homens: {num(sx["masculino"])} ({pc(pct(sx["masculino"], sx["total"]))}); mulheres: {num(sx["feminino"])} ({pc(pct(sx["feminino"], sx["total"]))}). {AVISO_TAB}', FT)
idade = P['internacoes_por_idade_e_categoria']['TOTAL_GERAL']
faixas = [(k, v) for k, v in idade.items() if isinstance(v, (int, float)) and k.lower() not in ('total', 'total_geral', 'ignorado', 'idade ignorada')]
top_id = max(faixas, key=lambda kv: kv[1])
q(S_TAB, 'Que faixa etária mais se interna por acidentes de transporte no Piauí (TABNET)?',
  f'A faixa de {top_id[0]} tem mais internações ({num(top_id[1])}). {AVISO_TAB}', FT)
HOSP_TE = 'Teresina recebe pacientes de todo o estado: são internações em hospitais da capital, não de moradores (para moradores, veja óbitos e internações por residência no mapa).'
q(S_TAB, 'Quantas internações por acidentes de transporte ocorreram em Teresina?',
  f'O TABNET registra {num(TE["internacoes_por_categoria"]["TOTAL_GERAL"])} internações em hospitais de Teresina de {SERIE_T}, {pc(pct(TE["internacoes_por_categoria"]["TOTAL_GERAL"], tot_p))} das internações do Piauí, com {num(TE["obitos_por_categoria"]["TOTAL_GERAL"])} óbitos hospitalares. {HOSP_TE}', FT)
q(S_TAB, 'Qual a letalidade hospitalar dos acidentes de transporte em Teresina?',
  f'Nos hospitais de Teresina é de {dec(TE["taxa_mortalidade_pct_por_categoria"]["TOTAL_GERAL"], 2)}%, contra {dec(P["taxa_mortalidade_pct_por_categoria"]["TOTAL_GERAL"], 2)}% no Piauí; a capital concentra os casos mais graves, encaminhados do interior. {AVISO_TAB}', FT)
q(S_TAB, 'Quantos motociclistas foram internados em Teresina por acidentes?',
  f'Foram {num(TE["internacoes_por_categoria"]["V20-V29"])} internações de motociclistas em hospitais de Teresina, {pc(pct(TE["internacoes_por_categoria"]["V20-V29"], TE["internacoes_por_categoria"]["TOTAL_GERAL"]))} do total da capital. {HOSP_TE}', FT)
q(S_TAB, 'Qual o valor médio de uma internação por acidente em Teresina?',
  f'R$ {brl(TE["valor_medio_aih_reais_por_categoria"]["TOTAL_GERAL"])} por internação nos hospitais de Teresina, contra R$ {brl(P["valor_medio_aih_reais_por_categoria"]["TOTAL_GERAL"])} no Piauí. {AVISO_TAB}', FT)
let_te = {k: v for k, v in TE['taxa_mortalidade_pct_por_categoria'].items() if k in CAT and TE['internacoes_por_categoria'].get(k, 0) >= 100}
maior_te = max(let_te, key=let_te.get)
q(S_TAB, 'Quantos pedestres foram internados em Teresina após acidentes?',
  f'Foram {num(TE["internacoes_por_categoria"]["V01-V09"])} internações de pedestres em hospitais de Teresina, com letalidade de {dec(TE["taxa_mortalidade_pct_por_categoria"]["V01-V09"], 2)}%'
  + (', a mais alta entre as categorias com 100 ou mais internações na capital.' if maior_te == 'V01-V09' else
     f'; a mais alta entre as categorias com 100 ou mais internações é a de {CAT[maior_te]} ({dec(let_te[maior_te], 2)}%).') + f' {HOSP_TE}', FT)
q(S_TAB, 'Quais as categorias de acidente de transporte do CID-10 usadas no TABNET?',
  'São os grupos V01 a V89: ' + '; '.join(f'{k} ({v})' for k, v in CAT.items()) + '.', FT)

# ------------------------------------------------------------------ VIVA 2014
V = D['fonte_dados_viva_2014']
PD, EV, AT = D['perfil_demografico'], D['evento'], D['atendimento_evolucao']
FV = 'VIVA Inquérito 2014 (Ministério da Saúde), nacional'
NAC = 'Dado nacional (VIVA 2014), não específico do Piauí.'


def vv(x):
    return f'{pc(100 * x["total_pct"])} ({num(x["total_n"])})'


q(S_VIVA, 'O que é a pesquisa VIVA 2014?',
  f'É o inquérito VIVA do Ministério da Saúde, com {num(V["amostra_total"])} atendimentos de emergência a motociclistas acidentados em {V["abrangencia"].split("-")[1].strip().split(" em ")[0]} de capitais e do DF, coletados de setembro a novembro de 2014. {NAC}', FV)
q(S_VIVA, 'Qual a importância de usar capacete nas motos?',
  f'Entre os motociclistas atendidos, {vv(EV["uso_capacete"]["nao"])} não usavam capacete e {vv(EV["uso_capacete"]["sim"])} usavam; {vv(EV["parte_corpo_atingida"]["cabeca_pescoco"])} tiveram a cabeça ou o pescoço atingidos. A pesquisa não compara a gravidade com e sem capacete. {NAC}', FV)
q(S_VIVA, 'Quantos motociclistas acidentados não usavam capacete?',
  f'{vv(EV["uso_capacete"]["nao"])} dos atendidos não usavam capacete. {NAC}', FV)
q(S_VIVA, 'Quantos motociclistas acidentados tinham consumido álcool?',
  f'{vv(EV["consumo_alcool"]["sim"])} relataram consumo de álcool; {vv(EV["consumo_alcool"]["nao"])} não. {NAC}', FV)
q(S_VIVA, 'Qual o perfil por sexo dos motociclistas acidentados?',
  f'{pc(100 * PD["sexo"]["masculino_pct_amostra"])} eram homens e {pc(100 * PD["sexo"]["feminino_pct_amostra"])} mulheres (razão de {PD["sexo"]["razao_masculino_feminino"]}). {NAC}', FV)
FX = {'0_a_9_anos': '0 a 9 anos', '10_a_19_anos': '10 a 19 anos', '20_a_39_anos': '20 a 39 anos', '40_a_59_anos': '40 a 59 anos', '60_anos_ou_mais': '60 anos ou mais'}
for k, v in PD['faixa_etaria'].items():
    q(S_VIVA, f'Quantos motociclistas acidentados tinham de {FX[k]}?' if k != '60_anos_ou_mais' else 'Quantos motociclistas acidentados tinham 60 anos ou mais?',
      f'{vv(v)} dos atendidos. {NAC}', FV)
fx_top = max(PD['faixa_etaria'].items(), key=lambda kv: kv[1]['total_n'])
q(S_VIVA, 'Qual a faixa etária mais atingida entre os motociclistas acidentados?',
  f'A faixa de {FX[fx_top[0]]}, com {vv(fx_top[1])} dos atendidos. {NAC}', FV)
RC = {'branca': 'brancos', 'preta_parda': 'pretos e pardos', 'amarela_indigena': 'amarelos ou indígenas'}
for k, v in PD['raca_cor'].items():
    q(S_VIVA, f'Qual a proporção de motociclistas acidentados {RC[k]}?',
      f'{vv(v)} dos atendidos. {NAC}', FV)
q(S_VIVA, 'Qual a escolaridade dos motociclistas acidentados?',
  f'Até 8 anos de estudo: {vv(PD["escolaridade"]["ate_8_anos"])}; 9 anos ou mais: {vv(PD["escolaridade"]["9_anos_ou_mais"])}. {NAC}', FV)
q(S_VIVA, 'Os motociclistas acidentados tinham atividade remunerada?',
  f'Sim, {vv(PD["atividade_remunerada"]["sim"])}; não, {vv(PD["atividade_remunerada"]["nao"])}. {NAC}', FV)
q(S_VIVA, 'Quantos motociclistas acidentados tinham plano de saúde?',
  f'{vv(PD["plano_saude"]["sim"])} tinham plano de saúde e {vv(PD["plano_saude"]["nao"])} não. {NAC}', FV)
q(S_VIVA, 'Os motociclistas acidentados eram condutores ou passageiros?',
  f'Condutores: {vv(EV["tipo_vitima"]["condutor"])}; passageiros: {vv(EV["tipo_vitima"]["passageiro"])}. {NAC}', FV)
q(S_VIVA, 'Com o que os motociclistas mais colidem?',
  f'Com automóveis em {vv(EV["outra_parte_envolvida"]["automovel"])} dos casos e com outras motocicletas em {vv(EV["outra_parte_envolvida"]["motocicleta"])}. {NAC}', FV)
q(S_VIVA, 'Que tipos de lesão sofrem os motociclistas acidentados?',
  f'Corte ou laceração: {vv(EV["natureza_lesao"]["corte_laceracao"])}; fratura ou amputação: {vv(EV["natureza_lesao"]["fratura_amputacao"])}. {NAC}', FV)
q(S_VIVA, 'Quais partes do corpo são mais atingidas nos acidentes de moto?',
  f'Membros inferiores: {vv(EV["parte_corpo_atingida"]["membros_inferiores"])}; membros superiores: {vv(EV["parte_corpo_atingida"]["membros_superiores"])}; cabeça e pescoço: {vv(EV["parte_corpo_atingida"]["cabeca_pescoco"])}. {NAC}', FV)
q(S_VIVA, 'Quantos acidentes de moto estão relacionados ao trabalho?',
  f'{vv(EV["relacionado_trabalho"]["sim"])} dos casos eram relacionados ao trabalho (inclui trajeto). {NAC}', FV)
q(S_VIVA, 'Como os motociclistas acidentados chegam ao hospital?',
  f'SAMU, ambulância ou resgate: {vv(AT["locomocao_para_hospital"]["samu_ambulancia_resgate"])}; veículo particular: {vv(AT["locomocao_para_hospital"]["veiculo_particular"])}. {NAC}', FV)
q(S_VIVA, 'Quantos motociclistas acidentados receberam atendimento antes do hospital?',
  f'{vv(AT["atendimento_previo"]["sim"])} tiveram atendimento prévio e {vv(AT["atendimento_previo"]["nao"])} não. {NAC}', FV)
for k, rot in [('alta', 'tiveram alta'), ('internacao_hospitalar', 'foram internados'), ('encaminhamento_ambulatorial', 'foram encaminhados ao ambulatório'), ('obito_outros', 'evoluíram para óbito ou outros desfechos')]:
    q(S_VIVA, f'Quantos motociclistas acidentados {rot}?',
      f'{vv(AT["evolucao"][k])} dos atendidos {rot}. {NAC}', FV)

# ------------------------------------------------------------------ Brasil (UFPI)
U = D['apresentacao_ufpi_morbimortalidade_brasil_2016_2025']
IB = U['internacoes_brasil_2016_2025']
OB = U['obitos_brasil_2015_2024']
FU = f'Apresentação UFPI (Amorim, Alves, Mascarenhas), {U["fonte"]["metodo"]["periodo"]}, dados nacionais'
NACU = 'Dado nacional (UFPI/SIH e SIM), não específico do Piauí.'
g = IB['geral']
q(S_BR, 'Como evoluiu a taxa de internação por acidentes de trânsito no Brasil?',
  f'Passou de {dec(g["coeficiente_internacao_100mil_hab"]["2016"])} por 100 mil hab. em 2016 para {dec(g["coeficiente_internacao_100mil_hab"]["2025"])} em 2025 (VPA {dec(g["coeficiente_internacao_100mil_hab"]["vpa_pct"], 2)}% ao ano, tendência crescente), alta de {g["variacao_internacoes_na_decada"].lstrip("+")} nas internações na década. {NACU}', FU)
q(S_BR, 'A letalidade hospitalar por acidentes de trânsito no Brasil está caindo?',
  f'Sim: de {dec(g["letalidade_hospitalar_pct"]["2016"], 2)}% em 2016 para {dec(g["letalidade_hospitalar_pct"]["2025"], 2)}% em 2025 (VPA {dec(g["letalidade_hospitalar_pct"]["vpa_pct"], 2)}% ao ano), enquanto internações e custos sobem. {NACU}', FU)
q(S_BR, 'Quanto custa uma internação por acidente de trânsito no Brasil?',
  f'O custo médio passou de R$ {brl(g["custo_medio_reais"]["2016"])} em 2016 para R$ {brl(g["custo_medio_reais"]["2025"])} em 2025 (VPA {dec(g["custo_medio_reais"]["vpa_pct"], 2)}% ao ano). {NACU}', FU)
q(S_BR, 'Quanto tempo dura a internação por acidentes de trânsito no Brasil?',
  f'A permanência média caiu de {dec(g["permanencia_media_dias"]["2016"])} dias em 2016 para {dec(g["permanencia_media_dias"]["2025"])} dias em 2025. {NACU}', FU)
q(S_BR, 'Por que as internações sobem e a letalidade cai no Brasil?',
  f'Segundo os autores: {g["explicacao_autores"]}. {NACU}', FU)
sx = IB['taxa_100mil_por_sexo']
q(S_BR, 'Qual a taxa de internação por acidentes de trânsito de homens e mulheres no Brasil?',
  f'Em 2025, homens: {dec(sx["masculino"]["2025"])} por 100 mil hab. e mulheres: {dec(sx["feminino"]["2025"])}. O crescimento feminino (VPA {dec(sx["feminino"]["vpa_pct"], 2)}%) é mais rápido que o masculino ({dec(sx["masculino"]["vpa_pct"], 2)}%). {NACU}', FU)
fa = IB['taxa_100mil_por_faixa_etaria']
q(S_BR, 'Qual faixa etária tem a maior taxa de internação por acidentes no Brasil?',
  f'De 20 a 29 anos: {dec(fa["20 a 29 anos"]["2025"])} por 100 mil hab. em 2025 (VPA {dec(fa["20 a 29 anos"]["vpa_pct"], 2)}% ao ano). {NACU}', FU)
q(S_BR, 'As internações por acidentes entre idosos estão aumentando no Brasil?',
  f'Entre 60 e 69 anos a tendência é crescente (taxa de {dec(fa["60 a 69 anos"]["2016"])} para {dec(fa["60 a 69 anos"]["2025"])}); de 70 a 79 e de 80 anos ou mais, estacionária. {NACU}', FU)
rc = IB['tendencia_por_raca_cor']
q(S_BR, 'Como evoluem as internações por acidentes entre negros e pardos no Brasil?',
  f'Crescem: VPA de {dec(rc["parda"]["vpa_pct"], 2)}% ao ano entre pardos e {dec(rc["preta"]["vpa_pct"], 2)}% entre pretos; entre brancos a tendência é estacionária ({dec(rc["branca"]["vpa_pct"], 2)}%). {NACU}', FU)
mt = OB['coeficiente_mortalidade_100mil_hab']
q(S_BR, 'Qual o coeficiente de mortalidade por acidentes de trânsito no Brasil?',
  f'Foi de {dec(mt["total"]["2015"])} por 100 mil hab. em 2015 e {dec(mt["total"]["2024"])} em 2024; a tendência é estacionária (VPA {dec(mt["total"]["vpa_pct"], 2)}%). {NACU}', FU)
uf = mt['por_unidade_federativa']
q(S_BR, 'Qual a posição do Piauí no ranking de mortalidade no trânsito do Brasil?',
  f'O Piauí teve o 2º maior coeficiente do país em 2024: {dec(uf["piaui"]["2024"])} por 100 mil hab., atrás do Tocantins ({dec(uf["tocantins"]["2024"])}) e à frente do Mato Grosso ({dec(uf["mato_grosso"]["2024"])}). A tendência é estacionária (VPA {dec(uf["piaui"]["vpa_pct"], 2)}%). Dado do SIM, residentes.', FU)
q(S_BR, 'Quais estados têm a menor mortalidade no trânsito no Brasil?',
  f'Em 2024: Rio de Janeiro ({dec(uf["rio_de_janeiro"]["2024"])}), Distrito Federal ({dec(uf["distrito_federal"]["2024"])}) e São Paulo ({dec(uf["sao_paulo"]["2024"])}) por 100 mil hab. {NACU}', FU)
q(S_BR, 'Qual estado mais reduziu a mortalidade no trânsito no Brasil?',
  f'O Ceará: de {dec(uf["ceara"]["2015"])} para {dec(uf["ceara"]["2024"])} por 100 mil hab. (VPA {dec(uf["ceara"]["vpa_pct"], 2)}% ao ano), seguido do DF e do Rio de Janeiro. {NACU}', FU)
q(S_BR, 'Qual a diferença da mortalidade no trânsito entre homens e mulheres no Brasil?',
  f'Em 2024, homens: {dec(mt["por_sexo"]["masculino"]["2024"])} por 100 mil hab.; mulheres: {dec(mt["por_sexo"]["feminino"]["2024"])}. O coeficiente masculino é cerca de 5 vezes o feminino. {NACU}', FU)
pf = mt['por_faixa_etaria']
q(S_BR, 'Que faixa etária morre mais no trânsito no Brasil?',
  f'A de 20 a 29 anos, com {dec(pf["20 a 29 anos"]["2024"])} por 100 mil hab. em 2024; adultos e idosos (30 a 80+) ficam entre {dec(pf["80 anos ou mais"]["2024"])} e {dec(pf["60 a 69 anos"]["2024"])}. A carga se concentra na população economicamente ativa. {NACU}', FU)
q(S_BR, 'A mortalidade de crianças no trânsito está caindo no Brasil?',
  f'Sim, entre 5 e 14 anos: VPA de {dec(pf["5 a 9 anos"]["vpa_pct"], 2)}% (5 a 9 anos) e {dec(pf["10 a 14 anos"]["vpa_pct"], 2)}% (10 a 14), o que pode refletir o uso de cadeirinhas (Resolução Contran). {NACU}', FU)
car = OB['caracteristicas_dos_obitos_pct_do_total_do_ano']
tv = car['tipo_de_vitima']
q(S_BR, 'Quem mais morre no trânsito no Brasil: motociclistas, pedestres ou ocupantes de carro?',
  f'Em 2024, motociclistas: {dec(tv["motociclista"]["2024"])}% dos óbitos (eram {dec(tv["motociclista"]["2015"])}% em 2015); ocupantes de automóvel: {dec(tv["ocupante_de_automovel"]["2024"])}%; pedestres: {dec(tv["pedestre"]["2024"])}%; ciclistas: {dec(tv["ciclista"]["2024"])}%. {NACU}', FU)
q(S_BR, 'A participação dos motociclistas nas mortes do trânsito está aumentando?',
  f'Sim: de {dec(tv["motociclista"]["2015"])}% dos óbitos em 2015 para {dec(tv["motociclista"]["2024"])}% em 2024 (VPA {dec(tv["motociclista"]["vpa_pct"], 2)}% ao ano). {NACU}', FU)
lo = car['local_de_ocorrencia']
q(S_BR, 'Onde morrem as vítimas de acidentes de trânsito no Brasil?',
  f'Em 2024, {dec(lo["via_publica"]["2024"])}% das mortes ocorreram na via pública e {dec(lo["hospital"]["2024"])}% no hospital. Muitas vítimas morrem antes da chegada do resgate. {NACU}', FU)
am = car['assistencia_medica']
q(S_BR, 'Quantos óbitos no trânsito ocorrem sem assistência médica no Brasil?',
  f'Em 2024, {dec(am["nao"]["2024"])}% dos óbitos foram sem assistência médica, contra {dec(am["sim"]["2024"])}% com assistência ({dec(am["ignorado"]["2024"])}% ignorado); considerando só o preenchido, há 8,35 vezes mais óbitos sem assistência. {NACU}', FU)
rcb = car['raca_cor']
q(S_BR, 'Qual a raça/cor das vítimas fatais do trânsito no Brasil?',
  f'Em 2024: pardos {dec(rcb["parda"]["2024"])}%, brancos {dec(rcb["branca"]["2024"])}%, pretos {dec(rcb["preta"]["2024"])}%. A queda de "ignorado" indica melhor preenchimento das declarações de óbito. {NACU}', FU)
q(S_BR, 'Quantas pessoas morrem e são internadas por acidentes de trânsito no Brasil por ano?',
  f'Segundo a apresentação: {U["contexto"]["brasil"]}. {NACU}', FU)
q(S_BR, 'Quantas pessoas morrem no trânsito no mundo?',
  f'Segundo a OMS, {U["contexto"]["mundo_oms"]}.', FU)
q(S_BR, 'O que aconteceu com o repasse do DPVAT ao SUS?',
  f'{up1(U["contexto"]["dpvat"])}.', FU)
q(S_BR, 'A frota de motocicletas está crescendo no Brasil?',
  f'Sim: {U["contexto"]["frota_motocicletas"]}. No Piauí, {U["piaui"]["motocicletas_por_domicilio"]}.', FU)
q(S_BR, 'O que os autores da UFPI concluem sobre os acidentes de trânsito no Brasil?',
  f'{up1(U["achados_qualitativos"][0])}; {U["achados_qualitativos"][2]}; {U["achados_qualitativos"][3]}. {NACU}', FU)
q(S_BR, 'Quais políticas os autores da UFPI recomendam?',
  '; '.join(up1(x) for x in U['recomendacoes_dos_autores']) + '.', FU)
q(S_BR, 'O que é o cinturão de risco no Norte e Nordeste?',
  f'{up1(U["piaui"]["cinturao_de_risco"])}.', FU)
q(S_BR, 'Qual o impacto da pandemia nos aglomerados de risco do trânsito?',
  'Segundo a apresentação, os aglomerados de risco no interior foram mantidos em 2020, mesmo com as restrições de mobilidade da COVID-19. Dado nacional (UFPI).', FU)
q(S_BR, 'A mortalidade no trânsito no Piauí está aumentando ou diminuindo?',
  f'Está estável: {dec(uf["piaui"]["2015"])} por 100 mil hab. em 2015 e {dec(uf["piaui"]["2024"])} em 2024 (VPA {dec(uf["piaui"]["vpa_pct"], 2)}%, tendência estacionária). Os autores veem nisso um platô insustentável. Dado do SIM, residentes.', FU)

# ------------------------------------------------------------------ Contexto
q(S_CTX, 'Quais fontes de dados este painel usa?',
  'Cinco: PRF (acidentes em rodovias federais do Piauí, 2020 em diante), SIH/SUS do artigo Bastos et al. (internações no Piauí 2010-2023), consulta bruta TABNET/DATASUS (Piauí e Teresina), VIVA Inquérito 2014 (motociclistas atendidos, nacional) e apresentação da UFPI (Brasil, 2016-2025).', 'metadata')
q(S_CTX, 'Qual a diferença entre os dados da PRF e os do SUS?',
  'A PRF conta acidentes e vítimas registrados nas rodovias federais; o SIH/SUS conta internações hospitalares de qualquer via, e o SIM conta óbitos por local de residência. São bases e metodologias diferentes, e os totais não devem ser somados nem comparados diretamente.', 'metadata')
q(S_CTX, 'O que é VPA?',
  'É a Variação Percentual Anual, calculada por regressão de Prais-Winsten: indica quanto, em média, um indicador cresce ou cai por ano. A tendência é crescente ou decrescente quando p < 0,05 e estacionária quando não há significância.', 'metadata')
q(S_CTX, 'O que é letalidade hospitalar?',
  'É a proporção de internações que terminam em óbito no hospital (óbitos hospitalares ÷ internações × 100). Não inclui mortes que ocorrem antes de a vítima chegar ao hospital.', 'metadata')
q(S_CTX, 'Qual a diferença entre acidente e sinistro de trânsito?',
  'A norma ABNT NBR 10697/2018 passou a usar "sinistro de trânsito" no lugar de "acidente", por ser um evento evitável, e não obra do acaso.', FU)
q(S_CTX, 'Os dados da PRF cobrem todas as vias do Piauí?',
  'Não. A PRF só atua em rodovias federais (BRs). Acidentes em rodovias estaduais, vias urbanas e estradas municipais não estão nesses números, por isso o total real de acidentes no estado é maior.', FPRF)
q(S_CTX, 'O que é um trecho crítico neste painel?',
  'É uma janela de 5 km de uma BR com muitos acidentes registrados pela PRF. A lista de trechos críticos ordena por número de acidentes ou por número de mortos.', FPRF)
q(S_CTX, 'Quais as limitações dos dados de internação do SIH/SUS?',
  'O SIH/SUS cobre cerca de 75% das internações do país e subestima o setor privado; os valores não incluem verbas de estados e municípios; há registros incompletos (principalmente no Nordeste); e o desenho ecológico não permite inferências causais individuais.', FE)
q(S_VG, 'Por que o Piauí tem tantos acidentes de moto?',
  f'Os dados indicam fatores como a alta presença de motocicletas ({dec(C["domicilios_com_motocicleta_pct_2024"])}% dos domicílios em 2024, a 2ª maior proporção do Brasil) e o crescimento da frota; a apresentação da UFPI também aponta baixa fiscalização no interior e vias rurais adaptadas. Isso é interpretação dos autores, não relação causal comprovada.', FE)
import calendar
dias_cheios = sum(366 if calendar.isleap(y) else 365 for y in ANOS_CHEIOS)
n_cheios = sum(st(g_ano[y])['n'] for y in ANOS_CHEIOS)
m_cheios = sum(st(g_ano[y])['m'] for y in ANOS_CHEIOS)
q(S_VG, 'Quantos acidentes e mortes acontecem por dia nas rodovias federais do Piauí?',
  f'Nos anos completos ({A0} a {A1}), a PRF registrou em média {dec(n_cheios / dias_cheios)} acidentes por dia ({dec(7 * n_cheios / dias_cheios)} por semana) e {dec(7 * m_cheios / dias_cheios)} mortes por semana, ou seja, uma morte a cada {dec(dias_cheios / m_cheios)} dias. {AVISO_PRF}', FPRF)
q(S_VG, 'Quanto os acidentes de trânsito custam ao SUS no Piauí?',
  f'De 2010 a 2023, as internações por acidentes de transporte custaram R$ {dec(VM["valor_total_periodo_reais"] / 1e6)} milhões ao SUS (R$ {dec(VM["valor_total_periodo_corrigido_igpm_reais"] / 1e6)} milhões corrigidos pelo IGP-M), em média R$ {brl(VM["geral"]["valor"])} por internação. O estudo avisa que não inclui verbas de estados e municípios, então o custo real é maior.', FE)
q(S_VG, 'Qual o perfil das vítimas de acidente de trânsito no Piauí?',
  f'Nas internações do SUS (2010-2023), predominam homens (taxa de {dec(TX["por_sexo"]["masculino"]["valor"])} por 100 mil, cerca de {dec(TX["por_sexo"]["masculino"]["valor"] / TX["por_sexo"]["feminino"]["valor"])} vezes a das mulheres), adultos jovens (maior taxa na faixa de {FAIXA[fa_top[0]]}, {dec(fa_top[1]["valor"])} por 100 mil) e motociclistas (taxa cerca de {dec(mo / pe, 0)} vezes a de pedestres).', FE)
q(S_VG, 'Quando é mais perigoso pegar a estrada no Piauí?',
  f'Pelos dados da PRF em rodovias federais: {PER_TXT[per_l]} é o período mais letal ({dec(st(g_per[per_l])["l"])} mortos por 100 acidentes); o horário com mais acidentes é {h_top[0][0]:02d}h; {d_m[0][0]} é o dia com mais mortos; e sábado e domingo reúnem {pc(pct(wk_m, TOT["m"]))} dos mortos. Trechos rurais concentram {pc(pct(rur["m"], TOT["m"]))} dos mortos e a pista simples, {pc(pct(ps["Simples"]["m"], TOT["m"]))}. {AVISO_PRF}', FPRF)
q(S_VG, 'Os acidentes de trânsito estão piorando no Piauí?',
  f'Depende do indicador. Nas rodovias federais (PRF), de {A0} a {A1} os acidentes tiveram {mud(var(pa[A0]["n"], pa[A1]["n"]))} e os mortos {mud(var(pa[A0]["m"], pa[A1]["m"]))}. A mortalidade no trânsito (SIM) está estável: {dec(uf["piaui"]["2015"])} por 100 mil hab. em 2015 e {dec(uf["piaui"]["2024"])} em 2024. Nas internações do SUS, a taxa teve tendência {tend(TX["geral"])} de 2010 a 2023. São bases diferentes.', FPRF + '; SIH/SUS; SIM')
q(S_VG, 'Qual a diferença de mortalidade nos acidentes usando cinto de segurança?',
  'Não é possível responder com os dados do painel: nenhuma das fontes carregadas (PRF, SIH/SUS, TABNET, VIVA 2014 e apresentação da UFPI) informa o uso de cinto de segurança. O VIVA 2014 traz só o uso de capacete entre motociclistas.', 'metadata')
mot_pi = cat_tot['V20-V29']
q(S_VG, 'Quais tipos de veículo mais se envolvem em sinistros?',
  f'As fontes não separam por veículo, e sim pelo tipo de vítima. No Piauí, motociclistas são {pc(pct(mot_pi, tot_p))} das internações por acidentes de transporte (TABNET) e a taxa de internação de motociclistas é cerca de {dec(mo / pe, 0)} vezes a de pedestres (SIH/SUS). No Brasil, motociclistas foram {dec(tv["motociclista"]["2024"])}% dos óbitos em 2024. O arquivo da PRF usado aqui não informa o tipo de veículo.', FT)
a_o = [st(g_ano[y])['m'] for y in ANOS_CHEIOS]
q(S_VG, 'Como evoluiu o número de óbitos nos últimos anos?',
  f'Nas rodovias federais do Piauí, a PRF registrou, por ano: {"; ".join(f"{y}, {st(g_ano[y])[chr(109)]} mortos" for y in ANOS_CHEIOS)}. Pelo SIM, o coeficiente de mortalidade no trânsito do estado ficou estável: {dec(uf["piaui"]["2015"])} por 100 mil hab. em 2015 e {dec(uf["piaui"]["2024"])} em 2024. São bases diferentes e não devem ser somadas.', FPRF + '; SIM 2015-2024')
q(S_CTX, 'Os dados da PRF e do SUS trazem informação sobre o tipo de veículo?',
  'Só parcialmente: as internações (SIH/SUS e TABNET) separam a vítima por tipo (motociclista, pedestre, ciclista, ocupante de automóvel etc.); o arquivo da PRF usado aqui não informa o tipo de veículo.', 'metadata')
q(S_CTX, 'Quem desenvolveu o projeto Infotrânsito?',
  'O projeto Infotrânsito (PICCS13381-2025), da Universidade Federal do Piauí, foi desenvolvido por Victor Hugo de Sousa Monteiro, com orientação de Márcio Dênis Medeiros Mascarenhas.', 'index.html')

# ------------------------------------------------------------------ validação e saída
# ------------------------------------------------------------------ Planos de ação (gerados por scripts/gerar_planos.py)
PLANOS = D['planos_de_acao']['temas']
NL = chr(10)
FPL = 'Diagnóstico: PRF, SIH/SUS e apresentação da UFPI; ações: propostas técnicas e recomendações dos autores'


def plano_txt(t, curto=False):
    linhas = ['Diagnóstico: ' + t['diagnostico'], 'Ações propostas:']
    for a_ in t['acoes']:
        origem = 'recomendação dos autores' if a_['origem'].startswith('recomendação') else 'proposta técnica'
        linhas.append(f'- {a_["acao"]} [{a_["eixo"]}; {origem}]')
    linhas.append('Acompanhar: ' + '; '.join(t['indicadores']) + '.')
    linhas.append('Quem envolver: ' + ', '.join(t['quem_envolver']) + '.')
    if t.get('observacao'):
        linhas.append('Observação: ' + t['observacao'])
    linhas.append('As ações são propostas a partir dos dados; os dados não medem a eficácia de cada medida.')
    return NL.join(linhas)


PERGUNTAS_PLANO = [
    ('plano_integrado', 'Monte um plano de ação integrado para reduzir mortes no trânsito do Piauí.'),
    ('pista_simples_rural', 'Que plano de ação reduziria as mortes nos trechos rurais de pista simples?'),
    ('colisao_frontal_contramao', 'Como reduzir as colisões frontais e as mortes por contramão nas rodovias federais?'),
    ('pedestres', 'Que ações reduziriam os atropelamentos nas rodovias federais do Piauí?'),
    ('noite_madrugada', 'Como reduzir os acidentes graves à noite e na madrugada?'),
    ('alcool_fim_de_semana', 'Que plano de ação combate o álcool ao volante e os acidentes de fim de semana?'),
    ('animais_na_pista', 'O que fazer para reduzir acidentes com animais na pista?'),
    ('atencao_fadiga', 'Como combater acidentes por falta de atenção, reação tardia e sono do condutor?'),
    ('teresina_urbano', 'Que medidas priorizar nos trechos críticos de Teresina?'),
    ('brs_mais_letais', 'Que ações priorizar nas rodovias federais mais letais por acidente?'),
    ('motociclistas', 'Que plano de ação reduziria os acidentes e as mortes de motociclistas no Piauí?'),
    ('atendimento_pre_hospitalar', 'Como melhorar o atendimento às vítimas para reduzir as mortes na via?'),
    ('dados_monitoramento', 'O que melhorar nos dados para monitorar os acidentes de trânsito no Piauí?'),
]
for chave, pergunta in PERGUNTAS_PLANO:
    q(S_PLANO, pergunta, plano_txt(PLANOS[chave]), FPL)

pi = PLANOS['plano_integrado']
q(S_PLANO, 'Por onde começar para reduzir as mortes nas rodovias federais do Piauí?',
  'Comece pelos recortes que concentram mais mortes. '
  + pi['diagnostico'] + NL + 'Trechos para começar: ' + '; '.join(pi['locais_prioritarios']) + '.' + NL +
  'As ações detalhadas de cada recorte estão nos planos de ação do painel. Elas são propostas a partir dos dados, que não medem a eficácia de cada medida.', FPL)
q(S_PLANO, 'Que recomendações os pesquisadores fazem para combater os sinistros no Piauí?',
  'Bastos et al. (2026) recomendam: ' + '; '.join(x.lower() for x in E['recomendacoes']) + '. '
  'A apresentação da UFPI recomenda: ' + '; '.join(x.lower() for x in U['recomendacoes_dos_autores']) + '.', 'Bastos et al. 2026; apresentação UFPI')

# ------------------------------------------------------------------ Planos por território e priorização (gerados por scripts/gerar_territorios.py)
PT = D['planos_por_territorio']
PZ = PT['priorizacao']
AT = D['atencao_territorial']
PACOTE = AT['pacote_de_medidas']


def plano_terr_txt(p):
    linhas = [f'Prioridade {p["prioridade"]["nivel"]}: ' + '; '.join(p['prioridade']['motivos']) + '.', 'Diagnóstico: ' + p['diagnostico']]
    if p.get('locais_prioritarios'):
        linhas.append('Trechos prioritários: ' + '; '.join(p['locais_prioritarios']) + '.')
    at_ = p.get('atencao') or {}
    if at_.get('nivel') in ('vermelho', 'laranja'):
        linhas.append(f'Mapa: {at_["rotulo"]}. Onde agir primeiro: {at_["onde_agir"]}')
    if p['acoes']:
        linhas.append('Ações propostas:')
        linhas += [f'- {a_["acao"]} [{a_["eixo"]}; {a_["origem"]}]' for a_ in p['acoes']]
    pacote = at_.get('pacote') or p.get('pacote') or []
    if pacote:
        linhas.append('Medidas para áreas em vermelho e laranja (diretriz do projeto):')
        linhas += [f'- {PACOTE[k]["titulo"]}: ' + ' '.join(PACOTE[k]['acoes']) for k in pacote]
        if 'gestao_velocidade' in pacote:
            linhas.append('Observação: ' + PACOTE['gestao_velocidade']['observacao'])
    linhas.append('Metas:')
    linhas += [f'- {m_["meta"]} ({m_["origem"]})' for m_ in p['metas']]
    linhas.append('Acompanhar: ' + '; '.join(p['indicadores']) + '.')
    linhas.append('Quem envolver: ' + ', '.join(p['quem_envolver']) + '.')
    linhas.append('As ações e metas são propostas a partir dos dados; os dados não medem a eficácia de cada medida.')
    return NL.join(linhas)


for p in PT['regioes_de_saude'].values():
    q(S_PLANO, f'Qual o plano de ação para a região de saúde {p["nome"]}?', plano_terr_txt(p), p['fonte'])
for p in PT['rodovias'].values():
    q(S_PLANO, f'Qual o plano de ação para a {p["nome"]}?', plano_terr_txt(p), p['fonte'])
for p in PT['municipios'].values():
    q(S_PLANO, f'Qual o plano de ação para {p["nome"]}?', plano_terr_txt(p), p['fonte'])

CR = PT['criterios_de_prioridade']
FPRF_PT = PT['rodovias'][next(iter(PT['rodovias']))]['fonte']
mz = PZ['municipios_prf']
fora = [x['municipio'] for x in mz['por_gravidade'][:5] + mz['por_crescimento'][:5] if x['municipio'] not in {y['municipio'] for y in mz['por_mortos']}]
q(S_PLANO, 'Quais 10 municípios priorizar nas rodovias federais do Piauí?',
  'Pelo número de mortos nas BRs (impacto), os 10 municípios a priorizar são:' + NL +
  NL.join(f'- {x["municipio"]}: {x["mortos"]} mortos em {num(x["acidentes"])} acidentes ({dec(x["mortos_por_100_acidentes"])} por 100), prioridade {x["prioridade"]}' for x in mz['por_mortos']) + NL +
  (f'Pela gravidade ou pelo crescimento também se destacam {lista(dict.fromkeys(fora))}. ' if fora else '') +
  f'Critério: {CR["alta_municipios_resumo"]}. São só rodovias federais (PRF); para óbitos e internações em todas as vias, veja as cores do mapa (SIM e SIH).', FPRF_PT)
rz = PZ['regioes_de_saude']
q(S_PLANO, 'Quais regiões de saúde priorizar para reduzir as internações por acidentes?',
  'Pelo nível de prioridade (taxa de internação e tendência, letalidade hospitalar):' + NL +
  NL.join(f'- {x["regiao"]}: {dec(x["taxa_100mil"])} internações por 100 mil hab., tendência {x["tendencia"]} (VPA {dec(x["vpa_pct"], 2)}% ao ano), letalidade {dec(x["letalidade_pct"])}%, prioridade {x["prioridade"]}'
          for x in sorted(rz['por_taxa'], key=lambda x: ('alta', 'média', 'monitorar').index(x['prioridade'])) if x['prioridade'] != 'monitorar') + NL +
  'Só monitorar: ' + lista(x['regiao'] for x in rz['por_taxa'] if x['prioridade'] == 'monitorar') + '. ' +
  CR['regioes_de_saude'].split('. ', 1)[1], FE)
tz = PZ['trechos_prf']
q(S_PLANO, 'Quais trechos das rodovias federais priorizar?',
  'Os 10 trechos de 5 km com mais mortos são:' + NL +
  NL.join(f'- {x["trecho"]} ({x["municipio"]}): {x["mortos"]} mortos em {num(x["acidentes"])} acidentes' for x in tz['por_mortos']) + NL +
  'Os mais graves por acidente (com 20 ou mais acidentes): ' + '; '.join(f'{x["trecho"]} ({x["municipio"]}, {dec(x["mortos_por_100_acidentes"])} mortos por 100)' for x in tz['por_gravidade'][:3]) + '.', FPRF_PT)
q(S_PLANO, 'Quais rodovias federais priorizar no Piauí?',
  'Entre as BRs com 100 ou mais acidentes, por número de mortos:' + NL +
  NL.join(f'- {x["rodovia"]}: {x["mortos"]} mortos em {num(x["acidentes"])} acidentes ({dec(x["mortos_por_100_acidentes"])} por 100), prioridade {x["prioridade"]}' for x in PZ['rodovias_prf']) + NL +
  'O plano de cada BR está no painel e nas perguntas "Qual o plano de ação para a BR-...?".', FPRF_PT)

# ------------------------------------------------------------------ Mapa: áreas em vermelho (SIM e SIH, todas as vias)
S_MAPA = S_PLANO
EST = AT['estado']
PRI = AT['prioritarios']
FAT = AT['fonte']


def area_txt(a):
    return f'{a["nome"]}: {dec(a["taxa_obitos"])} óbitos por 100 mil hab. por ano ({dec(a["razao_obitos"], 2)} vezes o estado) e {dec(a["taxa_internacoes"])} internações ({dec(a["razao_internacoes"], 2)} vezes)'


reg_verm = [a for a in AT['regioes'].values() if a['nivel'] == 'vermelho']
q(S_MAPA, 'Quais regiões do Piauí estão em vermelho no mapa?',
  f'Pela taxa de óbitos e de internações de residentes em {AT["periodo"]} (estado: {dec(EST["taxa_obitos"])} óbitos e {dec(EST["taxa_internacoes"])} internações por 100 mil hab. por ano), '
  'estão em vermelho:' + NL + NL.join('- ' + area_txt(a) for a in reg_verm) + NL +
  f'Em laranja: {lista(PRI["regioes_laranjas"])}. São {PRI["total_municipios_vermelhos"]} municípios em vermelho no estado. Regra: {AT["metodo"]}', FAT)
q(S_MAPA, 'Que plano de ação seguir nas regiões em vermelho do mapa?',
  'Nas regiões em vermelho (' + lista(a['nome'] for a in reg_verm) + '), a proposta combina quatro frentes:' + NL +
  NL.join(f'- {PACOTE[k]["titulo"]}: ' + ' '.join(PACOTE[k]['acoes']) + ' Quem executa: ' + ', '.join(PACOTE[k]['quem']) + '.' for k in ('gestao_velocidade', 'infraestrutura', 'fiscalizacao_eletronica', 'educacao')) + NL +
  'Onde começar: ' + '; '.join(f'{a["nome"]}: municípios ' + lista((a['municipios_vermelhos'] or a['municipios_com_mais_obitos'])[:4]) for a in reg_verm) + '.' + NL +
  PACOTE['gestao_velocidade']['observacao'] + ' As medidas são diretrizes do projeto, propostas; os dados não medem a eficácia delas.', FAT)
mv = PRI['municipios_vermelhos_com_mais_obitos']
q(S_MAPA, 'Quais municípios estão em vermelho no mapa com mais óbitos?',
  f'Dos {PRI["total_municipios_vermelhos"]} municípios em vermelho, os que têm mais óbitos de residentes por acidentes de transporte em {AT["periodo"]} são:' + NL +
  NL.join(f'- {x["municipio"]} ({x["regiao"]}): {x["obitos"]} óbitos, {dec(x["taxa_obitos"])} por 100 mil hab. por ano' for x in mv[:10]) + NL +
  f'Óbitos contados pelo município de residência da vítima. Estado: {dec(EST["taxa_obitos"])} por 100 mil hab. por ano.', FAT)
rv = PRI['rodovias_nos_municipios_vermelhos']
q(S_MAPA, 'Quais rodovias estaduais passam pelos municípios em vermelho?',
  f'Pelo traçado do OpenStreetMap, {len(rv["estaduais"])} rodovias estaduais cortam municípios em vermelho, entre elas {lista(rv["estaduais"][:15])}; '
  f'e as federais {lista(rv["federais"])}. A base não tem sinistros georreferenciados nas rodovias estaduais (só a PRF, nas BRs); por isso as cores vêm de óbitos e internações dos residentes. '
  'Nas travessias urbanas dessas rodovias, a proposta é baixar a velocidade e instalar fiscalização eletrônica, com o DER-PI (estaduais) e DNIT/PRF (federais).', FAT + '; OpenStreetMap')

# perguntas "de detalhe" (uma por BR, ano, faixa etária, região...) aparecem menos nas sugestões
DETALHE = re.compile(
    r'(Qual o plano de ação para |houve na BR-|trecho mais crítico da BR-|rodovias federais em [A-ZÁÉÍÓÚÂÊÔÃÕÇ]|Quantos acidentes e mortes houve em 20|foram causados por|'
    r'Quantos acidentes do tipo|Quantos acidentes ocorrem |internação por acidentes entre pessoas de|Qual a taxa de internação de |macrorregião [A-Z]|'
    r'região de saúde [A-Z]|houve no Piauí em 20\d\d segundo|Quantas internações de |motociclistas acidentados tinham|proporção de motociclistas|'
    r'Quantos motociclistas acidentados (tiveram|foram|receberam|evoluíram|não)|Quantos motociclistas foram internados em Teresina|Quantos pedestres foram internados)')
# perguntas de método/glossário/fontes: continuam respondidas se digitadas, mas não viram sugestão
SO_DIGITADA = {
    'O que é a pesquisa VIVA 2014?', 'Quais as categorias de acidente de transporte do CID-10 usadas no TABNET?',
    'Quais são as limitações do estudo de internações no Piauí?', 'Quantos habitantes e municípios tem o Piauí?',
}
vistos = set()
for i, item in enumerate(QA, 1):
    item['chip'] = item['secao'] != S_CTX and item['pergunta'] not in SO_DIGITADA
    item['destaque'] = not DETALHE.search(item['pergunta'])
    assert item['pergunta'] not in vistos, 'pergunta duplicada: ' + item['pergunta']
    vistos.add(item['pergunta'])
    assert 'None' not in item['resposta'] and 'nan' not in item['resposta'].lower().split(), item['pergunta']
    item['id'] = i

saida = os.path.join(ROOT, 'data', 'perguntas.json')
with open(saida, 'w', encoding='utf-8', newline='') as fh:
    json.dump(QA, fh, ensure_ascii=False, indent=1)
por_secao = collections.Counter(x['secao'] for x in QA)
print(len(QA), 'perguntas;', sum(x['chip'] for x in QA), 'elegíveis como sugestão;', sum(x['destaque'] for x in QA), 'em destaque')
for sec in por_secao:
    print(f'     destaque em "{sec}":', sum(1 for x in QA if x['secao'] == sec and x['destaque']))
for s, n in por_secao.items():
    print(f'  {n:3d}  {s}')
