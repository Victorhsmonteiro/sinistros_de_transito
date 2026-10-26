"""Filtra os CSVs da PRF (datatran*.csv em DADOS SINISTROS/) para UF = PI, grava o CSV filtrado e
atualiza data/sinistros.json (dados_prf_piaui, apresentacao_ufpi_..., indice_busca).
Uso: python scripts/importar_prf.py && python scripts/interpretar_prf.py"""
import csv, collections, datetime, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'DADOS SINISTROS')
OUT_JSON = os.path.join(ROOT, 'data', 'sinistros.json')
OUT_CSV = os.path.join(ROOT, 'data', 'prf_acidentes_pi.csv')

# ---------------------------------------------------------------- PRF: filtro UF = PI
rows = []
header = None
ANOS = sorted(int(re.search(r'datatran(\d{4})\.csv$', f).group(1)) for f in glob.glob(os.path.join(SRC, 'datatran*.csv')))
for y in ANOS:
    with open(os.path.join(SRC, f'datatran{y}.csv'), encoding='cp1252', newline='') as fh:
        rd = csv.DictReader(fh, delimiter=';')
        header = rd.fieldnames
        for r in rd:
            if r['uf'] == 'PI':
                r['ano'] = y
                rows.append(r)
assert rows, 'nenhuma linha com UF = PI'

# A PRF mudou a classificação em 2021: os mesmos conceitos ganharam nomes novos. Unifica só o que é renomeação clara
# (o arquivo original em DADOS SINISTROS/ não é alterado). Causas genéricas de 2020 que foram divididas depois
# (ex.: "Desobediência às normas de trânsito pelo condutor", 242 acidentes só em 2020) não podem ser separadas.
CAUSAS_RENOMEADAS = {
    'Ingestão de Álcool': 'Ingestão de álcool pelo condutor',
    'Ingestão de Substâncias Psicoativas': 'Ingestão de substâncias psicoativas pelo condutor',
    'Mal Súbito': 'Mal súbito do condutor',
    'Não guardar distância de segurança': 'Condutor deixou de manter distância do veículo da frente',
    'Transitar no Acostamento': 'Transitar no acostamento',
    'Fenômenos da Natureza': 'Demais Fenômenos da natureza',
    'Ingestão de álcool e/ou substâncias psicoativas pelo pedestre': 'Ingestão de álcool ou substâncias psicoativas pelo pedestre',
    'Ingestão de álcool ou de substâncias psicoativas pelo pedestre': 'Ingestão de álcool ou substâncias psicoativas pelo pedestre',
    'Pedestre - Ingestão de álcool/ substâncias psicoativas': 'Ingestão de álcool ou substâncias psicoativas pelo pedestre',
}
TIPOS_UNIFICADOS = {
    'Colisão com objeto estático': 'Colisão com objeto',
    'Colisão com objeto em movimento': 'Colisão com objeto',
    'Colisão lateral mesmo sentido': 'Colisão lateral',
    'Colisão lateral sentido oposto': 'Colisão lateral',
}
for r in rows:
    r['causa_acidente'] = CAUSAS_RENOMEADAS.get(r['causa_acidente'], r['causa_acidente'])
    r['tipo_acidente'] = TIPOS_UNIFICADOS.get(r['tipo_acidente'], r['tipo_acidente'])

def num(s):
    return float(str(s).replace(',', '.'))

for r in rows:
    for c in ['pessoas', 'mortos', 'feridos_leves', 'feridos_graves', 'ilesos', 'ignorados', 'feridos', 'veiculos']:
        r[c] = int(r[c])
    r['km_f'] = num(r['km']) if r['km'] not in ('', 'NA') else None
    r['hora'] = int(r['horario'][:2])

# CSV filtrado (UTF-8, vírgula, ponto decimal)
cols = ['id', 'data_inversa', 'dia_semana', 'horario', 'uf', 'br', 'km', 'municipio', 'causa_acidente', 'tipo_acidente',
        'classificacao_acidente', 'fase_dia', 'sentido_via', 'condicao_metereologica', 'tipo_pista', 'tracado_via',
        'uso_solo', 'pessoas', 'mortos', 'feridos_leves', 'feridos_graves', 'ilesos', 'ignorados', 'feridos',
        'veiculos', 'latitude', 'longitude', 'regional', 'delegacia', 'uop']
assert cols == header, header
with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for r in rows:
        out = []
        for c in cols:
            v = r[c]
            if c in ('km', 'latitude', 'longitude') and isinstance(v, str):
                v = v.replace(',', '.')
            out.append(v)
        w.writerow(out)

