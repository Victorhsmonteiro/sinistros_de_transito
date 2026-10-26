"""Baixa os dados de saúde do TABNET e o traçado das rodovias do Piauí:
- data/saude_municipios.json: óbitos (SIM) e internações (SIH/SUS) por acidentes de transporte terrestre (CID-10 V01-V89)
  por município de residência, com a região de saúde (CIR) de cada município; óbitos por local de ocorrência por região
  de saúde; população do Censo 2022 (IBGE).
- data/sinistros.json -> dados_tabnet_piaui_teresina: internações por local de internação (Piauí e hospitais de Teresina),
  por ano e categoria, sexo, idade, óbitos, letalidade, permanência e valor médio da AIH.
- data/vias_pi.json: rodovias federais (BR) e estaduais (PI) do OpenStreetMap, simplificadas para o mapa do painel.
Precisa de internet. Rode quando quiser atualizar esses dados; depois rode gerar_planos.py, gerar_territorios.py e gerar_perguntas.py.
Uso: python scripts/importar_saude_vias.py [--so-saude | --so-tabnet | --so-vias]"""
import datetime, gzip, html, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAUDE = os.path.join(ROOT, 'data', 'saude_municipios.json')
VIAS = os.path.join(ROOT, 'data', 'vias_pi.json')
ANOS = list(range(2020, 2025))   # anos completos e fechados no SIM e no SIH; mesmo início da série da PRF
GRUPOS_TERRESTRES = [str(i) for i in range(1, 10)]   # V01-V89 nos dois formulários (pedestre ... outros terrestres)
TABNET = 'http://tabnet.datasus.gov.br/cgi/'
UA = {'User-Agent': 'infotransito-ufpi/1.0 (projeto de pesquisa UFPI)'}


