"""Grava o vídeo tutorial do mapa das granjas (Playwright), com tempos ajustados à narração.
Uso: gravar_tutorial.py URL_BASE PASTA_SAIDA [duracoes.json] [libs_locais]
Gera PASTA_SAIDA/*.webm e PASTA_SAIDA/marcas.json (instante de início de cada fala, em segundos desde o início da gravação)."""
import sys, os, base64, glob, json, time
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
DUR = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else {}
LIBS = sys.argv[4] if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
CSS = """
#tut-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:880px;background:rgba(10,30,20,.88);color:#fff;
 font:600 21px/1.35 'Segoe UI',Arial,sans-serif;padding:14px 22px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.35);text-align:center;transition:opacity .35s}
#tut-cap small{display:block;font-weight:400;font-size:15px;opacity:.85;margin-top:4px}
#tut-step{position:fixed;top:14px;right:16px;z-index:99999;background:#2e7d32;color:#fff;font:700 14px Arial;padding:6px 12px;border-radius:999px}
.tut-foco{outline:4px solid #ffca28 !important;outline-offset:3px;border-radius:8px;transition:outline .2s}
#tut-cursor{position:fixed;z-index:100000;width:22px;height:22px;border-radius:50%;background:rgba(255,202,40,.85);border:2px solid #fff;pointer-events:none;
 transform:translate(-50%,-50%);transition:left .6s ease,top .6s ease;left:-50px;top:-50px;box-shadow:0 0 0 6px rgba(255,202,40,.25)}
#tut-intro{position:fixed;inset:0;z-index:100001;background:linear-gradient(135deg,#0b3d2e,#1b5e20);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Segoe UI',Arial;text-align:center;transition:opacity .8s}
#tut-intro h1{font-size:44px;margin:0 0 10px} #tut-intro p{font-size:22px;margin:4px;opacity:.9}
"""
marcas = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'])
    ctx = b.new_context(viewport={'width': W, 'height': H}, record_video_dir=OUT, record_video_size={'width': W, 'height': H}, locale='pt-BR')
    pg = ctx.new_page(); T0 = time.time()
    if LIBS:
        pg.route('**/mapbox-gl.js', lambda r: r.fulfill(path=LIBS + '/mapbox-gl/dist/mapbox-gl.js', content_type='application/javascript'))
        pg.route('**/mapbox-gl.css', lambda r: r.fulfill(path=LIBS + '/mapbox-gl/dist/mapbox-gl.css', content_type='text/css'))
        pg.route('**/turf.min.js', lambda r: r.fulfill(path=LIBS + '/@turf/turf/turf.min.js', content_type='application/javascript'))
    prev = {}
    import pymupdf
    for f in glob.glob('docs/*/*.pdf'):
        d = pymupdf.open(f); imgs = ''.join(f'<img src="data:image/jpeg;base64,{base64.b64encode(x.get_pixmap(dpi=80).tobytes("jpeg")).decode()}">' for x in list(d)[:2])
        prev[f.replace('\\', '/')] = f'<html><body style="margin:0;background:#525659;text-align:center">{imgs}<style>img{{width:92%;margin:14px auto;display:block;box-shadow:0 2px 10px #000}}</style></body></html>'
    def doc_route(route):
        k = next((k for k in prev if route.request.url.endswith(k)), None)
        if k and route.request.resource_type in ('document', 'iframe', 'sub_frame'): route.fulfill(body=prev[k], content_type='text/html')
        else: route.continue_()
    pg.route('**/docs/**', doc_route)
    pg.goto(BASE + '/index.html')
    pg.add_style_tag(content=CSS)
    pg.evaluate("""() => { const i=document.createElement('div'); i.id='tut-intro'; i.innerHTML='<h1>Frangos Pioneiro – Granjas integradas</h1><p>Como usar o mapa interativo</p><p style="font-size:17px;margin-top:22px">CS Consultoria Ambiental</p>'; document.body.appendChild(i);
        const c=document.createElement('div'); c.id='tut-cap'; c.style.opacity=0; document.body.appendChild(c);
        const s=document.createElement('div'); s.id='tut-step'; s.style.display='none'; document.body.appendChild(s);
        const k=document.createElement('div'); k.id='tut-cursor'; document.body.appendChild(k); }""")
    pg.wait_for_timeout(2500)
    def fala(chave, minimo=3.0):
        """marca o início da fala e devolve um 'relógio' para esperar o fim dela"""
        marcas[chave] = round(time.time() - T0, 2)
        fim = time.time() + max(DUR.get(chave, minimo) + 0.6, minimo)
        return lambda extra=0: pg.wait_for_timeout(max(0, int((fim + extra - time.time()) * 1000)))
    def cap(txt, sub='', passo=''):
        pg.evaluate("([t,s,p])=>{const c=document.getElementById('tut-cap'); c.style.opacity=0; setTimeout(()=>{c.innerHTML=t+(s?'<small>'+s+'</small>':''); c.style.opacity=1},300);"
                    "const e=document.getElementById('tut-step'); e.style.display=p?'block':'none'; e.textContent=p;}", [txt, sub, passo])
    def foco(sel, on=True):
        pg.evaluate("([s,o])=>{document.querySelectorAll('.tut-foco').forEach(e=>e.classList.remove('tut-foco')); const e=document.querySelector(s); if(e&&o){e.classList.add('tut-foco'); e.scrollIntoView({block:'center',behavior:'smooth'});}}", [sel, on])
    def cursor_em(xy):
        pg.evaluate("([x,y])=>{const k=document.getElementById('tut-cursor'); k.style.left=x+'px'; k.style.top=y+'px'}", xy); pg.wait_for_timeout(700)
    def clicar(sel):
        el = pg.locator(sel).first; el.scroll_into_view_if_needed(); pg.wait_for_timeout(400)
        bb = el.bounding_box(); cursor_em([bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2]); el.click()
    def tela_mapa(lon, lat):
        return pg.evaluate("([a,b])=>{const p=map.project([a,b]); const r=document.getElementById('map').getBoundingClientRect(); return [p.x+r.x,p.y+r.y]}", [lon, lat])
    # abertura (a fala começa com o título na tela; o mapa carrega por trás)
    esp = fala('intro', 8); esp()
    pg.evaluate("()=>{const i=document.getElementById('tut-intro'); i.style.opacity=0; setTimeout(()=>i.remove(),900)}"); pg.wait_for_timeout(900)
    esp = fala('geral'); cap('Visão geral: todas as granjas integradas no mapa', 'Cada contorno é o perímetro oficial do CAR, com imagem de satélite atual', '1 / 8'); esp()
    foco('.kpis'); esp = fala('resumo'); cap('Resumo do projeto', 'Granjas mapeadas, área total e aves alojadas por lote, com o andamento geral das adequações', '2 / 8'); esp()
    foco('#cardPendencias'); esp = fala('pendencias'); cap('Pendências por granja', 'O que falta regularizar em cada produtor – quem tem mais pendências aparece primeiro', '3 / 8'); esp()
    esp = fala('clique_produtor'); cap('Clique no nome do produtor para ir até a granja', 'O mapa aproxima e abre a ficha completa', '3 / 8'); clicar('#cardPendencias .pend-titulo'); esp(1)
    foco('.farm.open .pend-box'); esp = fala('ficha'); cap('Ficha da granja', 'Em vermelho, o que está pendente; abaixo, licença, água, CAR, matrícula e todas as adequações', '4 / 8')
    pg.wait_for_timeout(4500); foco('.farm.open dl'); esp()
    if pg.query_selector('.farm.open .doc-btn'):
        foco('.farm.open .doc-btn'); esp = fala('documentos'); cap('Documentos da granja', 'Recibo do CAR, licença e dispensa de outorga – dados pessoais tarjados', '5 / 8')
        pg.wait_for_timeout(2500); clicar('.farm.open .doc-btn'); esp()
        esp = fala('documento_aberto'); cap('O documento abre aqui mesmo', 'Também é possível abrir em nova aba ou baixar o PDF', '5 / 8'); esp(0.5)
        clicar('#docClose'); pg.wait_for_timeout(800)
    foco('x', False)
    f = pg.evaluate("()=>turf.pointOnFeature(geojsons['G03']).geometry.coordinates")
    pg.evaluate("c=>map.flyTo({center:c,zoom:15.6,duration:2500})", f)
    esp = fala('vizinhas'); cap('Granjas vizinhas: Fazenda Santa Maria – Lotes 01 A e 01 C', 'Mario Lucio Pozzan e Mauro Lucas Pozzan', '6 / 8'); esp(0.8)
    esp = fala('contorno'); cap('Clique no contorno para ver o resumo da granja', 'Andamento, pendências em destaque e documentos', '6 / 8')
    xy = tela_mapa(*f); cursor_em(xy); pg.mouse.click(*xy); esp(1)
    pg.evaluate("()=>document.querySelectorAll('.mapboxgl-popup').forEach(p=>p.remove())")
    pt = pg.evaluate("()=>fazendas.find(x=>x.id==='G03').pontos[2].coord")
    esp = fala('pontos'); cap('Pontos brancos: aviários e captações de água', 'Coordenadas tiradas das licenças e das dispensas de outorga', '6 / 8')
    xy = tela_mapa(*pt); cursor_em(xy); pg.mouse.click(*xy); esp(1)
    pg.evaluate("()=>document.querySelectorAll('.mapboxgl-popup').forEach(p=>p.remove())")
    clicar('#centerMap'); pg.wait_for_timeout(1200)
    foco('#cardPrazos'); esp = fala('vencimentos'); cap('Próximos vencimentos', 'Licenças, dispensas de outorga e condicionantes com prazo – os vencidos aparecem em vermelho', '7 / 8'); esp(1)
    foco('#cardCamadas'); esp = fala('camadas'); cap('Camadas e tipo de mapa', 'Ligue as bacias hidrográficas e alterne entre satélite atual, Mapbox e mapa de ruas', '8 / 8')
    pg.wait_for_timeout(1500)
    if pg.query_selector('#camadasOpcionais .camada-row[data-tipo=opc]'):
        clicar('#camadasOpcionais .camada-row[data-tipo=opc]'); pg.wait_for_timeout(2500); clicar('#camadasOpcionais .camada-row[data-tipo=opc]'); pg.wait_for_timeout(500)
    clicar('.segmented button[data-style="mapa"]'); pg.wait_for_timeout(2500)
    clicar('.segmented button[data-style="esri"]'); esp(1)
    foco('x', False)
    esp = fala('fim', 5); cap('Frangos Pioneiro – Granjas integradas', 'CS Consultoria Ambiental · Projeto Pioneiros', ''); esp(1.5)
    ctx.close(); b.close()
json.dump(marcas, open(os.path.join(OUT, 'marcas.json'), 'w'), indent=1)
print('ok', glob.glob(OUT + '/*.webm'), marcas)
