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

FUENTES = [
    (
        "desktop",
        f"https://www.facebook.com/{PAGE_NAME}/"
    ),
    (
        "mobile",
        f"https://m.facebook.com/{PAGE_NAME}/"
    ),
    (
        "mbasic",
        f"https://mbasic.facebook.com/{PAGE_NAME}/"
    )
]

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

    # Convertir m.facebook / mbasic a www
    href = href.replace(
        "https://m.facebook.com/",
        "https://www.facebook.com/"
    )

    href = href.replace(
        "https://mbasic.facebook.com/",
        "https://www.facebook.com/"
    )

    href = href.replace(
        "http://m.facebook.com/",
        "https://www.facebook.com/"
    )

    href = href.replace(
        "http://mbasic.facebook.com/",
        "https://www.facebook.com/"
    )

    if not href.startswith("http"):
        return None

    try:

        parsed = urlparse(href)

        if "facebook.com" not in parsed.netloc.lower():
            return None

    except:
        return None


    u = href.lower()


    # -----------------------------------------------------
    # IGNORAR ENLACES AJENOS
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
    # FORMATOS DE PUBLICACIÓN
    # -----------------------------------------------------

    patrones = [
        "/posts/",
        "/reel/",
        "/reels/",
        "/videos/",
        "/photos/",
        "/photo/",
        "/permalink/",
        "/story.php",
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
# CLAVE ÚNICA
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


        if "story_fbid" in query:

            return (
                "story:"
                +
                query["story_fbid"][0]
            )


        if "fbid" in query:

            return (
                "fbid:"
                +
                query["fbid"][0]
            )


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


        return path

    except:

        return url


# =========================================================
# VIDEO
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
# EXPANDIR VER MÁS
# =========================================================

async def expandir_ver_mas_articulo(
    articulo
):

    try:

        botones = articulo.locator(
            "div, span, "
            "div[role='button'], "
            "span[role='button']"
        )

        cantidad = await botones.count()

        for i in range(
            min(
                cantidad,
                700
            )
        ):

            try:

                boton = botones.nth(i)

                texto = (
                    await boton.inner_text()
                ).strip().lower()

                if texto not in [
                    "ver más",
                    "see more"
                ]:
                    continue

                if not await boton.is_visible():
                    continue

                await boton.evaluate(
                    "e => e.click()"
                )

                await asyncio.sleep(1)

                return

            except:
                pass

    except:
        pass


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

        for i in range(
            await mensajes.count()
        ):

            texto = await texto_con_emojis(
                mensajes.nth(i)
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

        cantidad = await bloques.count()

        for i in range(
            min(
                cantidad,
                250
            )
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
# CONTADOR
# =========================================================

def buscar_contador(
    texto,
    patrones
):

    for patron in patrones:

        encontrado = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if encontrado:

            return encontrado.group(1)

    return "—"


# =========================================================
# MÉTRICAS
# =========================================================

async def obtener_metricas_articulo(
    articulo
):

    texto = ""


    try:

        texto += await articulo.inner_text()

    except:
        pass


    try:

        aria = await articulo.locator(
            "[aria-label]"
        ).evaluate_all("""
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

        texto += "\n" + aria

    except:
        pass


    try:

        titles = await articulo.locator(
            "[title]"
        ).evaluate_all("""
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

        texto += "\n" + titles

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
# DESCUBRIR PUBLICACIONES
# =========================================================

async def descubrir_publicaciones(
    page,
    url_fuente,
    nombre_fuente
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
        url_fuente
    )
    print(
        "========================================"
    )


    try:

        await page.goto(
            url_fuente,
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
        8000
    )


    print(
        "URL REAL:",
        page.url
    )


    encontrados = []

    claves = set()


    # =====================================================
    # HASTA 12 SCROLLS
    # =====================================================

    for intento in range(
        12
    ):


        print(
            "Escaneo:",
            intento + 1
        )


        # -------------------------------------------------
        # PRIMERO BUSCAR ARTÍCULOS
        # -------------------------------------------------

        articulos = page.locator(
            '[role="article"]'
        )


        cantidad_articulos = (
            await articulos.count()
        )


        print(
            "Artículos:",
            cantidad_articulos
        )


        for i in range(
            cantidad_articulos
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


            if not urls:
                continue


            # Preferencias de URL
            url_elegida = None


            prioridades = [
                "/reel/",
                "/reels/",
                "/videos/",
                "/posts/",
                "story_fbid=",
                "/permalink/",
                "fbid=",
                "/photos/",
                "/photo/"
            ]


            for patron in prioridades:

                for url in urls:

                    if patron in url.lower():

                        url_elegida = url

                        break

                if url_elegida:
                    break


            if not url_elegida:

                url_elegida = urls[0]


            clave = clave_post(
                url_elegida
            )


            if (
                not clave
                or
                clave in claves
            ):
                continue


            # ---------------------------------------------
            # CAPTURAR INFORMACIÓN SI VIENE DEL ARTÍCULO
            # ---------------------------------------------

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


            metricas = (
                await obtener_metricas_articulo(
                    articulo
                )
            )


            encontrados.append({

                "url":
                    url_elegida,

                "key":
                    clave,

                "source":
                    nombre_fuente,

                "text":
                    descripcion,

                "likes":
                    metricas[0],

                "comments_count":
                    metricas[1],

                "shares":
                    metricas[2]

            })


            claves.add(
                clave
            )


            print(
                "Encontrado:",
                clave
            )


        # -------------------------------------------------
        # SEGUNDO:
        # BUSCAR TODOS LOS LINKS DE LA PÁGINA
        #
        # ESTO ES IMPORTANTE PARA M.FACEBOOK Y MBASIC
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


                clave = clave_post(
                    url
                )


                if (
                    not clave
                    or
                    clave in claves
                ):
                    continue


                encontrados.append({

                    "url":
                        url,

                    "key":
                        clave,

                    "source":
                        nombre_fuente,

                    "text":
                        "",

                    "likes":
                        "—",

                    "comments_count":
                        "—",

                    "shares":
                        "—"

                })


                claves.add(
                    clave
                )


                print(
                    "Encontrado global:",
                    clave
                )


            except:
                pass


        if len(
            encontrados
        ) >= 6:

            break


        # -------------------------------------------------
        # SCROLL
        # -------------------------------------------------

        try:

            await page.evaluate("""
                () => {
                    window.scrollBy(
                        0,
                        Math.max(
                            900,
                            window.innerHeight * 0.9
                        )
                    );
                }
            """)

        except:
            pass


        await page.wait_for_timeout(
            2000
        )


    print(
        "Total en fuente",
        nombre_fuente,
        ":",
        len(encontrados)
    )


    return encontrados


# =========================================================
# COMBINAR FUENTES
# =========================================================

def combinar_fuentes(
    resultados
):

    finales = []

    mapa = {}


    for lista in resultados:

        for post in lista:

            clave = post["key"]


            if clave not in mapa:

                mapa[clave] = len(
                    finales
                )

                finales.append(
                    post
                )

                continue


            existente = finales[
                mapa[clave]
            ]


            # Usar la descripción más completa
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

                if (
                    existente.get(
                        campo,
                        "—"
                    ) == "—"
                    and
                    post.get(
                        campo,
                        "—"
                    ) != "—"
                ):

                    existente[campo] = (
                        post[campo]
                    )


    return finales


# =========================================================
# DESCRIPCIÓN FALLBACK
# =========================================================

async def descripcion_fallback(
    page
):

    # OG DESCRIPTION

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


    # ARTICLE

    try:

        articulos = page.locator(
            '[role="article"]'
        )


        if await articulos.count():

            articulo = articulos.first


            await expandir_ver_mas_articulo(
                articulo
            )


            descripcion = (
                await obtener_descripcion_articulo(
                    articulo
                )
            )


            if descripcion:

                return descripcion

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

        aria = await page.locator(
            "[aria-label]"
        ).evaluate_all("""
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


    comments = buscar_contador(
        texto,
        [
            r"([\d.,KkMm]+)\s+comentarios",
            r"([\d.,KkMm]+)\s+comentario",
            r"([\d.,KkMm]+)\s+comments",
            r"([\d.,KkMm]+)\s+comment"
        ]
    )


    shares = buscar_contador(
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
        comments,
        shares
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

            datos = await imagenes.nth(
                i
            ).evaluate("""
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


    try:

        videos = page.locator(
            "video"
        )


        for i in range(
            await videos.count()
        ):

            datos = await videos.nth(
                i
            ).evaluate("""
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
                    .get_attribute(
                        "content"
                    )
                )


                if (
                    url
                    and
                    not url.startswith(
                        "blob:"
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


    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )


    return candidatos[0][1]


# =========================================================
# DESCARGAR ARCHIVO
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

        respuesta = await context.request.get(
            url,
            timeout=120000
        )


        if not respuesta.ok:

            print(
                "Error descarga HTTP:",
                respuesta.status
            )

            return ""


        contenido = await respuesta.body()


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
            "Error descargando:",
            e
        )

        return ""


# =========================================================
# PROCESAR PUBLICACIÓN
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
        "PROCESANDO",
        posicion
    )
    print(
        url
    )
    print(
        "========================================"
    )


    page = await context.new_page()


    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=90000
    )


    await page.wait_for_timeout(
        8000
    )


    url_final = page.url


    # -----------------------------------------------------
    # TEXTO
    # -----------------------------------------------------

    descripcion = datos.get(
        "text",
        ""
    )


    if not descripcion:

        descripcion = await descripcion_fallback(
            page
        )


    # -----------------------------------------------------
    # MÉTRICAS
    # -----------------------------------------------------

    fallback = await metricas_fallback(
        page
    )


    likes = datos.get(
        "likes",
        "—"
    )

    comments = datos.get(
        "comments_count",
        "—"
    )

    shares = datos.get(
        "shares",
        "—"
    )


    if likes == "—":
        likes = fallback[0]

    if comments == "—":
        comments = fallback[1]

    if shares == "—":
        shares = fallback[2]


    # -----------------------------------------------------
    # IMAGEN
    # -----------------------------------------------------

    os.makedirs(
        "posts",
        exist_ok=True
    )


    imagen_url = await obtener_mejor_imagen(
        page
    )


    imagen = ""


    if imagen_url:

        imagen = await descargar(
            context,
            imagen_url,
            f"posts/post_{posicion}.jpg",
            minimo=5000
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
            "Detectado video/reel."
        )


        try:

            videos = page.locator(
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


        await page.wait_for_timeout(
            5000
        )


        video_url = await obtener_video(
            page
        )


        if video_url:

            video = await descargar(
                context,
                video_url,
                f"posts/video_{posicion}.mp4",
                minimo=100000
            )


        if video:

            tipo = "video"


    await page.close()


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
            comments,

        "shares":
            shares,

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


        browser = await p.chromium.launch(
            headless=True
        )


        context = await browser.new_context(

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


        resultados_fuentes = []


        # =================================================
        # PROBAR LAS TRES FUENTES
        # =================================================

        for nombre, url in FUENTES:


            page = await context.new_page()


            try:

                encontrados = (
                    await descubrir_publicaciones(
                        page,
                        url,
                        nombre
                    )
                )


                resultados_fuentes.append(
                    encontrados
                )


            except Exception as e:

                print(
                    "Error fuente",
                    nombre,
                    ":",
                    repr(e)
                )


            await page.close()


        # =================================================
        # COMBINAR
        # =================================================

        candidatos = combinar_fuentes(
            resultados_fuentes
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
                post["key"],
                post["source"],
                post["url"]
            )


        if not candidatos:

            print(
                "No se encontraron publicaciones."
            )

            await browser.close()

            return


        # =================================================
        # TOMAR LAS PRIMERAS 2 DISTINTAS
        # =================================================

        seleccionados = candidatos[
            :MAX_POSTS
        ]


        print("")
        print(
            "SELECCIONADOS:",
            len(seleccionados)
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

                post = await procesar_post(
                    context,
                    datos,
                    posicion
                )


                resultado.append(
                    post
                )


            except Exception as e:

                print(
                    "ERROR POST",
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
                "No se procesó ninguna publicación."
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


asyncio.run(
    main()
)
