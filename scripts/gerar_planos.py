"""Gera data/sinistros.json -> planos_de_acao: para cada problema, um diagnóstico calculado dos dados da PRF,
do SIH/SUS e da apresentação da UFPI, mais ações propostas, indicadores e quem envolver.
O diagnóstico é calculado; as ações são propostas técnicas (inferência) ou recomendações dos autores, e cada uma
traz essa origem. Rode depois de importar_prf.py e interpretar_prf.py.
Uso: python scripts/gerar_planos.py"""
import collections, csv, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'data', 'sinistros.json')
D = json.load(open(JS, encoding='utf-8'))
ROWS = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'prf_acidentes_pi.csv'), encoding='utf-8', newline='')))

for r in ROWS:
    for c in ['pessoas', 'mortos', 'feridos_leves', 'feridos_graves']:
        r[c] = int(r[c])
    r['hora'] = int(r['horario'][:2])
    r['km_f'] = float(r['km']) if r['km'] not in ('', 'NA') else None
    r['noite'] = r['hora'] >= 18 or r['hora'] < 6
N = len(ROWS)
TOT_M = sum(r['mortos'] for r in ROWS)


def dec(x, c=1):
    return f'{x:.{c}f}'.replace('.', ',')


def num(x):
    return f'{int(round(x)):,}'.replace(',', '.')


def pc(x):
    return dec(x) + '%'


def pct(a, b):
    return 100 * a / b if b else 0.0


def lista(itens):
    itens = list(itens)
    return ''.join(itens) if len(itens) <= 1 else ', '.join(itens[:-1]) + ' e ' + itens[-1]


def pl(n, sing, plur):
    return f'{n} {sing if n == 1 else plur}'


def ordinal(i):
    return f'{i}º'


def st(rs):
    n = len(rs)
    m = sum(r['mortos'] for r in rs)
    return {'n': n, 'm': m, 'l': 100 * m / n if n else 0.0}


def bonito(nome):
    ac = {'PARNAIBA': 'Parnaíba', 'LOBAO': 'Lobão', 'PIAUI': 'Piauí', 'JOSE': 'José', 'JOAO': 'João', 'GONCALO': 'Gonçalo',
          'CONCEICAO': 'Conceição', 'LUIS': 'Luís', 'SAO ': 'São '}
    s = nome
    for k, v in ac.items():
        s = s.replace(k, '\0' + v + '\0')
    out = ''.join(c if c in ac.values() else c.title() for c in s.split('\0'))
    return ' '.join(w.lower() if w in {'Do', 'Da', 'De', 'Dos', 'Das'} else w for w in out.split(' '))


def grp(key, rs):
    g = collections.defaultdict(list)
    for r in rs:
        g[key(r)].append(r)
    return g


