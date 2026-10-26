"""Gera os planos de ação por território e os rankings de priorização (data/sinistros.json -> planos_por_territorio)
e os dados do mapa do painel (data/mapa_prf.json e data/malha_pi.json).
Territórios: as 12 regiões de saúde (SIH/SUS 2010-2023, Bastos et al. 2026), as rodovias federais com 100 ou mais
acidentes e os municípios com 30 ou mais acidentes nas BRs (PRF). Diagnóstico, prioridade e metas numéricas são
calculados; as ações vêm de planos_de_acao (gerar_planos.py) e são escolhidas pelos fatores do território que ficam
acima da média do estado. A malha municipal é baixada uma vez do IBGE e guardada em data/malha_pi.json.
Rode depois de gerar_planos.py e antes de gerar_perguntas.py.
Uso: python scripts/gerar_territorios.py"""
import collections, csv, gzip, json, os, unicodedata, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'data', 'sinistros.json')
MALHA = os.path.join(ROOT, 'data', 'malha_pi.json')
MAPA = os.path.join(ROOT, 'data', 'mapa_prf.json')
D = json.load(open(JS, encoding='utf-8'))
ROWS = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'prf_acidentes_pi.csv'), encoding='utf-8', newline='')))
PLANOS = D['planos_de_acao']['temas']

MIN_MUNICIPIO = 30   # acidentes nas BRs para o município ganhar plano e entrar nos rankings de gravidade/crescimento
MIN_BR = 100         # mesmo corte de perfil_por_br (interpretar_prf.py)
MIN_TRECHO = 20      # acidentes no trecho de 5 km para entrar no ranking de gravidade
TOP = 10


def dec(x, c=1):
    return f'{x:.{c}f}'.replace('.', ',')


def num(x):
    return f'{int(round(x)):,}'.replace(',', '.')


def pc(x, c=1):
    return dec(x, c) + '%'


def pct(a, b):
    return 100 * a / b if b else 0.0


def lista(itens):
    itens = list(itens)
    return ''.join(itens) if len(itens) <= 1 else ', '.join(itens[:-1]) + ' e ' + itens[-1]


def pl(n, sing, plur):
    return f'{num(n)} {sing if n == 1 else plur}'


def brl(x):
    inteiro, frac = f'{x:.2f}'.split('.')
    return f'{int(inteiro):,}'.replace(',', '.') + ',' + frac


def br_data(s):
    return f'{s[8:10]}/{s[5:7]}/{s[:4]}'


def chave(nome):
    """Nome sem acento, maiúsculo, para casar a grafia da PRF com a do IBGE."""
    s = unicodedata.normalize('NFD', nome).encode('ascii', 'ignore').decode()
    return s.upper().replace("'", '').replace('-', ' ').strip()


def grp(key, rs):
    g = collections.defaultdict(list)
    for r in rs:
        g[key(r)].append(r)
    return g


# ---------------------------------------------------------------- malha municipal do IBGE (baixada uma vez)
URL_MALHA = ('https://servicodados.ibge.gov.br/api/v3/malhas/estados/22'
             '?formato=application/vnd.geo%2Bjson&qualidade=intermediaria&intrarregiao=municipio')
URL_NOMES = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados/22/municipios'


def baixar(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        corpo = r.read()
    if corpo[:2] == b'\x1f\x8b':   # a API do IBGE responde em gzip mesmo sem pedir
        corpo = gzip.decompress(corpo)
    return json.loads(corpo.decode('utf-8'))


def simplificar(pts, tol):
    """Douglas-Peucker: tira vértices que se afastam menos de 'tol' graus da linha simplificada."""
    if len(pts) < 5:
        return pts
    manter = [False] * len(pts)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pts) - 1)]
    while pilha:
        a, b = pilha.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        norma = (dx * dx + dy * dy) ** 0.5
        pior, idx = 0.0, None
        for i in range(a + 1, b):
            x0, y0 = pts[i]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norma if norma else ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            if d > pior:
                pior, idx = d, i
        if idx is not None and pior > tol:
            manter[idx] = True
            pilha += [(a, idx), (idx, b)]
    out = [p for p, k in zip(pts, manter) if k]
    return out if len(out) >= 4 else pts


if not os.path.exists(MALHA):
    print('baixando a malha municipal do IBGE...')
    geo, nomes = baixar(URL_MALHA), baixar(URL_NOMES)
    nome_por_codigo = {str(m['id']): m['nome'] for m in nomes}
    municipios = []
    for f in geo['features']:
        g = f['geometry']
        poligonos = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        aneis = []
        for pol in poligonos:
            for anel in pol:
                s = simplificar(anel, 0.003)
                aneis.append([v for lon, lat in s for v in (round(lon, 3), round(lat, 3))])
        codigo = f['properties']['codarea']
        municipios.append({'codigo': codigo, 'nome': nome_por_codigo[codigo], 'aneis': aneis})
    municipios.sort(key=lambda m: m['nome'])
    malha = {'fonte': 'IBGE, malha municipal do Piauí (API de malhas v3, qualidade intermediária), simplificada para o painel',
             'origem': URL_MALHA, 'coordenadas': 'cada anel é uma lista [lon, lat, lon, lat, ...] em graus (WGS84)',
             'municipios': municipios}
    open(MALHA, 'w', encoding='utf-8', newline='').write(json.dumps(malha, ensure_ascii=False, separators=(',', ':')))
MALHA_D = json.load(open(MALHA, encoding='utf-8'))
NOME_IBGE = {chave(m['nome']): m['nome'] for m in MALHA_D['municipios']}

# ---------------------------------------------------------------- PRF
for r in ROWS:
    for c in ['mortos', 'feridos_graves']:
        r[c] = int(r[c])
    r['hora'] = int(r['horario'][:2])
    r['noite'] = r['hora'] >= 18 or r['hora'] < 6
    r['ano'] = int(r['data_inversa'][:4])
    r['km_f'] = float(r['km']) if r['km'] not in ('', 'NA') else None
    r['mun'] = NOME_IBGE.get(chave(r['municipio']), r['municipio'].title())
N = len(ROWS)
TOT_M = sum(r['mortos'] for r in ROWS)
LET = pct(TOT_M, N)
DATAS = sorted(r['data_inversa'] for r in ROWS)
DMIN, DMAX = DATAS[0], DATAS[-1]
ANO_PARCIAL = int(DMAX[:4]) if DMAX[5:] < '12-31' else None
ANOS = sorted({r['ano'] for r in ROWS})
CHEIOS = [y for y in ANOS if y != ANO_PARCIAL]
K = len(CHEIOS) // 2
ANTES, DEPOIS = CHEIOS[-2 * K:-K], CHEIOS[-K:]
PERIODO = f'{br_data(DMIN)} a {br_data(DMAX)}' + (f', sendo {ANO_PARCIAL} parcial' if ANO_PARCIAL else '')
FONTE_PRF = f'PRF, dados abertos, só rodovias federais do Piauí, {PERIODO}'
FONTE_SIH = 'SIH/SUS 2010-2023 (Bastos et al., Rev Bras Epidemiol 2026)'


def janela(anos):
    return f'{anos[0]}-{anos[-1]}'


def st(rs):
    n = len(rs)
    m = sum(r['mortos'] for r in rs)
    antes = [r for r in rs if r['ano'] in ANTES]
    depois = [r for r in rs if r['ano'] in DEPOIS]
    return {'n': n, 'm': m, 'fg': sum(r['feridos_graves'] for r in rs), 'l': pct(m, n),
            'n_antes': len(antes), 'n_depois': len(depois),
            'var': pct(len(depois) - len(antes), len(antes)) if antes else None,
            'm_ano_depois': sum(r['mortos'] for r in depois) / len(DEPOIS)}


