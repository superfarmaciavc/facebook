import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.async_api import async_playwright


# =========================================================
# CONFIGURACIÓN
# =========================================================

PAGE_NAME = "SuperFarmaciaVC"

FACEBOOK_URL = (
    f"https://www.facebook.com/{PAGE_NAME}/"
)

MAX_POSTS = 2


# =========================================================
# NORMALIZAR URL
# =========================================================

def normalizar_url(href):

    if not href:
        return None

    href = href.strip()

    if href.startswith("/"):
        href = urljoin(
            "https://www.facebook.com",
            href
        )

    href = href.replace(
        "https://m.facebook.com/",
        "https://www.facebook.com/"
    )

    href = href.replace(
        "https://mbasic.facebook.com/",
        "https://www.facebook.com/"
    )

    if not href.startswith("http"):
        return None

    try:

        parsed = urlparse(href)

        if (
            "facebook.com"
            not in parsed.netloc.lower()
        ):
            return None

    except:
        return None


    u = href.lower()


    # -----------------------------------------------------
    # IGNORAR ENLACES QUE NO SON POSTS
    # -----------------------------------------------------

    excluir = [
        "/login",
        "/help/",
        "/privacy/",
        "/policies/",
        "/settings/",
        "/notifications/",
        "/friends/",
        "/marketplace/",
        "/events/",
        "/groups/",
        "/gaming/",
        "/recover/",
        "/people/",
        "/followers/",
        "/following/",
        "/messages/",
        "/search/"
    ]


    if any(
        x in u
        for x in excluir
    ):
        return None


    # -----------------------------------------------------
    # SOLO FORMATOS REALES DE PUBLICACIÓN
    # -----------------------------------------------------

    patrones = [
        "/posts/",
        "/reel/",
        "/reels/",
        "/videos/",
        "/permalink/",
        "/story.php",
        "/share/p/",
        "/share/r/",
        "/share/v/",
        "story_fbid="
    ]


    if not any(
        x in u
        for x in patrones
    ):
        return None


    return href.split("#")[0]


# =========================================================
# CLAVE ÚNICA
# =========================================================

def clave_post(url):

    if not url:
        return ""

    try:

        parsed = urlparse(url)

        path = (
            parsed.path
            .rstrip("/")
            .lower()
        )

        query = parse_qs(
            parsed.query
        )


        # story_fbid
        if "story_fbid" in query:

            return (
                "story:"
                +
                query["story_fbid"][0]
            )


        # reel
        match = re.search(
            r"/reels?/([^/?]+)",
            path
        )

        if match:

            return (
                "reel:"
                +
                match.group(1)
            )


        # video
        match = re.search(
            r"/videos/([^/?]+)",
            path
        )

        if match:

            return (
                "video:"
                +
                match.group(1)
            )


        # post
        match = re.search(
            r"/posts/([^/?]+)",
            path
        )

        if match:

            return (
                "post:"
                +
                match.group(1)
            )


        # share
        match = re.search(
            r"/share/[prv]/([^/?]+)",
            path
        )

        if match:

            return (
                "share:"
                +
                match.group(1)
            )


        # permalink
        match = re.search(
            r"/permalink/([^/?]+)",
            path
        )

        if match:

            return (
                "permalink:"
                +
                match.group(1)
            )


        return path

    except:

        return url


# =========================================================
# DETECTAR VIDEO
# =========================================================

def es_video_url(url):

    if not url:
        return False

    u = url.lower()

    return (
        "/reel/" in u
        or
        "/reels/" in u
        or
        "/videos/" in u
        or
        "/share/r/" in u
        or
        "/share/v/" in u
    )


# =========================================================
# ELEGIR URL PRINCIPAL
# =========================================================

