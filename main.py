import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import Browser, sync_playwright
import concurrent.futures
import re
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://www.fineschiweb.com.ar",
        "https://www.fineschiweb.com.ar/app"
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/autos")
def buscar_autos(
    marca: str = Query(None, description="Marca exacta"),
    modelo: str = Query(None, description="Modelo exacto"),
    fuentes: str = Query("todas", description="Fuentes: ml, autocosmos, carone, todas"),
    anio: str = Query(None),
    precio_min: str = Query(None),
    precio_max: str = Query(None),
    km_max: str = Query(None),
    estado: str = Query(None),
    provincia: str = Query(None),
):
    resultados = []

    # Logica de busqueda
    q_final = None

    if marca and modelo:
        q_final = f"{marca} {modelo}"
    elif marca:
        q_final = marca
    elif modelo:
        q_final = modelo

    # Scraping en paralelo usando ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        
        # Lanzar scrapers en paralelo según las fuentes solicitadas
        if fuentes in ["ml", "todas"] and q_final:
            futures.append(executor.submit(buscar_ml_mejorada, q_final))
        
        if fuentes in ["autocosmos", "todas"] and q_final:
            futures.append(executor.submit(buscar_autocosmos, q_final))
        
        if fuentes in ["carone", "todas"] and marca and modelo:
            futures.append(executor.submit(buscar_carone, marca, modelo))
        
        # Recopilar resultados conforme van completándose
        for future in concurrent.futures.as_completed(futures, timeout=180):
            try:
                resultados += future.result()
            except Exception as e:
                # Si un scraper falla, continúa con los otros
                print(f"Error en scraper: {e}")
                continue

    autos_filtrados = []
    for auto in resultados:
        if anio and auto.get("anio"):
            try:
                # Extraer solo los números del año del auto
                auto_anio = ''.join(filter(str.isdigit, str(auto["anio"])))
                if auto_anio and int(auto_anio) < int(anio):
                    continue
            except:
                pass
        if precio_min and auto.get("precio"):
            try:
                precio = int(str(auto["precio"]).replace(".", "").replace("$", "").replace(" ", ""))
                if precio < int(precio_min):
                    continue
            except:
                pass
        if precio_max and auto.get("precio"):
            try:
                precio = int(str(auto["precio"]).replace(".", "").replace("$", "").replace(" ", ""))
                if precio > int(precio_max):
                    continue
            except:
                pass
        if km_max and auto.get("km"):
            try:
                km = int(str(auto["km"]).replace(".", "").replace("km", "").replace("Km", "").replace(" ", ""))
                if km > int(km_max):
                    continue
            except:
                pass
        if estado and auto.get("estado") and estado.lower() not in auto["estado"].lower():
            continue
        if provincia and auto.get("ubicacion") and provincia.lower() not in auto["ubicacion"].lower():
            continue

        autos_filtrados.append(auto)

    return {"autos": autos_filtrados}

def buscar_ml(q):
    autos = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
        url = f"https://autos.mercadolibre.com.ar/{q.lower().replace(' ', '-')}/"
        page.goto(url)
        page.wait_for_selector('div.ui-search-result__wrapper', timeout=40000)
        items = page.query_selector_all('div.ui-search-result__wrapper')

        for item in items:
            # Titulo y Link
            a_tag = item.query_selector("a.poly-component__title")
            titulo = a_tag.inner_text().strip() if a_tag else ""
            link = a_tag.get_attribute("href") if a_tag else ""

            # Precio
            precio_tag = item.query_selector(".andes-money-amount__fraction")
            precio = precio_tag.inner_text().strip() if precio_tag else ""

            # Año y km
            atributos = item.query_selector_all(".poly-attributes_list li")
            anio = atributos[0].inner_text().strip() if len(atributos) > 0 else ""
            km = atributos[1].inner_text().strip() if len(atributos) > 1 else ""

            # Ubicacion
            ubicacion_tag = item.query_selector(".poly-component__location")
            ubicacion = ubicacion_tag.inner_text().strip() if ubicacion_tag else ""

            # Foto
            foto_tag = item.query_selector("img.poly-component__picture")
            foto = foto_tag.get_attribute("data-src") if foto_tag else ""

            if titulo and precio and link and foto:
                autos.append({
                    "fuente": "MecadoLibre",
                    "titulo": titulo,
                    "precio": precio,
                    "anio": anio,
                    "km": km,
                    "ubicacion": ubicacion,
                    "foto": foto,
                    "link": link
                })
        browser.close()
    return autos

