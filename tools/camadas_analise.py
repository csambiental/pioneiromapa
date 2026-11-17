"""Recorta, para as propriedades do mapa, as camadas já levantadas pela Análise Rural da CS (territoriogeo/analise/data/m/<município>).
Uso: python3 tools/camadas_analise.py CAMINHO/territoriogeo/analise/data/m
Gera data/analise/*.geojson e atualiza data/fazendas.json (camadas + link do Raio-X de cada propriedade).
APP: estimativa pelas faixas legais do Código Florestal (rios até 10 m: 30 m; nascentes: raio de 50 m), sem a regra de área consolidada."""
import json, os, sys, math
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, transform

BASE = sys.argv[1]
OUT = 'data/analise'
os.makedirs(OUT, exist_ok=True)
cfg = json.load(open('data/fazendas.json'))
ler = lambda p: json.load(open(p)) if os.path.exists(p) else {'features': []}

def projetores(lat0):
    k = 111320 * math.cos(math.radians(lat0))
    ida = lambda x, y, z=None: (x * k, y * 110540)
    volta = lambda x, y, z=None: (x / k, y / 110540)
    return (lambda g: transform(ida, g)), (lambda g: transform(volta, g))

def r6(o):
    if isinstance(o, float): return round(o, 6)
    if isinstance(o, (list, tuple)): return [r6(x) for x in o]
    return o

def feat(geom, props):
    return {'type': 'Feature', 'properties': props, 'geometry': r6(mapping(geom))}

