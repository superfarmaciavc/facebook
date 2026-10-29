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

# Queremos mostrar las últimas 3 publicaciones
MAX_POSTS = 3

# Revisamos varias publicaciones para evitar fijadas o antiguas
MAX_CANDIDATOS = 12

# Cada publicación se mostrará 30 segundos
DURACION_POST = 30


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
# CLAVE ÚNICA DEL POST
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

                for(const child of node.childNodes){

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
# DETECTAR PUBLICACIÓN FIJADA
# =========================================================

async def es_publicacion_fijada(
    articulo
):

    try:

        texto = (
            await articulo.inner_text()
        ).lower()

        patrones = [
            "publicación fijada",
            "publicacion fijada",
            "post fijado",
            "fijado",
            "pinned post",
            "pinned"
        ]

        if any(
            x in texto
            for x in patrones
        ):

            return True

    except:

        pass

    try:

        aria = (
            await articulo
            .locator("[aria-label]")
            .evaluate_all("""
            els =>
                els
                .map(
                    e =>
                        e.getAttribute("aria-label")
                        ||
                        ""
                )
                .join("\\n")
                .toLowerCase()
            """)
        )

        if (
            "fijad" in aria
            or
            "pinned" in aria
        ):

            return True

    except:

        pass

    return False


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
# OBTENER DESCRIPCIÓN
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
# OBTENER FECHA / TIMESTAMP
# =========================================================

async def obtener_timestamp_articulo(
    articulo
):

    # -----------------------------------------------------
    # Intentar data-utime
    # -----------------------------------------------------

    try:

        elementos = articulo.locator(
            "[data-utime]"
        )

        cantidad = (
            await elementos.count()
        )

        for i in range(
            cantidad
        ):

            valor = (
                await elementos
                .nth(i)
                .get_attribute(
                    "data-utime"
                )
            )

            if valor:

                try:

                    timestamp = int(
                        valor
                    )

                    if timestamp > 1000000000:

                        return timestamp

                except:

                    pass

    except:

        pass

    # -----------------------------------------------------
    # Intentar etiqueta time
    # -----------------------------------------------------

    try:

        tiempos = articulo.locator(
            "time[datetime]"
        )

        if await tiempos.count():

            valor = (
                await tiempos
                .first
                .get_attribute(
                    "datetime"
                )
            )

            if valor:

                try:

                    fecha = datetime.fromisoformat(
                        valor.replace(
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

    # Si Facebook no entrega timestamp,
    # dejamos 0 y respetaremos el orden del muro.
    return 0


# =========================================================
# MEJOR IMAGEN DESDE EL ARTÍCULO
# =========================================================

async def obtener_mejor_imagen_articulo(
    articulo
):

    candidatos = []

    try:

        imagenes = articulo.locator(
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
                            0,

                        alt:
                            img.alt
                            ||
                            ""
                    })
                    """)
                )

                url = datos.get(
                    "url",
                    ""
                )

                width = datos.get(
                    "width",
                    0
                )

                height = datos.get(
                    "height",
                    0
                )

                alt = (
                    datos.get(
                        "alt",
                        ""
                    )
                    or
                    ""
                ).lower()

                if not url:
                    continue

                if width < 350:
                    continue

                if height < 250:
                    continue

                if any(
                    x in alt
                    for x in [
                        "foto del perfil",
                        "profile picture",
                        "emoji"
                    ]
                ):

                    continue

                candidatos.append(
                    (
                        width * height,
                        url
                    )
                )

            except:

                pass

    except:

        pass

    if not candidatos:

        return ""

    candidatos.sort(
        key=lambda x:
            x[0],
        reverse=True
    )

    return candidatos[0][1]


# =========================================================
# OBTENER VIDEO DESDE EL ARTÍCULO
# =========================================================

async def obtener_video_articulo(
    articulo
):

    candidatos = []

    try:

        videos = articulo.locator(
            "video"
        )

        for i in range(
            await videos.count()
        ):

            try:

                datos = (
                    await videos
                    .nth(i)
                    .evaluate("""
                    v => ({
                        currentSrc:
                            v.currentSrc
                            ||
                            "",

                        src:
                            v.src
                            ||
                            "",

                        width:
                            v.videoWidth
                            ||
                            0,

                        height:
                            v.videoHeight
                            ||
                            0
                    })
                    """)
                )

                for url in [
                    datos.get(
                        "currentSrc",
                        ""
                    ),
                    datos.get(
                        "src",
                        ""
                    )
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
                                datos.get(
                                    "width",
                                    0
                                )
                                *
                                datos.get(
                                    "height",
                                    0
                                ),
                                url
                            )
                        )

            except:

                pass

    except:

        pass

    try:

        sources = articulo.locator(
            "video source"
        )

        for i in range(
            await sources.count()
        ):

            try:

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

    except:

        pass

    if not candidatos:

        return ""

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
# DESCARGAR ARCHIVOS
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
# DESCUBRIR PUBLICACIONES DESDE EL MURO
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

    orden_descubrimiento = 0

    # Revisamos varios scrolls
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

        for i in range(
            cantidad
        ):

            articulo = articulos.nth(i)

            # -------------------------------------------------
            # IGNORAR PUBLICACIONES FIJADAS
            # -------------------------------------------------

            if await es_publicacion_fijada(
                articulo
            ):

                print(
                    "Publicación fijada ignorada."
                )

                continue

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
                "Nueva publicación encontrada:",
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

            timestamp = (
                await obtener_timestamp_articulo(
                    articulo
                )
            )

            imagen_url = (
                await obtener_mejor_imagen_articulo(
                    articulo
                )
            )

            video_url = (
                await obtener_video_articulo(
                    articulo
                )
            )

            orden_descubrimiento += 1

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

                "image_url":
                    imagen_url,

                "video_url":
                    video_url,

                "timestamp":
                    timestamp,

                "order":
                    orden_descubrimiento,

                "source":
                    "article"

            })

            claves.add(
                clave
            )

            if (
                len(encontrados)
                >=
                MAX_CANDIDATOS
            ):
                break

        if (
            len(encontrados)
            >=
            MAX_CANDIDATOS
        ):
            break

        # Scroll para cargar más publicaciones
        try:

            await page.evaluate("""
            () => {

                window.scrollBy(
                    0,
                    Math.max(
                        1200,
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
        "CANDIDATOS ENCONTRADOS:",
        len(encontrados)
    )

    print(
        "========================================"
    )

    # =====================================================
    # ORDENAR POR FECHA
    # =====================================================

    # Los que tienen timestamp real se ordenan por fecha.
    # Si Facebook no entrega timestamp, se respeta
    # el orden natural en que aparecen en el muro.

    con_fecha = [
        post
        for post in encontrados
        if post["timestamp"] > 0
    ]

    sin_fecha = [
        post
        for post in encontrados
        if post["timestamp"] == 0
    ]

    con_fecha.sort(
        key=lambda x:
            x["timestamp"],
        reverse=True
    )

    sin_fecha.sort(
        key=lambda x:
            x["order"]
    )

    if con_fecha:

        ordenados = (
            con_fecha
            +
            sin_fecha
        )

    else:

        ordenados = sin_fecha

    # Solo las últimas 3
    resultado = (
        ordenados[:MAX_POSTS]
    )

    print("")
    print(
        "========================================"
    )

    print(
        "PUBLICACIONES SELECCIONADAS:",
        len(resultado)
    )

    print(
        "========================================"
    )

    for i, post in enumerate(
        resultado,
        start=1
    ):

        print(
            i,
            post["key"],
            post["url"]
        )

    return resultado


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
        posicion,
        "DESDE EL MURO"
    )

    print(
        url
    )

    print(
        "========================================"
    )

    descripcion = limpiar_texto(
        datos.get(
            "text",
            ""
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

    os.makedirs(
        "posts",
        exist_ok=True
    )

    # =====================================================
    # IMAGEN
    # =====================================================

    imagen = ""

    imagen_url = datos.get(
        "image_url",
        ""
    )

    if imagen_url:

        imagen = (
            await descargar(
                context,
                imagen_url,
                f"posts/post_{posicion}.jpg",
                minimo=5000
            )
        )

    # =====================================================
    # VIDEO
    # =====================================================

    video = ""

    video_url = datos.get(
        "video_url",
        ""
    )

    if video_url:

        print(
            "Video detectado directamente en el muro."
        )

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

    else:

        tipo = "image"

    timestamp = datos.get(
        "timestamp",
        0
    )

    fecha_texto = (
        "Publicación reciente"
    )

    if timestamp:

        try:

            fecha_texto = (
                datetime
                .fromtimestamp(
                    timestamp,
                    timezone.utc
                )
                .isoformat()
            )

        except:

            pass

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
            url,

        "date":
            fecha_texto,

        "timestamp":
            timestamp,

        # MUY IMPORTANTE:
        # la página debe mostrar este post 30 segundos
        "duration":
            DURACION_POST,

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

        if not resultado:

            print(
                "No se pudo procesar ninguna publicación."
            )

            return

        # =================================================
        # GUARDAR POSTS.JSON
        # =================================================

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
            "Duración por publicación:",
            DURACION_POST,
            "segundos"
        )

        print(
            "Duración total del ciclo:",
            len(resultado)
            *
            DURACION_POST,
            "segundos"
        )

        print(
            "========================================"
        )


asyncio.run(
    main()
)