def buscar_autocosmos(q):
    autos = []
    url = f"https://www.autocosmos.com.ar/auto/usado?q={q.lower().replace(' ', '-')}"
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.find_all("article", class_="listing-card")

    for item in items:
        # Link y Fotos
        a_tag = item.find("a", href=True)
        link = "https://www.autocosmos.com.ar" + a_tag["href"] if a_tag else ""
        img_tag = item.select_one("figure.listing-card__image img")
        foto = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
        
        # Titulo
        marca = item.select_one(".listing-card__brand")
        modelo = item.select_one(".listing-card__model")
        version = item.select_one(".listing-card__version")
        titulo = "".join([
            marca.text.strip() if marca else "",
            modelo.text.strip() if modelo else "",
            version.text.strip() if version else ""
        ]).strip()

        # Año y Km
        anio = item.select_one(".listing-card__year")
        km = item.select_one(".listing-card__km")

        # Ubicacion 
        ciudad = item.select_one(".listing-card__city")
        provincia = item.select_one(".listing-card__province")
        ubicacion = "".join([
            ciudad.text.strip() if ciudad else "",
            provincia.text.strip() if provincia else ""
        ]).replace("|", "").strip()

        # Precio
        precio = item.select_one(".listing-card__price-value")

        # Diccionario
        if titulo and precio and link and foto:
            autos.append({
                "fuente": "Autocosmos",
                "titulo": titulo,
                "precio": precio.text.strip() if precio else "",
                "anio": anio.text.strip() if anio else "",
                "km": km.text.strip() if km else "",
                "ubicacion": ubicacion,
                "foto": foto,
                "link": link
            })
    
    return autos

def buscar_carone(marca, modelo):
    autos = []
    url = f"https://www.carone.com.ar/categoria-producto/usados/marca-{marca.lower()}/modelo-{modelo.lower()}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    response = requests.get(url,headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("ul.products li.product")

    for item in items:
        # Titulo
        marca_tag = item.select_one(".box-bottom-title h2.p-marca")
        version_tag = item.select_one(".box-bottom p.p-modelo")
        titulo = (marca_tag.text.strip() if marca_tag else "") + " " + (version_tag.text.strip() if version_tag else "")

        # Precio
        precio_tag = item.select_one(".box-bottom .p-price ins .woocommerce-Price-amount")
        if not precio_tag:
            precio_tag = item.select_one(".box-bottom .p-price .woocommerce-Price-amount")
        precio = precio_tag.text.strip() if precio_tag else ""

        # Año y Km
        anio_km = item.select_one(".box-bottom .p-cuotas-2")
        anio = km = ""
        if anio_km:
            partes = anio_km.text.strip().split(" - ")
            if len(partes) == 2:
                anio = partes[0].strip()
                km = partes[1].replace("Km", "").strip()

        # Foto
        img = item.select_one(".box-top img")
        foto = img["data-src"] if img and img.has_attr("data-src") else ""

        # Link
        a_tag = item.select_one(".box-bottom a")
        link = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""

        # Diccionario
        if titulo and precio and link and foto:
            autos.append ({
                "fuente": "CarOne",
                "titulo": titulo,
                "precio": precio,
                "anio": anio,
                "km": km,
                "ubicacion": "",
                "foto": foto,
                "link": link
            })

    return autos

