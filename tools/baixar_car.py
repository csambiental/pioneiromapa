"""Baixa o perímetro dos imóveis do CAR (SICAR, WFS público) para os códigos em data/car_codigos.json.
Saída: data/propriedades/<id>.geojson e data/_diag/car.txt"""
import json, urllib.request, urllib.parse, time, os, re
codigos = json.load(open('data/car_codigos.json'))
os.makedirs('data/propriedades', exist_ok=True)
FONTES = [
    ('https://geoserver.car.gov.br/geoserver/sicar/wfs', 'sicar:sicar_imoveis_{uf}', 'cod_imovel'),
    ('https://geoserver.car.gov.br/geoserver/wfs', 'sicar:sicar_imoveis_{uf}', 'cod_imovel'),
]
def get(url, tent=4):
    for t in range(tent):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()
        except Exception as e:
            print('   tentativa', t + 1, e); time.sleep(5 * (t + 1))
    return None
for id_, cod in codigos.items():
    variantes = {cod, cod.replace('.', ''), re.sub(r'^(\w\w-\d{7}-)(\w{4})(\w{4})(\w{4})(\w{4})(\w{4})(\w{4})(\w{4})(\w{4})$', r'\1\2.\3.\4.\5.\6.\7.\8.\9', cod.replace('.', ''))}
    ok = False
    for base, layer, campo in FONTES:
        for v in variantes:
            q = {'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature', 'typeName': layer.format(uf=cod[:2].lower()),
                 'outputFormat': 'application/json', 'srsName': 'EPSG:4326', 'CQL_FILTER': f"{campo}='{v}'"}
            r = get(base + '?' + urllib.parse.urlencode(q))
            if not r: continue
            try: g = json.loads(r)
            except Exception: print(id_, 'resposta não-JSON', r[:300]); continue
            n = len(g.get('features', []))
            print(id_, v, base, n, (g['features'][0]['properties'] if n else ''))
            if n:
                json.dump(g, open(f'data/propriedades/{id_}.geojson', 'w'), ensure_ascii=False); ok = True; break
        if ok: break
    if not ok: print(id_, 'NÃO ENCONTRADO', cod)