# ---------------------------------------------------------------- agregações
def agg(group_rows):
    n = len(group_rows)
    mortos = sum(r['mortos'] for r in group_rows)
    return {
        'ocorrencias': n,
        'mortos': mortos,
        'feridos_graves': sum(r['feridos_graves'] for r in group_rows),
        'feridos_leves': sum(r['feridos_leves'] for r in group_rows),
        'mortos_por_100_ocorrencias': round(100 * mortos / n, 1) if n else None,
    }

def group(key, rs=None):
    g = collections.defaultdict(list)
    for r in (rs if rs is not None else rows):
        g[key(r)].append(r)
    return g

def ranking(g, topn=None, by='ocorrencias'):
    items = [(k, agg(v)) for k, v in g.items()]
    items.sort(key=lambda kv: (-kv[1][by], -kv[1]['mortos'], str(kv[0])))
    return items[:topn] if topn else items

ACENTOS = {'SAO ': 'São ', 'PARNAIBA': 'Parnaíba', 'LOBAO': 'Lobão', 'PIAUI': 'Piauí', 'JOSE': 'José', 'JOAO': 'João',
           'GONCALO': 'Gonçalo', 'CONCEICAO': 'Conceição', 'LUIS': 'Luís', 'ESPERANTINA': 'Esperantina'}
SMALL = {'Do', 'Da', 'De', 'Dos', 'Das'}

def bonito(nome):
    s = nome
    for k, v in ACENTOS.items():
        s = s.replace(k, '\0' + v + '\0') if k.endswith(' ') else s.replace(k, '\0' + v + '\0')
    parts = []
    for chunk in s.split('\0'):
        if chunk in ACENTOS.values():
            parts.append(chunk)
        else:
            parts.append(chunk.title())
    out = ''.join(parts)
    return ' '.join(w.lower() if w in SMALL else w for w in out.split(' '))

def periodo(h):
    return ('madrugada (00h-05h59)' if h < 6 else 'manhã (06h-11h59)' if h < 12
            else 'tarde (12h-17h59)' if h < 18 else 'noite (18h-23h59)')

def tabela(key, topn=None, by='ocorrencias', rename=None):
    out = {}
    for k, a in ranking(group(key), topn, by):
        out[(rename or (lambda x: x))(k)] = a
    return out

DATAS = sorted(r['data_inversa'] for r in rows)
DMIN, DMAX = DATAS[0], DATAS[-1]
ANO_PARCIAL = int(DMAX[:4]) if DMAX[5:] < '12-31' else None
def br_data(s):
    return f'{s[8:10]}/{s[5:7]}/{s[:4]}'

por_ano = {}
for y in sorted({r['ano'] for r in rows}):
    rs = [r for r in rows if r['ano'] == y]
    a = agg(rs)
    a['pessoas_envolvidas'] = sum(r['pessoas'] for r in rs)
    a['ilesos'] = sum(r['ilesos'] for r in rs)
    a['veiculos_envolvidos'] = sum(r['veiculos'] for r in rs)
    cl = collections.Counter(r['classificacao_acidente'] for r in rs)
    a['ocorrencias_com_vitimas_fatais'] = cl['Com Vítimas Fatais']
    a['ocorrencias_com_vitimas_feridas'] = cl['Com Vítimas Feridas']
    a['ocorrencias_sem_vitimas'] = cl['Sem Vítimas']
    if y == ANO_PARCIAL:
        a['observacao'] = f'ano parcial: janeiro a {br_data(DMAX)}'
    por_ano[str(y)] = a

def rodovia_label(br):
    return 'BR-' + br if br != '0' else 'sem BR identificada (código 0)'

por_rodovia = tabela(lambda r: r['br'], rename=rodovia_label)

mun_ocorr = tabela(lambda r: r['municipio'], 15, rename=bonito)
mun_mortos = {bonito(k): a for k, a in ranking(group(lambda r: r['municipio']), 10, by='mortos')}

