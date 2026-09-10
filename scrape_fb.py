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

    if not any(
        p in href
        for p in patrones
    ):
        return None

    return href


# =========================================================
# TIPO DE CONTENIDO
# =========================================================

def es_video_url(url):

    if not url:
        return False

    return (
        "/reel/" in url
        or
        "/reels/" in url
        or
        "/videos/" in url
    )


# =========================================================
# ELEGIR URL PRINCIPAL DEL ARTÍCULO
# =========================================================

def elegir_url_articulo(urls):

    if not urls:
        return None

    # Reel
    for url in urls:
        if (
            "/reel/" in url
            or
            "/reels/" in url
        ):
            return url.split("?")[0]

    # Video
    for url in urls:
        if "/videos/" in url:
            return url.split("?")[0]

    # Post normal
    for url in urls:
        if "/posts/" in url:
            return url.split("?")[0]

    # Story
    for url in urls:
        if "story_fbid=" in url:
            return url

    # Foto
    for url in urls:
        if "/photos/" in url:
            return url

    return urls[0]


# =========================================================
# DETECTAR FIJADO
# =========================================================

async def esta_fijada(articulo):

    try:

        texto = (
            await articulo.inner_text()
        ).lower()

        palabras = [
            "publicación fijada",
            "publicacion fijada",
            "pinned post"
        ]

        return any(
            x in texto
            for x in palabras
        )

    except:

        return False


# =========================================================
# TIMESTAMP
# =========================================================

async def extraer_timestamp_articulo(
    articulo
):

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
                .get_attribute(
                    "data-utime"
                )
            )

            if (
                valor
                and valor.isdigit()
            ):
                return int(valor)

    except:
        pass


    try:

        times = articulo.locator(
            "time"
        )

        for i in range(
            await times.count()
        ):

            dt = (
                await times
                .nth(i)
                .get_attribute(
                    "datetime"
                )
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
        min(cantidad, 20)
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
                    .get_attribute(
                        "href"
                    )
                )

                url = normalizar_url(
                    href
                )

                if (
                    url
                    and url not in urls
                ):
                    urls.append(url)

            except:
                pass


        url_principal = (
            elegir_url_articulo(
                urls
            )
        )


        if not url_principal:
            continue


        candidatos.append({

            "url":
                url_principal,

            "timestamp":
                timestamp,

            "fijada":
                fijado,

            "indice":
                i
        })


    return candidatos


# =========================================================
# ELEGIR MÁS RECIENTE
# =========================================================

def elegir_mas_reciente(
    candidatos
):

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
            key=lambda x:
                x["timestamp"]
        )


    return min(
        candidatos,
        key=lambda x:
            x["indice"]
    )


# =========================================================
# EXPANDIR VER MÁS
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

async def texto_con_emojis(
    locator
):

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
                        child.tagName
                        .toLowerCase();


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


                    resultado +=
                        recorrer(child);


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
                .replace(
                    /\\u00a0/g,
                    " "
                )
                .replace(
                    /[ \\t]+\\n/g,
                    "\\n"
                )
                .replace(
                    /\\n[ \\t]+/g,
                    "\\n"
                )
                .replace(
                    /\\n{3,}/g,
                    "\\n\\n"
                )
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
# DESCRIPCIÓN DEL ARTÍCULO
# =========================================================

async def obtener_descripcion_articulo(
    articulo
):

    candidatos = []


    try:

        mensajes = articulo.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = (
            await mensajes.count()
        )

        for i in range(cantidad):

            texto = (
                await texto_con_emojis(
                    mensajes.nth(i)
                )
            )

            texto = limpiar_texto(
                texto
            )

            if len(texto) > 10:
                candidatos.append(
                    texto
                )

    except:
        pass


    try:

        bloques = articulo.locator(
            'div[dir="auto"]'
        )

        cantidad = (
            await bloques.count()
        )

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


                minuscula = (
                    texto.lower()
                )


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
            "DESCRIPCIÓN COMPLETA:"
        )

        print(
            descripcion
        )

        return descripcion


    return ""


# =========================================================
# FALLBACK DESCRIPCIÓN
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
                .get_attribute(
                    "content"
                )
            )

            return limpiar_texto(
                texto or ""
            )

    except:
        pass


    return ""


# =========================================================
# MEJOR IMAGEN
# =========================================================

async def obtener_mejor_imagen(page):

    candidatos = []

    imagenes = page.locator(
        "img"
    )

    cantidad = (
        await imagenes.count()
    )


    for i in range(cantidad):

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


            ancho = datos["width"]
            alto = datos["height"]


            if ancho < 500:
                continue


            if alto < 350:
                continue


            candidatos.append(
                (
                    ancho * alto,
                    datos["url"]
                )
            )

        except:
            pass


    if candidatos:

        candidatos.sort(
            key=lambda x:
                x[0],
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
                .get_attribute(
                    "content"
                )
            ) or ""

    except:
        pass


    return ""


# =========================================================
# BUSCAR VIDEO MP4
# =========================================================