def inspeccionar_ML(url_pagina: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print(f"🔍 Navegando a: {url_pagina}")
            page.goto(url_pagina, timeout=60000)
            
            # Esperar a que carguen los resultados
            page.wait_for_selector('ol.ui-search-layout', timeout=10000)
            
            # Tomar el primer resultado
            primer_auto = page.query_selector('li.ui-search-layout__item')
            
            if not primer_auto:
                print("❌ No se encontraron resultados de vehículos")
                return
                
            # Buscar el enlace en la estructura correcta
            link = primer_auto.query_selector('a.poly-component__title')
            
            if not link:
                print("❌ No se pudo encontrar el enlace al detalle")
                return
                
            detalle_url = link.get_attribute('href')
            print(f"\n🔗 Enlace al detalle: {detalle_url}")
            
            # Navegar a la página de detalle
            page.goto(detalle_url, timeout=60000)
            
            # Extraer información específica
            print("\n🔍 Buscando información detallada...")
            
            # 1. Fecha de publicación
            fecha = page.query_selector('span.ui-pdp-subtitle')
            print(f"📅 Fecha: {fecha.inner_text() if fecha else 'No disponible'}")
            
            # 2. Estado (Nuevo/Usado)
            estado = page.query_selector('.ui-pdp-subtitle + span')
            print(f"🏷️ Estado: {estado.inner_text() if estado else 'No disponible'}")
            
            # 3. Descripción
            descripcion = page.query_selector('.ui-pdp-description__content')
            print(f"\n📝 Descripción:")
            print(descripcion.inner_text()[:200] + "..." if descripcion else "No disponible")
            
            # 4. Contacto
            contacto = page.query_selector('.ui-pdp-seller__link-trigger')
            print(f"\n📞 Contacto: {contacto.inner_text() if contacto else 'No disponible'}")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            
        finally:
            input("\nPresiona Enter para cerrar el navegador...")
            browser.close()


def buscar_ml_mejorada(q):
    """
    Scraper mejorado para MercadoLibre con:
    - Resistencia a bloqueos
    - Extracción de datos completos
    - Manejo de CAPTCHAs
    - Reintentos automáticos
    """
    from random import uniform, randint
    from time import sleep
    import re
    
    autos = []
    max_retries = 3
    
    with sync_playwright() as p:
        for attempt in range(max_retries):
            try:
                # 1. Configuración stealth del navegador
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        f'--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{randint(110, 120)}.0.{randint(0, 9999)}.0 Safari/537.36',
                        '--window-size=1366,768',
                        '--start-maximized'
                    ],
                    slow_mo=randint(100, 500)
                )
                
                context = browser.new_context(
                    viewport={'width': 1366, 'height': 768},
                    locale='es-AR',
                    timezone_id='America/Argentina/Buenos_Aires',
                    java_script_enabled=True
                )
                
                page = context.new_page()
                
                # 2. Navegación inteligente
                url = f"https://autos.mercadolibre.com.ar/{q.lower().replace(' ', '-')}/_NoIndex_True?cache_bust={randint(1, 10000)}"
                print(f"\n🔍 Intento {attempt + 1}/{max_retries} - URL: {url}")
                
                # Navegar como humano
                page.goto(url, timeout=120000, wait_until='networkidle')
                sleep(uniform(1.5, 3.5))
                
                # 3. Verificar CAPTCHA
                if page.query_selector('#captchacharacters'):
                    print("⚠️ CAPTCHA detectado - Requiere intervención manual")
                    print("Por favor resuelve el CAPTCHA en la ventana del navegador...")
                    input("Presiona Enter después de resolver el CAPTCHA...")
                
                # 4. Detección de resultados con múltiples selectores
                items = []
                selectors = [
                    'div.ui-search-result__wrapper',
                    'li.ui-search-layout__item',
                    'section.ui-search-results',
                    'div.andes-card'
                ]
                
                for selector in selectors:
                    try:
                        page.wait_for_selector(selector, state='attached', timeout=30000)
                        items = page.query_selector_all(selector)
                        if items:
                            print(f"Encontrados {len(items)} resultados con selector: {selector}")
                            break
                    except:
                        continue
                
                if not items:
                    print("No se encontraron resultados")
                    if attempt < max_retries - 1:
                        sleep(uniform(5, 10))
                        continue
                    return []
                
                # 5. Procesar resultados (máx 15)
                for idx, item in enumerate(items[:15]):
                    try:
                        sleep(uniform(0.5, 2))  # Comportamiento humano
                        
                        # Extraer datos básicos
                        data = {
                            'titulo': get_text(item, "a.ui-search-result__content, a.poly-component__title"),
                            'link': get_attribute(item, "a.ui-search-result__content, a.poly-component__title", "href"),
                            'precio': clean_price(get_text(item, ".andes-money-amount__fraction, .price-tag-fraction")),
                            'anio': get_text_from_list(item, ".ui-search-card-attributes__attribute, .poly-attributes_list li", 0),
                            'km': clean_km(get_text_from_list(item, ".ui-search-card-attributes__attribute, .poly-attributes_list li", 1)),
                            'ubicacion': get_text(item, ".ui-search-item__location, .poly-component__location"),
                            'foto': get_image_src(item)
                        }
                        
                        # Validar datos mínimos
                        if not all([data['titulo'], data['precio'], data['link']]):
                            continue
                            
                        # Extraer detalles adicionales
                        if data['link']:
                            data.update(get_additional_details(context, data['link']))
                        
                        autos.append({
                            "fuente": "MercadoLibre",
                            **data
                        })
                        
                        print(f"[{idx + 1}/{len(items[:15])}] Procesado: {data['titulo']}")
                        
                    except Exception as e:
                        print(f"Error procesando item: {str(e)}")
                        continue
                
                # Si llegamos aquí, fue exitoso
                break
                
            except Exception as e:
                print(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt == max_retries - 1:
                    return []
                sleep(uniform(5, 10))
                
            finally:
                try:
                    browser.close()
                except:
                    pass
    
    return autos

# Funciones auxiliares
def get_text(element, selector):
    node = element.query_selector(selector)
    return node.inner_text().strip() if node else ""

def get_attribute(element, selector, attr):
    node = element.query_selector(selector)
    return node.get_attribute(attr) if node else ""

def get_text_from_list(element, selector, index):
    nodes = element.query_selector_all(selector)
    return nodes[index].inner_text().strip() if len(nodes) > index else ""

def get_image_src(element):
    for selector in ["img.ui-search-result-image__element", "img.poly-component__picture"]:
        img = element.query_selector(selector)
        if img:
            return img.get_attribute("data-src") or img.get_attribute("src")
    return ""

def clean_price(price):
    return re.sub(r'[^\d]', '', price) if price else ""

def clean_km(km):
    return re.sub(r'[^\d]', '', km) if km else ""

def get_additional_details(context, url):
    details = {
        'antiguedad': "No disponible",
        'descripcion': "No disponible"
    }
    
    try:
        page = context.new_page()
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        
        # Fecha de publicación
        fecha_elem = page.query_selector('span.ui-pdp-subtitle')
        if fecha_elem:
            details['antiguedad'] = re.sub(r'Publicado\s*', '', fecha_elem.inner_text().strip())
        
        # Descripción
        desc_elem = page.query_selector('.ui-pdp-description__content')
        if desc_elem:
            details['descripcion'] = desc_elem.inner_text().strip()
        
        page.close()
    except Exception as e:
        print(f"Error en detalles: {str(e)}")
    
    return details
