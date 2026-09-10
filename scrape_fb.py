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

FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"

FACEBOOK_POSTS_URL = (
    "https://www.facebook.com/SuperFarmaciaVC/posts/"
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

    if not href.startswith("http"):
        return None

    try:

        parsed = urlparse(href)

        host = parsed.netloc.lower()

        if "facebook.com" not in host:
            return None

    except:
        return None


    u = href.lower()


    # -----------------------------------------------------
    # IGNORAR ENLACES QUE NO SON PUBLICACIONES
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
        "/following/"
    ]


    if any(
        x in u
        for x in excluir
    ):
        return None


    # -----------------------------------------------------
    # FORMATOS VÁLIDOS
    # -----------------------------------------------------

    patrones = [
        "/posts/",
        "/reel/",
        "/reels/",
        "/videos/",
        "/photos/",
        "/photo/",
        "/permalink/",
        "/share/p/",
        "/share/r/",
        "/share/v/",
        "story_fbid=",
        "fbid="
    ]


    if not any(
        x in u
        for x in patrones
    ):
        return None


    return href.split("#")[0]


# =========================================================
# CREAR CLAVE ÚNICA DEL POST
# =========================================================

def clave_post(url):

    if not url:
        return ""

    try:

        parsed = urlparse(url)

        path = parsed.path.rstrip("/").lower()

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


        # fbid
        if "fbid" in query:

            return (
                "fbid:"
                +
                query["fbid"][0]
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


        # foto clásica
        match = re.search(
            r"/photos/[^/]+/([^/?]+)",
            path
        )

        if match:

            return (
                "photo:"
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
# ELEGIR LA MEJOR URL DEL ARTÍCULO
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
        "/share/p/",
        "fbid=",
        "/photo/",
        "/photos/"
    ]


    for patron in prioridades:

        for url in urls:

            if patron in url.lower():
                return url


    return urls[0]


# =========================================================
# DETECTAR PUBLICACIÓN FIJADA
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

async def extraer_timestamp_articulo(
    articulo
):


    # -----------------------------------------------------
    # DATA-UTIME
    # -----------------------------------------------------

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
                and
                valor.isdigit()
            ):

                return int(valor)

    except:

        pass


    # -----------------------------------------------------
    # TIME
    # -----------------------------------------------------

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

                    fecha = (
                        datetime
                        .fromisoformat(
                            dt.replace(
                                "Z",
                                "+00:00"
                            )
                        )
                    )


                    return int(
                        fecha.timestamp()
                    )

                except:

                    pass

    except:

        pass


    # -----------------------------------------------------
    # HTML
    # -----------------------------------------------------

    try:

        html = (
            await articulo.inner_html()
        )


        encontrados = re.findall(
            r'(?:"timestamp"|data-utime)[^0-9]{0,50}([0-9]{10})',
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
                min(
                    cantidad,
                    700
                )
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


                    await asyncio.sleep(
                        2
                    )


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
# DESCRIPCIÓN DEL ARTÍCULO
# =========================================================

async def obtener_descripcion_articulo(
    articulo
):

    candidatos = []


    # -----------------------------------------------------
    # DATA AD PREVIEW
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # DIV DIR AUTO
    # -----------------------------------------------------

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
# BUSCAR CONTADOR
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


        texto += (
            "\\n"
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
            elementos =>
                elementos
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
            "\\n"
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
            r"([\d.,KkMm]+)\s+personas reaccionaron",
            r"reacciones[^0-9]*([\d.,KkMm]+)"
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
# CAPTURAR DESDE UNA PÁGINA DE FACEBOOK
# =========================================================

async def capturar_desde_fuente(
    page,
    fuente,
    nombre_fuente,
    limite=4
):

    print("")
    print(
        "========================================"
    )
    print(
        "FUENTE:",
        nombre_fuente
    )
    print(
        fuente
    )
    print(
        "========================================"
    )


    try:

        await page.goto(
            fuente,
            wait_until="domcontentloaded",
            timeout=90000
        )

    except Exception as e:

        print(
            "Error abriendo fuente:",
            e
        )

        return []


    await page.wait_for_timeout(
        10000
    )


    print(
        "URL real:",
        page.url
    )


    capturados = []

    claves_vistas = set()


    for escaneo in range(
        10
    ):


        print("")
        print(
            f"--- ESCANEO {escaneo + 1} ---"
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


        for i in range(
            cantidad
        ):


            articulo = articulos.nth(i)


            try:

                if await esta_fijada(
                    articulo
                ):

                    print(
                        "Artículo fijado ignorado:",
                        i
                    )

                    continue

            except:

                pass


            # ------------------------------------------------
            # OBTENER TODOS LOS LINKS
            # ------------------------------------------------

            urls = []


            links = articulo.locator(
                "a[href]"
            )


            cantidad_links = (
                await links.count()
            )


            for j in range(
                cantidad_links
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


            print(
                "Artículo",
                i,
                "- URLs válidas:",
                len(urls)
            )


            for u in urls:

                print(
                    "   ",
                    u
                )


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
                clave in claves_vistas
            ):

                continue


            print("")
            print(
                "NUEVA PUBLICACIÓN:"
            )
            print(
                url_principal
            )
            print(
                "Clave:",
                clave
            )


            try:

                await articulo.scroll_into_view_if_needed()

            except:

                pass


            await page.wait_for_timeout(
                500
            )


            await expandir_ver_mas_articulo(
                articulo
            )


            await page.wait_for_timeout(
                800
            )


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


            timestamp = (
                await extraer_timestamp_articulo(
                    articulo
                )
            )


            capturados.append({

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

                "timestamp":
                    timestamp,

                "source":
                    nombre_fuente

            })


            claves_vistas.add(
                clave
            )


            print(
                "Capturados en fuente:",
                len(capturados)
            )


            if len(capturados) >= limite:

                return capturados


        # -------------------------------------------------
        # SCROLL
        # -------------------------------------------------

        try:

            await page.evaluate("""
            () => {
                window.scrollBy(
                    0,
                    Math.max(
                        window.innerHeight * 0.9,
                        800
                    )
                );
            }
            """)

        except:

            pass


        await page.wait_for_timeout(
            2500
        )


    return capturados


# =========================================================
# COMBINAR FUENTES
# =========================================================

def combinar_fuentes(
    listas
):

    resultado = []

    indices = {}


    for lista in listas:

        for post in lista:

            clave = post["key"]


            # ------------------------------------------------
            # NUEVO
            # ------------------------------------------------

            if clave not in indices:

                indices[clave] = len(
                    resultado
                )

                resultado.append(
                    post
                )

                continue


            # ------------------------------------------------
            # YA EXISTÍA:
            # completar información faltante
            # ------------------------------------------------

            existente = resultado[
                indices[clave]
            ]


            if (
                len(post.get("text", ""))
                >
                len(existente.get("text", ""))
            ):

                existente["text"] = (
                    post["text"]
                )


            for campo in [
                "likes",
                "comments_count",
                "shares"
            ]:

                actual = existente.get(
                    campo,
                    "—"
                )

                nuevo = post.get(
                    campo,
                    "—"
                )


                if (
                    actual == "—"
                    and
                    nuevo != "—"
                ):

                    existente[campo] = (
                        nuevo
                    )


            if (
                post.get("timestamp", 0)
                >
                existente.get(
                    "timestamp",
                    0
                )
            ):

                existente["timestamp"] = (
                    post["timestamp"]
                )


    return resultado


# =========================================================
# FALLBACK DESCRIPCIÓN
# =========================================================

async def descripcion_fallback(
    page
):

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
# MÉTRICAS FALLBACK
# =========================================================

async def obtener_metricas_fallback(
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


        texto += (
            "\\n"
            +
            aria
        )

    except:

        pass


    likes = buscar_contador(

        texto,

        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción",
            r"([\d.,KkMm]+)\s+Me gusta"
        ]

    )


    comentarios = buscar_contador(

        texto,

        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario"
        ]

    )


    compartidos = buscar_contador(

        texto,

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

        if (
            a
            and
            a != "—"
        ):

            resultado.append(
                a
            )

        else:

            resultado.append(
                b
            )


    return tuple(
        resultado
    )


# =========================================================
# OBTENER MEJOR IMAGEN
# =========================================================

async def obtener_mejor_imagen(
    page
):

    candidatos = []


    imagenes = page.locator(
        "img"
    )


    cantidad = (
        await imagenes.count()
    )


    for i in range(
        cantidad
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


    # -----------------------------------------------------
    # OG IMAGE
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # VIDEO
    # -----------------------------------------------------

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
                    not url.startswith(
                        "blob:"
                    )
                ):

                    candidatos.append({

                        "url":
                            url,

                        "area":
                            datos["width"]
                            *
                            datos["height"]

                    })

    except:

        pass


    # -----------------------------------------------------
    # SOURCE
    # -----------------------------------------------------

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

                candidatos.append({

                    "url":
                        src,

                    "area":
                        1

                })

    except:

        pass


    # -----------------------------------------------------
    # OG VIDEO
    # -----------------------------------------------------

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

                    candidatos.append({

                        "url":
                            src,

                        "area":
                            1

                    })

        except:

            pass


    # -----------------------------------------------------
    # PERFORMANCE RESOURCES
    # -----------------------------------------------------

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

                candidatos.append({

                    "url":
                        url,

                    "area":
                        1

                })

    except:

        pass


    if not candidatos:

        return ""


    # -----------------------------------------------------
    # QUITAR DUPLICADOS
    # -----------------------------------------------------

    unicos = []

    vistos = set()


    for candidato in candidatos:

        url = candidato["url"]


        if url in vistos:
            continue


        vistos.add(
            url
        )


        unicos.append(
            candidato
        )


    unicos.sort(
        key=lambda x:
            x["area"],
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
                url,
                timeout=120000
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
                "Error HTTP video:",
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
# PROCESAR PUBLICACIÓN INDIVIDUAL
# =========================================================

async def procesar_post(
    context,
    datos,
    posicion
):

    post_url = datos["url"]


    print("")
    print(
        "========================================"
    )
    print(
        "PROCESANDO POST",
        posicion
    )
    print(
        post_url
    )
    print(
        "Fuente:",
        datos.get(
            "source",
            ""
        )
    )
    print(
        "========================================"
    )


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


    url_final = (
        post_page.url
    )


    print(
        "URL final:",
        url_final
    )


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
                post_page
            )
        )


    # -----------------------------------------------------
    # MÉTRICAS
    # -----------------------------------------------------

    metricas_fallback = (
        await obtener_metricas_fallback(
            post_page
        )
    )


    (
        likes,
        comentarios,
        compartidos
    ) = combinar_metricas(

        (
            datos.get(
                "likes",
                "—"
            ),

            datos.get(
                "comments_count",
                "—"
            ),

            datos.get(
                "shares",
                "—"
            )
        ),

        metricas_fallback

    )


    print(
        "Likes:",
        likes
    )

    print(
        "Comentarios:",
        comentarios
    )

    print(
        "Compartidos:",
        compartidos
    )


    # -----------------------------------------------------
    # IMAGEN
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


    if (
        es_video_url(
            post_url
        )
        or
        es_video_url(
            url_final
        )
    ):


        print(
            "Detectado VIDEO / REEL."
        )


        try:

            videos = post_page.locator(
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
            url_final
            or
            post_url,

        "date":
            "Publicación reciente",

        "likes":
            likes,

        "comments_count":
            comentarios,

        "shares":
            compartidos,

        "timestamp":
            datos.get(
                "timestamp",
                0
            ),

        "source":
            datos.get(
                "source",
                ""
            ),

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


        # =================================================
        # FUENTE 1: PÁGINA PRINCIPAL
        # =================================================

        page_principal = (
            await context.new_page()
        )


        principal = (
            await capturar_desde_fuente(

                page_principal,

                FACEBOOK_URL,

                "principal",

                limite=4

            )
        )


        await page_principal.close()


        print("")
        print(
            "Encontrados en principal:",
            len(principal)
        )


        # =================================================
        # FUENTE 2: /POSTS/
        # =================================================

        page_posts = (
            await context.new_page()
        )


        posts_page = (
            await capturar_desde_fuente(

                page_posts,

                FACEBOOK_POSTS_URL,

                "posts",

                limite=6

            )
        )


        await page_posts.close()


        print("")
        print(
            "Encontrados en /posts/:",
            len(posts_page)
        )


        # =================================================
        # COMBINAR Y QUITAR DUPLICADOS
        # =================================================

        candidatos = combinar_fuentes(
            [
                principal,
                posts_page
            ]
        )


        print("")
        print(
            "========================================"
        )
        print(
            "PUBLICACIONES ÚNICAS:",
            len(candidatos)
        )
        print(
            "========================================"
        )


        for i, post in enumerate(
            candidatos,
            start=1
        ):

            print(
                i,
                "-",
                post["key"],
                "-",
                post["source"],
                "-",
                post["url"]
            )


        if not candidatos:

            print(
                "No se encontró ninguna publicación."
            )

            await browser.close()

            return


        # =================================================
        # ORDEN
        #
        # IMPORTANTE:
        # mantenemos primero el orden encontrado en la
        # página principal y luego /posts/.
        #
        # Esto evita que un timestamp ausente de Facebook
        # mande el Reel nuevo al final.
        # =================================================


        seleccionados = (
            candidatos[
                :MAX_POSTS
            ]
        )


        print("")
        print(
            "========================================"
        )
        print(
            "SELECCIONADOS:",
            len(seleccionados)
        )
        print(
            "========================================"
        )


        for i, post in enumerate(
            seleccionados,
            start=1
        ):

            print(
                "POST",
                i,
                ":",
                post["url"]
            )


        # =================================================
        # PROCESAR
        # =================================================

        resultado = []


        for posicion, datos in enumerate(
            seleccionados,
            start=1
        ):

            try:

                post = (
                    await procesar_post(
                        context,
                        datos,
                        posicion
                    )
                )


                resultado.append(
                    post
                )


            except Exception as e:

                print(
                    "ERROR procesando post",
                    posicion,
                    ":",
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
            "posts.json actualizado correctamente."
        )
        print(
            "Cantidad:",
            len(resultado)
        )
        print(
            "========================================"
        )


        if len(resultado) < MAX_POSTS:

            print("")
            print(
                "ADVERTENCIA:"
            )

            print(
                "Solo se pudieron obtener",
                len(resultado),
                "publicación(es)."
            )


asyncio.run(
    main()
)
