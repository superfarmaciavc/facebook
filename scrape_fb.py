import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"
MAX_POSTS = 2


# =========================================================
# NORMALIZAR URL
# =========================================================

def normalizar_url(href):
    if not href:
        return None

    if href.startswith("/"):
        href = urljoin(
            "https://www.facebook.com",
            href
        )

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
# DETECTAR VIDEO / REEL
# =========================================================

def es_video_url(url):
    if not url:
        return False

    return (
        "/reel/" in url
        or "/reels/" in url
        or "/videos/" in url
    )


# =========================================================
# ELEGIR URL PRINCIPAL DEL ARTÍCULO
# =========================================================

def elegir_url_articulo(urls):
    if not urls:
        return None

    # Reel
    for url in urls:
        if "/reel/" in url or "/reels/" in url:
            return url.split("?")[0]

    # Video
    for url in urls:
        if "/videos/" in url:
            return url.split("?")[0]

    # Post
    for url in urls:
        if "/posts/" in url:
            return url.split("?")[0]

    # story_fbid
    for url in urls:
        if "story_fbid=" in url:
            return url

    # Foto
    for url in urls:
        if "/photos/" in url:
            return url

    return urls[0]


# =========================================================
# PUBLICACIÓN FIJADA
# =========================================================

async def esta_fijada(articulo):
    try:
        texto = (
            await articulo.inner_text()
        ).lower()

        indicadores = [
            "publicación fijada",
            "publicacion fijada",
            "pinned post"
        ]

        return any(
            x in texto
            for x in indicadores
        )

    except:
        return False


# =========================================================
# TIMESTAMP
# =========================================================

