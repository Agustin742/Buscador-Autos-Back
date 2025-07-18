import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://buscadorautosarg.netlify.app"],
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
    combustible: str = Query(None),
    transmision: str = Query(None),
    color: str = Query(None),
    puertas: str = Query(None),
    dueno: str = Query(None)
):
    resultados = []

    # Logica de bsuqueda
    q_final = None

    if marca and modelo:
        q_final = f"{marca} {modelo}"
    
    elif marca:
        q_final = marca

    elif modelo:
        q_final = modelo

    if fuentes in ["ml", "todas"]:
        if q_final:
            resultados += buscar_ml(q_final)

    if fuentes in ["autocosmos", "todas"]:
        if q_final:
            resultados += buscar_autocosmos(q_final)

    if fuentes in ["carone", "todas"]:
        if marca and modelo:
            resultados += buscar_carone(marca, modelo)

    autos_filtrados = []
    for auto in resultados:
        if anio and auto.get("anio") and anio not in auto["anio"]:
            continue
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