async def obtener_video(page):

    candidatos = []


    # -----------------------------------------------------
    # VIDEO TAG
    # -----------------------------------------------------

    try:

        videos = page.locator(
            "video"
        )

        for i in range(
            await videos.count()
        ):

            datos = await videos.nth(i).evaluate("""
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


    # -----------------------------------------------------
    # SOURCE TAG
    # -----------------------------------------------------

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
                .get_attribute(
                    "src"
                )
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


    # -----------------------------------------------------
    # META OG VIDEO
    # -----------------------------------------------------

    metas = [
        'meta[property="og:video"]',
        'meta[property="og:video:url"]',
        'meta[property="og:video:secure_url"]'
    ]


    for selector in metas:

        try:

            meta = page.locator(
                selector
            )

            if await meta.count():

                url = (
                    await meta
                    .first
                    .get_attribute(
                        "content"
                    )
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


    # -----------------------------------------------------
    # RECURSOS MP4 CARGADOS POR FACEBOOK
    # -----------------------------------------------------

    try:

        recursos = await page.evaluate("""
        () =>
            performance
            .getEntriesByType("resource")
            .map(x => x.name)
            .filter(
                x =>
                    x &&
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


    # eliminar duplicados
    vistos = set()
    finales = []


    for candidato in candidatos:

        url = candidato["url"]

        if url in vistos:
            continue

        vistos.add(url)

        finales.append(
            candidato
        )


    if not finales:

        print(
            "No se encontró MP4 directo."
        )

        return ""


    finales.sort(
        key=lambda x:
            x["area"],
        reverse=True
    )


    print(
        "Video encontrado."
    )


    return finales[0]["url"]


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
            "Error imagen:",
            e
        )


    return ""


# =========================================================
# DESCARGAR VIDEO
# =========================================================

async def descargar_video(
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
        "ultimo_video.mp4"
    )


    try:

        print(
            "Descargando video..."
        )


        respuesta = (
            await context.request.get(
                url,
                timeout=120000
            )
        )


        if not respuesta.ok:

            print(
                "Facebook respondió:",
                respuesta.status
            )

            return ""


        contenido = (
            await respuesta.body()
        )


        if len(contenido) < 100000:

            print(
                "El archivo recibido es demasiado pequeño."
            )

            return ""


        with open(
            ruta,
            "wb"
        ) as archivo:

            archivo.write(
                contenido
            )


        tamaño_mb = (
            len(contenido)
            /
            1024
            /
            1024
        )


        print(
            "Video guardado:",
            ruta
        )


        print(
            "Tamaño:",
            round(
                tamaño_mb,
                2
            ),
            "MB"
        )


        return ruta


    except Exception as e:

        print(
            "Error descargando video:",
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

        texto = (
            await page
            .locator("body")
            .inner_text()
        )

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

        browser = (
            await p.chromium.launch(
                headless=True
            )
        )


        context = (
            await browser.new_context(

                viewport={
                    "width":1920,
                    "height":1080
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


        # =================================================
        # PÁGINA PRINCIPAL
        # =================================================

        page = await context.new_page()


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


        candidatos = (
            await obtener_candidatos(
                page
            )
        )


        elegido = (
            elegir_mas_reciente(
                candidatos
            )
        )


        if not elegido:

            print(
                "No se encontró publicación."
            )

            await browser.close()

            return


        post_url = (
            elegido["url"]
        )


        print(
            "Publicación elegida:",
            post_url
        )


        # =================================================
        # DESCRIPCIÓN COMPLETA DEL MURO
        # =================================================

        articulos = page.locator(
            '[role="article"]'
        )


        articulo = articulos.nth(
            elegido["indice"]
        )


        await articulo.scroll_into_view_if_needed()


        await page.wait_for_timeout(
            1000
        )


        await expandir_ver_mas_articulo(
            articulo
        )


        await page.wait_for_timeout(
            2000
        )


        descripcion = (
            await obtener_descripcion_articulo(
                articulo
            )
        )


        # =================================================
        # ABRIR PUBLICACIÓN
        # =================================================

        post_page = (
            await context.new_page()
        )


        await post_page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await post_page.wait_for_timeout(
            10000
        )


        if not descripcion:

            descripcion = (
                await descripcion_fallback(
                    post_page
                )
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
        # IMAGEN / PORTADA
        # =================================================

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
                    imagen_url
                )
            )


        # =================================================
        # VIDEO / REEL
        # =================================================

        tipo = "image"
        video_final = ""


        if es_video_url(
            post_url
        ):

            print(
                "Contenido detectado como VIDEO/REEL"
            )


            # dar tiempo a que cargue video
            try:

                await post_page.mouse.click(
                    960,
                    500
                )

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
                        video_url
                    )
                )


            if video_final:

                tipo = "video"

                print(
                    "Video listo para reproducir."
                )

            else:

                print(
                    "No se pudo descargar el video."
                )

                print(
                    "Se mostrará la portada."
                )


        await post_page.close()

        await page.close()

        await browser.close()


        if not descripcion:

            descripcion = (
                "Publicación reciente de Super Farmacia"
            )


        # =================================================
        # JSON
        # =================================================

        resultado = [
            {
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


        print(
            "posts.json actualizado."
        )


asyncio.run(main())