def seg(r):
    return None if (r['km_f'] is None or r['br'] == '0') else (r['br'], int(r['km_f'] // 5) * 5)


def top_trechos(rs, by='m', n=3):
    """Trechos de 5 km com mais mortos ('m') ou acidentes ('n') dentro de rs."""
    g = {k: v for k, v in grp(seg, rs).items() if k is not None}
    its = sorted(g.items(), key=lambda kv: (-(sum(r['mortos'] for r in kv[1]) if by == 'm' else len(kv[1])),
                                            -len(kv[1]), kv[0]))
    out = []
    for k, v in its[:n]:
        s = st(v)
        mun = bonito(collections.Counter(r['municipio'] for r in v).most_common(1)[0][0])
        out.append(f'BR-{k[0]} km {k[1]} ao {k[1] + 5} ({mun}: {pl(s["n"], "acidente", "acidentes")}, {pl(s["m"], "morto", "mortos")})')
    return out


def causa(*nomes):
    return [r for r in ROWS if r['causa_acidente'] in nomes]


def tipo(*nomes):
    return [r for r in ROWS if r['tipo_acidente'] in nomes]


PROP = 'proposta técnica (inferência a partir do diagnóstico; os dados não medem a eficácia da medida)'
AUT_B = 'recomendação dos autores (Bastos et al., Rev Bras Epidemiol 2026)'
AUT_U = 'recomendação dos autores (apresentação UFPI)'
E = {'f': 'fiscalização', 'e': 'engenharia', 'd': 'educação e comunicação', 'a': 'atendimento às vítimas', 'g': 'dados e gestão', 'x': 'articulação'}


def acao(texto, eixo, origem=PROP):
    return {'acao': texto, 'eixo': E[eixo], 'origem': origem}


QUEM = {
    'rod': ['PRF (fiscalização)', 'DNIT (infraestrutura das rodovias federais)', 'DETRAN-PI', 'prefeituras'],
    'saude': ['SESAPI', 'SAMU', 'hospitais de referência', 'PRF e Corpo de Bombeiros (resgate)']
}

temas = {}


def ranking_de(campo, valor, por, minimo=0):
    """Posição (1 = maior) de 'valor' no campo ('tipo_acidente' ou 'causa_acidente'), por 'm' (mortos), 'n' (acidentes) ou 'l' (letalidade)."""
    g = grp(lambda r: r[campo], ROWS)
    its = [(k, st(v)) for k, v in g.items() if len(v) >= minimo]
    its.sort(key=lambda kv: (-kv[1][por], kv[0]))
    return next(i for i, (k, _) in enumerate(its, 1) if k == valor)


# ---------------------------------------------------------------- 1. trechos rurais / pista simples
rural = [r for r in ROWS if r['uso_solo'] == 'Não']
simples = [r for r in ROWS if r['tipo_pista'] == 'Simples']
urb = [r for r in ROWS if r['uso_solo'] == 'Sim']
sr, su, ss = st(rural), st(urb), st(simples)
t_rural = top_trechos(rural, 'm', 3)
temas['pista_simples_rural'] = {
    'titulo': 'Reduzir mortes em trechos rurais e de pista simples',
    'diagnostico': (f'Trechos sem construções (rurais) concentram {pc(pct(sr["m"], TOT_M))} dos mortos ({sr["m"]}) com {dec(sr["l"])} mortos por 100 acidentes, '
                    f'contra {dec(su["l"])} nos urbanos; a pista simples reúne {pc(pct(ss["m"], TOT_M))} dos mortos. '
                    f'Trechos rurais com mais mortos: {"; ".join(t_rural)}.'),
    'locais_prioritarios': t_rural,
    'acoes': [
        acao('Revisar a infraestrutura dos trechos rurais prioritários (acostamento, sinalização horizontal e vertical, sinalização de curvas e de ultrapassagem proibida) e avaliar faixas adicionais ou duplicação nos segmentos mais letais.', 'e', AUT_B + ': revisão da infraestrutura viária nas áreas de maior risco; detalhamento é ' + PROP),
        acao('Instalar controle de velocidade e fiscalização de ultrapassagem nesses trechos, com pontos fixos e operações móveis.', 'f'),
        acao('Posicionar apoio de resgate (bases ou ambulâncias do SAMU, em acordo com a PRF) perto dos trechos rurais mais letais, para reduzir o tempo até o socorro.', 'a', AUT_U + ': alocação estratégica de investimentos do SUS nos aglomerados críticos; local exato é ' + PROP),
    ],
    'indicadores': ['mortos por 100 acidentes em trechos rurais', 'mortos por ano nos trechos prioritários', 'acidentes em pista simples'],
    'quem_envolver': QUEM['rod'] + ['SAMU'],
}

# ---------------------------------------------------------------- 2. colisão frontal e contramão
fr = tipo('Colisão frontal')
cm = causa('Transitar na contramão')
ul = causa('Ultrapassagem Indevida')
sf, sc, sul = st(fr), st(cm), st(ul)
br_fr = collections.Counter()
for r in fr:
    br_fr[r['br']] += r['mortos']
t_fr = top_trechos(fr, 'm', 3)
temas['colisao_frontal_contramao'] = {
    'titulo': 'Reduzir colisões frontais e mortes por circulação na contramão',
    'diagnostico': (f'Colisão frontal: {num(sf["n"])} acidentes e {sf["m"]} mortos ({dec(sf["l"])} por 100 acidentes; {ordinal(ranking_de("tipo_acidente", "Colisão frontal", "l", 50))} lugar em letalidade entre os tipos e {ordinal(ranking_de("tipo_acidente", "Colisão frontal", "m"))} em mortos). '
                    f'Transitar na contramão: {num(sc["n"])} acidentes e {sc["m"]} mortos ({dec(sc["l"])} por 100). Ultrapassagem indevida: {num(sul["n"])} acidentes e {sul["m"]} mortos. '
                    f'BRs com mais mortos em colisões frontais: {lista(f"BR-{b} ({m})" for b, m in br_fr.most_common(3))}. Trechos: {"; ".join(t_fr)}.'),
    'locais_prioritarios': t_fr,
    'acoes': [
        acao('Separar os sentidos nos trechos de pista simples mais críticos (sinalização e tachas refletivas, faixa central dupla, avaliar barreira ou canteiro central onde houver mais mortes).', 'e'),
        acao('Sinalizar de forma reforçada retornos, acessos e entradas de pistas duplas para evitar a entrada na contramão.', 'e'),
        acao('Fiscalizar ultrapassagens proibidas e a circulação na contramão nesses trechos, com abordagem e flagrantes.', 'f'),
        acao('Campanhas dirigidas a condutores sobre ultrapassagem segura em pista simples.', 'd'),
    ],
    'indicadores': ['mortos em colisões frontais por ano', 'acidentes por contramão por ano', 'mortos por 100 acidentes frontais'],
    'quem_envolver': QUEM['rod'],
}

# ---------------------------------------------------------------- 3. pedestres
at = tipo('Atropelamento de Pedestre')
sat = st(at)
c_ped = [r for r in ROWS if 'edestre' in r['causa_acidente']]
sped = st(c_ped)
sem_trav = [r for r in ROWS if r['causa_acidente'].startswith('Área urbana sem a presença de local apropriado')]
g_mun_at = grp(lambda r: r['municipio'], at)
mun_at = sorted(g_mun_at.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:3]
t_at = top_trechos(at, 'n', 3)
temas['pedestres'] = {
    'titulo': 'Reduzir atropelamentos de pedestres',
    'diagnostico': (f'Foram {num(sat["n"])} atropelamentos de pedestres com {sat["m"]} mortos ({dec(sat["l"])} por 100; {ordinal(ranking_de("tipo_acidente", "Atropelamento de Pedestre", "l", 50))} lugar em letalidade entre os tipos e {ordinal(ranking_de("tipo_acidente", "Atropelamento de Pedestre", "m"))} em mortos). '
                    f'Causas ligadas ao pedestre somam {num(sped["n"])} acidentes e {sped["m"]} mortos. '
                    f'Municípios com mais atropelamentos: {lista(f"{bonito(k)} ({len(v)})" for k, v in mun_at)}. Trechos com mais atropelamentos: {"; ".join(t_at)}.'),
    'locais_prioritarios': t_at,
    'acoes': [
        acao('Implantar travessias seguras nos trechos urbanos das BRs com mais atropelamentos: passarelas ou faixas com semáforo para pedestres, refúgios e redutores de velocidade antes da travessia.', 'e'),
        acao('Iluminar travessias e pontos de parada, onde há acidentes noturnos com pedestres.', 'e'),
        acao('Construir calçadas e vias marginais ou acostamentos utilizáveis, para pedestres não andarem na pista.', 'e'),
        acao('Articular PRF, DNIT e prefeituras, porque os trechos urbanos de BR têm gestão compartilhada.', 'x'),
        acao('Campanhas de educação para pedestres e condutores nos municípios mais afetados.', 'd'),
    ],
    'indicadores': ['atropelamentos de pedestres por ano', 'mortos em atropelamentos por ano', 'número de travessias seguras implantadas'],
    'quem_envolver': QUEM['rod'],
}

# ---------------------------------------------------------------- 4. noite e madrugada
nt = [r for r in ROWS if r['noite']]
mad = [r for r in ROWS if r['hora'] < 6]
snt, smd = st(nt), st(mad)
t_nt = top_trechos(nt, 'm', 3)
temas['noite_madrugada'] = {
    'titulo': 'Reduzir acidentes graves à noite e na madrugada',
    'diagnostico': (f'Das 18h às 5h59 ocorrem {pc(pct(snt["n"], N))} dos acidentes, mas {pc(pct(snt["m"], TOT_M))} dos mortos ({snt["m"]}); '
                    f'a madrugada tem {dec(smd["l"])} mortos por 100 acidentes ({"a maior gravidade do dia" if smd["l"] == max(st([r for r in ROWS if lo <= r["hora"] < hi])["l"] for lo, hi in [(0, 6), (6, 12), (12, 18), (18, 24)]) else "não é a maior do dia"}). Trechos com mais mortos à noite: {"; ".join(t_nt)}.'),
    'locais_prioritarios': t_nt,
    'acoes': [
        acao('Concentrar a fiscalização noturna (velocidade, álcool, fadiga) nos trechos e horários listados, em vez de distribuí-la igualmente ao longo do dia.', 'f'),
        acao('Melhorar iluminação e sinalização refletiva (tachas, delineadores, placas) nos trechos mais letais à noite.', 'e'),
        acao('Campanhas sobre direção à noite e fadiga, em postos e paradas de caminhoneiros.', 'd'),
    ],
    'indicadores': ['mortos entre 18h e 5h59', 'mortos por 100 acidentes na madrugada', 'operações noturnas realizadas'],
    'quem_envolver': QUEM['rod'],
}

# ---------------------------------------------------------------- 5. álcool e fim de semana
al = causa('Ingestão de álcool pelo condutor')
sal = st(al)
al_noite = pct(sum(1 for r in al if r['noite']), len(al))
al_fds = pct(sum(1 for r in al if r['dia_semana'] in ('sábado', 'domingo')), len(al))
fds = [r for r in ROWS if r['dia_semana'] in ('sábado', 'domingo')]
sfd = st(fds)
g_mun_al = grp(lambda r: r['municipio'], al)
mun_al = sorted(g_mun_al.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:3]
temas['alcool_fim_de_semana'] = {
    'titulo': 'Combater a direção sob efeito de álcool e os acidentes de fim de semana',
    'diagnostico': (f'O álcool do condutor aparece em {num(sal["n"])} acidentes ({pc(pct(sal["n"], N))}) e {sal["m"]} mortos, {pc(al_noite)} deles à noite ou na madrugada e {pc(al_fds)} aos sábados e domingos. '
                    f'Sábado e domingo reúnem {pc(pct(sfd["n"], N))} dos acidentes e {pc(pct(sfd["m"], TOT_M))} dos mortos. '
                    f'Municípios com mais acidentes por álcool: {lista(f"{bonito(k)} ({len(v)})" for k, v in mun_al)}. O dado só conta quando a PRF registrou o álcool como causa.'),
    'locais_prioritarios': [f'{bonito(k)} ({len(v)} acidentes por álcool)' for k, v in mun_al],
    'acoes': [
        acao('Programar operações de fiscalização de álcool (Lei Seca) de sexta à noite até domingo, nos municípios e trechos com mais registros.', 'f'),
        acao('Campanhas de conscientização em bares, eventos e festas dos municípios com mais ocorrências, com alternativas de transporte.', 'd'),
        acao('Melhorar o registro: padronizar teste de alcoolemia e anotação da causa, porque o dado atual provavelmente subestima o problema.', 'g'),
    ],
    'indicadores': ['acidentes com álcool como causa por ano', 'mortos aos sábados e domingos', 'testes de alcoolemia realizados'],
    'quem_envolver': QUEM['rod'],
}

# ---------------------------------------------------------------- 6. animais
an = causa('Animais na Pista')
tan = tipo('Atropelamento de Animal')
san, stan = st(an), st(tan)
g_br_an = collections.Counter(r['br'] for r in an)
t_an = top_trechos(an, 'n', 3)
an_noite = pct(sum(1 for r in an if r['noite']), len(an))
temas['animais_na_pista'] = {
    'titulo': 'Reduzir acidentes com animais na pista',
    'diagnostico': (f'Animais na pista: {num(san["n"])} acidentes ({pc(pct(san["n"], N))}) e {san["m"]} mortos, {pc(an_noite)} à noite ou na madrugada. '
                    f'Atropelamentos de animais: {num(stan["n"])}. BRs com mais casos: {lista(f"BR-{b} ({n})" for b, n in g_br_an.most_common(3))}. Trechos: {"; ".join(t_an)}.'),
    'locais_prioritarios': t_an,
    'acoes': [
        acao('Sinalizar os trechos com mais registros e reforçar a sinalização refletiva e a iluminação nesses pontos.', 'e'),
        acao('Trabalhar com prefeituras e produtores rurais para evitar animais soltos na faixa de domínio (cercamento, recolhimento).', 'x'),
        acao('Campanhas para condutores sobre redução de velocidade à noite em trechos rurais.', 'd'),
    ],
    'indicadores': ['acidentes com animais por ano', 'mortos em acidentes com animais', 'animais recolhidos das rodovias'],
    'quem_envolver': QUEM['rod'] + ['produtores rurais'],
}

# ---------------------------------------------------------------- 7. atenção e fadiga
hum = causa('Ausência de reação do condutor', 'Reação tardia ou ineficiente do condutor', 'Condutor deixou de manter distância do veículo da frente',
            'Falta de Atenção à Condução', 'Condutor Dormindo')
shum = st(hum)
dorm = causa('Condutor Dormindo')
sdorm = st(dorm)
dorm_mad = pct(sum(1 for r in dorm if r['hora'] < 6), len(dorm))
ausencia = st(causa('Ausência de reação do condutor'))
temas['atencao_fadiga'] = {
    'titulo': 'Combater acidentes por falta de atenção, reação tardia e sono do condutor',
    'diagnostico': (f'Falta de atenção, ausência ou demora de reação, falta de distância e sono somam {num(shum["n"])} acidentes ({pc(pct(shum["n"], N))}) e {shum["m"]} mortos ({pc(pct(shum["m"], TOT_M))}). '
                    f'"Ausência de reação do condutor" ocupa o {ordinal(ranking_de("causa_acidente", "Ausência de reação do condutor", "n"))} lugar em acidentes ({num(ausencia["n"])}) e o {ordinal(ranking_de("causa_acidente", "Ausência de reação do condutor", "m"))} em mortos ({ausencia["m"]}). '
                    f'Condutor dormindo: {num(sdorm["n"])} acidentes e {sdorm["m"]} mortos, {pc(dorm_mad)} na madrugada.'),
    'locais_prioritarios': [],
    'acoes': [
        acao('Instalar faixas sonorizadoras (alerta ao sair da faixa) e sinalização de alerta de fadiga em trechos retos e longos com mais acidentes por sono ou ausência de reação.', 'e'),
        acao('Criar ou sinalizar pontos de parada e descanso ao longo das BRs, e orientar sobre tempo máximo de direção, em especial para motoristas profissionais.', 'e'),
        acao('Campanhas de atenção ao volante (celular, cansaço, distância de segurança) e fiscalização de velocidade, que reduz o tempo de reação exigido.', 'f'),
    ],
    'indicadores': ['acidentes por ausência ou demora de reação', 'acidentes com condutor dormindo', 'pontos de parada implantados'],
    'quem_envolver': QUEM['rod'],
    'observacao': 'A causa registrada pela PRF descreve o comportamento observado e pode esconder motivos (fadiga, distração, mal-estar), por isso as ações são mais amplas.',
}

# ---------------------------------------------------------------- 8. Teresina
ter = [r for r in ROWS if r['municipio'] == 'TERESINA']
ster = st(ter)
t_ter = top_trechos(ter, 'n', 4)
g_tipo_ter = grp(lambda r: r['tipo_acidente'], ter)
tipos_ter = sorted(g_tipo_ter.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:3]
ter_at = st([r for r in ter if r['tipo_acidente'] == 'Atropelamento de Pedestre'])
temas['teresina_urbano'] = {
    'titulo': 'Atuar nos trechos urbanos críticos de Teresina',
    'diagnostico': (f'Teresina concentra {pc(pct(ster["n"], N))} dos acidentes ({num(ster["n"])}) e {pc(pct(ster["m"], TOT_M))} dos mortos ({ster["m"]}) das BRs do Piauí, com {dec(ster["l"])} mortos por 100 acidentes (média {dec(pct(TOT_M, N))}). '
                    f'Tipos mais comuns: {lista(f"{k.lower()} ({len(v)})" for k, v in tipos_ter)}; atropelamentos de pedestres: {ter_at["n"]} ({ter_at["m"]} mortos). '
                    f'Trechos com mais acidentes: {"; ".join(t_ter)}.'),
    'locais_prioritarios': t_ter,
    'acoes': [
        acao('Tratar os trechos urbanos como via urbana: semaforização coordenada, fiscalização eletrônica de velocidade e avanço de sinal, e controle de acessos.', 'e'),
        acao('Separar o tráfego local do tráfego de passagem com vias marginais e retornos sinalizados.', 'e'),
        acao('Definir um comitê PRF–DNIT–prefeitura para os trechos urbanos de BR, com metas e acompanhamento mensal.', 'x'),
    ],
    'indicadores': ['acidentes por mês nos 4 trechos prioritários', 'colisões transversais e traseiras', 'atropelamentos'],
    'quem_envolver': QUEM['rod'],
}

# ---------------------------------------------------------------- 9. BRs mais letais por acidente
g_br = grp(lambda r: r['br'], [r for r in ROWS if r['br'] != '0'])
brs = sorted(((k, st(v)) for k, v in g_br.items() if len(v) >= 100), key=lambda kv: -kv[1]['l'])[:3]
t_brs = []
for k, s_ in brs:
    t = top_trechos([r for r in ROWS if r['br'] == k], 'm', 1)
    t_brs += t
temas['brs_mais_letais'] = {
    'titulo': 'Priorizar as rodovias mais letais por acidente',
    'diagnostico': (f'Entre as BRs com 100 ou mais acidentes, as mais letais são {lista(f"BR-{k} ({dec(s_['l'])} mortos por 100 acidentes, {s_['m']} mortos em {num(s_['n'])})" for k, s_ in brs)}; '
                    f'a média do estado é {dec(pct(TOT_M, N))}. Trecho com mais mortos em cada uma: {"; ".join(t_brs)}.'),
    'locais_prioritarios': t_brs,
    'acoes': [
        acao('Direcionar patrulhamento e operações para essas BRs, que têm menos acidentes, mas muito mais mortes por acidente, o que pode indicar velocidade alta e trechos rurais.', 'f'),
        acao('Fazer uma inspeção de segurança viária nos trechos de maior letalidade (sinalização, acostamento, defeitos na pista).', 'e'),
        acao('Mapear o tempo de chegada do resgate nesses trechos e instalar apoio onde for maior.', 'a'),
    ],
    'indicadores': ['mortos por 100 acidentes em cada BR', 'mortos por ano em cada BR'],
    'quem_envolver': QUEM['rod'] + ['SAMU'],
}

# ---------------------------------------------------------------- 10. motociclistas (internações, VIVA, UFPI)
E_ = D['estudo_morbidade_piaui_2010_2023']
TX = E_['taxa_internacao_hospitalar_100mil_hab']
TB = D['dados_tabnet_piaui_teresina']['piaui']
moto_tab = TB['internacoes_por_categoria_e_ano']['V20-V29']['total_periodo']
tot_tab = TB['internacoes_por_ano']['total_periodo']
mo, pe = TX['por_tipo_vitima']['motociclista']['valor'], TX['por_tipo_vitima']['pedestre']['valor']
cap = D['evento']['uso_capacete']['nao']['total_pct'] * 100
alc_v = D['evento']['consumo_alcool']['sim']['total_pct'] * 100
trab = D['evento']['relacionado_trabalho']['sim']['total_pct'] * 100
U = D['apresentacao_ufpi_morbimortalidade_brasil_2016_2025']
tv = U['obitos_brasil_2015_2024']['caracteristicas_dos_obitos_pct_do_total_do_ano']['tipo_de_vitima']['motociclista']
temas['motociclistas'] = {
    'titulo': 'Reduzir acidentes e mortes de motociclistas',
    'diagnostico': (f'No Piauí, motociclistas são {pc(pct(moto_tab, tot_tab))} das internações por acidentes de transporte (TABNET) e têm taxa de internação de {dec(mo)} por 100 mil, cerca de {dec(mo / pe, 0)} vezes a dos pedestres (SIH/SUS 2010-2023). '
                    f'{dec(E_["contexto_estado_piaui"]["domicilios_com_motocicleta_pct_2024"])}% dos domicílios têm moto (2024). No Brasil, motociclistas passaram de {dec(tv["2015"])}% para {dec(tv["2024"])}% dos óbitos (2015-2024). '
                    f'No inquérito nacional VIVA 2014, {dec(cap)}% dos motociclistas atendidos não usavam capacete, {dec(alc_v)}% relataram álcool e {dec(trab)}% dos casos eram ligados ao trabalho. '
                    'A base da PRF usada aqui não separa o tipo de veículo.'),
    'locais_prioritarios': [],
    'acoes': [
        acao('Ampliar a educação no trânsito dirigida a motociclistas jovens.', 'd', AUT_B),
        acao('Combinar a fiscalização viária local com a regulação do trabalho por aplicativo e do motofrete (jornada, equipamentos, formação).', 'x', AUT_U),
        acao('Fiscalização de capacete, habilitação e álcool com foco nos municípios do interior, em vez de só na capital.', 'f', AUT_U + ': descentralizar as políticas para municípios de pequeno e médio porte; foco em capacete e habilitação é ' + PROP),
        acao('Passar a registrar o tipo de veículo e o uso de capacete nos acidentes, para medir o problema no Piauí com dado local.', 'g'),
    ],
    'indicadores': ['internações de motociclistas por 100 mil habitantes', 'mortos motociclistas (SIM)', 'proporção sem capacete nas abordagens'],
    'quem_envolver': ['DETRAN-PI', 'PRF', 'prefeituras', 'SESAPI', 'sindicatos e empresas de aplicativo'],
    'observacao': 'Capacete, álcool e trabalho vêm do VIVA 2014 (nacional); a taxa e a participação nas internações vêm de dados do Piauí.',
}

# ---------------------------------------------------------------- 11. atendimento pré-hospitalar
lo = U['obitos_brasil_2015_2024']['caracteristicas_dos_obitos_pct_do_total_do_ano']['local_de_ocorrencia']
am = U['obitos_brasil_2015_2024']['caracteristicas_dos_obitos_pct_do_total_do_ano']['assistencia_medica']
temas['atendimento_pre_hospitalar'] = {
    'titulo': 'Melhorar o atendimento às vítimas para reduzir mortes na via',
    'diagnostico': (f'No Brasil, {dec(lo["via_publica"]["2024"])}% das mortes ocorrem na via pública e {dec(lo["hospital"]["2024"])}% no hospital (2024), e {dec(am["nao"]["2024"])}% dos óbitos foram sem assistência médica. '
                    f'Na PRF do Piauí, trechos rurais têm {dec(sr["l"])} mortos por 100 acidentes contra {dec(su["l"])} nos urbanos, o que pode refletir distância do socorro (hipótese, os dados não medem tempo de resgate). '
                    f'Nos hospitais, a letalidade no Piauí é de {dec(E_["letalidade_hospitalar_pct"]["geral"]["valor"])}% (SIH/SUS).'),
    'locais_prioritarios': t_rural,
    'acoes': [
        acao('Adequar a rede de atenção ao trauma (leitos, referência regional, transporte entre hospitais).', 'a', AUT_B),
        acao('Alocar investimentos do SUS, como bases do SAMU e leitos de trauma, nos aglomerados de maior risco.', 'a', AUT_U),
        acao('Treinar equipes da PRF e comunidades próximas às rodovias em primeiros socorros e acionamento do SAMU.', 'a'),
        acao('Medir o tempo entre o acidente e a chegada do socorro nos trechos críticos, hoje ausente da base.', 'g'),
    ],
    'indicadores': ['tempo de resposta do socorro nos trechos críticos', 'proporção de óbitos na via pública', 'letalidade hospitalar'],
    'quem_envolver': QUEM['saude'],
}

# ---------------------------------------------------------------- 12. dados
temas['dados_monitoramento'] = {
    'titulo': 'Melhorar os dados para monitorar os acidentes de trânsito',
    'diagnostico': ('A base reúne fontes separadas que não se cruzam (PRF, SIH/SUS, SIM) e tem lacunas: o arquivo da PRF não traz o tipo de veículo; o SIH/SUS cobre cerca de 75% das internações; '
                    f'há subnotificação em municípios isolados e {dec(am["ignorado"]["2024"])}% dos óbitos nacionais têm assistência médica "ignorada" (2024). '
                    'A PRF mudou a classificação de causas em 2021, o que dificulta comparar anos.'),
    'locais_prioritarios': [],
    'acoes': [
        acao('Integrar PRF, SAMU, hospitais e SIM por geolocalização e data, para contar cada vítima de ponta a ponta.', 'g'),
        acao('Padronizar o preenchimento de raça/cor, assistência médica, tipo de veículo e uso de equipamentos de segurança.', 'g'),
        acao('Publicar um painel mensal por trecho e município, para acompanhar metas.', 'g'),
        acao('Obter dados de vias estaduais e urbanas (DETRAN-PI, SESAPI), hoje fora da base.', 'g'),
    ],
    'indicadores': ['proporção de registros com campos "ignorado"', 'número de fontes integradas'],
    'quem_envolver': ['SESAPI', 'DETRAN-PI', 'PRF', 'prefeituras', 'UFPI'],
}

# ---------------------------------------------------------------- 13. plano integrado
fr_ped_m = st(fr)['m'] + st(at)['m']
prior = sorted([
    ('trechos rurais', pct(sr['m'], TOT_M)),
    ('noite e madrugada', pct(snt['m'], TOT_M)),
    ('colisões frontais e atropelamentos de pedestres', pct(fr_ped_m, TOT_M)),
    ('sábados e domingos', pct(sfd['m'], TOT_M)),
], key=lambda kv: -kv[1])
temas['plano_integrado'] = {
    'titulo': 'Plano integrado para reduzir mortes no trânsito do Piauí',
    'diagnostico': ('Onde estão as mortes registradas pela PRF (os recortes se sobrepõem, não somam 100%): '
                    + '; '.join(f'{nome} ({pc(v)} dos mortos)' for nome, v in prior) +
                    f'. O Piauí teve o 2º maior coeficiente de mortalidade do país em 2024 ({dec(U["piaui"]["coeficiente_mortalidade_100mil_hab"]["2024"])} por 100 mil hab.), estável desde 2015, e os autores da UFPI pedem descentralizar as políticas para o interior e unir fiscalização local e regulação do motofrete.'),
    'locais_prioritarios': t_rural[:2] + top_trechos(ter, 'm', 1),
    'acoes': [
        acao('Fiscalização: concentrar operações nos trechos, horários e dias mais letais (noite/madrugada, fins de semana), com foco em velocidade, álcool e ultrapassagem.', 'f'),
        acao('Engenharia: tratar primeiro os trechos rurais de pista simples com mais mortos e os trechos urbanos de Teresina com mais atropelamentos e colisões.', 'e'),
        acao('Educação: campanhas dirigidas a motociclistas jovens, motoristas profissionais (fadiga) e pedestres.', 'd', AUT_B + ': educação para motociclistas jovens; demais públicos são ' + PROP),
        acao('Atendimento às vítimas: apoio de resgate perto dos trechos rurais críticos e adequação da rede de trauma.', 'a', AUT_B + ' e ' + AUT_U),
        acao('Gestão: metas por trecho, painel mensal e integração de dados; comitê entre PRF, DNIT, DETRAN-PI, SESAPI e prefeituras.', 'g'),
    ],
    'indicadores': ['mortos por ano nas rodovias federais (PRF)', 'mortos por 100 acidentes', 'coeficiente de mortalidade (SIM)', 'internações por 100 mil habitantes (SIH)'],
    'quem_envolver': ['PRF', 'DNIT', 'DETRAN-PI', 'SESAPI', 'SAMU', 'prefeituras'],
}

planos = {
    'como_usar': ('Propostas de plano de ação com diagnóstico calculado dos dados. Ao responder pedidos de plano/medidas, use o diagnóstico (números), os locais prioritários, '
                  'as ações (indicando a origem de cada uma), os indicadores e quem envolver. Diga que as ações são propostas e não resultado dos dados.'),
    'limite_da_inferencia': ('O diagnóstico vem dos dados (PRF 2020 em diante em rodovias federais, SIH/SUS 2010-2023, TABNET e apresentação da UFPI). As ações marcadas como "proposta técnica" '
                             'são inferências a partir do diagnóstico e de práticas usuais de segurança viária; os dados não medem a eficácia, o custo ou a viabilidade de cada medida, nem as causas '
                             'além do que a PRF registra. As marcadas como "recomendação dos autores" vêm dos estudos citados.'),
    'temas': temas,
}

raw = open(JS, encoding='utf-8', newline='').read()
d = json.loads(raw)
d.pop('planos_de_acao', None)
novo = {}
for k, v in d.items():
    novo[k] = v
    if k == 'interpretacao_prf_piaui':
        novo['planos_de_acao'] = planos
open(JS, 'w', encoding='utf-8', newline='').write(json.dumps(novo, ensure_ascii=False, indent=2))
print(len(temas), 'temas;', len(json.dumps(planos, ensure_ascii=False)), 'caracteres')
for k, t in temas.items():
    print('==', k); print(t['diagnostico'])
