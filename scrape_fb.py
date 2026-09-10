import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


# =========================================================
# NORMALIZAR URL
# =========================================================

def normalizar_url(href):
    if not href:
        return None

    if href.startswith("/"):
        href = urljoin("https://www.facebook.com", href)

    patrones = [
        "/posts/",
        "/photos/",
        "/videos/",
        "/reel/",
        "/reels/",
        "story_fbid="
    ]

    if not any(p in href for p in patrones):
        return None

    return href


# =========================================================
# ELEGIR MEJOR URL DENTRO DEL ARTÍCULO
# =========================================================

def elegir_url_articulo(urls):
    if not urls:
        return None

    # Reel
    for url in urls:
        if "/reel/" in url or "/reels/" in url:
            return url.split("?")[0]

    # Post normal
    for url in urls:
        if "/posts/" in url:
            return url.split("?")[0]

    # Video
    for url in urls:
        if "/videos/" in url:
            return url.split("?")[0]

    # story_fbid
    for url in urls:
        if "story_fbid=" in url:
            return url

    # Foto como último recurso
    for url in urls:
        if "/photos/" in url:
            return url

    return urls[0]


# =========================================================
# DETECTAR FIJADO
# =========================================================

async def esta_fijada(articulo):
    try:
        texto = (await articulo.inner_text()).lower()

        palabras = [
            "publicación fijada",
            "publicacion fijada",
            "pinned post"
        ]

        return any(x in texto for x in palabras)

    except:
        return False


# =========================================================
# TIMESTAMP
# =========================================================

async def extraer_timestamp_articulo(articulo):

    # data-utime
    try:
        elementos = articulo.locator("[data-utime]")

        for i in range(await elementos.count()):
            valor = await elementos.nth(i).get_attribute(
                "data-utime"
            )

            if valor and valor.isdigit():
                return int(valor)

    except:
        pass

    # time datetime
    try:
        times = articulo.locator("time")

        for i in range(await times.count()):
            dt = await times.nth(i).get_attribute(
                "datetime"
            )

            if dt:
                try:
                    fecha = datetime.fromisoformat(
                        dt.replace("Z", "+00:00")
                    )

                    return int(
                        fecha.timestamp()
                    )
                except:
                    pass

    except:
        pass

    # buscar timestamp en HTML
    try:
        html = await articulo.inner_html()

        encontrados = re.findall(
            r'(?:"timestamp"|data-utime)[^0-9]{0,30}([0-9]{10})',
            html
        )

        if encontrados:
            return max(
                int(x)
                for x in encontrados
            )

    except:
        pass

    return 0


# =========================================================
# OBTENER PUBLICACIONES
# =========================================================

async def obtener_candidatos(page):

    articulos = page.locator(
        '[role="article"]'
    )

    cantidad = await articulos.count()

    print(
        "Artículos encontrados:",
        cantidad
    )

    candidatos = []

    for i in range(
        min(cantidad, 20)
    ):

        articulo = articulos.nth(i)

        fijado = await esta_fijada(
            articulo
        )

        timestamp = await extraer_timestamp_articulo(
            articulo
        )

        urls = []

        links = articulo.locator("a")

        for j in range(
            await links.count()
        ):

            try:
                href = await links.nth(j).get_attribute(
                    "href"
                )

                url = normalizar_url(
                    href
                )

                if url and url not in urls:
                    urls.append(url)

            except:
                pass

        url_principal = elegir_url_articulo(
            urls
        )

        if not url_principal:
            continue

        candidatos.append({
            "url": url_principal,
            "timestamp": timestamp,
            "fijada": fijado,
            "indice": i
        })

    return candidatos


# =========================================================
# ELEGIR MÁS RECIENTE
# =========================================================

def elegir_mas_reciente(candidatos):

    if not candidatos:
        return None

    no_fijados = [
        x for x in candidatos
        if not x["fijada"]
    ]

    if no_fijados:
        candidatos = no_fijados

    con_fecha = [
        x for x in candidatos
        if x["timestamp"] > 0
    ]

    if con_fecha:

        return max(
            con_fecha,
            key=lambda x: x["timestamp"]
        )

    # Facebook normalmente muestra lo reciente primero
    return min(
        candidatos,
        key=lambda x: x["indice"]
    )


# =========================================================
# EXPANDIR "VER MÁS" EN UN ARTÍCULO
# =========================================================

async def expandir_ver_mas_articulo(articulo):

    for intento in range(4):

        encontrado = False

        # Primero: buscar por texto dentro del artículo
        try:

            elementos = articulo.locator(
                "div, span, div[role='button'], span[role='button']"
            )

            cantidad = await elementos.count()

            for i in range(
                min(cantidad, 600)
            ):

                try:

                    el = elementos.nth(i)

                    texto = (
                        await el.inner_text()
                    ).strip()

                    if texto.lower() not in [
                        "ver más",
                        "see more"
                    ]:
                        continue

                    if not await el.is_visible():
                        continue

                    print(
                        "Encontrado Ver más. Expandiendo..."
                    )

                    await el.evaluate(
                        "element => element.click()"
                    )

                    await asyncio.sleep(2)

                    encontrado = True
                    break

                except:
                    pass

        except:
            pass

        if not encontrado:
            break