def baixar(url, dados=None, timeout=300):
    req = urllib.request.Request(url, data=dados, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        corpo = r.read()
    return gzip.decompress(corpo) if corpo[:2] == b'\x1f\x8b' else corpo


# ---------------------------------------------------------------- TABNET
def tabnet(defe, troca):
    """Envia o formulário do TABNET com os valores padrão, trocando os campos de 'troca'; devolve linhas do formato prn."""
    form = baixar(TABNET + 'deftohtm.exe?' + defe).decode('latin-1')
    pares = []
    for sel in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', form, re.S | re.I):
        nome = sel.group(1)
        ops = re.findall(r'<option([^>]*)value="([^"]*)"', sel.group(2), re.I)
        padrao = [v for a, v in ops if 'selected' in a.lower()] or ([ops[0][1]] if ops else [])
        pares += [(nome, v) for v in troca.get(nome, padrao)]
    pares += [('formato', 'prn'), ('mostre', 'Mostra')]
    corpo = urllib.parse.urlencode(pares, encoding='latin-1').encode('ascii')
    t = baixar(TABNET + 'tabcgi.exe?' + defe, corpo).decode('latin-1')
    pre = re.search(r'<PRE>(.*?)</PRE>', t, re.S | re.I)
    assert pre, 'TABNET não devolveu tabela para ' + defe
    linhas = [html.unescape(x).strip() for x in pre.group(1).strip().splitlines() if x.strip() and x.strip() != '&']
    return [[c.strip().strip('"') for c in x.split(';')] for x in linhas]


def numero(v):
    return 0 if v in ('-', '', '...') else int(v.replace('.', ''))


def por_municipio(tab):
    """Tabela Município x Região de saúde -> {código IBGE (6 díg.): (nome, região, total)}."""
    cab = tab[0]
    regioes = cab[1:-1]
    out = {}
    for lin in tab[1:]:
        m = re.match(r'^(\d{6}) (.+)$', lin[0])
        if not m:
            continue   # "MUNICIPIO IGNORADO" e "Total"
        vals = [numero(v) for v in lin[1:-1]]
        reg = next((regioes[i] for i, v in enumerate(vals) if v), None)
        out[m.group(1)] = (m.group(2), reg, numero(lin[-1]))
    total = numero(tab[-1][-1]) if tab[-1][0] == 'Total' else None
    ignorado = sum(numero(l[-1]) for l in tab[1:] if 'IGNORADO' in l[0].upper())
    return out, total, ignorado


def baixar_saude():
    print('TABNET: óbitos (SIM) por município de residência...')
    sim = tabnet('sim/cnv/ext10pi.def', {
        'Linha': ['Município'], 'Coluna': ['Região_de_Saúde_(CIR)'], 'Incremento': ['Óbitos_p/Residênc'],
        'Arquivos': [f'extpi{str(a)[2:]}.dbf' for a in ANOS], 'SGrupo_CID10': GRUPOS_TERRESTRES})
    print('TABNET: internações (SIH/SUS) por município de residência...')
    # frpi = causas externas por local de RESIDÊNCIA (fipi seria por local de internação e concentraria tudo nos polos hospitalares)
    sih = tabnet('sih/cnv/frpi.def', {
        'Linha': ['Município'], 'Coluna': ['Região_de_Saúde_(CIR)'], 'Incremento': ['Internações'],
        'Arquivos': [f'frpi{str(a)[2:]}{m:02d}.dbf' for a in ANOS for m in range(1, 13)], 'SGrupo_de_Causas': GRUPOS_TERRESTRES})
    print('TABNET: óbitos por local de ocorrência e região de saúde...')
    local = tabnet('sim/cnv/ext10pi.def', {
        'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['Local_ocorrência'], 'Incremento': ['Óbitos_p/Residênc'],
        'Arquivos': [f'extpi{str(a)[2:]}.dbf' for a in ANOS], 'SGrupo_CID10': GRUPOS_TERRESTRES})
    print('IBGE: população do Censo 2022 por município...')
    pop_api = json.loads(baixar('https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[N3[22]]'))
    pop = {s['localidade']['id'][:6]: int(s['serie']['2022']) for s in pop_api[0]['resultados'][0]['series']}

    ob, ob_total, ob_ign = por_municipio(sim)
    it, it_total, it_ign = por_municipio(sih)
    municipios = {}
    for cod in sorted(set(pop) | set(ob) | set(it)):
        nome, reg = (ob.get(cod) or it.get(cod) or (None, None, 0))[:2]
        if reg is None:
            reg = (it.get(cod) or ob.get(cod) or (None, None))[1]
        municipios[cod] = {'nome_tabnet': nome, 'regiao_de_saude': reg, 'obitos': ob.get(cod, (0, 0, 0))[2],
                           'internacoes': it.get(cod, (0, 0, 0))[2], 'populacao_2022': pop.get(cod)}
    cab = local[0]
    local_por_regiao = {}
    for lin in local[1:]:
        if lin[0] == 'Total' or 'Ignorad' in lin[0]:
            continue
        local_por_regiao[lin[0]] = {cab[i]: numero(lin[i]) for i in range(1, len(cab))}
    hoje = datetime.date.today().isoformat()
    dados = {
        'fonte': {
            'obitos': f'SIM/DATASUS (TABNET), óbitos por residência, CID-10 V01-V89 (acidentes de transporte terrestre), Piauí, {ANOS[0]}-{ANOS[-1]}',
            'internacoes': f'SIH/SUS (TABNET), internações por residência, CID-10 V01-V89, Piauí, {ANOS[0]}-{ANOS[-1]}',
            'populacao': 'IBGE, Censo Demográfico 2022 (tabela 4714)',
            'consultado_em': hoje,
        },
        'anos': ANOS,
        'totais_tabnet': {'obitos': ob_total, 'obitos_municipio_ignorado': ob_ign, 'internacoes': it_total, 'internacoes_municipio_ignorado': it_ign},
        'municipios': municipios,
        'obitos_por_local_de_ocorrencia': local_por_regiao,
    }
    sem_regiao = [m for m in municipios.values() if not m['regiao_de_saude']]
    assert not sem_regiao, f'{len(sem_regiao)} municípios sem região de saúde'
    open(SAUDE, 'w', encoding='utf-8', newline='').write(json.dumps(dados, ensure_ascii=False, indent=1))
    print(f'{len(municipios)} municípios; óbitos {ob_total} (ignorado {ob_ign}); internações {it_total} (ignorado {it_ign})')


# ---------------------------------------------------------------- TABNET: seção dados_tabnet_piaui_teresina de sinistros.json
# Mesma consulta que gerou a seção original (DADOS.docx), conferida contra ela: SIH/SUS, causas externas por LOCAL DE
# INTERNAÇÃO (fipi), linha "ano de atendimento", grupos V01-V89. A original usava os arquivos de jan/2010 a jun/2026; aqui
# entram todos os arquivos disponíveis (de jan/2008 ao último mês), e o recorte de Teresina é o dos hospitais da capital.
JS = os.path.join(ROOT, 'data', 'sinistros.json')
FIPI = 'sih/cnv/fipi.def'


def valor(v):
    v = v.strip()
    if v in ('-', '', '...'):
        return 0
    return float(v.replace('.', '').replace(',', '.')) if ',' in v else int(v.replace('.', ''))


def opcoes_do_campo(form, campo):
    sel = next(m.group(2) for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', form, re.S | re.I) if m.group(1) == campo)
    return [(v, html.unescape(t).strip()) for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', sel, re.I)]


def chave_grupo(rotulo):
    m = re.match(r'^(V\d\d-V\d\d)', rotulo)
    return m.group(1) if m else ('TOTAL_GERAL' if rotulo == 'Total' else None)


def baixar_tabnet_internacoes():
    form = baixar(TABNET + 'deftohtm.exe?' + FIPI).decode('latin-1')
    arquivos = sorted(v for v, _ in opcoes_do_campo(form, 'Arquivos'))
    meses = {v: t for v, t in opcoes_do_campo(form, 'Arquivos')}
    teresina = next(v for v, t in opcoes_do_campo(form, 'SMunicípio') if 'TERESINA' in t.upper())
    ultimo = meses[arquivos[-1]]                       # ex.: "Ago/2026"
    ano_ini, ano_fim = int(meses[arquivos[0]][-4:]), int(ultimo[-4:])
    parcial = ano_fim if not ultimo.startswith('Dez') else None
    print(f'TABNET (SIH por local de internação): arquivos de {meses[arquivos[0]]} a {ultimo}')

    def consulta(linha, coluna, incremento, municipio=None):
        troca = {'Linha': [linha], 'Coluna': [coluna], 'Incremento': [incremento], 'Arquivos': arquivos, 'SGrupo_de_Causas': GRUPOS_TERRESTRES}
        if municipio:
            troca['SMunicípio'] = [municipio]
        return tabnet(FIPI, troca)

    def por_grupo(incremento, municipio):
        tab = consulta('Grupo_de_Causas', '--Não-Ativa--', incremento, municipio)
        return {chave_grupo(l[0]): valor(l[-1]) for l in tab[1:] if chave_grupo(l[0])}

    def cruzado(coluna, municipio, rotulos):
        tab = consulta('Grupo_de_Causas', coluna, 'Internações', municipio)
        cab = tab[0][1:]
        out = {}
        for l in tab[1:]:
            k = chave_grupo(l[0])
            if k:
                out[k] = {rotulos(c): valor(v) for c, v in zip(cab, l[1:])}
        return out

    def local(municipio):
        tab = consulta('Ano_atendimento', 'Grupo_de_Causas', 'Internações', municipio)
        cab = [chave_grupo(c) for c in tab[0][1:]]
        por_ano, por_cat = {}, {k: {} for k in cab if k and k != 'TOTAL_GERAL'}
        for l in tab[1:]:
            if not re.match(r'^\d{4}$', l[0]) or not ano_ini <= int(l[0]) <= ano_fim:
                continue   # anos antes do primeiro arquivo só têm internações atrasadas, e a linha "Total"
            for k, v in zip(cab, l[1:]):
                if k == 'TOTAL_GERAL':
                    por_ano[l[0]] = valor(v)
                elif k:
                    por_cat[k][l[0]] = valor(v)
        por_ano['total_periodo'] = sum(por_ano.values())
        for c in por_cat.values():
            c['total_periodo'] = sum(c.values())
        sexo = cruzado('Sexo', municipio, lambda c: {'Masc': 'masculino', 'Fem': 'feminino', 'Total': 'total'}.get(c, c.lower()))
        idade = cruzado('Faixa_Etária_1', municipio, lambda c: c)
        for k in idade:
            idade[k].pop('Total', None)
        obitos = por_grupo('Óbitos', municipio)
        internacoes = {k: v['total_periodo'] for k, v in por_cat.items()}
        internacoes['TOTAL_GERAL'] = por_ano['total_periodo']
        assert sum(v for k, v in internacoes.items() if k != 'TOTAL_GERAL') == internacoes['TOTAL_GERAL'], 'categorias não somam o total'
        return {
            'internacoes_por_ano': por_ano,
            'internacoes_por_categoria': internacoes,
            'internacoes_por_categoria_e_ano': por_cat,
            'internacoes_por_sexo_e_categoria': sexo,
            'internacoes_por_idade_e_categoria': idade,
            'taxa_mortalidade_pct_por_categoria': por_grupo('Taxa_mortalidade', municipio),
            'obitos_por_categoria': obitos,
            'permanencia_media_dias_por_categoria': por_grupo('Média_permanência', municipio),
            'valor_medio_aih_reais_por_categoria': por_grupo('Valor_médio_AIH', municipio),
        }

    print('  Piauí...')
    pi = local(None)
    print('  hospitais de Teresina...')
    te = local(teresina)
    rotulos = {chave_grupo(t): t.split(' ', 1)[1] for v, t in opcoes_do_campo(form, 'SGrupo_de_Causas') if v in GRUPOS_TERRESTRES}
    periodo = f'{ano_ini}-{ano_fim}' + (f' ({ano_fim} parcial: arquivos até {ultimo})' if parcial else '')
    secao = {
        'observacao': (f'Consulta do TABNET/DATASUS (SIH/SUS, Morbidade Hospitalar por Causas Externas) por LOCAL DE INTERNAÇÃO, linha "ano de '
                       f'atendimento", grupos CID-10 V01-V89 (acidentes de transporte terrestre), arquivos de {meses[arquivos[0]]} a {ultimo}. '
                       f'Série do Piauí {periodo}. "teresina" são as internações em HOSPITAIS DE TERESINA (pacientes de todo o estado), não os '
                       'moradores da capital; para residentes, use atencao_territorial (SIM e SIH por residência). Esta consulta não usa a metodologia '
                       'do artigo em estudo_morbidade_piaui_2010_2023 (SIH por residência, ano de processamento), então os totais não coincidem. '
                       'Sexo, idade, óbitos, letalidade, permanência e valor médio da AIH são acumulados do período. TOTAL_GERAL é a soma de V01-V89.'),
        'consulta': {'formulario': TABNET + 'deftohtm.exe?' + FIPI, 'recorte': 'local de internação', 'linha': 'ano de atendimento',
                     'grupos': 'V01-V89', 'arquivos': f'{meses[arquivos[0]]} a {ultimo}', 'consultado_em': datetime.date.today().isoformat(),
                     'gerado_por': 'scripts/importar_saude_vias.py'},
        'periodo': periodo, 'ano_parcial': parcial,
        'categorias_cid10': rotulos,
        'piaui': pi,
        'teresina': te,
    }
    d = json.loads(open(JS, encoding='utf-8', newline='').read())
    antiga = d.get('dados_tabnet_piaui_teresina', {})
    d['dados_tabnet_piaui_teresina'] = secao   # mesma posição no JSON (a chave já existe)
    d['metadata']['fontes_recomendadas'] = [
        f for f in d['metadata']['fontes_recomendadas'] if not f.startswith(('DADOS.docx', 'TABNET/DATASUS, SIH/SUS por local de internação'))
    ] + [f'TABNET/DATASUS, SIH/SUS por local de internação ({periodo}), consultado por scripts/importar_saude_vias.py - em dados_tabnet_piaui_teresina '
         '(substitui a consulta bruta de DADOS.docx, com a mesma metodologia)']
    open(JS, 'w', encoding='utf-8', newline='').write(json.dumps(d, ensure_ascii=False, indent=2))
    a_ant = antiga.get('piaui', {}).get('internacoes_por_ano', {})
    print('  ano: antes -> agora')
    for a in sorted(set(a_ant) | set(pi['internacoes_por_ano'])):
        if a_ant.get(a) != pi['internacoes_por_ano'].get(a):
            print(f'    {a}: {a_ant.get(a)} -> {pi["internacoes_por_ano"].get(a)}')
    print(f'  Teresina: {antiga.get("teresina", {}).get("internacoes_por_categoria", {}).get("TOTAL_GERAL")} -> {te["internacoes_por_categoria"]["TOTAL_GERAL"]}')


# ---------------------------------------------------------------- OpenStreetMap (Overpass)
def simplificar(pts, tol):
    """Douglas-Peucker sobre [(lon, lat), ...]."""
    if len(pts) < 3:
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
    return [p for p, k in zip(pts, manter) if k]


PAVIMENTADA = {'asphalt', 'paved', 'concrete', 'concrete:plates', 'paving_stones', 'sett', 'chipseal'}


def baixar_vias():
    print('OpenStreetMap: rodovias BR e PI no Piauí (pode levar alguns minutos)...')
    q = ('[out:json][timeout:600];area["ISO3166-2"="BR-PI"]["admin_level"="4"]->.a;'
         'way["highway"]["ref"~"(BR|PI)[- ]?[0-9]"](area.a);out tags geom;')
    bruto = json.loads(baixar('https://overpass-api.de/api/interpreter', urllib.parse.urlencode({'data': q}).encode(), timeout=900))
    rodovias = {}
    for w in bruto['elements']:
        t = w.get('tags', {})
        refs = sorted({re.sub(r'^(BR|PI)[- ]?0*', r'\1-', r.strip().upper()) for r in t.get('ref', '').split(';')
                       if re.match(r'^\s*(BR|PI)[- ]?\d', r.strip(), re.I)})
        if not refs or 'geometry' not in w:
            continue
        pts = simplificar([(g['lon'], g['lat']) for g in w['geometry']], 0.0012)
        coords = [v for lon, lat in pts for v in (round(lon, 3), round(lat, 3))]
        sup = t.get('surface', '')
        pav = 'p' if sup in PAVIMENTADA else 'n' if sup else ''
        chave = '/'.join(refs)
        r = rodovias.setdefault(chave, {'tipo': 'federal' if any(x.startswith('BR') for x in refs) else 'estadual', 'linhas': []})
        r['linhas'].append({'s': pav, 'c': coords})
    dados = {
        'fonte': 'OpenStreetMap (Overpass API), vias com ref BR-* ou PI-* dentro do Piauí, simplificadas para o painel',
        'licenca': 'Dados © colaboradores do OpenStreetMap, licença ODbL (openstreetmap.org/copyright)',
        'consultado_em': datetime.date.today().isoformat(),
        'superficie': {'p': 'pavimentada', 'n': 'não pavimentada (terra, cascalho etc.)', '': 'não informada'},
        'rodovias': dict(sorted(rodovias.items())),
    }
    open(VIAS, 'w', encoding='utf-8', newline='').write(json.dumps(dados, ensure_ascii=False, separators=(',', ':')))
    fed = sum(1 for r in rodovias.values() if r['tipo'] == 'federal')
    print(f'{len(rodovias)} rodovias ({fed} federais, {len(rodovias) - fed} estaduais); {os.path.getsize(VIAS)} bytes')


if __name__ == '__main__':
    so = next((a[5:] for a in sys.argv[1:] if a.startswith('--so-')), None)   # --so-saude, --so-tabnet ou --so-vias
    if so in (None, 'saude'):
        baixar_saude()
    if so in (None, 'tabnet'):
        baixar_tabnet_internacoes()
    if so in (None, 'vias'):
        baixar_vias()