def seg(r):
    return None if (r['km_f'] is None or r['br'] == '0') else (r['br'], int(r['km_f'] // 5) * 5)


def trechos(rs):
    """Trechos de 5 km (BR + janela de km), com o município mais frequente, como em importar_prf.py."""
    out = []
    for k, v in grp(seg, rs).items():
        if k is None:
            continue
        s = st(v)
        out.append({'k': k, 'trecho': f'BR-{k[0]}, km {k[1]} a {k[1] + 5}',
                    'municipio': collections.Counter(r['mun'] for r in v).most_common(1)[0][0], **s})
    return out


def por_mortos(itens):
    return sorted(itens, key=lambda t: (-t['m'], -t['n'], t['k']))


def trecho_txt(t):
    return f'{t["trecho"]} ({t["municipio"]}: {pl(t["n"], "acidente", "acidentes")}, {pl(t["m"], "morto", "mortos")})'


# ---------------------------------------------------------------- fatores comparados com a média do estado
HUM = {'Ausência de reação do condutor', 'Reação tardia ou ineficiente do condutor',
       'Condutor deixou de manter distância do veículo da frente', 'Falta de Atenção à Condução', 'Condutor Dormindo'}
FATORES = [
    ('trechos rurais', lambda r: r['uso_solo'] == 'Não', 'pista_simples_rural'),
    ('pista simples', lambda r: r['tipo_pista'] == 'Simples', 'pista_simples_rural'),
    ('noite e madrugada (18h às 5h59)', lambda r: r['noite'], 'noite_madrugada'),
    ('colisão frontal, contramão ou ultrapassagem indevida',
     lambda r: r['tipo_acidente'] == 'Colisão frontal' or r['causa_acidente'] in ('Transitar na contramão', 'Ultrapassagem Indevida'),
     'colisao_frontal_contramao'),
    ('atropelamento de pedestre', lambda r: r['tipo_acidente'] == 'Atropelamento de Pedestre', 'pedestres'),
    ('animais na pista', lambda r: r['causa_acidente'] == 'Animais na Pista' or r['tipo_acidente'] == 'Atropelamento de Animal', 'animais_na_pista'),
    ('álcool do condutor', lambda r: r['causa_acidente'] == 'Ingestão de álcool pelo condutor', 'alcool_fim_de_semana'),
    ('sábado e domingo', lambda r: r['dia_semana'] in ('sábado', 'domingo'), 'alcool_fim_de_semana'),
    ('falta de atenção, reação tardia ou sono', lambda r: r['causa_acidente'] in HUM, 'atencao_fadiga'),
]
REF = {nome: pct(sum(1 for r in ROWS if f(r)), N) for nome, f, _ in FATORES}


def fatores(rs):
    """Participação de cada fator nos acidentes do território. 'Acima da média': ao menos 3 casos, 20% acima da
    média do estado e 2 pontos percentuais ou mais de diferença; 'abaixo': 20% ou mais abaixo da média."""
    out = []
    for nome, f, tema in FATORES:
        sel = [r for r in rs if f(r)]
        v, ref = pct(len(sel), len(rs)), REF[nome]
        acima = len(sel) >= 3 and v >= 1.2 * ref and v - ref >= 2
        out.append({'fator': nome, 'pct_acidentes': round(v, 1), 'media_estado_pct': round(ref, 1),
                    'acidentes': len(sel), 'mortos': sum(r['mortos'] for r in sel),
                    'situacao': 'acima da média' if acima else 'abaixo da média' if v <= 0.8 * ref else 'próximo da média',
                    'tema': tema, '_razao': v / ref if ref else 0})
    return out


# ---------------------------------------------------------------- prioridade, ações e metas
META_ONU = 'referência: meta da ONU para 2030'
PROP = 'proposta técnica'
AUT_B = 'recomendação dos autores (Bastos et al., Rev Bras Epidemiol 2026)'
AUT_U = 'recomendação dos autores (apresentação UFPI)'


def curta(a):
    """Rótulo curto da origem (o texto completo de cada tipo fica em planos_por_territorio.origens)."""
    o = a['origem']
    autores = [n for n, chave_ in (('Bastos et al. 2026', 'Bastos'), ('UFPI', 'UFPI')) if chave_ in o]
    if not autores:
        rotulo = PROP
    else:
        rotulo = 'recomendação dos autores (' + ' e '.join(autores) + ')' + (', detalhada como proposta técnica' if 'proposta técnica' in o else '')
    return {'acao': a['acao'], 'eixo': a['eixo'], 'origem': rotulo, 'por_que': a['por_que']}


def acao_de(tema, i, por_que):
    return {**PLANOS[tema]['acoes'][i], 'por_que': por_que}


def sem_repetir(acoes):
    vistos, out = set(), []
    for a in acoes:
        if a['acao'] not in vistos:
            vistos.add(a['acao'])
            out.append(a)
    return out


def nivel_prf(s, pos_m, pos_g, regra, mediana_m, nome_lista):
    """alta: entre os top_m em mortos, ou entre os top_g em gravidade com mortos na mediana ou acima; média: mortos
    acima da mediana, gravidade acima da média ou acidentes crescendo 20% ou mais entre os triênios; monitorar: nenhum."""
    top_m, top_g = regra
    fortes, medios = [], []
    if pos_m <= top_m:
        fortes.append(f'{pos_m}º em mortos entre {nome_lista}')
    if pos_g <= top_g and s['m'] >= mediana_m:
        fortes.append(f'{pos_g}º em gravidade ({dec(s["l"])} mortos por 100 acidentes, {dec(s["l"] / LET)} vezes a média do estado) com {pl(s["m"], "morto", "mortos")}')
    elif s['l'] > LET:
        medios.append(f'gravidade acima da média do estado ({dec(s["l"])} contra {dec(LET)} mortos por 100 acidentes)')
    if pos_m > top_m and s['m'] > mediana_m:
        medios.append(f'mortos acima da mediana ({num(s["m"])} contra {dec(mediana_m)})')
    if s['var'] is not None and s['var'] >= 20:
        medios.append(f'acidentes cresceram {dec(s["var"])}% de {janela(ANTES)} para {janela(DEPOIS)}')
    nivel = 'alta' if fortes else 'média' if medios else 'monitorar'
    return {'nivel': nivel, 'motivos': fortes + medios or ['nenhum critério acima da referência do estado']}


def plano_prf(nome, tipo, rs, pos_m, pos_n, pos_g, regra, mediana_m, nome_lista, extra_temas=None):
    """extra_temas: {tema: motivo} que entram antes dos fatores (ex.: o plano urbano de Teresina)."""
    s = st(rs)
    fs = fatores(rs)
    acima = sorted((f for f in fs if f['situacao'] == 'acima da média'), key=lambda f: -f['_razao'])
    temas, motivo = list(extra_temas or {}), dict(extra_temas or {})
    for f in acima:
        if f['tema'] not in temas:
            temas.append(f['tema'])
            motivo[f['tema']] = f'{f["fator"]}: {pc(f["pct_acidentes"])} dos acidentes (média do estado {pc(f["media_estado_pct"])})'
    for f in sorted(fs, key=lambda f: -f['mortos']):   # sem fatores de destaque: os que mais matam no território
        if len(temas) >= 2:
            break
        if f['tema'] not in temas and f['mortos']:
            temas.append(f['tema'])
            motivo[f['tema']] = f'{f["fator"]}: fator com mais mortos no território ({num(f["mortos"])}), perto da média do estado'
    temas = temas[:3]
    acoes = [acao_de(t, i, motivo[t]) for t in temas for i in range(min(2, len(PLANOS[t]['acoes'])))]
    if s['l'] > LET:
        acoes.append(acao_de('atendimento_pre_hospitalar', 1, f'gravidade acima da média do estado ({dec(s["l"])} contra {dec(LET)} mortos por 100 acidentes)'))
    acoes.append(acao_de('dados_monitoramento', 2, 'acompanhar as metas do território'))

    locais = por_mortos(trechos(rs))[:3]
    metas = []
    base = s['m_ano_depois']
    if base > 0:
        anos = 2030 - DEPOIS[-1]
        queda = 100 * (1 - 0.5 ** (1 / anos))
        metas.append({'meta': f'Reduzir pela metade os mortos por ano até 2030: de {dec(base)} (média de {janela(DEPOIS)}) para no máximo {dec(base / 2)}, '
                              f'queda de cerca de {pc(queda, 0)} ao ano.', 'origem': META_ONU})
    else:
        metas.append({'meta': f'Manter zero mortos por ano (nenhum morto em {janela(DEPOIS)}).', 'origem': META_ONU})
    if s['l'] > LET:
        metas.append({'meta': f'Baixar a gravidade de {dec(s["l"])} para no máximo {dec(LET)} mortos por 100 acidentes (média do estado).', 'origem': PROP})
    if locais:
        metas.append({'meta': f'Fazer a inspeção de segurança viária {"do trecho prioritário" if len(locais) == 1 else f"dos {len(locais)} trechos prioritários"} e definir as obras no primeiro ano do plano.', 'origem': PROP})

    indicadores = ['mortos por ano nas BRs (PRF)', 'mortos por 100 acidentes', 'acidentes e mortos por ano nos trechos prioritários']
    quem = []
    for t in temas:
        # o primeiro indicador do tema que não cite uma contagem fixa de trechos (ex.: "nos 4 trechos" de Teresina)
        indicadores += [x for x in PLANOS[t]['indicadores'] if not any(c.isdigit() for c in x)][:1]
        for x in PLANOS[t]['quem_envolver']:
            if not any(y.split(' (')[0] == x.split(' (')[0] for y in quem):   # "PRF" e "PRF (fiscalização)" contam uma vez
                quem.append(x)
    indicadores = list(dict.fromkeys(indicadores))
    if tipo == 'municipio':
        quem = [f'prefeitura de {nome}' if x == 'prefeituras' else x for x in quem]

    por_ano = {str(y): sum(r['mortos'] for r in rs if r['ano'] == y) for y in ANOS}
    anos_txt = '; '.join(f'{y}: {m}' for y, m in por_ano.items()) + (f' ({ANO_PARCIAL} parcial)' if ANO_PARCIAL else '')
    var_txt = (f'Acidentes em {janela(ANTES)}: {num(s["n_antes"])}; em {janela(DEPOIS)}: {num(s["n_depois"])}'
               + (f' ({"+" if s["var"] >= 0 else ""}{dec(s["var"])}%)' if s['var'] is not None else '') + '.')
    ord_ = 'º' if tipo == 'municipio' else 'ª'
    diag = (f'{nome}: {pl(s["n"], "acidente", "acidentes")} e {pl(s["m"], "morto", "mortos")} nas rodovias federais ({PERIODO}), '
            f'{dec(s["l"])} mortos por 100 acidentes (média do estado: {dec(LET)}). {pos_m}{ord_} em mortos e {pos_n}{ord_} em acidentes entre {nome_lista}. '
            f'Mortos por ano: {anos_txt}. {var_txt} '
            + (f'Fatores acima da média do estado: {lista(f"{f["fator"]} ({pc(f["pct_acidentes"])} dos acidentes, média {pc(f["media_estado_pct"])})" for f in acima)}.'
               if acima else 'Nenhum fator fica acima da média do estado.'))
    if tipo == 'municipio':
        brs = collections.Counter(r['br'] for r in rs if r['br'] != '0').most_common(3)
        diag += f' BRs no município: {lista(f"BR-{b} ({num(n)} acidentes)" for b, n in brs)}.'
    else:
        muns = sorted(grp(lambda r: r['mun'], rs).items(), key=lambda kv: (-sum(r['mortos'] for r in kv[1]), -len(kv[1]), kv[0]))[:3]
        diag += f' Municípios com mais mortos na rodovia: {lista(f"{k} ({sum(r["mortos"] for r in v)})" for k, v in muns)}.'
    return {
        'nome': nome, 'tipo': 'município (rodovias federais)' if tipo == 'municipio' else 'rodovia federal',
        'fonte': FONTE_PRF,
        'prioridade': nivel_prf(s, pos_m, pos_g, regra, mediana_m, nome_lista),
        'diagnostico': diag,
        'numeros': {'acidentes': s['n'], 'mortos': s['m'], 'feridos_graves': s['fg'], 'mortos_por_100_acidentes': round(s['l'], 1),
                    'mortos_por_ano': por_ano, f'acidentes_{janela(ANTES)}': s['n_antes'], f'acidentes_{janela(DEPOIS)}': s['n_depois'],
                    'variacao_acidentes_pct': None if s['var'] is None else round(s['var'], 1)},
        'fatores': [{'fator': f['fator'], 'pct_acidentes': f['pct_acidentes'], 'mortos': f['mortos'], 'situacao': f['situacao']} for f in fs],
        'locais_prioritarios': [trecho_txt(t) for t in locais],
        'acoes': [curta(a) for a in sem_repetir(acoes)],
        'metas': metas,
        'indicadores': indicadores,
        'quem_envolver': quem,
    }


def mediana(vals):
    v = sorted(vals)
    return (v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2 if v else 0


# ---------------------------------------------------------------- municípios e rodovias (PRF)
g_mun = grp(lambda r: r['mun'], ROWS)
s_mun = {k: st(v) for k, v in g_mun.items()}
ord_m = sorted(s_mun, key=lambda k: (-s_mun[k]['m'], -s_mun[k]['n'], k))
ord_n = sorted(s_mun, key=lambda k: (-s_mun[k]['n'], -s_mun[k]['m'], k))
elegiveis = [k for k in ord_m if s_mun[k]['n'] >= MIN_MUNICIPIO]
grav = sorted(elegiveis, key=lambda k: (-s_mun[k]['l'], -s_mun[k]['m'], k))
med_mun = mediana([s_mun[k]['m'] for k in elegiveis])
LISTA_MUN = f'os {len(s_mun)} municípios com acidentes nas BRs'
REGRA_MUN, REGRA_BR = (TOP, 5), (3, 2)   # (top em mortos, top em gravidade) para prioridade alta
municipios = {}
for k in elegiveis:
    municipios[k] = plano_prf(k, 'municipio', g_mun[k], ord_m.index(k) + 1, ord_n.index(k) + 1, grav.index(k) + 1, REGRA_MUN, med_mun, LISTA_MUN,
                              {'teresina_urbano': f'capital com {pc(pct(s_mun[k]["n"], N))} dos acidentes das BRs do estado, em trechos urbanos'}
                              if k == 'Teresina' else None)

g_br = {k: v for k, v in grp(lambda r: r['br'], ROWS).items() if k != '0' and len(v) >= MIN_BR}
s_br = {k: st(v) for k, v in g_br.items()}
ordb_m = sorted(s_br, key=lambda k: (-s_br[k]['m'], -s_br[k]['n'], k))
ordb_n = sorted(s_br, key=lambda k: (-s_br[k]['n'], -s_br[k]['m'], k))
ordb_g = sorted(s_br, key=lambda k: (-s_br[k]['l'], -s_br[k]['m'], k))
med_br = mediana([s['m'] for s in s_br.values()])
LISTA_BR = f'as {len(s_br)} BRs com {MIN_BR} ou mais acidentes'
rodovias = {}
for k in ordb_m:
    rodovias['BR-' + k] = plano_prf('BR-' + k, 'br', g_br[k], ordb_m.index(k) + 1, ordb_n.index(k) + 1, ordb_g.index(k) + 1, REGRA_BR, med_br, LISTA_BR)

# ---------------------------------------------------------------- regiões de saúde (SIH/SUS)
E = D['estudo_morbidade_piaui_2010_2023']
TX, LT, VM = E['taxa_internacao_hospitalar_100mil_hab'], E['letalidade_hospitalar_pct'], E['valor_medio_internacao_reais']
NOMES_REGIAO = {   # mesmos nomes e macrorregiões de script.js
    'carnaubais': ('Carnaubais', 'meio_norte'), 'chapada_das_mangabeiras': ('Chapada das Mangabeiras', 'semiarido'),
    'cocais': ('Cocais', 'meio_norte'), 'entre_rios': ('Entre Rios', 'meio_norte'),
    'planicie_litoranea': ('Planície Litorânea', 'litoral'), 'serra_da_capivara': ('Serra da Capivara', 'semiarido'),
    'tabuleiros_do_alto_parnaiba': ('Tabuleiros do Alto Parnaíba', 'cerrado'), 'vale_do_caninde': ('Vale do Canindé', 'semiarido'),
    'vale_do_rio_guaribas': ('Vale do Rio Guaribas', 'semiarido'), 'vale_do_sambito': ('Vale do Sambito', 'meio_norte'),
    'vale_dos_rios_piaui_e_itaueiras': ('Vale dos Rios Piauí e Itaueiras', 'cerrado'),
    'chapada_vale_do_rio_itaim': ('Chapada Vale do Rio Itaim', 'litoral'),
}
NOMES_MACRO = {'meio_norte': 'Meio-Norte', 'semiarido': 'Semiárido', 'litoral': 'Litoral', 'cerrado': 'Cerrado'}
TX_PI, LT_PI = TX['geral']['valor'], LT['geral']['valor']
reg_tx = TX['por_regiao_de_saude']
reg_lt = LT['por_regiao_de_saude']
ordr_tx = sorted(reg_tx, key=lambda k: -reg_tx[k]['valor'])
ordr_vpa = sorted(reg_tx, key=lambda k: -reg_tx[k]['vpa_pct'])
ordr_lt = sorted(reg_lt, key=lambda k: -reg_lt[k]['valor'])


def tend(x):
    return x['tendencia'].lower()


def ic(x):
    return f'VPA {dec(x["vpa_pct"], 2)}% ao ano, IC95% {dec(x["ic95_min"], 2)} a {dec(x["ic95_max"], 2)}'


regioes = {}
for k in ordr_tx:
    nome, macro = NOMES_REGIAO[k]
    t, l = reg_tx[k], reg_lt[k]
    taxa_alta, cresce = t['valor'] > TX_PI, tend(t) == 'crescente'
    let_alta, let_cresce = l['valor'] > LT_PI, tend(l) == 'crescente'
    fortes, medios = [], []
    if taxa_alta and cresce:
        fortes.append(f'taxa acima da média do estado e em alta ({dec(t["valor"])} contra {dec(TX_PI)} por 100 mil hab.; {ic(t)})')
    else:
        if taxa_alta:
            medios.append(f'taxa acima da média do estado ({dec(t["valor"])} contra {dec(TX_PI)} por 100 mil hab.)')
        if cresce:
            medios.append(f'taxa em alta ({ic(t)})')
    if let_alta and let_cresce:
        fortes.append(f'letalidade acima da média e em alta ({dec(l["valor"])}% contra {dec(LT_PI)}%)')
    elif let_alta:
        medios.append(f'letalidade hospitalar acima da média do estado ({dec(l["valor"])}% contra {dec(LT_PI)}%)')
    nivel = 'alta' if fortes else 'média' if medios else 'monitorar'

    acoes = []
    if taxa_alta or cresce:
        acoes.append({'acao': 'Fortalecer a fiscalização nas rodovias da região, que está entre as de maior taxa ou em alta.', 'eixo': 'fiscalização',
                      'origem': AUT_B + ': fortalecimento da fiscalização em rodovias das regiões com maiores taxas', 'tema': 'Regiões com maiores taxas',
                      'por_que': medios[0] if medios else fortes[0]})
        acoes.append({'acao': 'Revisar a infraestrutura viária dos pontos de maior risco da região (sinalização, acostamento, travessias urbanas).', 'eixo': 'engenharia',
                      'origem': AUT_B + ': revisão da infraestrutura viária nas áreas de maior risco; detalhamento é ' + PROP, 'tema': 'Regiões com maiores taxas',
                      'por_que': 'taxa de internação acima da média ou em alta'})
    acoes.append({**PLANOS['motociclistas']['acoes'][0], 'tema': PLANOS['motociclistas']['titulo'],
                  'por_que': 'motociclistas são o grupo com maior taxa de internação no estado (perfil estadual, não há dado por região)'})
    acoes.append({**PLANOS['motociclistas']['acoes'][2], 'tema': PLANOS['motociclistas']['titulo'],
                  'por_que': 'a UFPI recomenda descentralizar as políticas para municípios de pequeno e médio porte'})
    if let_alta or let_cresce:
        acoes.append({**PLANOS['atendimento_pre_hospitalar']['acoes'][0], 'tema': PLANOS['atendimento_pre_hospitalar']['titulo'],
                      'por_que': f'letalidade hospitalar de {dec(l["valor"])}% (estado {dec(LT_PI)}%)'})
        acoes.append({**PLANOS['atendimento_pre_hospitalar']['acoes'][1], 'tema': PLANOS['atendimento_pre_hospitalar']['titulo'],
                      'por_que': 'concentrar leitos de trauma e bases do SAMU onde morrem mais internados'})
    acoes.append({'acao': 'Acompanhar todo ano os óbitos (SIM) e as internações (SIH) por município de residência da região e cobrar dos hospitais o registro da causa externa nas internações.',
                  'eixo': 'dados e gestão', 'origem': PROP, 'tema': PLANOS['dados_monitoramento']['titulo'],
                  'por_que': 'nem todo hospital registra a causa externa, o que pode subestimar as internações da região'})

    metas = []
    if cresce:
        metas.append({'meta': 'Interromper a alta: tendência da taxa de internação estável ou decrescente (VPA de no máximo 0) na próxima série avaliada.', 'origem': PROP})
    if taxa_alta:
        metas.append({'meta': f'Aproximar a taxa de internação da média do estado ({dec(TX_PI)} por 100 mil hab.); hoje é {dec(t["valor"])}.', 'origem': PROP})
    if let_alta:
        metas.append({'meta': f'Letalidade hospitalar de no máximo {dec(LT_PI)}% (média do estado); hoje é {dec(l["valor"])}%.', 'origem': PROP})
    if not metas:
        metas.append({'meta': f'Manter a taxa abaixo da média do estado ({dec(TX_PI)} por 100 mil hab.) e a tendência {tend(t)}, com avaliação anual.', 'origem': PROP})
    metas.append({'meta': 'Longo prazo: reduzir pela metade as mortes e lesões graves no trânsito até 2030.', 'origem': META_ONU})

    vm = VM['por_macrorregiao'][macro]
    tm = TX['por_macrorregiao'][macro]
    regioes[k] = {
        'nome': nome, 'tipo': 'região de saúde', 'macrorregiao': NOMES_MACRO[macro],
        'fonte': FONTE_SIH,
        'prioridade': {'nivel': nivel, 'motivos': fortes + medios or ['taxa e letalidade abaixo da média do estado, sem tendência de alta']},
        'diagnostico': (f'{nome} (macrorregião {NOMES_MACRO[macro]}): taxa média de internação por acidentes de transporte de {dec(t["valor"])} por 100 mil hab. em 2010-2023, '
                        f'{ordr_tx.index(k) + 1}ª maior taxa entre as 12 regiões de saúde (estado: {dec(TX_PI)}); tendência {tend(t)} ({ic(t)}). '
                        f'Letalidade hospitalar de {dec(l["valor"])}% (estado: {dec(LT_PI)}%), tendência {tend(l)}. '
                        f'Na macrorregião {NOMES_MACRO[macro]}, a taxa é {dec(tm["valor"])} por 100 mil hab. (tendência {tend(tm)}) e o valor médio por internação é R$ {brl(vm["valor"])}.'),
        'numeros': {'taxa_internacao_100mil': t, 'letalidade_hospitalar_pct': l, 'media_estado_taxa': TX_PI, 'media_estado_letalidade': LT_PI,
                    'posicao_taxa': ordr_tx.index(k) + 1, 'posicao_crescimento': ordr_vpa.index(k) + 1, 'posicao_letalidade': ordr_lt.index(k) + 1,
                    'valor_medio_internacao_macrorregiao_reais': vm['valor']},
        'acoes': [curta(a) for a in acoes],
        'metas': metas,
        'indicadores': ['internações por 100 mil hab. (SIH/SUS)', 'VPA da taxa de internação', 'letalidade hospitalar', 'internações de motociclistas'],
        'quem_envolver': ['SESAPI e coordenação da região de saúde', 'SAMU', 'hospitais de referência em trauma', 'DETRAN-PI', 'PRF', 'prefeituras da região'],
    }

# ---------------------------------------------------------------- nível de atenção (cores do mapa): óbitos (SIM) e internações (SIH), todas as vias
# Dados de data/saude_municipios.json (scripts/importar_saude_vias.py), por município de RESIDÊNCIA, e rodovias de data/vias_pi.json.
SAUDE = json.load(open(os.path.join(ROOT, 'data', 'saude_municipios.json'), encoding='utf-8'))
VIAS_D = json.load(open(os.path.join(ROOT, 'data', 'vias_pi.json'), encoding='utf-8'))
ANOS_S = SAUDE['anos']
PER_S = janela(ANOS_S)
FONTE_SAUDE = f'SIM e SIH/SUS (TABNET/DATASUS), por município de residência, acidentes de transporte terrestre (CID-10 V01-V89), {PER_S}; população: IBGE, Censo 2022'
MIN_OBITOS, MIN_INTERNACOES = 10, 30   # casos nos 5 anos para um município ser vermelho ou laranja por esse critério
NIVEL_PRIORIDADE = {'vermelho': 'alta', 'laranja': 'média', 'amarelo': 'monitorar'}
ROTULO_COR = {'vermelho': 'vermelho (atenção máxima)', 'laranja': 'laranja (atenção alta)', 'amarelo': 'amarelo (abaixo da média do estado)'}

REGIAO_POR_NOME = {chave(nome): k for k, (nome, _) in NOMES_REGIAO.items()}
por_codigo = {m['codigo'][:6]: m for m in MALHA_D['municipios']}
mun_saude = {}
for cod, m in SAUDE['municipios'].items():
    nome_reg = m['regiao_de_saude'].split(' ', 1)[1]   # "22007 Tabuleiros do Alto Parnaíba"
    mun_saude[por_codigo[cod]['nome']] = {'codigo': por_codigo[cod]['codigo'], 'regiao': REGIAO_POR_NOME[chave(nome_reg)],
                                          'o': m['obitos'], 'i': m['internacoes'], 'pop': m['populacao_2022']}
POP_PI = sum(m['pop'] for m in mun_saude.values())


def taxa(casos, pop):
    return casos / len(ANOS_S) / pop * 1e5


TXO_PI = taxa(sum(m['o'] for m in mun_saude.values()), POP_PI)
TXI_PI = taxa(sum(m['i'] for m in mun_saude.values()), POP_PI)


def nivel_atencao(o, i, pop, com_minimo):
    """vermelho: taxa de óbitos >= 1,2x a do estado, ou >= 1,1x com internações >= 1,2x; laranja: óbitos acima da média ou
    internações >= 1,2x; amarelo: o resto. Em municípios, cada critério exige o mínimo de casos (poucos casos dão taxas instáveis)."""
    ro, ri = taxa(o, pop) / TXO_PI, taxa(i, pop) / TXI_PI
    ok_o = o >= MIN_OBITOS or not com_minimo
    ok_i = i >= MIN_INTERNACOES or not com_minimo
    txt_o = f'taxa de óbitos de {dec(taxa(o, pop))} por 100 mil hab. por ano, {dec(ro, 2)} vezes a do estado ({dec(TXO_PI)})'
    txt_i = f'taxa de internações de {dec(taxa(i, pop))} por 100 mil hab. por ano, {dec(ri, 2)} vezes a do estado ({dec(TXI_PI)})'
    if ok_o and ro >= 1.2:
        return 'vermelho', [txt_o] + ([txt_i] if ok_i and ri >= 1.2 else [])
    if ok_o and ok_i and ro >= 1.1 and ri >= 1.2:
        return 'vermelho', [txt_o, txt_i]
    if (ok_o and ro > 1) or (ok_i and ri >= 1.2):
        return 'laranja', [x for x, c in ((txt_o, ok_o and ro > 1), (txt_i, ok_i and ri >= 1.2)) if c]
    return 'amarelo', ['taxas de óbitos e de internações abaixo das referências do estado' if (ok_o or ok_i) else
                       f'poucos casos para classificar ({o} óbitos e {i} internações em {PER_S})']


def dentro(lon, lat, aneis):
    """Ponto no polígono (regra par-ímpar sobre todos os anéis, que inclui buracos)."""
    dentro_ = False
    for a in aneis:
        n = len(a) // 2
        j = n - 1
        for k in range(n):
            xi, yi, xj, yj = a[2 * k], a[2 * k + 1], a[2 * j], a[2 * j + 1]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                dentro_ = not dentro_
            j = k
    return dentro_


# rodovias que passam por cada município (vértices do traçado dentro do polígono)
caixas = []
for m in MALHA_D['municipios']:
    xs = [v for a in m['aneis'] for v in a[0::2]]
    ys = [v for a in m['aneis'] for v in a[1::2]]
    caixas.append((min(xs), max(xs), min(ys), max(ys), m))
vias_mun = collections.defaultdict(set)
for ref_, r in VIAS_D['rodovias'].items():
    for linha in r['linhas']:
        c = linha['c']
        for k in range(0, len(c), 2):
            lon, lat = c[k], c[k + 1]
            for x0, x1, y0, y1, m in caixas:
                if x0 <= lon <= x1 and y0 <= lat <= y1 and dentro(lon, lat, m['aneis']):
                    vias_mun[m['nome']].update(ref_.split('/'))
                    break


def ordem_via(r):
    return (r[:2] != 'BR', int(r[3:]) if r[3:].isdigit() else 0)


def vias_de(nomes):
    todas = sorted(set().union(*(vias_mun.get(n, set()) for n in nomes)), key=ordem_via)
    return [r for r in todas if r.startswith('BR')], [r for r in todas if r.startswith('PI')]


PACOTE = {
    'gestao_velocidade': {
        'titulo': 'Gestão de velocidade',
        'acoes': ['Reduzir e fiscalizar os limites nas vias urbanas: 50 km/h nas vias arteriais e 30 km/h nas vias locais e perto de escolas, unidades de saúde e comércio.',
                  'Nas travessias urbanas das rodovias, baixar a velocidade com sinalização, redutores e controle de acessos, em acordo com DNIT e PRF (BRs) ou DER-PI (rodovias estaduais).'],
        'quem': ['prefeitura e órgão municipal de trânsito (STRANS, em Teresina)', 'DETRAN-PI onde o trânsito não é municipalizado', 'DNIT e PRF', 'DER-PI'],
        'observacao': ('Pelo Código de Trânsito (art. 61), sem sinalização o limite é 60 km/h em via arterial e 30 km/h em via local; 50 km/h na arterial depende de '
                       'regulamentação e placas do órgão responsável pela via.'),
    },
    'infraestrutura': {
        'titulo': 'Infraestrutura viária',
        'acoes': ['Redesenhar ruas com calçadas mais largas, contínuas e acessíveis.',
                  'Converter faixas de rolamento em espaço para pedestres e ciclistas (calçada ampliada, ciclofaixa) onde o volume de veículos permitir.',
                  'Implantar faixas de pedestres elevadas perto de escolas, unidades de saúde e comércio, com iluminação nas travessias.'],
        'quem': ['prefeitura (obras e trânsito)', 'DER-PI e DNIT nas travessias urbanas das rodovias'],
    },
    'fiscalizacao_eletronica': {
        'titulo': 'Fiscalização eletrônica',
        'acoes': ['Instalar radares fixos e lombadas eletrônicas nos trechos e acessos urbanos com mais óbitos.',
                  'Usar câmeras e operações com radar móvel para coibir excesso de velocidade, avanço de sinal e outras infrações.',
                  'Divulgar os locais fiscalizados e os resultados (velocidade média e sinistros antes e depois).'],
        'quem': ['órgão municipal de trânsito (STRANS, em Teresina)', 'DETRAN-PI', 'PRF e DNIT nas BRs', 'DER-PI nas rodovias estaduais'],
    },
    'educacao': {
        'titulo': 'Educação e conscientização',
        'acoes': ['Campanhas integradas de promoção da saúde com SAMU, DETRAN-PI e o órgão municipal de trânsito (STRANS, em Teresina), sobre velocidade, capacete, álcool e travessia de pedestres.',
                  'Ações em escolas, autoescolas e com motociclistas profissionais (mototaxistas e entregadores).',
                  'Reforçar a comunicação nos dias e períodos com mais sinistros (fins de semana, feriados e festas).'],
        'quem': ['SAMU', 'DETRAN-PI', 'STRANS (Teresina) e órgãos municipais de trânsito', 'SESAPI e secretarias municipais de saúde e educação'],
    },
}
ORIGEM_PACOTE = 'diretriz do projeto Infotrânsito (medidas de segurança viária urbana); proposta técnica, os dados não medem a eficácia'


def resumo_local(k):
    """Óbitos na via pública x no hospital na região (SIM, local de ocorrência)."""
    loc = next((v for n, v in SAUDE['obitos_por_local_de_ocorrencia'].items() if REGIAO_POR_NOME.get(chave(n.split(' ', 1)[1])) == k), None)
    if not loc or not loc.get('Total'):
        return None
    return {'pct_via_publica': round(pct(loc.get('Via pública', 0), loc['Total']), 1), 'pct_hospital': round(pct(loc.get('Hospital', 0), loc['Total']), 1)}


at_mun = {}
for nome, m in sorted(mun_saude.items()):
    cor, motivos = nivel_atencao(m['o'], m['i'], m['pop'], True)
    federais, estaduais = vias_de([nome])
    at_mun[nome] = {'codigo': m['codigo'], 'regiao': NOMES_REGIAO[m['regiao']][0], 'nivel': cor, 'obitos': m['o'], 'internacoes': m['i'], 'populacao': m['pop'],
                    'taxa_obitos': round(taxa(m['o'], m['pop']), 1), 'taxa_internacoes': round(taxa(m['i'], m['pop']), 1),
                    'mortos_prf': s_mun[nome]['m'] if nome in s_mun else 0, 'rodovias_federais': federais, 'rodovias_estaduais': estaduais}
    if cor != 'amarelo':
        at_mun[nome]['motivos'] = motivos

at_reg = {}
for k, (nome, macro) in NOMES_REGIAO.items():
    membros = [n for n, m in mun_saude.items() if m['regiao'] == k]
    o, i, pop = (sum(mun_saude[n][c] for n in membros) for c in ('o', 'i', 'pop'))
    cor, motivos = nivel_atencao(o, i, pop, False)
    vermelhos = sorted((n for n in membros if at_mun[n]['nivel'] == 'vermelho'), key=lambda n: (-at_mun[n]['obitos'], n))
    foco = vermelhos or sorted(membros, key=lambda n: (-at_mun[n]['obitos'], n))[:3]
    federais, estaduais = vias_de(foco)
    loc = resumo_local(k)
    at_reg[k] = {'nome': nome, 'nivel': cor, 'motivos': motivos, 'obitos': o, 'internacoes': i, 'populacao': pop,
                 'taxa_obitos': round(taxa(o, pop), 1), 'taxa_internacoes': round(taxa(i, pop), 1),
                 'razao_obitos': round(taxa(o, pop) / TXO_PI, 2), 'razao_internacoes': round(taxa(i, pop) / TXI_PI, 2),
                 'municipios': len(membros), 'municipios_vermelhos': vermelhos,
                 'municipios_com_mais_obitos': sorted(membros, key=lambda n: (-at_mun[n]['obitos'], n))[:5],
                 'rodovias_federais_nos_focos': federais, 'rodovias_estaduais_nos_focos': estaduais, **(loc or {})}


def onde_agir(focos, federais, estaduais, loc=None):
    partes = []
    um = len(focos) == 1
    if focos:
        partes.append(('município ' if um else 'municípios ') + lista(focos[:6]) + (f' e mais {len(focos) - 6}' if len(focos) > 6 else ''))
    if federais or estaduais:
        partes.append(f'rodovias que cortam {"o município" if um else "esses municípios"}: ' + lista(federais + estaduais[:8]) + (' e outras' if len(estaduais) > 8 else ''))
    txt = '; '.join(partes)
    if loc and loc.get('pct_via_publica') is not None:
        txt += f'. {pc(loc["pct_via_publica"])} das mortes ocorrem na via pública e {pc(loc["pct_hospital"])} no hospital, o que pesa a favor do socorro rápido (SAMU)'
    return txt + '.'


def bloco_atencao(a, foco, federais, estaduais, loc=None):
    return {'nivel': a['nivel'], 'rotulo': ROTULO_COR[a['nivel']], 'motivos': a.get('motivos', []), 'fonte': FONTE_SAUDE,
            'obitos': a['obitos'], 'internacoes': a['internacoes'], 'taxa_obitos': a['taxa_obitos'], 'taxa_internacoes': a['taxa_internacoes'],
            'onde_agir': onde_agir(foco, federais, estaduais, loc),
            'pacote': list(PACOTE) if a['nivel'] != 'amarelo' else []}


def combinar(plano, at):
    """Prioridade final = a maior entre a regra própria do plano e a cor do mapa."""
    ordem = ['monitorar', 'média', 'alta']
    p = plano['prioridade']
    via_cor = NIVEL_PRIORIDADE[at['nivel']]
    if at['nivel'] != 'amarelo':
        p['motivos'] = p['motivos'] + [f'mapa {at["rotulo"]}: ' + '; '.join(at['motivos'])]
        if p['motivos'][0].startswith('nenhum critério') or p['motivos'][0].startswith('taxa e letalidade abaixo'):
            p['motivos'] = p['motivos'][1:]
    if ordem.index(via_cor) > ordem.index(p['nivel']):
        p['nivel'] = via_cor
    plano['atencao'] = at


for k, plano in regioes.items():
    a = at_reg[k]
    combinar(plano, bloco_atencao(a, a['municipios_vermelhos'] or a['municipios_com_mais_obitos'][:3],
                                  a['rodovias_federais_nos_focos'], a['rodovias_estaduais_nos_focos'], a))
    plano['fonte'] += '; ' + FONTE_SAUDE
    plano['diagnostico'] += (f' Em {PER_S} (SIM e SIH, todas as vias): {num(a["obitos"])} óbitos e {num(a["internacoes"])} internações de residentes, '
                             f'taxas de {dec(a["taxa_obitos"])} óbitos e {dec(a["taxa_internacoes"])} internações por 100 mil hab. por ano '
                             f'(estado: {dec(TXO_PI)} e {dec(TXI_PI)}).')

for nome, plano in municipios.items():
    a = at_mun[nome]
    combinar(plano, bloco_atencao(a, [nome], a['rodovias_federais'], a['rodovias_estaduais']))
    plano['fonte'] += '; ' + FONTE_SAUDE
    plano['diagnostico'] += (f' Em {PER_S}, todas as vias (SIM e SIH, residentes): {num(a["obitos"])} óbitos ({dec(a["taxa_obitos"])} por 100 mil hab. por ano; '
                             f'estado {dec(TXO_PI)}) e {num(a["internacoes"])} internações.')

# municípios em vermelho que não têm plano pela PRF: plano a partir de óbitos e internações (todas as vias)
for nome, a in at_mun.items():
    if a['nivel'] != 'vermelho' or nome in municipios:
        continue
    base = a['obitos'] / len(ANOS_S)
    anos_meta = 2030 - ANOS_S[-1]
    federais, estaduais = a['rodovias_federais'], a['rodovias_estaduais']
    municipios[nome] = {
        'nome': nome, 'tipo': 'município (todas as vias: SIM e SIH)', 'fonte': FONTE_SAUDE + ('; ' + FONTE_PRF if a['mortos_prf'] else ''),
        'prioridade': {'nivel': 'alta', 'motivos': [f'mapa {ROTULO_COR["vermelho"]}: ' + '; '.join(a['motivos'])]},
        'diagnostico': (f'{nome} (região de saúde {a["regiao"]}): {num(a["obitos"])} óbitos e {num(a["internacoes"])} internações de residentes por acidentes de '
                        f'transporte terrestre em {PER_S}, taxas de {dec(a["taxa_obitos"])} óbitos e {dec(a["taxa_internacoes"])} internações por 100 mil hab. por ano '
                        f'(estado: {dec(TXO_PI)} e {dec(TXI_PI)}). População de {num(a["populacao"])} hab. (Censo 2022). '
                        + (f'Rodovias no município: {lista(federais + estaduais)}. ' if federais or estaduais else '')
                        + (f'A PRF registrou {pl(a["mortos_prf"], "morto", "mortos")} nas BRs do município ({PERIODO}).' if a['mortos_prf'] else
                           'A PRF não registrou mortos em BRs no município; os óbitos vêm de vias estaduais, municipais ou de sinistros fora do município.')),
        'numeros': {'obitos': a['obitos'], 'internacoes': a['internacoes'], 'populacao_2022': a['populacao'], 'taxa_obitos_100mil_ano': a['taxa_obitos'],
                    'taxa_internacoes_100mil_ano': a['taxa_internacoes'], 'mortos_prf': a['mortos_prf']},
        'locais_prioritarios': [f'{r} (trecho dentro de {nome})' for r in federais + estaduais][:6],
        'acoes': [],
        'metas': [{'meta': f'Reduzir pela metade os óbitos por ano até 2030: de {dec(base)} (média de {PER_S}) para no máximo {dec(base / 2)}, '
                           f'queda de cerca de {pc(100 * (1 - 0.5 ** (1 / anos_meta)), 0)} ao ano.', 'origem': META_ONU},
                  {'meta': f'Trazer a taxa de óbitos para no máximo a do estado ({dec(TXO_PI)} por 100 mil hab. por ano).', 'origem': PROP}],
        'indicadores': ['óbitos por acidentes de transporte de residentes (SIM)', 'internações (SIH)', 'velocidade média nos pontos fiscalizados',
                        'travessias elevadas e km de calçada implantados'],
        'quem_envolver': [f'prefeitura de {nome} e órgão municipal de trânsito', 'DETRAN-PI', 'SAMU', 'secretaria municipal de saúde e SESAPI']
                         + (['DNIT e PRF'] if federais else []) + (['DER-PI'] if estaduais else []),
    }
    municipios[nome]['atencao'] = bloco_atencao(a, [nome], federais, estaduais)

for k, plano in rodovias.items():   # BRs: municípios em vermelho no trajeto
    no_trajeto = sorted((n for n, a in at_mun.items() if k in a['rodovias_federais'] and a['nivel'] == 'vermelho'), key=lambda n: (-at_mun[n]['obitos'], n))
    if no_trajeto:
        plano['municipios_em_vermelho_no_trajeto'] = no_trajeto
        plano['pacote'] = ['gestao_velocidade', 'fiscalizacao_eletronica']
        plano['diagnostico'] += f' Municípios em vermelho no mapa (SIM e SIH {PER_S}) cortados pela rodovia: {lista(no_trajeto[:8])}' + (' e outros.' if len(no_trajeto) > 8 else '.')

ordem_reg = sorted(at_reg, key=lambda k: (['vermelho', 'laranja', 'amarelo'].index(at_reg[k]['nivel']), -at_reg[k]['razao_obitos']))
verm_mun = sorted((n for n, a in at_mun.items() if a['nivel'] == 'vermelho'), key=lambda n: (-at_mun[n]['obitos'], n))
fed_v, est_v = vias_de(verm_mun)
atencao = {
    'como_usar': ('Cores do mapa e nível de atenção por região de saúde e município, calculados de óbitos (SIM) e internações (SIH/SUS) por município de residência, '
                  'em todas as vias (federais, estaduais e urbanas). Para regiões ou municípios em vermelho ou laranja, proponha as medidas de "pacote_de_medidas" '
                  'adaptadas ao local ("onde_agir": municípios e rodovias), citando quem executa, e diga que são propostas.'),
    'fonte': FONTE_SAUDE, 'periodo': PER_S,
    'metodo': (f'Taxas por 100 mil hab. por ano ({PER_S}, população do Censo 2022), comparadas com as do estado: óbitos {dec(TXO_PI)} e internações {dec(TXI_PI)}. '
               'Vermelho: taxa de óbitos de pelo menos 1,2 vez a do estado, ou 1,1 vez com internações de pelo menos 1,2 vez. Laranja: óbitos acima da média '
               'do estado ou internações de pelo menos 1,2 vez. Amarelo: o resto. Em municípios, o critério de óbitos exige '
               f'{MIN_OBITOS} ou mais óbitos e o de internações {MIN_INTERNACOES} ou mais internações em {PER_S}.'),
    'estado': {'obitos': sum(m['o'] for m in mun_saude.values()), 'internacoes': sum(m['i'] for m in mun_saude.values()), 'populacao': POP_PI,
               'taxa_obitos': round(TXO_PI, 1), 'taxa_internacoes': round(TXI_PI, 1),
               'obitos_municipio_ignorado': SAUDE['totais_tabnet']['obitos_municipio_ignorado']},
    'prioritarios': {
        'regioes_vermelhas': [at_reg[k]['nome'] for k in ordem_reg if at_reg[k]['nivel'] == 'vermelho'],
        'regioes_laranjas': [at_reg[k]['nome'] for k in ordem_reg if at_reg[k]['nivel'] == 'laranja'],
        'municipios_vermelhos_com_mais_obitos': [{'municipio': n, 'regiao': at_mun[n]['regiao'], 'obitos': at_mun[n]['obitos'], 'taxa_obitos': at_mun[n]['taxa_obitos']}
                                                 for n in verm_mun[:15]],
        'total_municipios_vermelhos': len(verm_mun),
        'rodovias_nos_municipios_vermelhos': {'federais': fed_v, 'estaduais': est_v},
    },
    'pacote_de_medidas': {**PACOTE, 'origem': ORIGEM_PACOTE},
    'regioes': {k: at_reg[k] for k in ordem_reg},
    'municipios': at_mun,
    'limites': ('Óbitos e internações são contados no município de RESIDÊNCIA da vítima, não no local do sinistro. Nem todo hospital registra a causa externa da '
                'internação, então algumas regiões podem ter internações subestimadas (ex.: taxas muito baixas no Vale do Rio Guaribas). Rodovias estaduais vêm do '
                'OpenStreetMap só como traçado: a base não tem sinistros georreferenciados nelas. Taxas de municípios pequenos variam muito de um ano para outro.'),
}

# ---------------------------------------------------------------- rankings de priorização
def item_mun(i, k):
    s = s_mun[k]
    return {'posicao': i, 'municipio': k, 'mortos': s['m'], 'acidentes': s['n'], 'mortos_por_100_acidentes': round(s['l'], 1),
            'variacao_acidentes_pct': None if s['var'] is None else round(s['var'], 1),
            'prioridade': municipios[k]['prioridade']['nivel'] if k in municipios else None}


def item_trecho(i, t):
    return {'posicao': i, 'trecho': t['trecho'], 'municipio': t['municipio'], 'mortos': t['m'], 'acidentes': t['n'],
            'mortos_por_100_acidentes': round(t['l'], 1)}


def item_reg(i, k):
    return {'posicao': i, 'regiao': NOMES_REGIAO[k][0], 'taxa_100mil': reg_tx[k]['valor'], 'vpa_pct': reg_tx[k]['vpa_pct'],
            'tendencia': tend(reg_tx[k]), 'letalidade_pct': reg_lt[k]['valor'], 'prioridade': regioes[k]['prioridade']['nivel']}


cresc = sorted((k for k in elegiveis if s_mun[k]['var'] is not None), key=lambda k: (-s_mun[k]['var'], -s_mun[k]['m'], k))
TR = trechos(ROWS)
tr_grav = sorted((t for t in TR if t['n'] >= MIN_TRECHO), key=lambda t: (-t['l'], -t['m'], t['k']))
NIVEIS = ('alta', 'média', 'monitorar')
priorizacao = {
    'municipios_prf': {
        'por_mortos': [item_mun(i, k) for i, k in enumerate(ord_m[:TOP], 1)],
        'por_gravidade': [item_mun(i, k) for i, k in enumerate(grav[:TOP], 1)],
        'por_crescimento': [item_mun(i, k) for i, k in enumerate(cresc[:TOP], 1)],
    },
    'rodovias_prf': [{'posicao': i, 'rodovia': 'BR-' + k, 'mortos': s_br[k]['m'], 'acidentes': s_br[k]['n'], 'mortos_por_100_acidentes': round(s_br[k]['l'], 1),
                      'prioridade': rodovias['BR-' + k]['prioridade']['nivel']} for i, k in enumerate(ordb_m, 1)],
    'trechos_prf': {
        'por_mortos': [item_trecho(i, t) for i, t in enumerate(por_mortos(TR)[:TOP], 1)],
        'por_gravidade': [item_trecho(i, t) for i, t in enumerate(tr_grav[:TOP], 1)],
    },
    'regioes_de_saude': {
        'por_taxa': [item_reg(i, k) for i, k in enumerate(ordr_tx, 1)],
        'por_crescimento': [item_reg(i, k) for i, k in enumerate(ordr_vpa, 1)],
        'por_letalidade': [item_reg(i, k) for i, k in enumerate(ordr_lt, 1)],
    },
    'lista_recomendada': {
        'municipios_prioridade_alta': [k for k in ord_m if k in municipios and municipios[k]['prioridade']['nivel'] == 'alta'],
        'rodovias_prioridade_alta': [k for k, p in rodovias.items() if p['prioridade']['nivel'] == 'alta'],
        'regioes_por_nivel': {n: [regioes[k]['nome'] for k in ordr_tx if regioes[k]['prioridade']['nivel'] == n] for n in NIVEIS},
    },
}

criterios = {
    'resumo': ('Os rankings ordenam os territórios por impacto (mortos ou taxa), gravidade (mortos por 100 acidentes ou letalidade hospitalar) e crescimento. '
               'O nível de prioridade combina esses critérios com regras fixas, descritas abaixo. É uma proposta de critério, não uma conclusão dos dados.'),
    'municipios_e_rodovias_prf': (f'Fonte: {FONTE_PRF}. Gravidade = mortos por 100 acidentes (média do estado: {dec(LET)}). Prioridade alta: estar entre os '
                                  f'{REGRA_MUN[0]} municípios (ou as {REGRA_BR[0]} BRs) com mais mortos, ou entre os {REGRA_MUN[1]} municípios (as {REGRA_BR[1]} BRs) '
                                  'de maior gravidade tendo mortos na mediana ou acima. Média: mortos acima da mediana, gravidade acima da média ou acidentes '
                                  f'crescendo 20% ou mais de {janela(ANTES)} para {janela(DEPOIS)}. Monitorar: nenhum desses. Planos, gravidade e crescimento só '
                                  f'para municípios com {MIN_MUNICIPIO} ou mais acidentes e BRs com {MIN_BR} ou mais; trechos de 5 km só entram no ranking de '
                                  f'gravidade com {MIN_TRECHO} ou mais acidentes.'),
    'alta_municipios_resumo': (f'prioridade alta = entre os {REGRA_MUN[0]} municípios com mais mortos ou entre os {REGRA_MUN[1]} de maior gravidade '
                               f'com mortos na mediana ou acima (municípios com {MIN_MUNICIPIO} ou mais acidentes)'),
    'regioes_de_saude': (f'Fonte: {FONTE_SIH}. Prioridade alta: taxa de internação acima da média do estado ({dec(TX_PI)} por 100 mil hab.) e tendência crescente, '
                         f'ou letalidade hospitalar acima da média ({dec(LT_PI)}%) e crescente. Média: só um desses sinais. Monitorar: nenhum. '
                         'Crescimento = VPA da taxa de internação (variação percentual anual).'),
    'cor_do_mapa': ('O nível final de cada região de saúde e município é o maior entre a regra própria (PRF ou estudo SIH 2010-2023) e a cor do mapa '
                    f'(SIM e SIH {PER_S}): vermelho = alta, laranja = média, amarelo = monitorar. Regra das cores em atencao_territorial.metodo.'),
    'limites': ('Rankings de municípios, trechos e BRs da PRF cobrem só rodovias federais. Óbitos e internações por município (todas as vias, por residência) '
                'estão em atencao_territorial. PRF, SIM e SIH são fontes diferentes e não devem ser somadas.'),
}

planos_territorio = {
    'como_usar': ('Planos de ação JÁ MONTADOS por território: regiões de saúde (SIH/SUS), rodovias federais e municípios (PRF, só rodovias federais). '
                  'Cada plano traz prioridade (com os motivos), diagnóstico calculado, fatores comparados com a média do estado, locais prioritários, ações '
                  '(com eixo, origem e por que foram escolhidas), metas, indicadores e quem envolver. Cite a fonte e o período de cada plano. '
                  "Para perguntas de priorização, use 'priorizacao' e 'criterios_de_prioridade'."),
    'origens': {
        'proposta técnica': 'inferência a partir do diagnóstico e de práticas usuais de segurança viária; os dados não medem a eficácia, o custo nem a viabilidade da medida',
        'recomendação dos autores': 'vem dos estudos: Bastos et al., Rev Bras Epidemiol 2026 (SIH/SUS Piauí) ou apresentação da UFPI (Amorim, Alves, Mascarenhas)',
        'referência: meta da ONU para 2030': ('Segunda Década de Ação pela Segurança no Trânsito (ONU, resolução A/RES/74/299, 2021-2030), que pede reduzir em pelo menos '
                                              f'50% as mortes e lesões no trânsito até 2030; a queda anual necessária é calculada a partir da média de mortos de {janela(DEPOIS)}. '
                                              'É uma referência externa, não um dado da base'),
    },
    'fatores_media_estado_pct': {nome: round(v, 1) for nome, v in REF.items()},
    'regra_dos_fatores': ('Fator "acima da média": ao menos 3 acidentes, participação 20% maior que a média do estado e 2 pontos percentuais ou mais de diferença. '
                          '"Abaixo da média": participação 20% ou mais menor. As ações do plano vêm dos temas dos fatores acima da média (até 3 temas).'),
    'limites': {
        'prf': ('Só rodovias federais: acidentes em vias estaduais e urbanas não entram. A PRF não informa tipo de veículo, volume de tráfego nem tempo de '
                'socorro; os fatores mostram associação, não causa. As ações são propostas e os dados não medem a eficácia delas.'),
        'regioes_de_saude': ('O estudo traz só médias e tendências da região, sem dados por município ou por rodovia; a ligação entre regiões de saúde e os '
                             'municípios da PRF não está na base. O perfil de vítimas (motociclistas, homens de 20 a 39 anos) é do estado, não da região.'),
    },
    'criterios_de_prioridade': criterios,
    'priorizacao': priorizacao,
    'regioes_de_saude': regioes,
    'rodovias': rodovias,
    'municipios': municipios,
}

# ---------------------------------------------------------------- JSON + índice
d = json.loads(open(JS, encoding='utf-8', newline='').read())
d.pop('planos_por_territorio', None)
d.pop('atencao_territorial', None)
novo = {}
for k, v in d.items():
    novo[k] = v
    if k == 'planos_de_acao':
        novo['planos_por_territorio'] = planos_territorio
        novo['atencao_territorial'] = atencao
d = novo

P = 'planos_por_territorio.'
A = 'atencao_territorial.'
ix = d['indice_busca']
for _k in list(ix):   # tira as entradas destas seções; palavras que só apontavam para elas saem do índice
    restantes = [p for p in ix[_k] if not p.startswith(P) and not p.startswith(A)]
    if ix[_k] and not restantes:
        del ix[_k]
    else:
        ix[_k] = restantes


def norm(s):
    return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()


def add(palavra, paths):
    cur = ix.setdefault(palavra, [])
    for p in paths:
        if p not in cur:
            cur.append(p)


add('regiao de saude', [P + 'priorizacao.regioes_de_saude.por_taxa'])
add('regioes de saude', [P + 'priorizacao.regioes_de_saude.por_taxa'])
for k, r in regioes.items():
    add(norm(r['nome']), [P + 'regioes_de_saude.' + k, A + 'regioes.' + k])
for k in rodovias:
    b = k[3:]
    for palavra in (f'br-{b}', f'br {b}', f'br{b}'):
        add(palavra, [P + 'rodovias.' + k])
for k in municipios:
    add(norm(k), [P + 'municipios.' + k])
for k, a in at_mun.items():
    if a['nivel'] != 'amarelo':
        add(norm(k), [A + 'municipios.' + k])
# cores do mapa, áreas que pedem mais atenção e o pacote de medidas urbanas
GERAL_A = [A + 'metodo', A + 'estado', A + 'prioritarios', A + 'pacote_de_medidas', A + 'limites']
for palavra in ('vermelh', 'laranja', 'atencao', 'mapa', 'mais obitos', 'maior numero de obitos', 'regioes criticas', 'areas criticas', 'municipios criticos'):
    add(palavra, GERAL_A)
for palavra in ('gestao de velocidade', 'limite de velocidade', 'km/h', 'radar', 'fiscalizacao eletronica', 'lombada', 'calcada', 'faixa elevada',
                'faixa de pedestre', 'ciclista', 'ciclofaixa', 'campanha', 'conscientiza', 'educacao', 'samu', 'detran', 'strans', 'infraestrutura'):
    add(palavra, [A + 'pacote_de_medidas'])
for palavra in ('estadua', 'rodovias estaduais', 'der-pi', 'pi-'):
    add(palavra, [A + 'prioritarios.rodovias_nos_municipios_vermelhos', A + 'limites'])
for palavra in ('internac', 'obito', 'morte', 'residencia'):
    add(palavra, [A + 'estado'])
d['indice_busca'] = ix
open(JS, 'w', encoding='utf-8', newline='').write(json.dumps(d, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------- dados do mapa
nomes_mapa = sorted({r['mun'] for r in ROWS})
idx = {k: i for i, k in enumerate(nomes_mapa)}
pontos = [[round(float(r['latitude']), 4), round(float(r['longitude']), 4), r['ano'], int(r['br']),
           None if r['km_f'] is None else int(r['km_f'] // 5) * 5, r['mortos'], r['feridos_graves'], idx[r['mun']]] for r in ROWS]
mapa = {
    'fonte': FONTE_PRF, 'periodo': PERIODO, 'ano_parcial': ANO_PARCIAL, 'anos': ANOS,
    'janelas': {'antes': ANTES, 'depois': DEPOIS}, 'media_mortos_por_100': round(LET, 1),
    'minimos': {'municipio': MIN_MUNICIPIO, 'trecho': MIN_TRECHO},
    'municipios': nomes_mapa,
    'colunas': ['lat', 'lon', 'ano', 'br', 'km_trecho', 'mortos', 'feridos_graves', 'municipio'],
    'pontos': pontos,
}
open(MAPA, 'w', encoding='utf-8', newline='').write(json.dumps(mapa, ensure_ascii=False, separators=(',', ':')))

print(len(regioes), 'regiões;', len(rodovias), 'rodovias;', len(municipios), 'municípios;',
      len(json.dumps(planos_territorio, ensure_ascii=False)), 'caracteres em planos_por_territorio')
print('mapa:', len(pontos), 'pontos;', os.path.getsize(MAPA), 'bytes; malha:', os.path.getsize(MALHA), 'bytes')
print('prioridade alta (municípios):', priorizacao['lista_recomendada']['municipios_prioridade_alta'])
print('prioridade alta (BRs):', priorizacao['lista_recomendada']['rodovias_prioridade_alta'])
print('regiões por nível:', priorizacao['lista_recomendada']['regioes_por_nivel'])
print('atenção (regiões):', {c: [at_reg[k]['nome'] for k in ordem_reg if at_reg[k]['nivel'] == c] for c in ('vermelho', 'laranja', 'amarelo')})
print('atenção (municípios):', collections.Counter(a['nivel'] for a in at_mun.values()), '| planos municipais:', len(municipios),
      '| tamanho atencao_territorial:', len(json.dumps(atencao, ensure_ascii=False)))
print('== Teresina'); print(municipios['Teresina']['diagnostico'])
print('== BR-316'); print(rodovias['BR-316']['diagnostico'])
print('== carnaubais'); print(regioes['carnaubais']['diagnostico'])