saida = {k: [] for k in ['rios', 'nascentes', 'app', 'outorgas', 'licencas', 'barragens', 'massas', 'sigef', 'vizinhos']}
resumo = []
for f in cfg['fazendas']:
    cod = f['car'].split('-')[1]
    D = f'{BASE}/{cod}'
    if not os.path.exists(f'{D}/config.json'):
        print(f['id'], 'município', cod, 'ainda não processado na Análise Rural'); continue
    g = unary_union([shape(x['geometry']) for x in json.load(open(f"data/propriedades/{f['id']}.geojson"))['features']])
    ida, volta = projetores(g.centroid.y)
    gm = ida(g)
    zona = lambda m: volta(gm.buffer(m))
    z300, z1k = zona(300), zona(1000)
    tag = {'propriedade': f['nome'].split(' – ')[0], 'id': f['id']}
    # rios e nascentes (FBDS)
    rios = [shape(x['geometry']) for x in ler(f'{D}/rios_fbds.geojson')['features']]
    rios = [r.intersection(z300) for r in rios if r.intersects(z300)]
    for r in rios: saida['rios'].append(feat(r, {'nome': 'Rio / córrego (FBDS)', **tag}))
    nasc = [shape(x['geometry']) for x in ler(f'{D}/nascentes_fbds.geojson')['features']]
    nasc = [n for n in nasc if n.intersects(z300)]
    for n in nasc: saida['nascentes'].append(feat(n, {'nome': 'Nascente (FBDS)', **tag}))
    # APP estimada dentro da propriedade
    faixas = [ida(r).buffer(30) for r in rios] + [ida(n).buffer(50) for n in nasc]
    app_ha = 0.0
    if faixas:
        app = unary_union(faixas).intersection(gm)
        if not app.is_empty:
            app_ha = app.area / 10000
            saida['app'].append(feat(volta(app), {'nome': 'APP estimada (faixa legal)', 'Área (ha)': f'{app_ha:.2f}'.replace('.', ','),
                                                  'Critério': 'Rios até 10 m: 30 m · nascentes: raio de 50 m (Código Florestal, sem regra de área consolidada)', **tag}))
    # pontos no entorno de 1 km
    for chave, arq, campos in [('outorgas', 'outorgas_rural.geojson', ['grupo', 'Documento', 'Portaria / declaração', 'Situação', 'Finalidade', 'Corpo hídrico / aquífero', 'Vazão máxima (m³/h)', 'Vencimento']),
                               ('licencas', 'licencas.geojson', ['grupo', 'Situação', 'Atividade', 'Nº do documento', 'Emissão', 'Validade', 'Protocolo']),
                               ('barragens', 'barragens.geojson', ['Categoria de risco', 'Dano potencial associado (DPA)', 'Uso principal', "Curso d'água", 'Altura (m)'])]:
        for x in ler(f'{D}/{arq}')['features']:
            if not x.get('geometry'): continue
            s = shape(x['geometry'])
            if s.intersects(z1k):
                p = x['properties']
                saida[chave].append(feat(s, {'nome': p.get('nome') or '', **{k: p[k] for k in campos if p.get(k)}, 'Distância da propriedade': f"{ida(s).distance(gm):.0f} m", **tag}))
    for x in ler(f'{D}/massas_dagua.geojson')['features']:
        s = shape(x['geometry'])
        if s.intersects(z300):
            p = x['properties']; saida['massas'].append(feat(s, {'nome': p.get('nome') or 'Massa d\'água', 'Tipo': p.get('Tipo', ''), 'Área (ha)': p.get('Área (ha)', ''), **tag}))
    # SIGEF que toca a propriedade e CAR vizinhos (só o código do CAR, sem nome de titular)
    for x in ler(f'{D}/sigef.geojson')['features']:
        s = shape(x['geometry'])
        if s.intersects(g) and ida(s).intersection(gm).area > 100:
            p = x['properties']; saida['sigef'].append(feat(s, {'nome': 'Parcela certificada (SIGEF/INCRA)', 'Situação': p.get('Situação', ''), 'Certificado em': p.get('Certificado em', ''), 'Área (ha)': p.get('Área (ha)', ''), **tag}))
    norm = lambda c: c.replace('.', '').upper()
    car_prop = None
    for x in ler(f'{D}/car.geojson')['features']:
        p = x['properties']
        if norm(p.get('nome', '')) == norm(f['car']): car_prop = p; continue
        s = shape(x['geometry'])
        if p.get('situacao') != 'Cancelado' and s.intersects(z300) and not s.within(g):
            saida['vizinhos'].append(feat(s, {'nome': 'Imóvel vizinho (CAR)', 'CAR': p.get('nome', ''), 'Área (ha)': p.get('Área (ha)', ''), 'Situação': p.get('Condição', ''), **tag}))
    # link do Raio-X e resumo na ficha da propriedade
    link = f"https://csambiental.github.io/territoriogeo/analise/?m={cod}&car={f['car'].replace('.', '')}"
    docs = [d for d in f.get('documentos', []) if 'Raio-X' not in d.get('titulo', '')]
    f['documentos'] = docs + [{'titulo': 'Raio-X automático do imóvel (Análise Rural CS)', 'arquivo': link}]
    info = {k: v for k, v in f['info'].items() if not k.startswith('Análise automática')}
    if car_prop:
        info['Análise automática – vegetação nativa'] = f"{str(round(car_prop.get('veg_nativa_pct') or 0, 1)).replace('.', ',')}% do imóvel ({car_prop.get('faixa_veg', '')})"
        if car_prop.get('Uso do solo 2023 – Agricultura (%)'): info['Análise automática – agricultura'] = car_prop['Uso do solo 2023 – Agricultura (%)'] + '% do imóvel (2023)'
        info['Análise automática – SIGEF'] = car_prop.get('Georreferenciamento SIGEF', '')
    info['Análise automática – APP estimada'] = f"{app_ha:.2f} ha ({len(rios)} trecho(s) de rio e {len(nasc)} nascente(s) no entorno de 300 m)".replace('.', ',', 1)
    f['info'] = info
    resumo.append((f['id'], cod, len(rios), len(nasc), round(app_ha, 2), car_prop is not None))

for k, v in saida.items():
    json.dump({'type': 'FeatureCollection', 'features': v}, open(f'{OUT}/{k}.geojson', 'w'), ensure_ascii=False, separators=(',', ':'))