def elegir_url_articulo(urls):

    if not urls:
        return None


    prioridades = [
        "/reel/",
        "/reels/",
        "/videos/",
        "/posts/",
        "story_fbid=",
        "/permalink/",
        "/share/r/",
        "/share/v/",
        "/share/p/"
    ]


    for patron in prioridades:

        for url in urls:

            if patron in url.lower():
                return url


    return urls[0]


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
        r"\s*Ver menos\s*$",
        "",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"\s*See less\s*$",
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
                            child.getAttribute("aria-label")
                            ||
                            child.getAttribute("title")
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
# EXPANDIR VER MÁS
# =========================================================

async def expandir_ver_mas_articulo(
    articulo
):

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
            min(
                cantidad,
                700
            )
        ):

            try:

                el = elementos.nth(i)

                texto = (
                    await el.inner_text()
                ).strip().lower()


                if texto not in [
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
                    "e => e.click()"
                )


                await asyncio.sleep(
                    1
                )


                return

            except:

                pass

    except:

        pass


# =========================================================
# DESCRIPCIÓN
# =========================================================

async def obtener_descripcion_articulo(
    articulo
):

    candidatos = []


    # data-ad-preview
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

                candidatos.append(
                    texto
                )

    except:

        pass


    # div dir auto
    try:

        bloques = articulo.locator(
            'div[dir="auto"]'
        )


        cantidad = (
            await bloques.count()
        )


        for i in range(
            min(
                cantidad,
                250
            )
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
                    x in minuscula
                    for x in basura
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

        return max(
            candidatos,
            key=len
        )


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
# MÉTRICAS
# =========================================================

async def obtener_metricas_articulo(
    articulo
):

    texto = ""


    try:

        texto += (
            await articulo.inner_text()
        )

    except:

        pass


    # aria-label
    try:

        aria = (
            await articulo
            .locator("[aria-label]")
            .evaluate_all("""
            els =>
                els
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


        texto += (
            "\n"
            +
            aria
        )

    except:

        pass


    # title
    try:

        titles = (
            await articulo
            .locator("[title]")
            .evaluate_all("""
            els =>
                els
                .map(
                    x =>
                        x.getAttribute(
                            "title"
                        )
                )
                .filter(Boolean)
                .join("\\n")
            """)
        )


        texto += (
            "\n"
            +
            titles
        )

    except:

        pass


    likes = buscar_contador(
        texto,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"Todas las reacciones[^0-9]*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción",
            r"([\d.,KkMm]+)\s+Me gusta",
            r"([\d.,KkMm]+)\s+personas reaccionaron"
        ]
    )


    comentarios = buscar_contador(
        texto,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario",
            r"([\d.,KkMm]+)\s+comments",
            r"([\d.,KkMm]+)\s+comment"
        ]
    )


    compartidos = buscar_contador(
        texto,
        [
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+vez compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido",
            r"([\d.,KkMm]+)\s+shares",
            r"([\d.,KkMm]+)\s+share"
        ]
    )


    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# DESCUBRIR POSTS DESDE EL MURO
# =========================================================

async def descubrir_publicaciones(
    page
):


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


    encontrados = []

    claves = set()


    # =====================================================
    # ESCANEAR Y HACER SCROLL
    # =====================================================

    for escaneo in range(
        15
    ):


        print("")
        print(
            f"===== ESCANEO {escaneo + 1} ====="
        )


        articulos = page.locator(
            '[role="article"]'
        )


        cantidad = (
            await articulos.count()
        )


        print(
            "Artículos visibles:",
            cantidad
        )


        # -------------------------------------------------
        # PRIMERO: ARTÍCULOS
        # -------------------------------------------------

        for i in range(
            cantidad
        ):


            articulo = articulos.nth(i)


            links = articulo.locator(
                "a[href]"
            )


            urls = []


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
                        and
                        url not in urls
                    ):

                        urls.append(
                            url
                        )

                except:

                    pass


            url_principal = (
                elegir_url_articulo(
                    urls
                )
            )


            if not url_principal:

                continue


            clave = clave_post(
                url_principal
            )


            if (
                not clave
                or
                clave in claves
            ):

                continue


            print(
                "Nueva publicación desde artículo:",
                clave
            )


            try:

                await expandir_ver_mas_articulo(
                    articulo
                )

            except:

                pass


            descripcion = (
                await obtener_descripcion_articulo(
                    articulo
                )
            )


            (
                likes,
                comentarios,
                compartidos
            ) = await obtener_metricas_articulo(
                articulo
            )


            encontrados.append({

                "url":
                    url_principal,

                "key":
                    clave,

                "text":
                    descripcion,

                "likes":
                    likes,

                "comments_count":
                    comentarios,

                "shares":
                    compartidos,

                "source":
                    "article"

            })


            claves.add(
                clave
            )


        # -------------------------------------------------
        # SEGUNDO: LINKS GLOBALES
        #
        # SOLO URLS DE PUBLICACIÓN.
        # NO FOTOS SUELTAS.
        # -------------------------------------------------

        links_globales = page.locator(
            "a[href]"
        )


        cantidad_links = (
            await links_globales.count()
        )


        print(
            "Links globales:",
            cantidad_links
        )


        for i in range(
            cantidad_links
        ):

            try:

                href = (
                    await links_globales
                    .nth(i)
                    .get_attribute(
                        "href"
                    )
                )


                url = normalizar_url(
                    href
                )


                if not url:

                    continue


                # -----------------------------------------
                # SEGURIDAD:
                # nunca aceptar foto suelta como post
                # -----------------------------------------

                u = url.lower()


                if (
                    "/photo/" in u
                    or
                    "/photos/" in u
                    or
                    (
                        "fbid=" in u
                        and
                        "story_fbid=" not in u
                    )
                ):

                    continue


                clave = clave_post(
                    url
                )


                if (
                    not clave
                    or
                    clave in claves
                ):

                    continue


                print(
                    "Nueva publicación global:",
                    clave
                )


                encontrados.append({

                    "url":
                        url,

                    "key":
                        clave,

                    "text":
                        "",

                    "likes":
                        "—",

                    "comments_count":
                        "—",

                    "shares":
                        "—",

                    "source":
                        "global"

                })


                claves.add(
                    clave
                )


            except:

                pass


        if len(encontrados) >= MAX_POSTS:

            break


        # -------------------------------------------------
        # SCROLL REAL
        # -------------------------------------------------

        try:

            await page.evaluate("""
            () => {

                window.scrollBy(
                    0,
                    Math.max(
                        1000,
                        window.innerHeight
                    )
                );

            }
            """)

        except:

            pass


        await page.wait_for_timeout(
            2500
        )


    print("")
    print(
        "========================================"
    )
    print(
        "PUBLICACIONES REALES ENCONTRADAS:",
        len(encontrados)
    )
    print(
        "========================================"
    )


    for i, post in enumerate(
        encontrados,
        start=1
    ):

        print(
            i,
            post["key"],
            post["url"]
        )


    return encontrados


# =========================================================
# DESCRIPCIÓN FALLBACK
# =========================================================

async def descripcion_fallback(
    page
):

    # -----------------------------------------------------
    # PRIMERO ARTÍCULO
    # -----------------------------------------------------

    try:

        articulos = page.locator(
            '[role="article"]'
        )


        if await articulos.count():

            articulo = articulos.first


            await expandir_ver_mas_articulo(
                articulo
            )


            texto = (
                await obtener_descripcion_articulo(
                    articulo
                )
            )


            if texto:

                return texto

    except:

        pass


    # -----------------------------------------------------
    # OG DESCRIPTION
    # -----------------------------------------------------

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


            if texto:

                return limpiar_texto(
                    texto
                )

    except:

        pass


    return ""


# =========================================================
# MÉTRICAS FALLBACK
# =========================================================

async def metricas_fallback(
    page
):

    texto = ""


    try:

        texto += (
            await page
            .locator("body")
            .inner_text()
        )

    except:

        pass


    try:

        aria = (
            await page
            .locator("[aria-label]")
            .evaluate_all("""
            els =>
                els
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


        texto += (
            "\n"
            +
            aria
        )

    except:

        pass


    likes = buscar_contador(
        texto,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"Todas las reacciones[^0-9]*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción",
            r"([\d.,KkMm]+)\s+Me gusta"
        ]
    )


    comentarios = buscar_contador(
        texto,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario",
            r"([\d.,KkMm]+)\s+comments",
            r"([\d.,KkMm]+)\s+comment"
        ]
    )


    compartidos = buscar_contador(
        texto,
        [
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+vez compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido",
            r"([\d.,KkMm]+)\s+shares",
            r"([\d.,KkMm]+)\s+share"
        ]
    )


    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# MEJOR IMAGEN
# =========================================================

async def obtener_mejor_imagen(
    page
):

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
# OBTENER VIDEO
# =========================================================

async def obtener_video(
    page
):

    candidatos = []


    # VIDEO TAG
    try:

        videos = page.locator(
            "video"
        )


        for i in range(
            await videos.count()
        ):

            datos = (
                await videos
                .nth(i)
                .evaluate("""
                v => ({
                    currentSrc:
                        v.currentSrc || "",

                    src:
                        v.src || "",

                    width:
                        v.videoWidth || 0,

                    height:
                        v.videoHeight || 0
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
                    not url.startswith(
                        "blob:"
                    )
                ):

                    candidatos.append(
                        (
                            datos["width"]
                            *
                            datos["height"],

                            url
                        )
                    )

    except:

        pass


    # SOURCE
    try:

        sources = page.locator(
            "video source"
        )


        for i in range(
            await sources.count()
        ):

            src = (
                await sources
                .nth(i)
                .get_attribute(
                    "src"
                )
            )


            if (
                src
                and
                not src.startswith(
                    "blob:"
                )
            ):

                candidatos.append(
                    (
                        1,
                        src
                    )
                )

    except:

        pass


    # OG VIDEO
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

                src = (
                    await meta
                    .first
                    .get_attribute(
                        "content"
                    )
                )


                if (
                    src
                    and
                    not src.startswith(
                        "blob:"
                    )
                ):

                    candidatos.append(
                        (
                            1,
                            src
                        )
                    )

        except:

            pass


    # PERFORMANCE
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
                not url.startswith(
                    "blob:"
                )
                and
                (
                    ".mp4" in url.lower()
                    or
                    "fbcdn" in url.lower()
                )
            ):

                candidatos.append(
                    (
                        1,
                        url
                    )
                )

    except:

        pass


    if not candidatos:

        return ""


    # quitar duplicados
    unicos = []

    vistos = set()


    for area, url in candidatos:

        if url in vistos:

            continue


        vistos.add(
            url
        )


        unicos.append(
            (
                area,
                url
            )
        )


    unicos.sort(
        key=lambda x:
            x[0],
        reverse=True
    )


    return unicos[0][1]


# =========================================================
# DESCARGAR
# =========================================================

async def descargar(
    context,
    url,
    ruta,
    minimo=1000
):

    if not url:

        return ""


    try:

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


        if len(contenido) < minimo:

            return ""


        with open(
            ruta,
            "wb"
        ) as archivo:

            archivo.write(
                contenido
            )


        print(
            "Guardado:",
            ruta
        )


        return ruta


    except Exception as e:

        print(
            "Error descarga:",
            e
        )


        return ""


# =========================================================
# PROCESAR POST
# =========================================================

async def procesar_post(
    context,
    datos,
    posicion
):


    url = datos["url"]


    print("")
    print(
        "========================================"
    )
    print(
        "PROCESANDO POST",
        posicion
    )
    print(
        url
    )
    print(
        "========================================"
    )


    page = (
        await context.new_page()
    )


    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=90000
    )


    await page.wait_for_timeout(
        8000
    )


    url_final = (
        page.url
    )


    print(
        "URL final:",
        url_final
    )


    # -----------------------------------------------------
    # SI FACEBOOK MANDA A LOGIN,
    # NO LO CONSIDERAMOS VÁLIDO
    # -----------------------------------------------------

    if (
        "/login" in
        url_final.lower()
    ):

        print(
            "PUBLICACIÓN DESCARTADA: redirección a login."
        )


        await page.close()


        return None


    # -----------------------------------------------------
    # DESCRIPCIÓN
    # -----------------------------------------------------

    descripcion = (
        datos.get(
            "text",
            ""
        )
    )


    if not descripcion:

        descripcion = (
            await descripcion_fallback(
                page
            )
        )


    descripcion = limpiar_texto(
        descripcion
    )


    # -----------------------------------------------------
    # MÉTRICAS
    # -----------------------------------------------------

    fallback = (
        await metricas_fallback(
            page
        )
    )


    likes = datos.get(
        "likes",
        "—"
    )


    comentarios = datos.get(
        "comments_count",
        "—"
    )


    compartidos = datos.get(
        "shares",
        "—"
    )


    if likes == "—":

        likes = fallback[0]


    if comentarios == "—":

        comentarios = fallback[1]


    if compartidos == "—":

        compartidos = fallback[2]


    # -----------------------------------------------------
    # IMAGEN
    # -----------------------------------------------------

    os.makedirs(
        "posts",
        exist_ok=True
    )


    imagen_url = (
        await obtener_mejor_imagen(
            page
        )
    )


    imagen = ""


    if imagen_url:

        imagen = (
            await descargar(
                context,
                imagen_url,
                f"posts/post_{posicion}.jpg",
                minimo=5000
            )
        )


    # -----------------------------------------------------
    # VIDEO
    # -----------------------------------------------------

    tipo = "image"

    video = ""


    if (
        es_video_url(
            url
        )
        or
        es_video_url(
            url_final
        )
    ):


        print(
            "Detectado VIDEO / REEL"
        )


        try:

            videos = page.locator(
                "video"
            )


            if await videos.count():

                await videos.first.evaluate("""
                v => {

                    v.muted = true;

                    v.play()
                    .catch(() => {});

                }
                """)

        except:

            pass


        await page.wait_for_timeout(
            5000
        )


        video_url = (
            await obtener_video(
                page
            )
        )


        if video_url:

            video = (
                await descargar(
                    context,
                    video_url,
                    f"posts/video_{posicion}.mp4",
                    minimo=100000
                )
            )


        if video:

            tipo = "video"


    await page.close()


    return {

        "type":
            tipo,

        "text":
            descripcion
            or
            "Publicación reciente de Super Farmacia",

        "image":
            imagen,

        "video":
            video,

        "url":
            url_final
            or
            url,

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
                    "width":
                        1920,

                    "height":
                        1080
                },

                locale=
                    "es-ES",

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


        # =================================================
        # DESCUBRIR
        # =================================================

        candidatos = (
            await descubrir_publicaciones(
                page
            )
        )


        await page.close()


        if not candidatos:

            print(
                "No se encontraron publicaciones."
            )


            await browser.close()

            return


        # =================================================
        # PROCESAR HASTA CONSEGUIR 2 VÁLIDAS
        #
        # IMPORTANTE:
        # no nos limitamos a los 2 primeros candidatos.
        # Si uno redirige a login, probamos el siguiente.
        # =================================================

        resultado = []


        for datos in candidatos:


            if len(resultado) >= MAX_POSTS:

                break


            posicion = (
                len(resultado)
                +
                1
            )


            try:

                post = (
                    await procesar_post(
                        context,
                        datos,
                        posicion
                    )
                )


                if not post:

                    continue


                resultado.append(
                    post
                )


            except Exception as e:

                print(
                    "ERROR PROCESANDO:",
                    repr(e)
                )


        await browser.close()


        # =================================================
        # GUARDAR JSON
        # =================================================

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
            "========================================"
        )
        print(
            "posts.json actualizado."
        )
        print(
            "Cantidad:",
            len(resultado)
        )
        print(
            "========================================"
        )


        if len(resultado) < MAX_POSTS:

            print(
                "ADVERTENCIA:"
            )

            print(
                "Facebook solo permitió obtener",
                len(resultado),
                "publicación(es) reales."
            )


asyncio.run(
    main()
)