# trechos críticos: BR + janela de 5 km
def seg(r):
    if r['km_f'] is None:
        return None
    return (r['br'], int(r['km_f'] // 5) * 5)
gseg = {k: v for k, v in group(seg).items() if k is not None and k[0] != '0'}
def trecho_item(k, v):
    a = agg(v)
    mun = collections.Counter(r['municipio'] for r in v).most_common(1)[0][0]
    anos = collections.Counter(r['ano'] for r in v)
    return {'trecho': f'BR-{k[0]}, km {k[1]} a {k[1] + 5}', 'municipio_predominante': bonito(mun), **a}
trechos_ocorr = [trecho_item(k, v) for k, v in sorted(gseg.items(), key=lambda kv: (-len(kv[1]), -sum(r['mortos'] for r in kv[1]), kv[0]))[:15]]
trechos_mortos = [trecho_item(k, v) for k, v in sorted(gseg.items(), key=lambda kv: (-sum(r['mortos'] for r in kv[1]), -len(kv[1]), kv[0]))[:10]]

prf = {
    'fonte': {
        'descricao': 'Dados abertos da Polícia Rodoviária Federal (PRF): acidentes agrupados por ocorrência (arquivos datatran), filtrados para UF = PI.',
        'origem': 'https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf',
        'periodo': f'{DMIN} a {DMAX}' + (f' ({ANO_PARCIAL} é parcial)' if ANO_PARCIAL else ''),
        'total_ocorrencias': len(rows),
        'escopo': 'SOMENTE rodovias federais (BRs) no Piauí. Não inclui vias estaduais, municipais nem ruas urbanas; por isso os números de Teresina referem-se só aos trechos de BR no município.',
        'natureza': 'Contagem de ocorrências registradas pela PRF e vítimas (mortos, feridos) informadas no boletim; não é a mesma base nem a mesma metodologia do SIH/SUS (internações) nem do SIM (óbitos), então os totais não são comparáveis entre si.',
        'arquivo_filtrado': 'data/prf_acidentes_pi.csv (uma linha por ocorrência, UTF-8)',
        'km_agrupado': 'trechos críticos agrupam ocorrências por BR em janelas de 5 km',
        'classificacao': 'A PRF mudou a classificação de causas e tipos em 2021. Renomeações claras foram unificadas (ex.: "Ingestão de Álcool" de 2020 passou a "Ingestão de álcool pelo condutor"; colisões laterais e com objeto foram agrupadas). Em 2020 algumas causas eram mais genéricas (ex.: "Desobediência às normas de trânsito pelo condutor" tem 242 acidentes só em 2020), então compare causas entre 2020 e os demais anos com cautela.'
    },
    'por_ano': por_ano,
    'por_rodovia': por_rodovia,
    'municipios_mais_ocorrencias': mun_ocorr,
    'municipios_mais_mortos': mun_mortos,
    'trechos_criticos_por_ocorrencias': trechos_ocorr,
    'trechos_criticos_por_mortos': trechos_mortos,
    'causas_do_acidente': tabela(lambda r: r['causa_acidente'], 15),
    'tipos_de_acidente': tabela(lambda r: r['tipo_acidente'], 15),
    'fase_do_dia': tabela(lambda r: r['fase_dia']),
    'periodo_do_dia': tabela(lambda r: periodo(r['hora'])),
    'dia_da_semana': tabela(lambda r: r['dia_semana']),
    'condicao_meteorologica': tabela(lambda r: r['condicao_metereologica']),
    'tipo_de_pista': tabela(lambda r: r['tipo_pista']),
    'ocorrencias_por_classificacao': dict(collections.Counter(r['classificacao_acidente'] for r in rows if r['classificacao_acidente'] != 'NA').most_common()),
}

# ---------------------------------------------------------------- PDF (apresentação UFPI)
def linha(v2015, v2024, vpa, ic, tend):
    return {'2015': v2015, '2024': v2024, 'vpa_pct': vpa, 'ic95': ic, 'tendencia': tend}

def lin2016(t2016, t2025, vpa, ic, tend):
    return {'2016': t2016, '2025': t2025, 'vpa_pct': vpa, 'ic95': ic, 'tendencia': tend}

apresentacao = {
    'fonte': {
        'citacao': 'Amorim GSB, Alves LBC, Mascarenhas MDM. Evolução espaço-temporal de internações e óbitos por acidentes de trânsito no Piauí e Brasil. Universidade Federal do Piauí (UFPI). Apresentação de slides (arquivo "14.09.26 Tendência, distribuição espacial e determinantes das internações por acidentes de trânsito no Brasil, 2016 a 2025").',
        'natureza': 'Resultados NACIONAIS (Brasil), com poucos destaques específicos do Piauí (seção "piaui"). Apresentação de resultados, não artigo revisado.',
        'metodo': {
            'desenho': 'estudo epidemiológico ecológico e analítico, 5.570 municípios brasileiros',
            'populacao': 'internações hospitalares e óbitos de residentes do Brasil por acidentes de transporte terrestre (CID-10 V01-V89)',
            'periodo': 'internações 2016-2025; óbitos 2015-2024',
            'fontes_dados': 'SIH/SUS (cobertura de cerca de 75% das internações do país, exclui o setor privado exclusivo), SIM e IBGE',
            'indicadores': ['coeficiente de internação hospitalar (por 100 mil hab.)', 'custo médio por internação (R$)', 'tempo médio de permanência (dias)', 'taxa de mortalidade hospitalar/letalidade (%)', 'coeficiente de mortalidade (por 100 mil hab.)', 'percentual do total de óbitos'],
            'tendencia': 'regressão de Prais-Winsten sobre log10 dos coeficientes; VPA = variação percentual anual; crescente (p<0,05 e VPA positiva), decrescente (p<0,05 e VPA negativa), estacionária (p>0,05)',
            'analise_espacial': 'mapas coropléticos e LISA (aglomerados Alto-Alto, Baixo-Baixo, Alto-Baixo, Baixo-Alto) nos cortes 2016, 2020 e 2024'
        }
    },
    'contexto': {
        'mundo_oms': 'cerca de 1,19 milhão de óbitos por ano e 20 a 50 milhões de feridos, concentrados em países de baixa e média renda',
        'brasil': 'cerca de 40 mil óbitos por ano; custo de cerca de R$ 50 bilhões por ano para a sociedade; mais de 170 mil internações por ano',
        'frota_motocicletas': 'crescimento de mais de 60% na frota nacional na última década',
        'terminologia': 'ABNT NBR 10697/2018 substitui "acidente" por "sinistro de trânsito" (evento evitável)',
        'dpvat': 'o fim dos repasses do DPVAT ao SUS em 2021 retirou cerca de R$ 580 milhões por ano do orçamento da saúde pública'
    },
    'piaui': {
        'motocicletas_por_domicilio': '52,1% dos lares piauienses tinham motocicleta em 2024, a 2ª maior proporção do Brasil',
        'coeficiente_mortalidade_100mil_hab': {'2015': 34.5, '2024': 34.4, 'vpa_pct': -0.19, 'ic95': '(-4,10 ; 3,87)', 'tendencia': 'Estacionária',
                                               'posicao_2024': '2º maior do Brasil (atrás apenas do Tocantins, 38,7)'},
        'interpretacao_dos_autores': 'a estabilidade seria um platô insustentável; o estado reúne expansão de motocicletas no interior, baixa fiscalização fora da capital e vias rurais adaptadas',
        'cinturao_de_risco': 'o Piauí integra o macrocinturão de aglomerados Alto-Alto (Pará, Tocantins, Maranhão, Piauí, Ceará, Paraíba, Bahia, Goiás e Mato Grosso), associado à expansão da fronteira agrícola e a tráfego pesado em rodovias de pista simples sem acostamento misturado à circulação local de motocicletas',
        'fonte_do_dado': 'SIM, residentes, 2015-2024'
    },
    'internacoes_brasil_2016_2025': {
        'geral': {
            'coeficiente_internacao_100mil_hab': lin2016(87.8, 112.4, 3.40, '(2,47 ; 4,34)', 'Crescente'),
            'permanencia_media_dias': lin2016(6.1, 5.0, -2.02, '(-2,89 ; -1,15)', 'Decrescente'),
            'custo_medio_reais': lin2016(1412.36, 1610.75, 1.84, '(1,38 ; 2,29)', 'Crescente'),
            'letalidade_hospitalar_pct': lin2016(2.77, 2.00, -3.05, '(-3,37 ; -2,72)', 'Decrescente'),
            'variacao_internacoes_na_decada': '+28%',
            'explicacao_autores': 'paradoxo assistencial: internações e custo em alta, letalidade e permanência em queda, associado à expansão de leitos de UTI, cirurgias ortopédicas/traumatológicas complexas e protocolos cirúrgicos'
        },
        'taxa_100mil_por_sexo': {
            'masculino': lin2016(141.4, 177.8, 3.34, '(2,62 ; 4,07)', 'Crescente'),
            'feminino': lin2016(36.6, 55.1, 3.92, '(2,13 ; 5,75)', 'Crescente'),
        },
        'taxa_100mil_por_faixa_etaria': {
            '0 a 4 anos': lin2016(16.0, 15.9, 0.09, '(-1,78 ; 1,99)', 'Estacionária'),
            '5 a 9 anos': lin2016(27.2, 26.4, -0.13, '(-1,36 ; 1,11)', 'Estacionária'),
            '10 a 14 anos': lin2016(37.1, 40.7, 1.15, '(-0,70 ; 3,02)', 'Estacionária'),
            '15 a 19 anos': lin2016(114.3, 143.7, 2.88, '(0,88 ; 4,92)', 'Crescente'),
            '20 a 29 anos': lin2016(150.3, 209.7, 4.46, '(3,66 ; 5,28)', 'Crescente'),
            '30 a 39 anos': lin2016(114.9, 148.6, 3.60, '(3,05 ; 4,16)', 'Crescente'),
            '40 a 49 anos': lin2016(97.6, 126.0, 3.66, '(2,88 ; 4,45)', 'Crescente'),
            '50 a 59 anos': lin2016(78.1, 106.3, 4.00, '(2,80 ; 5,21)', 'Crescente'),
            '60 a 69 anos': lin2016(60.8, 78.1, 3.44, '(1,45 ; 5,48)', 'Crescente'),
            '70 a 79 anos': lin2016(55.6, 62.2, 2.65, '(-2,29 ; 7,85)', 'Estacionária'),
            '80 anos ou mais': lin2016(53.9, 59.9, 1.90, '(-0,87 ; 4,75)', 'Estacionária'),
        },
        'tendencia_por_raca_cor': {
            'parda': {'vpa_pct': 6.64, 'ic95': '(4,83 ; 8,47)', 'tendencia': 'Crescente'},
            'preta': {'vpa_pct': 4.68, 'ic95': '(3,17 ; 6,22)', 'tendencia': 'Crescente'},
            'branca': {'vpa_pct': -0.92, 'ic95': '(-1,72 ; -0,12)', 'tendencia': 'Estacionária', 'p_valor': 0.055},
        },
        'unidade': 'taxas por 100 mil habitantes; VPA em % ao ano'
    },
    'obitos_brasil_2015_2024': {
        'coeficiente_mortalidade_100mil_hab': {
            'total': linha(19.1, 17.5, -1.00, '(-3,27 ; 1,33)', 'Estacionária'),
            'por_sexo': {
                'masculino': linha(32.2, 29.5, -0.96, '(-3,11 ; 1,23)', 'Estacionária'),
                'feminino': linha(6.6, 6.0, -1.08, '(-4,14 ; 2,08)', 'Estacionária'),
                'observacao': 'coeficiente masculino cerca de 5 vezes o feminino em todo o período'
            },
            'por_faixa_etaria': {
                '0 a 4 anos': linha(2.9, 2.4, -2.38, '(-5,82 ; 1,18)', 'Estacionária'),
                '5 a 9 anos': linha(2.5, 1.7, -4.46, '(-7,35 ; -1,48)', 'Decrescente'),
                '10 a 14 anos': linha(3.7, 2.4, -4.71, '(-7,05 ; -2,31)', 'Decrescente'),
                '15 a 19 anos': linha(18.3, 14.2, -2.89, '(-5,73 ; 0,04)', 'Estacionária'),
                '20 a 29 anos': linha(27.3, 24.8, -1.09, '(-3,60 ; 1,47)', 'Estacionária'),
                '30 a 39 anos': linha(23.2, 21.1, -1.07, '(-2,98 ; 0,87)', 'Estacionária'),
                '40 a 49 anos': linha(22.8, 21.1, -0.82, '(-2,79 ; 1,18)', 'Estacionária'),
                '50 a 59 anos': linha(22.6, 21.0, -0.77, '(-2,67 ; 1,17)', 'Estacionária'),
                '60 a 69 anos': linha(23.0, 21.3, -0.86, '(-3,49 ; 1,83)', 'Estacionária'),
                '70 a 79 anos': linha(26.1, 20.9, -2.65, '(-5,80 ; 0,59)', 'Estacionária'),
                '80 anos ou mais': linha(26.8, 20.1, -3.56, '(-7,63 ; 0,69)', 'Estacionária'),
                'observacao': 'a carga concentra-se na população economicamente ativa; a queda em crianças de 5 a 14 anos pode refletir a eficácia parcial do uso de cadeirinhas (Resolução Contran)'
            },
            'por_unidade_federativa': {
                'tocantins': linha(35.8, 38.7, 0.51, '(-2,64 ; 3,76)', 'Estacionária'),
                'piaui': linha(34.5, 34.4, -0.19, '(-4,10 ; 3,87)', 'Estacionária'),
                'mato_grosso': linha(31.3, 32.1, 0.81, '(-0,44 ; 2,07)', 'Estacionária'),
                'sao_paulo': linha(13.9, 11.7, -1.71, '(-3,59 ; 0,21)', 'Estacionária'),
                'distrito_federal': linha(16.6, 10.8, -4.33, '(-6,62 ; -1,98)', 'Decrescente'),
                'rio_de_janeiro': linha(12.9, 7.8, -3.50, '(-6,12 ; -0,80)', 'Decrescente'),
                'ceara': linha(26.1, 16.3, -5.07, '(-9,13 ; -0,83)', 'Decrescente'),
                'observacao': 'Tocantins, Piauí e Mato Grosso têm os 3 maiores coeficientes de 2024; São Paulo, Distrito Federal e Rio de Janeiro os 3 menores; Ceará, Distrito Federal e Rio de Janeiro tiveram as reduções mais expressivas'
            }
        },
        'caracteristicas_dos_obitos_pct_do_total_do_ano': {
            'raca_cor': {
                'branca': linha(40.9, 37.2, -1.07, '(-1,45 ; -0,68)', 'Decrescente'),
                'preta': linha(5.0, 5.8, 1.70, '(1,28 ; 2,12)', 'Crescente'),
                'amarela': linha(0.2, 0.2, 0.50, '(-1,06 ; 2,08)', 'Estacionária'),
                'parda': linha(50.2, 55.5, 1.00, '(0,79 ; 1,21)', 'Crescente'),
                'indigena': linha(0.2, 0.4, 6.89, '(4,83 ; 8,99)', 'Crescente'),
                'ignorado': linha(3.4, 1.0, -11.33, '(-14,92 ; -7,60)', 'Decrescente'),
                'observacao': 'a forte queda de "ignorado" indica melhor preenchimento das Declarações de Óbito, o que infla as demais categorias'
            },
            'assistencia_medica': {
                'sim': linha(3.8, 5.6, 4.23, '(1,90 ; 6,61)', 'Crescente'),
                'nao': linha(37.4, 46.8, 2.30, '(1,72 ; 2,88)', 'Crescente'),
                'ignorado': linha(58.9, 47.6, -2.15, '(-2,81 ; -1,48)', 'Decrescente'),
                'observacao': 'considerando só as informações preenchidas, há 8,35 vezes mais óbitos sem assistência médica'
            },
            'local_de_ocorrencia': {
                'hospital': linha(41.0, 39.9, -0.38, '(-0,64 ; -0,12)', 'Decrescente'),
                'outro_estabelecimento_de_saude': linha(1.2, 1.6, 2.26, '(1,36 ; 3,17)', 'Crescente'),
                'domicilio': linha(0.9, 1.0, 1.44, '(0,20 ; 2,69)', 'Crescente'),
                'via_publica': linha(51.0, 51.2, 0.22, '(0,12 ; 0,33)', 'Crescente'),
                'outros': linha(5.7, 6.2, 0.60, '(-1,08 ; 2,30)', 'Estacionária'),
                'ignorado': linha(0.2, 0.1, -13.46, '(-15,66 ; -11,21)', 'Decrescente'),
                'observacao': 'muitas vítimas morrem antes da chegada do resgate'
            },
            'tipo_de_vitima': {
                'motociclista': linha(31.2, 41.6, 2.79, '(1,75 ; 3,84)', 'Crescente'),
                'ocupante_de_automovel': linha(22.9, 20.2, -1.48, '(-2,04 ; -0,91)', 'Decrescente'),
                'pedestre': linha(18.0, 15.3, -1.75, '(-2,91 ; -0,57)', 'Decrescente'),
                'ciclista': linha(3.4, 4.2, 2.35, '(0,56 ; 4,17)', 'Crescente'),
                'ocupante_de_veiculo_pesado': linha(1.9, 2.9, 3.21, '(1,14 ; 5,31)', 'Crescente'),
                'ocupante_de_caminhonete': linha(0.8, 0.9, 0.51, '(-2,25 ; 3,35)', 'Estacionária'),
                'ocupante_de_onibus': linha(0.6, 0.4, -5.48, '(-7,04 ; -3,89)', 'Decrescente'),
                'ocupante_de_triciclo_motorizado': linha(0.2, 0.1, -2.30, '(-10,1 ; 6,18)', 'Estacionária'),
                'outros_acidentes_de_transporte_terrestre': linha(20.9, 14.4, -3.00, '(-6,45 ; 0,58)', 'Estacionária'),
            }
        },
        'unidade': 'coeficientes por 100 mil habitantes; VPA em % ao ano; caracteristicas em % do total de óbitos do ano'
    },
    'achados_qualitativos': [
        'a mortalidade nacional está estacionária: a estabilidade esconde a expansão da epidemia viária',
        'as internações crescem de forma contínua, com impacto financeiro crescente no SUS, enquanto a letalidade hospitalar cai',
        'a carga das lesões se desloca das capitais para o interior (interiorização do agravo)',
        'o impacto é desproporcional sobre homens jovens, população parda e preta e motociclistas',
        'o crescimento feminino das internações (VPA 3,92%) é mais rápido que o masculino (3,34%), embora o masculino seja 3 vezes maior',
        'as vias públicas concentram 51,2% das mortes em 2024; o interior sofreu explosão de frotas motorizadas sem contrapartida de infraestrutura ou fiscalização',
        'a Lei Seca e outras políticas foram focadas em grandes centros urbanos'
    ],
    'recomendacoes_dos_autores': [
        'descentralizar as políticas de segurança para municípios de pequeno e médio porte',
        'ações intersetoriais integrando fiscalização viária local e regulação do trabalho por aplicativo (motofrete)',
        'alocar investimentos do SUS de forma estratégica e equitativa nos aglomerados críticos'
    ],
    'limitacoes': [
        'desenho ecológico: dados agregados não permitem deduções causais individuais',
        'dados secundários do SIH/SUS (cobertura de cerca de 75% das internações) e do SIM',
        'subnotificação em municípios isolados e diferenças no preenchimento de raça/cor',
        'sem dados adequados para estratificação socioeconômica; análise apenas univariada'
    ]
}

# ---------------------------------------------------------------- JSON
raw = open(OUT_JSON, encoding='utf-8', newline='').read()
d = json.loads(raw)
d.pop('dados_prf_piaui', None)
d.pop('apresentacao_ufpi_morbimortalidade_brasil_2016_2025', None)

new = {}
for k, v in d.items():
    new[k] = v
    if k == 'dados_tabnet_piaui_teresina':
        new['dados_prf_piaui'] = prf
        new['apresentacao_ufpi_morbimortalidade_brasil_2016_2025'] = apresentacao
d = new

ix = d.pop('indice_busca')
P = 'dados_prf_piaui.'
A = 'apresentacao_ufpi_morbimortalidade_brasil_2016_2025.'

def add(palavra, paths):
    cur = ix.setdefault(palavra, [])
    for p in paths:
        if p not in cur:
            cur.append(p)

# a seção piaui_dados_locais é fictícia: sai do índice para nunca ser enviada ao modelo.
for k in ('local', 'municipio', 'rodovia'):
    ix[k] = [p for p in ix[k] if not p.startswith('piaui_dados_locais')]
add('local', [P + 'municipios_mais_ocorrencias', P + 'trechos_criticos_por_ocorrencias'])
add('municipio', [P + 'municipios_mais_ocorrencias', P + 'municipios_mais_mortos'])
add('rodovia', [P + 'fonte', P + 'por_rodovia', P + 'trechos_criticos_por_ocorrencias'])
add('onde', [P + 'trechos_criticos_por_ocorrencias', P + 'municipios_mais_ocorrencias', P + 'por_rodovia'])
add('morte', [P + 'por_ano', P + 'municipios_mais_mortos', A + 'piaui', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab'])
add('obito', [P + 'por_ano', A + 'piaui', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab'])
add('mortalidade', [A + 'piaui', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab'])
add('ano', [P + 'por_ano'])
add('alcool', [P + 'causas_do_acidente'])
add('moto', [A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.tipo_de_vitima', A + 'piaui.motocicletas_por_domicilio'])
add('motociclista', [A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.tipo_de_vitima'])
add('pedestre', [P + 'tipos_de_acidente', A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.tipo_de_vitima'])
add('ciclista', [A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.tipo_de_vitima'])
add('veiculo', [P + 'tipos_de_acidente'])
add('sexo', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_sexo', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_sexo'])
add('genero', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_sexo'])
add('homem', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_sexo', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_sexo'])
add('mulher', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_sexo', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_sexo'])
add('idade', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_faixa_etaria', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_faixa_etaria'])
add('faixa etaria', [A + 'internacoes_brasil_2016_2025.taxa_100mil_por_faixa_etaria', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_faixa_etaria'])
add('raca', [A + 'internacoes_brasil_2016_2025.tendencia_por_raca_cor', A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.raca_cor'])
add('cor', [A + 'internacoes_brasil_2016_2025.tendencia_por_raca_cor'])
add('tendencia', [A + 'internacoes_brasil_2016_2025.geral', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.total'])
add('custo', [A + 'internacoes_brasil_2016_2025.geral'])
add('permanencia', [A + 'internacoes_brasil_2016_2025.geral'])
add('letalidade', [A + 'internacoes_brasil_2016_2025.geral'])
add('internacao', [A + 'internacoes_brasil_2016_2025.geral'])
add('hospital', [A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.local_de_ocorrencia'])
add('cluster', [A + 'piaui.cinturao_de_risco'])
add('espacial', [A + 'piaui.cinturao_de_risco'])
add('capital', [P + 'municipios_mais_ocorrencias'])
add('teresina', [P + 'municipios_mais_ocorrencias', P + 'municipios_mais_mortos'])
# novos termos
add('prf', [P + 'fonte', P + 'por_ano', P + 'por_rodovia', P + 'trechos_criticos_por_ocorrencias'])
add('br', [P + 'por_rodovia', P + 'trechos_criticos_por_ocorrencias', P + 'trechos_criticos_por_mortos'])
add('km', [P + 'trechos_criticos_por_ocorrencias', P + 'trechos_criticos_por_mortos'])
add('trecho', [P + 'trechos_criticos_por_ocorrencias', P + 'trechos_criticos_por_mortos'])
add('critico', [P + 'trechos_criticos_por_ocorrencias', P + 'trechos_criticos_por_mortos', P + 'municipios_mais_ocorrencias'])
add('perigos', [P + 'trechos_criticos_por_ocorrencias', P + 'trechos_criticos_por_mortos'])
add('causa', [P + 'causas_do_acidente'])
add('colisao', [P + 'tipos_de_acidente'])
add('atropelamento', [P + 'tipos_de_acidente'])
add('tipo de acidente', [P + 'tipos_de_acidente'])
add('horario', [P + 'periodo_do_dia', P + 'fase_do_dia'])
add('hora', [P + 'periodo_do_dia', P + 'fase_do_dia'])
add('noite', [P + 'periodo_do_dia', P + 'fase_do_dia'])
add('madrugada', [P + 'periodo_do_dia', P + 'fase_do_dia'])
add('chuva', [P + 'condicao_meteorologica'])
add('clima', [P + 'condicao_meteorologica'])
add('dia da semana', [P + 'dia_da_semana'])
add('fim de semana', [P + 'dia_da_semana'])
add('sabado', [P + 'dia_da_semana'])
add('domingo', [P + 'dia_da_semana'])
add('pista', [P + 'tipo_de_pista'])
add('ocorrencia', [P + 'por_ano', P + 'ocorrencias_por_classificacao'])
add('frota', [A + 'contexto', A + 'piaui.motocicletas_por_domicilio'])
add('dpvat', [A + 'contexto'])
add('brasil', [A + 'internacoes_brasil_2016_2025.geral', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.total', A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_unidade_federativa'])
add('estado', [A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_unidade_federativa'])
add('ranking', [A + 'obitos_brasil_2015_2024.coeficiente_mortalidade_100mil_hab.por_unidade_federativa'])
add('assistencia', [A + 'obitos_brasil_2015_2024.caracteristicas_dos_obitos_pct_do_total_do_ano.assistencia_medica'])
add('recomendacao', [A + 'recomendacoes_dos_autores'])
d['indice_busca'] = ix

# metadata
d['metadata']['ultima_atualizacao'] = datetime.date.today().isoformat() + ' (dados_prf_piaui, interpretacao_prf_piaui e apresentacao_ufpi_morbimortalidade_brasil_2016_2025)'
if "'dados_prf_piaui'" not in d['metadata']['observacao']:
  d['metadata']['observacao'] += (" Também são dados REAIS: 'dados_prf_piaui' (PRF, ocorrências em rodovias federais do Piauí, filtradas por UF=PI) e "
                                "'apresentacao_ufpi_morbimortalidade_brasil_2016_2025' (resultados nacionais da UFPI, com destaques do Piauí). "
                                "'piaui_dados_locais' continua sendo apenas EXEMPLO fictício e foi retirado do índice de busca, portanto não é enviado ao modelo.")

with open(OUT_JSON, 'w', encoding='utf-8', newline='') as fh:
    fh.write(json.dumps(d, ensure_ascii=False, indent=2))
print('ok', len(json.dumps(prf, ensure_ascii=False)), len(json.dumps(apresentacao, ensure_ascii=False)))
print(json.dumps(por_ano, ensure_ascii=False)[:600])
print(trechos_ocorr[:3]); print(list(mun_ocorr.items())[:3]); print(por_rodovia)