CAM = [
    {'id': 'an-app', 'nome': 'APP estimada (faixa legal)', 'arquivo': f'{OUT}/app.geojson', 'tipo': 'fill', 'cor': '#e53935', 'opacidade': 0.35, 'rotulo': False, 'campos': ['propriedade', 'Área (ha)', 'Critério']},
    {'id': 'an-rios', 'nome': 'Rios e córregos (FBDS)', 'arquivo': f'{OUT}/rios.geojson', 'tipo': 'line', 'cor': '#29b6f6', 'rotulo': False},
    {'id': 'an-nascentes', 'nome': 'Nascentes (FBDS)', 'arquivo': f'{OUT}/nascentes.geojson', 'tipo': 'circle', 'cor': '#00e5ff', 'rotulo': False, 'campos': ['propriedade']},
    {'id': 'an-massas', 'nome': "Represas e massas d'água", 'arquivo': f'{OUT}/massas.geojson', 'tipo': 'fill', 'cor': '#1e88e5', 'opacidade': 0.5, 'rotulo': False, 'campos': ['Tipo', 'Área (ha)']},
    {'id': 'an-sigef', 'oculta': True, 'nome': 'Parcelas certificadas (SIGEF)', 'arquivo': f'{OUT}/sigef.geojson', 'tipo': 'fill', 'cor': '#ab47bc', 'opacidade': 0.15, 'rotulo': False, 'campos': ['propriedade', 'Situação', 'Certificado em', 'Área (ha)']},
    {'id': 'an-vizinhos', 'oculta': True, 'nome': 'Imóveis vizinhos (CAR)', 'arquivo': f'{OUT}/vizinhos.geojson', 'tipo': 'fill', 'cor': '#bdbdbd', 'opacidade': 0.08, 'rotulo': False, 'campos': ['CAR', 'Área (ha)', 'Situação']},
    {'id': 'an-outorgas', 'nome': 'Outorgas de água no entorno (1 km)', 'arquivo': f'{OUT}/outorgas.geojson', 'tipo': 'circle', 'cor_por': 'grupo', 'rotulo': False,
     'cores': {'Captação superficial': '#0288d1', 'Poço (água subterrânea)': '#6a1b9a', 'Barragem / soleira': '#00897b', 'Lançamento de efluentes': '#8d6e63', 'Obras e intervenções em rios': '#f9a825'},
     'campos': ['Documento', 'Portaria / declaração', 'Situação', 'Finalidade', 'Corpo hídrico / aquífero', 'Vazão máxima (m³/h)', 'Vencimento', 'Distância da propriedade']},
    {'id': 'an-licencas', 'oculta': True, 'nome': 'Licenças ambientais no entorno (1 km)', 'arquivo': f'{OUT}/licencas.geojson', 'tipo': 'circle', 'cor_por': 'grupo', 'rotulo': False,
     'cores': {'Licença de Operação': '#2e7d32', 'Licença Simplificada': '#66bb6a', 'Dispensa de licenciamento': '#9e9d24', 'Licença Prévia / de Instalação': '#ffa000', 'Licença por Adesão e Compromisso': '#26a69a', 'Autorização Ambiental': '#5c6bc0'},
     'campos': ['Situação', 'Atividade', 'Nº do documento', 'Emissão', 'Validade', 'Protocolo', 'Distância da propriedade']},
    {'id': 'an-barragens', 'oculta': True, 'nome': 'Barragens cadastradas (SNISB)', 'arquivo': f'{OUT}/barragens.geojson', 'tipo': 'circle', 'cor': '#ff7043', 'rotulo': False,
     'campos': ['Categoria de risco', 'Dano potencial associado (DPA)', 'Uso principal', "Curso d'água", 'Altura (m)', 'Distância da propriedade']},
]
CAM = [c for c in CAM if saida[c['arquivo'].split('/')[-1][:-8]]]
cfg['camadas'] = [c for c in cfg.get('camadas', []) if not c['id'].startswith('an-')] + CAM
json.dump(cfg, open('data/fazendas.json', 'w'), ensure_ascii=False, indent=1)
for r in resumo: print('propriedade %s (mun %s): %d rios, %d nascentes, APP %.2f ha, CAR na análise: %s' % r)
print({k: len(v) for k, v in saida.items()})
