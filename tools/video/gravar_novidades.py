"""Grava o vídeo das novidades (análise automática por granja), usando a Chácara Vilela (G05, Joaquim Távora) como exemplo.
Uso: gravar_novidades.py URL_BASE PASTA_SAIDA duracoes.json
Gera PASTA_SAIDA/*.webm e PASTA_SAIDA/marcas.json."""
import sys, os, glob, json, time
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
DUR = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else {}
RAIOX = 'https://csambiental.github.io/territoriogeo/analise/?m=4112801&car=PR-4112801-9909EF3F019B46418EE22313A6238908'
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
CSS = """
#tut-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:900px;background:rgba(10,30,20,.9);color:#fff;
 font:600 21px/1.35 'Segoe UI',Arial,sans-serif;padding:14px 22px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.35);text-align:center;transition:opacity .35s}
#tut-cap small{display:block;font-weight:400;font-size:15px;opacity:.88;margin-top:4px}
#tut-step{position:fixed;top:14px;right:16px;z-index:99999;background:#2e7d32;color:#fff;font:700 14px Arial;padding:6px 12px;border-radius:999px}
#tut-novo{position:fixed;top:14px;left:50%;transform:translateX(-50%);z-index:99999;background:#ffca28;color:#1b1b1b;font:800 13px Arial;letter-spacing:.06em;padding:5px 12px;border-radius:999px;display:none}
.tut-foco{outline:4px solid #ffca28 !important;outline-offset:3px;border-radius:6px;background:rgba(255,202,40,.12) !important;transition:outline .2s}
#tut-cursor{position:fixed;z-index:100000;width:22px;height:22px;border-radius:50%;background:rgba(255,202,40,.85);border:2px solid #fff;pointer-events:none;
 transform:translate(-50%,-50%);transition:left .6s ease,top .6s ease;left:-50px;top:-50px;box-shadow:0 0 0 6px rgba(255,202,40,.25)}
#tut-intro{position:fixed;inset:0;z-index:100001;background:linear-gradient(135deg,#0b3d2e,#1b5e20);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Segoe UI',Arial;text-align:center;transition:opacity .8s}
#tut-intro h1{font-size:42px;margin:0 0 10px} #tut-intro p{font-size:22px;margin:4px;opacity:.92} #tut-intro .tag{background:#ffca28;color:#1b1b1b;font-weight:800;font-size:15px;padding:5px 14px;border-radius:999px;margin-bottom:18px;letter-spacing:.08em}
"""
marcas = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl'])
    ctx = b.new_context(viewport={'width': W, 'height': H}, record_video_dir=OUT, record_video_size={'width': W, 'height': H}, locale='pt-BR')
    pg = ctx.new_page(); T0 = time.time()

    def preparar(intro=None):
        pg.add_style_tag(content=CSS)
        pg.evaluate("""(intro) => { if (intro) { const i=document.createElement('div'); i.id='tut-intro'; i.innerHTML=intro; document.body.appendChild(i); }
            const c=document.createElement('div'); c.id='tut-cap'; c.style.opacity=0; document.body.appendChild(c);
            const s=document.createElement('div'); s.id='tut-step'; s.style.display='none'; document.body.appendChild(s);
            const n=document.createElement('div'); n.id='tut-novo'; n.textContent='NOVO'; document.body.appendChild(n);
            const k=document.createElement('div'); k.id='tut-cursor'; document.body.appendChild(k); }""", intro)

    def fala(chave, minimo=3.0):
        marcas[chave] = round(time.time() - T0, 2)
        fim = time.time() + max(DUR.get(chave, minimo) + 0.6, minimo)
        return lambda extra=0: pg.wait_for_timeout(max(0, int((fim + extra - time.time()) * 1000)))

    def cap(txt, sub='', passo='', novo=False):
        pg.evaluate("([t,s,p,n])=>{const c=document.getElementById('tut-cap'); c.style.opacity=0; setTimeout(()=>{c.innerHTML=t+(s?'<small>'+s+'</small>':''); c.style.opacity=1},300);"
                    "const e=document.getElementById('tut-step'); e.style.display=p?'block':'none'; e.textContent=p; document.getElementById('tut-novo').style.display=n?'block':'none';}", [txt, sub, passo, novo])

    def foco(sel, on=True):
        pg.evaluate("([s,o])=>{document.querySelectorAll('.tut-foco').forEach(e=>e.classList.remove('tut-foco')); if(!o) return; const e=document.querySelector(s); if(e){e.classList.add('tut-foco'); e.scrollIntoView({block:'center',behavior:'smooth'});}}", [sel, on])

    def foco_texto(sel, texto):
        """destaca os elementos 'sel' cujo texto contém 'texto' (e o elemento seguinte, para pares dt/dd)"""
        pg.evaluate("""([s,t])=>{document.querySelectorAll('.tut-foco').forEach(e=>e.classList.remove('tut-foco'));
            const els=[...document.querySelectorAll(s)].filter(e=>e.textContent.includes(t));
            els.forEach(e=>{e.classList.add('tut-foco'); if(e.nextElementSibling && e.tagName==='DT') e.nextElementSibling.classList.add('tut-foco');});
            if(els[0]) els[0].scrollIntoView({block:'center',behavior:'smooth'});}""", [sel, texto])

    def cursor_em(xy):
        pg.evaluate("([x,y])=>{const k=document.getElementById('tut-cursor'); if(!k) return; k.style.left=x+'px'; k.style.top=y+'px'}", xy); pg.wait_for_timeout(700)

    def clicar(sel, texto=None):
        el = (pg.locator(sel, has_text=texto) if texto else pg.locator(sel)).first
        el.scroll_into_view_if_needed(); pg.wait_for_timeout(400)
        bb = el.bounding_box(); cursor_em([bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2]); el.click()

    def tela_mapa(lon, lat):
        return pg.evaluate("([a,b])=>{const p=map.project([a,b]); const r=document.getElementById('map').getBoundingClientRect(); return [p.x+r.x,p.y+r.y]}", [lon, lat])

    def fechar_popups():
        pg.evaluate("()=>document.querySelectorAll('.mapboxgl-popup').forEach(p=>p.remove())")

    # ---------- abertura ----------
    pg.goto(BASE + '/index.html')
    preparar('<div class="tag">NOVIDADES</div><h1>Frangos Pioneiro – Granjas integradas</h1><p>Análise ambiental automática de cada granja</p><p style="font-size:17px;margin-top:22px">CS Consultoria Ambiental · Projeto Pioneiros</p>')
    pg.wait_for_timeout(2500)
    esp = fala('intro', 9)
    pg.wait_for_function("()=>typeof fazendas!=='undefined' && fazendas.length && map.loaded()", timeout=60000); esp()
    pg.evaluate("()=>{const i=document.getElementById('tut-intro'); i.style.opacity=0; setTimeout(()=>i.remove(),900)}"); pg.wait_for_timeout(900)

    # ---------- granja modelo ----------
    esp = fala('granja'); cap('Exemplo: Chácara Vilela – Joaquim Távora', 'Produtor Reginaldo Vilela · clique no nome para ir até a granja', '1 / 6')
    pg.wait_for_timeout(1800)
    clicar('#cardPendencias .pend-titulo[data-id="G05"]') if pg.query_selector('#cardPendencias .pend-titulo[data-id="G05"]') else pg.evaluate("()=>selecionarFazenda('G05', true)")
    esp(1)
    foco('.farm.open .pend-box'); esp = fala('ficha'); cap('Ficha da granja', 'Pendências, licença, água, CAR e documentos', '2 / 6'); pg.wait_for_timeout(3500); foco('.farm.open dl'); esp()
    foco_texto('.farm.open dt', 'Análise automática'); esp = fala('analise')
    cap('Análise automática da granja', 'Vegetação nativa, agricultura, SIGEF e APP estimada – calculadas pela CS', '2 / 6', True); esp(0.5)
    foco('x', False)

    # ---------- camadas no mapa ----------
    c5 = pg.evaluate("()=>turf.centroid(geojsons['G05']).geometry.coordinates")
    pg.evaluate("c=>map.flyTo({center:c,zoom:15.8,duration:2500})", c5)
    esp = fala('app'); cap('APP estimada (em vermelho)', 'Rios e nascentes da FBDS com as faixas do Código Florestal', '3 / 6', True); esp(0.5)
    pg.evaluate("c=>map.flyTo({center:c,zoom:15.0,duration:2000})", c5)
    esp = fala('rios'); cap('Rios, córregos e nascentes no entorno', 'Raio de 300 m da granja', '3 / 6', True); esp()
    pg.evaluate("c=>map.flyTo({center:c,zoom:13.9,duration:2000})", c5); pg.wait_for_timeout(2300)
    esp = fala('outorgas'); cap('Outorgas de água no entorno de 1 km', 'Clique no ponto: uso, vazão, validade e distância até a granja', '4 / 6', True)
    pt = pg.evaluate("""()=>{const fs=(camadasData['an-outorgas']||{features:[]}).features.filter(f=>f.properties.id==='G05');
        fs.sort((a,b)=>parseFloat(a.properties['Distância da propriedade'])-parseFloat(b.properties['Distância da propriedade'])); return fs.length?fs[0].geometry.coordinates:null}""")
    pg.wait_for_timeout(1500)
    if pt:
        xy = tela_mapa(*pt); cursor_em(xy); pg.mouse.click(*xy)
    esp(1.5); fechar_popups()
    foco('#cardCamadas'); esp = fala('licencas'); cap('Ligue as licenças ambientais e os imóveis vizinhos do CAR', 'Contexto ambiental da vizinhança', '4 / 6', True)
    pg.wait_for_timeout(1500)
    for cid in ('an-licencas', 'an-vizinhos'):
        if pg.query_selector(f'.camada-row[data-id="{cid}"]'): clicar(f'.camada-row[data-id="{cid}"]'); pg.wait_for_timeout(1300)
    esp(1)
    for cid in ('an-licencas', 'an-vizinhos'):
        if pg.query_selector(f'.camada-row[data-id="{cid}"].ativo'): pg.click(f'.camada-row[data-id="{cid}"]')
    foco('x', False)

    # ---------- Raio-X ----------
    pg.evaluate("()=>selecionarFazenda('G05', false)"); pg.wait_for_timeout(800)
    esp = fala('raiox_botao'); cap('Raio-X automático do imóvel', 'Botão na ficha de cada granja', '5 / 6', True)
    foco_texto('.farm.open .doc-btn', 'Raio-X'); esp(0.8)
    pg.goto(RAIOX)
    preparar()
    pg.wait_for_function("()=>document.getElementById('raioxDialog')?.open && document.querySelector('#raioxCorpo .rx-flags, #raioxCorpo .itr-box')", timeout=90000)
    pg.wait_for_timeout(1500)
    esp = fala('raiox'); cap('Raio-X: o imóvel cruzado com todas as camadas ambientais', 'Uso do solo, relevo, água, licenças, alertas, embargos – pendências e adequações', '5 / 6', True)
    for _ in range(6):
        pg.evaluate("()=>document.getElementById('raioxCorpo').scrollBy({top:260,behavior:'smooth'})"); pg.wait_for_timeout(1700)
    esp()
    esp = fala('itr'); cap('Prévia do ITR por satélite e relatório em PDF', 'Pronto para enviar ao produtor', '5 / 6', True)
    pg.evaluate("()=>{const b=document.querySelector('#raioxCorpo .itr-box'); if(b) b.scrollIntoView({block:'start',behavior:'smooth'});}"); pg.wait_for_timeout(3000)
    pg.evaluate("()=>document.getElementById('raioxCorpo').scrollBy({top:300,behavior:'smooth'})"); pg.wait_for_timeout(1500)
    foco('#raioxPdf'); esp(0.8)

    # ---------- volta ao mapa ----------
    pg.goto(BASE + '/index.html')
    preparar()
    pg.wait_for_function("()=>typeof fazendas!=='undefined' && fazendas.length && map.loaded()", timeout=60000); pg.wait_for_timeout(1500)
    esp = fala('volta'); cap('Disponível para todas as granjas do projeto', 'Joaquim Távora, Ibaiti e Wenceslau Braz', '6 / 6'); esp(1)
    esp = fala('fim', 5); cap('Frangos Pioneiro – Granjas integradas', 'CS Consultoria Ambiental · Projeto Pioneiros', ''); esp(1.5)
    ctx.close(); b.close()
json.dump(marcas, open(os.path.join(OUT, 'marcas.json'), 'w'), indent=1)
print('ok', glob.glob(OUT + '/*.webm'), marcas)
