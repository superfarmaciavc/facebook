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

    if not any(
        p in href
        for p in patrones
    ):
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
# ELEGIR URL PRINCIPAL
# =========================================================

def elegir_url_articulo(urls):

    if not urls:
        return None

    for url in urls:
        if (
            "/reel/" in url
            or "/reels/" in url
        ):
            return url.split("?")[0]

    for url in urls:
        if "/videos/" in url:
            return url.split("?")[0]

    for url in urls:
        if "/posts/" in url:
            return url.split("?")[0]

    for url in urls:
        if "story_fbid=" in url:
            return url

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
# DESCRIPCIÓN ARTÍCULO
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
# MÉTRICAS ARTÍCULO
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
                    x =>
                        x.getAttribute(
                            "title"
                        )
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
            r"([\d.,KkMm]+)\s+comment"
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
            r"([\d.,KkMm]+)\s+share"
        ]
    )


    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# CAPTURAR POSTS PROGRESIVAMENTE
# =========================================================

async def capturar_posts_progresivamente(
    page,
    limite=2
):

    capturados = []
    urls_vistas = set()

    for intento in range(12):

        print(
            f"Escaneo {intento + 1}"
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


        for i in range(cantidad):

            if len(capturados) >= limite:
                return capturados


            articulo = articulos.nth(i)


            try:
                fijado = await esta_fijada(
                    articulo
                )

                if fijado:
                    continue
            except:
                pass


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


            # Normalizar para deduplicar mejor
            clave_url = (
                url_principal
                .split("&")[0]
                .rstrip("/")
            )


            if clave_url in urls_vistas:
                continue


            print(
                "Nueva publicación encontrada:",
                url_principal
            )


            await articulo.scroll_into_view_if_needed()

            await page.wait_for_timeout(
                800
            )


            await expandir_ver_mas_articulo(
                articulo
            )


            await page.wait_for_timeout(
                1200
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

                "text":
                    descripcion,

                "likes":
                    likes,

                "comments_count":
                    comentarios,

                "shares":
                    compartidos,

                "timestamp":
                    timestamp
            })


            urls_vistas.add(
                clave_url
            )


            print(
                "Capturados:",
                len(capturados)
            )


            if len(capturados) >= limite:
                return capturados


        # Scroll para cargar siguiente contenido
        await page.mouse.wheel(
            0,
            1200
        )

        await page.wait_for_timeout(
            2000
        )


    return capturados


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
            "\\n" + aria
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
            resultado.append(a)

        else:
            resultado.append(b)

    return tuple(resultado)


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
# VIDEO
# =========================================================

async def obtener_video(page):

    candidatos = []


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
                        "url": url,
                        "area":
                            datos["width"]
                            *
                            datos["height"]
                    })

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

                    candidatos.append({
                        "url": url,
                        "area": 1
                    })

        except:
            pass


    if not candidatos:
        return ""


    candidatos.sort(
        key=lambda x:
            x["area"],
        reverse=True
    )


    return candidatos[0]["url"]


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
        respuesta = (
            await context.request.get(
                url,
                timeout=120000
            )
        )


        if not respuesta.ok:
            return ""


        contenido = (
            await respuesta.body()
        )


        if len(contenido) < 100000:
            return ""


        with open(
            ruta,
            "wb"
        ) as archivo:

            archivo.write(
                contenido
            )


        return ruta

    except Exception as e:

        print(
            "Error video:",
            e
        )


    return ""


# =========================================================
# PROCESAR POST CAPTURADO
# =========================================================

async def procesar_post(
    context,
    datos,
    posicion
):

    post_url = datos["url"]


    print("")
    print(
        f"Procesando post {posicion}:"
    )
    print(
        post_url
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


    descripcion = (
        datos["text"]
    )


    if not descripcion:

        descripcion = (
            await descripcion_fallback(
                post_page
            )
        )


    metricas_fallback = (
        await obtener_metricas_fallback(
            post_page
        )
    )


    metricas = combinar_metricas(

        (
            datos["likes"],
            datos["comments_count"],
            datos["shares"]
        ),

        metricas_fallback

    )


    (
        likes,
        comentarios,
        compartidos
    ) = metricas


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


    if es_video_url(
        post_url
    ):

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

        "timestamp":
            datos["timestamp"],

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


        # =================================================
        # CAPTURAR 2 POSTS
        # =================================================

        capturados = (
            await capturar_posts_progresivamente(
                page,
                MAX_POSTS
            )
        )


        print("")
        print(
            "===================================="
        )
        print(
            "POSTS CAPTURADOS:",
            len(capturados)
        )
        print(
            "===================================="
        )


        for i, post in enumerate(
            capturados,
            start=1
        ):

            print(
                i,
                post["url"]
            )


        if not capturados:

            await browser.close()

            return


        # =================================================
        # ORDENAR POR FECHA SI EXISTE
        # =================================================

        con_fecha = [
            x
            for x in capturados
            if x["timestamp"] > 0
        ]


        if len(con_fecha) == len(
            capturados
        ):

            capturados.sort(
                key=lambda x:
                    x["timestamp"],
                reverse=True
            )


        # =================================================
        # PROCESAR AMBOS
        # =================================================

        resultado = []


        for posicion, datos in enumerate(
            capturados[:MAX_POSTS],
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
                    f"Error post {posicion}:",
                    e
                )


        await page.close()

        await browser.close()


        # =================================================
        # GUARDAR JSON
        # =================================================

        if not resultado:

            print(
                "No se pudo procesar ningún post."
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
            "posts.json actualizado."
        )
        print(
            "Cantidad:",
            len(resultado)
        )
        print(
            "===================================="
        )


        if len(resultado) < MAX_POSTS:

            print(
                "ADVERTENCIA:"
            )

            print(
                "Facebook solo permitió obtener",
                len(resultado),
                "publicación(es)."
            )


asyncio.run(
    main()
)