async def extraer_timestamp_articulo(articulo):

    # data-utime
    try:
        elementos = articulo.locator(
            "[data-utime]"
        )

        for i in range(
            await elementos.count()
        ):
            valor = (
                await elementos
                .nth(i)
                .get_attribute("data-utime")
            )

            if valor and valor.isdigit():
                return int(valor)

    except:
        pass


    # time datetime
    try:
        times = articulo.locator("time")

        for i in range(
            await times.count()
        ):
            dt = (
                await times
                .nth(i)
                .get_attribute("datetime")
            )

            if dt:
                try:
                    fecha = datetime.fromisoformat(
                        dt.replace(
                            "Z",
                            "+00:00"
                        )
                    )

                    return int(
                        fecha.timestamp()
                    )

                except:
                    pass

    except:
        pass


    # Buscar timestamp en HTML
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
# OBTENER CANDIDATOS
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
        min(cantidad, 25)
    ):

        articulo = articulos.nth(i)

        fijado = await esta_fijada(
            articulo
        )

        timestamp = (
            await extraer_timestamp_articulo(
                articulo
            )
        )

        urls = []

        links = articulo.locator("a")

        for j in range(
            await links.count()
        ):

            try:
                href = (
                    await links
                    .nth(j)
                    .get_attribute("href")
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
# ELEGIR LOS 2 MÁS RECIENTES
# =========================================================

def elegir_ultimos_posts(
    candidatos,
    limite=2
):

    if not candidatos:
        return []


    # Preferir publicaciones no fijadas
    no_fijados = [
        x
        for x in candidatos
        if not x["fijada"]
    ]

    if no_fijados:
        candidatos = no_fijados


    # Eliminar URLs duplicadas
    unicos = []
    urls_vistas = set()

    for candidato in candidatos:

        if candidato["url"] in urls_vistas:
            continue

        urls_vistas.add(
            candidato["url"]
        )

        unicos.append(
            candidato
        )


    # Timestamp primero.
    # Si Facebook no entrega timestamp,
    # usamos el orden del muro.
    ordenados = sorted(
        unicos,
        key=lambda x: (
            1 if x["timestamp"] > 0 else 0,
            x["timestamp"],
            -x["indice"]
        ),
        reverse=True
    )


    return ordenados[:limite]


# =========================================================
# EXPANDIR "VER MÁS"
# =========================================================

async def expandir_ver_mas_articulo(
    articulo
):

    for _ in range(4):

        encontrado = False

        try:

            elementos = articulo.locator(
                "div, span, "
                "div[role='button'], "
                "span[role='button']"
            )

            cantidad = (
                await elementos.count()
            )

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
                        "Expandiendo descripción..."
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

                for(
                    const child
                    of node.childNodes
                ){

                    if(
                        child.nodeType ===
                        Node.TEXT_NODE
                    ){
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

                        resultado +=
                            child.getAttribute("alt")
                            ||
                            child.getAttribute(
                                "aria-label"
                            )
                            ||
                            child.getAttribute(
                                "title"
                            )
                            ||
                            "";

                        continue;
                    }


                    resultado += recorrer(child);


                    if(
                        tag === "div"
                        ||
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
# DESCRIPCIÓN COMPLETA DESDE EL MURO
# =========================================================

async def obtener_descripcion_articulo(
    articulo
):

    candidatos = []


    # Método principal
    try:

        mensajes = articulo.locator(
            '[data-ad-preview="message"]'
        )

        for i in range(
            await mensajes.count()
        ):

            texto = (
                await texto_con_emojis(
                    mensajes.nth(i)
                )
            )

            texto = limpiar_texto(
                texto
            )

            if len(texto) > 10:
                candidatos.append(texto)

    except:
        pass


    # Método alternativo
    try:

        bloques = articulo.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        for i in range(
            min(cantidad, 200)
        ):

            try:

                texto = (
                    await texto_con_emojis(
                        bloques.nth(i)
                    )
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

        print(
            "Descripción obtenida:"
        )

        print(
            descripcion
        )

        return descripcion


    return ""


# =========================================================
# FALLBACK DE DESCRIPCIÓN
# =========================================================

async def descripcion_fallback(page):

    try:

        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():

            texto = (
                await meta
                .first
                .get_attribute("content")
            )

            return limpiar_texto(
                texto or ""
            )

    except:
        pass

    return ""


# =========================================================
# CONTADORES
# =========================================================

def buscar_contador(
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


# =========================================================
# MÉTRICAS DEL ARTÍCULO
# =========================================================

async def obtener_metricas_articulo(
    articulo
):

    texto_total = ""


    try:
        texto_total += (
            await articulo.inner_text()
        )
    except:
        pass


    try:

        aria = (
            await articulo
            .locator("[aria-label]")
            .evaluate_all("""
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
        )

        texto_total += (
            "\\n" + aria
        )

    except:
        pass


    try:

        titles = (
            await articulo
            .locator("[title]")
            .evaluate_all("""
            elementos =>
                elementos
                .map(
                    x => x.getAttribute("title")
                )
                .filter(Boolean)
                .join("\\n")
            """)
        )

        texto_total += (
            "\\n" + titles
        )

    except:
        pass


    likes = buscar_contador(
        texto_total,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"Todas las reacciones[^0-9]*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción",
            r"([\d.,KkMm]+)\s+Me gusta",
            r"([\d.,KkMm]+)\s+personas reaccionaron",
            r"reacciones[^0-9]*([\d.,KkMm]+)"
        ]
    )


    comentarios = buscar_contador(
        texto_total,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario",
            r"([\d.,KkMm]+)\s+comments",
            r"([\d.,KkMm]+)\s+comment",
            r"comentarios[^0-9]*([\d.,KkMm]+)"
        ]
    )


    compartidos = buscar_contador(
        texto_total,
        [
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+vez compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido",
            r"([\d.,KkMm]+)\s+shares",
            r"([\d.,KkMm]+)\s+share",
            r"compartidos[^0-9]*([\d.,KkMm]+)"
        ]
    )


    print(
        "Interacciones:",
        likes,
        comentarios,
        compartidos
    )


    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# MÉTRICAS FALLBACK
# =========================================================

async def obtener_metricas_fallback(page):

    texto_total = ""

    try:
        texto_total += (
            await page.locator(
                "body"
            ).inner_text()
        )
    except:
        pass


    try:

        aria = (
            await page
            .locator("[aria-label]")
            .evaluate_all("""
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
        )

        texto_total += (
            "\\n" + aria
        )

    except:
        pass


    likes = buscar_contador(
        texto_total,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción",
            r"([\d.,KkMm]+)\s+Me gusta"
        ]
    )


    comentarios = buscar_contador(
        texto_total,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario"
        ]
    )


    compartidos = buscar_contador(
        texto_total,
        [
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+vez compartido",
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
# COMBINAR MÉTRICAS
# =========================================================

def combinar_metricas(
    principal,
    fallback
):

    resultado = []

    for a, b in zip(
        principal,
        fallback
    ):

        if a and a != "—":
            resultado.append(a)
        else:
            resultado.append(b)


    return tuple(resultado)


# =========================================================
# MEJOR IMAGEN
# =========================================================

async def obtener_mejor_imagen(page):

    candidatos = []

    imagenes = page.locator(
        "img"
    )

    for i in range(
        await imagenes.count()
    ):

        try:

            datos = (
                await imagenes
                .nth(i)
                .evaluate("""
                img => ({

                    url:
                        img.currentSrc
                        ||
                        img.src
                        ||
                        "",

                    width:
                        img.naturalWidth
                        ||
                        0,

                    height:
                        img.naturalHeight
                        ||
                        0
                })
                """)
            )


            if not datos["url"]:
                continue


            if datos["width"] < 500:
                continue


            if datos["height"] < 350:
                continue


            candidatos.append(
                (
                    datos["width"]
                    *
                    datos["height"],

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

        return candidatos[0][1]


    try:

        og = page.locator(
            'meta[property="og:image"]'
        )

        if await og.count():

            return (
                await og
                .first
                .get_attribute("content")
            ) or ""

    except:
        pass


    return ""


# =========================================================
# OBTENER VIDEO
# =========================================================

async def obtener_video(page):

    candidatos = []


    # Video HTML
    try:

        videos = page.locator("video")

        for i in range(
            await videos.count()
        ):

            datos = (
                await videos
                .nth(i)
                .evaluate("""
                video => ({

                    currentSrc:
                        video.currentSrc || "",

                    src:
                        video.src || "",

                    width:
                        video.videoWidth || 0,

                    height:
                        video.videoHeight || 0
                })
                """)
            )


            for url in [
                datos["currentSrc"],
                datos["src"]
            ]:

                if (
                    url
                    and
                    not url.startswith("blob:")
                ):

                    candidatos.append({
                        "url": url,
                        "area":
                            datos["width"]
                            *
                            datos["height"]
                    })

    except:
        pass


    # Source
    try:

        sources = page.locator(
            "video source"
        )

        for i in range(
            await sources.count()
        ):

            url = (
                await sources
                .nth(i)
                .get_attribute("src")
            )

            if (
                url
                and
                not url.startswith("blob:")
            ):

                candidatos.append({
                    "url": url,
                    "area": 1
                })

    except:
        pass


    # OpenGraph video
    for selector in [
        'meta[property="og:video"]',
        'meta[property="og:video:url"]',
        'meta[property="og:video:secure_url"]'
    ]:

        try:

            meta = page.locator(
                selector
            )

            if await meta.count():

                url = (
                    await meta
                    .first
                    .get_attribute("content")
                )

                if (
                    url
                    and
                    not url.startswith("blob:")
                ):

                    candidatos.append({
                        "url": url,
                        "area": 1
                    })

        except:
            pass


    # Recursos cargados
    try:

        recursos = await page.evaluate("""
        () =>
            performance
            .getEntriesByType("resource")
            .map(x => x.name)
            .filter(
                x =>
                    x
                    &&
                    (
                        x.includes(".mp4")
                        ||
                        x.includes("video")
                    )
            )
        """)


        for url in recursos:

            if (
                url
                and
                not url.startswith("blob:")
                and
                (
                    ".mp4" in url.lower()
                    or
                    "fbcdn" in url.lower()
                )
            ):

                candidatos.append({
                    "url": url,
                    "area": 1
                })

    except:
        pass


    # Quitar duplicados
    unicos = []
    vistos = set()

    for candidato in candidatos:

        if candidato["url"] in vistos:
            continue

        vistos.add(
            candidato["url"]
        )

        unicos.append(
            candidato
        )


    if not unicos:
        return ""


    unicos.sort(
        key=lambda x: x["area"],
        reverse=True
    )


    return unicos[0]["url"]


# =========================================================
# DESCARGAR IMAGEN
# =========================================================

async def descargar_imagen(
    context,
    url,
    posicion
):

    if not url:
        return ""


    os.makedirs(
        "posts",
        exist_ok=True
    )


    ruta = (
        f"posts/post_{posicion}.jpg"
    )


    try:

        respuesta = (
            await context.request.get(
                url
            )
        )


        if respuesta.ok:

            contenido = (
                await respuesta.body()
            )


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
# DESCARGAR VIDEO
# =========================================================

async def descargar_video(
    context,
    url,
    posicion
):

    if not url:
        return ""


    os.makedirs(
        "posts",
        exist_ok=True
    )


    ruta = (
        f"posts/video_{posicion}.mp4"
    )


    try:

        print(
            f"Descargando video {posicion}..."
        )


        respuesta = (
            await context.request.get(
                url,
                timeout=120000
            )
        )


        if not respuesta.ok:

            print(
                "Error HTTP:",
                respuesta.status
            )

            return ""


        contenido = (
            await respuesta.body()
        )


        if len(contenido) < 100000:

            print(
                "Video demasiado pequeño."
            )

            return ""


        with open(
            ruta,
            "wb"
        ) as archivo:

            archivo.write(
                contenido
            )


        print(
            "Video guardado:",
            ruta
        )


        return ruta

    except Exception as e:

        print(
            "Error descargando video:",
            e
        )


    return ""


# =========================================================
# PROCESAR UNA PUBLICACIÓN
# =========================================================

async def procesar_publicacion(
    context,
    page,
    candidato,
    posicion
):

    print("")
    print(
        "===================================="
    )
    print(
        f"PROCESANDO PUBLICACIÓN {posicion}"
    )
    print(
        "===================================="
    )


    articulos = page.locator(
        '[role="article"]'
    )


    articulo = articulos.nth(
        candidato["indice"]
    )


    await articulo.scroll_into_view_if_needed()

    await page.wait_for_timeout(
        1000
    )


    # -----------------------------------------------------
    # DESCRIPCIÓN
    # -----------------------------------------------------

    await expandir_ver_mas_articulo(
        articulo
    )

    await page.wait_for_timeout(
        1500
    )


    descripcion = (
        await obtener_descripcion_articulo(
            articulo
        )
    )


    # -----------------------------------------------------
    # INTERACCIONES DEL MURO
    # -----------------------------------------------------

    metricas_muro = (
        await obtener_metricas_articulo(
            articulo
        )
    )


    post_url = candidato["url"]


    print(
        "URL:",
        post_url
    )


    # -----------------------------------------------------
    # ABRIR PUBLICACIÓN INDIVIDUAL
    # -----------------------------------------------------

    post_page = (
        await context.new_page()
    )


    await post_page.goto(
        post_url,
        wait_until="domcontentloaded",
        timeout=90000
    )


    await post_page.wait_for_timeout(
        8000
    )


    # -----------------------------------------------------
    # FALLBACK DESCRIPCIÓN
    # -----------------------------------------------------

    if not descripcion:

        descripcion = (
            await descripcion_fallback(
                post_page
            )
        )


    # -----------------------------------------------------
    # FALLBACK MÉTRICAS
    # -----------------------------------------------------

    metricas_post = (
        await obtener_metricas_fallback(
            post_page
        )
    )


    (
        likes,
        comentarios,
        compartidos
    ) = combinar_metricas(
        metricas_muro,
        metricas_post
    )


    print(
        f"Post {posicion} - Likes:",
        likes
    )

    print(
        f"Post {posicion} - Comentarios:",
        comentarios
    )

    print(
        f"Post {posicion} - Compartidos:",
        compartidos
    )


    # -----------------------------------------------------
    # IMAGEN / PORTADA
    # -----------------------------------------------------

    imagen_url = (
        await obtener_mejor_imagen(
            post_page
        )
    )


    imagen_final = ""


    if imagen_url:

        imagen_final = (
            await descargar_imagen(
                context,
                imagen_url,
                posicion
            )
        )


    # -----------------------------------------------------
    # VIDEO
    # -----------------------------------------------------

    tipo = "image"

    video_final = ""


    if es_video_url(
        post_url
    ):

        print(
            f"Post {posicion} es VIDEO/REEL."
        )


        # Intentar activar video
        try:

            videos = post_page.locator(
                "video"
            )

            if await videos.count():

                await videos.first.evaluate("""
                v => {
                    v.muted = true;
                    v.play().catch(() => {});
                }
                """)

        except:
            pass


        await post_page.wait_for_timeout(
            5000
        )


        video_url = (
            await obtener_video(
                post_page
            )
        )


        if video_url:

            video_final = (
                await descargar_video(
                    context,
                    video_url,
                    posicion
                )
            )


        if video_final:
            tipo = "video"


    await post_page.close()


    if not descripcion:

        descripcion = (
            "Publicación reciente de Super Farmacia"
        )


    return {

        "type":
            tipo,

        "text":
            descripcion,

        "image":
            imagen_final,

        "video":
            video_final,

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


# =========================================================
# MAIN
# =========================================================

async def main():

    async with async_playwright() as p:


        browser = (
            await p.chromium.launch(
                headless=True
            )
        )


        context = (
            await browser.new_context(

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
        )


        page = (
            await context.new_page()
        )


        print(
            "Abriendo Facebook..."
        )


        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await page.wait_for_timeout(
            10000
        )


        # -------------------------------------------------
        # CARGAR VARIAS PUBLICACIONES
        # -------------------------------------------------

        for _ in range(6):

            await page.mouse.wheel(
                0,
                900
            )

            await page.wait_for_timeout(
                1200
            )


        # Volver arriba
        await page.mouse.wheel(
            0,
            -8000
        )


        await page.wait_for_timeout(
            2000
        )


        # -------------------------------------------------
        # OBTENER CANDIDATOS
        # -------------------------------------------------

        candidatos = (
            await obtener_candidatos(
                page
            )
        )


        print(
            "Candidatos encontrados:",
            len(candidatos)
        )


        elegidos = (
            elegir_ultimos_posts(
                candidatos,
                MAX_POSTS
            )
        )


        print(
            "Publicaciones seleccionadas:",
            len(elegidos)
        )


        for numero, candidato in enumerate(
            elegidos,
            start=1
        ):

            print(
                f"{numero}:",
                candidato["url"]
            )


        if not elegidos:

            print(
                "No se encontraron publicaciones."
            )

            await browser.close()

            return


        # -------------------------------------------------
        # PROCESAR LAS 2
        # -------------------------------------------------

        resultado = []


        for posicion, candidato in enumerate(
            elegidos,
            start=1
        ):

            try:

                post = (
                    await procesar_publicacion(
                        context,
                        page,
                        candidato,
                        posicion
                    )
                )


                resultado.append(
                    post
                )


            except Exception as e:

                print(
                    f"Error procesando post {posicion}:",
                    e
                )


        await page.close()

        await browser.close()


        # -------------------------------------------------
        # GUARDAR JSON
        # -------------------------------------------------

        if not resultado:

            print(
                "No se pudo procesar ninguna publicación."
            )

            return


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
            "===================================="
        )
        print(
            "posts.json actualizado correctamente."
        )
        print(
            "Cantidad de posts:",
            len(resultado)
        )
        print(
            "===================================="
        )


asyncio.run(
    main()
)