# =========================================================
# TEXTO CON EMOJIS
# =========================================================

async def texto_con_emojis(locator):

    try:

        return await locator.evaluate("""
        element => {

            function recorrer(node){

                let resultado = "";

                for(const child of node.childNodes){

                    if(child.nodeType === Node.TEXT_NODE){

                        resultado +=
                            child.textContent || "";

                        continue;
                    }

                    if(
                        child.nodeType !==
                        Node.ELEMENT_NODE
                    ){
                        continue;
                    }

                    const tag =
                        child.tagName.toLowerCase();


                    if(tag === "br"){

                        resultado += "\\n";

                        continue;
                    }


                    if(tag === "img"){

                        const emoji =
                            child.getAttribute("alt") ||
                            child.getAttribute("aria-label") ||
                            child.getAttribute("title") ||
                            "";

                        resultado += emoji;

                        continue;
                    }


                    resultado += recorrer(child);


                    if(
                        tag === "div" ||
                        tag === "p"
                    ){

                        resultado += "\\n";

                    }

                }

                return resultado;
            }


            return recorrer(element)
                .replace(/\\u00a0/g, " ")
                .replace(/[ \\t]+\\n/g, "\\n")
                .replace(/\\n[ \\t]+/g, "\\n")
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)

    except:

        return ""


# =========================================================
# LIMPIAR TEXTO
# =========================================================

def limpiar_texto(texto):

    if not texto:
        return ""

    texto = re.sub(
        r"\s*(\.\.\.)?\s*Ver más\s*",
        "",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"\s*(\.\.\.)?\s*See more\s*",
        "",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# =========================================================
# DESCRIPCIÓN DESDE EL ARTÍCULO DEL MURO
# =========================================================

async def obtener_descripcion_articulo(
    articulo
):

    candidatos = []


    # MÉTODO 1
    try:

        mensajes = articulo.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        print(
            "Mensajes dentro del artículo:",
            cantidad
        )

        for i in range(cantidad):

            texto = await texto_con_emojis(
                mensajes.nth(i)
            )

            texto = limpiar_texto(
                texto
            )

            if len(texto) > 10:
                candidatos.append(texto)

    except:
        pass


    # MÉTODO 2
    try:

        bloques = articulo.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        for i in range(
            min(cantidad, 200)
        ):

            try:

                texto = await texto_con_emojis(
                    bloques.nth(i)
                )

                texto = limpiar_texto(
                    texto
                )

                if len(texto) < 25:
                    continue

                minuscula = texto.lower()

                basura = [
                    "me gusta",
                    "comentar",
                    "compartir",
                    "todas las reacciones",
                    "iniciar sesión",
                    "crear cuenta"
                ]

                if any(
                    palabra in minuscula
                    for palabra in basura
                ):
                    continue

                candidatos.append(
                    texto
                )

            except:
                pass

    except:
        pass


    if candidatos:

        descripcion = max(
            candidatos,
            key=len
        )

        print("")
        print(
            "=============================="
        )
        print(
            "DESCRIPCIÓN COMPLETA:"
        )
        print(
            "=============================="
        )
        print(
            descripcion
        )
        print(
            "=============================="
        )
        print("")

        return descripcion


    return ""


# =========================================================
# FALLBACK DESCRIPCIÓN DEL POST INDIVIDUAL
# =========================================================

async def descripcion_fallback(page):

    try:

        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():

            texto = await meta.first.get_attribute(
                "content"
            )

            return limpiar_texto(
                texto or ""
            )

    except:
        pass

    return ""


# =========================================================
# IMAGEN DE MAYOR CALIDAD
# =========================================================

async def obtener_mejor_imagen(page):

    candidatos = []

    imagenes = page.locator("img")

    cantidad = await imagenes.count()

    for i in range(cantidad):

        try:

            datos = await imagenes.nth(i).evaluate("""
            img => {

                const url =
                    img.currentSrc ||
                    img.src ||
                    "";

                return {
                    url: url,
                    width:
                        img.naturalWidth || 0,
                    height:
                        img.naturalHeight || 0
                };
            }
            """)

            if not datos["url"]:
                continue

            ancho = datos["width"]
            alto = datos["height"]

            if ancho < 500:
                continue

            if alto < 350:
                continue

            area = ancho * alto

            candidatos.append(
                (
                    area,
                    datos["url"]
                )
            )

        except:
            pass


    if candidatos:

        candidatos.sort(
            key=lambda x: x[0],
            reverse=True
        )

        print(
            "Imagen principal encontrada."
        )

        return candidatos[0][1]


    # OG IMAGE
    try:

        og = page.locator(
            'meta[property="og:image"]'
        )

        if await og.count():

            src = await og.first.get_attribute(
                "content"
            )

            if src:
                return src

    except:
        pass


    return ""


# =========================================================
# DESCARGAR IMAGEN
# =========================================================

async def descargar_imagen(
    context,
    url
):

    if not url:
        return ""

    os.makedirs(
        "posts",
        exist_ok=True
    )

    ruta = (
        "posts/"
        "ultima_publicacion.jpg"
    )

    try:

        respuesta = await context.request.get(
            url
        )

        if respuesta.ok:

            contenido = await respuesta.body()

            with open(
                ruta,
                "wb"
            ) as archivo:

                archivo.write(
                    contenido
                )

            print(
                "Imagen guardada:",
                ruta
            )

            return ruta

    except Exception as e:

        print(
            "Error descargando imagen:",
            e
        )

    return ""


# =========================================================
# MÉTRICAS
# =========================================================

def extraer_numero(
    texto,
    patrones
):

    for patron in patrones:

        resultado = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if resultado:
            return resultado.group(1)

    return "—"


async def obtener_metricas(page):

    try:

        texto = await page.locator(
            "body"
        ).inner_text()

    except:

        texto = ""


    try:

        aria = await page.locator(
            "[aria-label]"
        ).evaluate_all("""
        elementos =>
            elementos
            .map(
                x =>
                x.getAttribute(
                    "aria-label"
                )
            )
            .filter(Boolean)
            .join("\\n")
        """)

        texto += (
            "\\n" +
            aria
        )

    except:
        pass


    likes = extraer_numero(
        texto,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción"
        ]
    )


    comentarios = extraer_numero(
        texto,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario"
        ]
    )


    compartidos = extraer_numero(
        texto,
        [
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido"
        ]
    )


    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )


        context = await browser.new_context(

            viewport={
                "width": 1920,
                "height": 1080
            },

            locale="es-ES",

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        )


        # =================================================
        # ABRIR FACEBOOK
        # =================================================

        page = await context.new_page()


        print(
            "Abriendo página de Facebook..."
        )


        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await page.wait_for_timeout(
            10000
        )


        # cargar publicaciones
        for _ in range(4):

            await page.mouse.wheel(
                0,
                900
            )

            await page.wait_for_timeout(
                1200
            )


        await page.mouse.wheel(
            0,
            -5000
        )


        await page.wait_for_timeout(
            1500
        )


        # =================================================
        # BUSCAR MÁS RECIENTE
        # =================================================

        candidatos = await obtener_candidatos(
            page
        )


        print(
            "Candidatos encontrados:",
            len(candidatos)
        )


        elegido = elegir_mas_reciente(
            candidatos
        )


        if not elegido:

            print(
                "No se encontró publicación."
            )

            await browser.close()

            return


        print(
            "Publicación elegida:",
            elegido["url"]
        )


        print(
            "Índice del artículo:",
            elegido["indice"]
        )


        print(
            "Timestamp:",
            elegido["timestamp"]
        )


        # =================================================
        # AQUÍ ESTÁ EL CAMBIO IMPORTANTE
        # SACAR TEXTO DEL MURO ANTES DE CERRARLO
        # =================================================

        articulos = page.locator(
            '[role="article"]'
        )


        articulo_elegido = articulos.nth(
            elegido["indice"]
        )


        await articulo_elegido.scroll_into_view_if_needed()


        await page.wait_for_timeout(
            1000
        )


        await expandir_ver_mas_articulo(
            articulo_elegido
        )


        await page.wait_for_timeout(
            2000
        )


        descripcion = await obtener_descripcion_articulo(
            articulo_elegido
        )


        post_url = elegido["url"]


        # =================================================
        # ABRIR POST INDIVIDUAL
        # SOLO PARA IMAGEN Y MÉTRICAS
        # =================================================

        post_page = await context.new_page()


        print(
            "Abriendo publicación individual..."
        )


        await post_page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await post_page.wait_for_timeout(
            8000
        )


        # fallback solamente si no conseguimos texto del muro
        if not descripcion:

            print(
                "No se encontró texto completo en el muro."
            )

            descripcion = await descripcion_fallback(
                post_page
            )


        # =================================================
        # MÉTRICAS
        # =================================================

        (
            likes,
            comentarios,
            compartidos
        ) = await obtener_metricas(
            post_page
        )


        # =================================================
        # IMAGEN
        # =================================================

        imagen_url = await obtener_mejor_imagen(
            post_page
        )


        imagen_final = ""


        if imagen_url:

            imagen_final = await descargar_imagen(
                context,
                imagen_url
            )


        await post_page.close()

        await page.close()

        await browser.close()


        # =================================================
        # FALLBACK
        # =================================================

        if not descripcion:

            descripcion = (
                "Publicación reciente de Super Farmacia"
            )


        # =================================================
        # GUARDAR JSON
        # =================================================

        resultado = [
            {
                "text":
                    descripcion,

                "image":
                    imagen_final,

                "url":
                    post_url,

                "date":
                    "Publicación reciente",

                "likes":
                    likes,

                "comments_count":
                    comentarios,

                "shares":
                    compartidos,

                "scraped_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            }
        ]


        with open(
            "posts.json",
            "w",
            encoding="utf-8"
        ) as archivo:

            json.dump(
                resultado,
                archivo,
                ensure_ascii=False,
                indent=2
            )


        print("")
        print(
            "posts.json actualizado correctamente."
        )


asyncio.run(main())
