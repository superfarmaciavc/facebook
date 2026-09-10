import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

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

    # Quitar parámetros innecesarios
    try:
        if "?" in href and "story_fbid=" not in href:
            href = href.split("?")[0]
    except:
        pass

    return href


# =========================================================
# DETECTAR POST FIJADO
# =========================================================

async def esta_fijada(articulo):
    try:
        texto = (await articulo.inner_text()).lower()

        indicadores = [
            "publicación fijada",
            "publicacion fijada",
            "pinned post",
            "fijado"
        ]

        return any(x in texto for x in indicadores)

    except:
        return False


# =========================================================
# EXTRAER TIMESTAMP
# =========================================================

async def extraer_timestamp_articulo(articulo):
    # 1. data-utime
    try:
        abbrs = articulo.locator("abbr")

        for i in range(await abbrs.count()):
            try:
                valor = await abbrs.nth(i).get_attribute("data-utime")

                if valor and valor.isdigit():
                    return int(valor)
            except:
                pass
    except:
        pass

    # 2. time datetime
    try:
        times = articulo.locator("time")

        for i in range(await times.count()):
            try:
                dt = await times.nth(i).get_attribute("datetime")

                if dt:
                    parsed = datetime.fromisoformat(
                        dt.replace("Z", "+00:00")
                    )

                    return int(parsed.timestamp())
            except:
                pass
    except:
        pass

    # 3. buscar timestamps dentro del HTML
    try:
        html = await articulo.inner_html()

        matches = re.findall(
            r'(?:"timestamp"|data-utime)[^0-9]{0,30}([0-9]{10})',
            html
        )

        if matches:
            return max(int(x) for x in matches)

    except:
        pass

    return 0


# =========================================================
# OBTENER CANDIDATOS
# =========================================================

async def obtener_candidatos(page):
    articulos = page.locator('[role="article"]')

    cantidad = await articulos.count()

    print("Artículos encontrados:", cantidad)

    candidatos = []

    for i in range(min(cantidad, 20)):
        articulo = articulos.nth(i)

        try:
            fijada = await esta_fijada(articulo)
        except:
            fijada = False

        try:
            timestamp = await extraer_timestamp_articulo(
                articulo
            )
        except:
            timestamp = 0

        links = articulo.locator("a")

        urls = []

        for j in range(await links.count()):
            try:
                href = await links.nth(j).get_attribute("href")

                url = normalizar_url(href)

                if url and url not in urls:
                    urls.append(url)

            except:
                pass

        if not urls:
            continue

        for url in urls:
            candidatos.append({
                "url": url,
                "timestamp": timestamp,
                "fijada": fijada,
                "indice": i
            })

    return candidatos


# =========================================================
# ELEGIR EL MÁS RECIENTE
# =========================================================

def elegir_mas_reciente(candidatos):
    if not candidatos:
        return None

    # Preferir no fijados
    no_fijados = [
        c for c in candidatos
        if not c["fijada"]
    ]

    if no_fijados:
        candidatos = no_fijados

    # Si existen timestamps válidos
    con_fecha = [
        c for c in candidatos
        if c["timestamp"] > 0
    ]

    if con_fecha:
        con_fecha.sort(
            key=lambda x: x["timestamp"],
            reverse=True
        )

        return con_fecha[0]

    # Fallback: primer artículo visible
    candidatos.sort(
        key=lambda x: x["indice"]
    )

    return candidatos[0]


# =========================================================
# EXPANDIR "VER MÁS"
# =========================================================

async def expandir_ver_mas(page):
    await page.wait_for_timeout(2000)

    # Primero intentar dentro del mensaje del post
    try:
        mensajes = page.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        print(
            "Bloques de mensaje encontrados:",
            cantidad
        )

        for i in range(cantidad):
            mensaje = mensajes.nth(i)

            try:
                botones = mensaje.get_by_text(
                    re.compile(
                        r"^\s*(Ver más|See more)\s*$",
                        re.IGNORECASE
                    )
                )

                for j in range(await botones.count()):
                    boton = botones.nth(j)

                    if await boton.is_visible():
                        print("Expandiendo descripción...")

                        await boton.click(
                            force=True,
                            timeout=5000
                        )

                        await page.wait_for_timeout(
                            1500
                        )

            except:
                pass

    except:
        pass

    # Segundo intento global
    try:
        elementos = page.locator(
            'div[role="button"], span[role="button"]'
        )

        cantidad = await elementos.count()

        for i in range(min(cantidad, 300)):
            try:
                el = elementos.nth(i)

                texto = (
                    await el.inner_text()
                ).strip().lower()

                if texto in [
                    "ver más",
                    "see more"
                ]:
                    if await el.is_visible():
                        print(
                            "Expandiendo descripción por método alternativo..."
                        )

                        await el.click(
                            force=True,
                            timeout=5000
                        )

                        await page.wait_for_timeout(
                            1500
                        )

            except:
                pass

    except:
        pass


# =========================================================
# TEXTO CON EMOJIS
# =========================================================

async def texto_con_emojis(locator):
    try:
        return await locator.evaluate("""
        element => {

            function leer(node) {

                let salida = "";

                for (const child of node.childNodes) {

                    if (child.nodeType === Node.TEXT_NODE) {
                        salida += child.textContent || "";
                        continue;
                    }

                    if (child.nodeType !== Node.ELEMENT_NODE) {
                        continue;
                    }

                    const tag =
                        child.tagName.toLowerCase();

                    if (tag === "br") {
                        salida += "\\n";
                        continue;
                    }

                    if (tag === "img") {

                        salida +=
                            child.getAttribute("alt") ||
                            child.getAttribute("aria-label") ||
                            child.getAttribute("title") ||
                            "";

                        continue;
                    }

                    const aria =
                        child.getAttribute("aria-label");

                    if (
                        aria &&
                        aria.length <= 30 &&
                        /[^a-zA-Z0-9\\s]/u.test(aria)
                    ) {
                        salida += aria;
                        continue;
                    }

                    salida += leer(child);

                    if (
                        tag === "div" ||
                        tag === "p"
                    ) {
                        salida += "\\n";
                    }
                }

                return salida;
            }

            return leer(element)
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

    texto = texto.replace(
        "... Ver más",
        ""
    )

    texto = texto.replace(
        "Ver más",
        ""
    )

    texto = texto.replace(
        "See more",
        ""
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# =========================================================
# OBTENER DESCRIPCIÓN COMPLETA
# =========================================================

async def obtener_descripcion(page):
    candidatos = []

    # -----------------------------------------------------
    # MÉTODO 1: data-ad-preview="message"
    # -----------------------------------------------------

    try:
        mensajes = page.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        print(
            "Mensajes encontrados:",
            cantidad
        )

        for i in range(cantidad):
            try:
                texto = await texto_con_emojis(
                    mensajes.nth(i)
                )

                texto = limpiar_texto(
                    texto
                )

                if texto:
                    candidatos.append(texto)

            except:
                pass

    except:
        pass

    # -----------------------------------------------------
    # MÉTODO 2: bloques dir="auto"
    # -----------------------------------------------------

    try:
        bloques = page.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        for i in range(
            min(cantidad, 300)
        ):
            try:
                texto = await texto_con_emojis(
                    bloques.nth(i)
                )

                texto = limpiar_texto(
                    texto
                )

                if len(texto) < 30:
                    continue

                texto_lower = texto.lower()

                basura = [
                    "iniciar sesión",
                    "crear cuenta",
                    "me gusta",
                    "comentar",
                    "compartir",
                    "todas las reacciones",
                    "más relevantes"
                ]

                if any(
                    x in texto_lower
                    for x in basura
                ):
                    continue

                candidatos.append(texto)

            except:
                pass

    except:
        pass

    # -----------------------------------------------------
    # DEVOLVER EL TEXTO MÁS LARGO
    # -----------------------------------------------------

    if candidatos:
        descripcion = max(
            candidatos,
            key=len
        )

        print(
            "Descripción seleccionada:"
        )

        print(descripcion)

        return descripcion

    # -----------------------------------------------------
    # FALLBACK: OG DESCRIPTION
    # -----------------------------------------------------

    try:
        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():
            texto = await meta.first.get_attribute(
                "content"
            )

            if texto:
                print(
                    "Usando og:description como último recurso."
                )

                return limpiar_texto(
                    texto
                )

    except:
        pass

    return ""


# =========================================================
# OBTENER MEJOR IMAGEN
# =========================================================

async def obtener_mejor_imagen(page):
    candidatos = []

    imagenes = page.locator("img")

    cantidad = await imagenes.count()

    for i in range(cantidad):
        try:
            datos = await imagenes.nth(i).evaluate("""
            img => {

                let opciones = [];

                if (img.currentSrc) {
                    opciones.push({
                        url: img.currentSrc,
                        score:
                            (img.naturalWidth || 0) *
                            (img.naturalHeight || 0)
                    });
                }

                if (img.src) {
                    opciones.push({
                        url: img.src,
                        score:
                            (img.naturalWidth || 0) *
                            (img.naturalHeight || 0)
                    });
                }

                const srcset =
                    img.getAttribute("srcset");

                if (srcset) {

                    srcset
                    .split(",")
                    .forEach(item => {

                        const partes =
                            item.trim().split(/\\s+/);

                        const size =
                            parseInt(partes[1]) || 0;

                        opciones.push({
                            url: partes[0],
                            score: size * size
                        });
                    });
                }

                opciones.sort(
                    (a,b) =>
                    b.score - a.score
                );

                return {
                    src:
                        opciones.length
                        ? opciones[0].url
                        : "",

                    width:
                        img.naturalWidth || 0,

                    height:
                        img.naturalHeight || 0
                };
            }
            """)

            if not datos["src"]:
                continue

            if datos["width"] < 500:
                continue

            if datos["height"] < 350:
                continue

            area = (
                datos["width"] *
                datos["height"]
            )

            candidatos.append(
                (
                    area,
                    datos["src"]
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

    # fallback og:image
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

async def descargar_imagen(context, url):
    if not url:
        return ""

    os.makedirs(
        "posts",
        exist_ok=True
    )

    ruta = "posts/ultima_publicacion.jpg"

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

def extraer_numero(texto, patrones):
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
        # ABRIR PÁGINA DE FACEBOOK
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

        # cargar algunos posts
        for _ in range(4):

            await page.mouse.wheel(
                0,
                1000
            )

            await page.wait_for_timeout(
                1500
            )

        # regresar arriba
        await page.mouse.wheel(
            0,
            -5000
        )

        await page.wait_for_timeout(
            1500
        )

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

        post_url = elegido["url"]

        print(
            "Publicación elegida:",
            post_url
        )

        print(
            "Timestamp:",
            elegido["timestamp"]
        )

        await page.close()

        # =================================================
        # ABRIR POST INDIVIDUAL
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

        # =================================================
        # EXPANDIR TEXTO
        # =================================================

        await expandir_ver_mas(
            post_page
        )

        await post_page.wait_for_timeout(
            2000
        )

        # =================================================
        # DESCRIPCIÓN
        # =================================================

        descripcion = await obtener_descripcion(
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

        # =================================================
        # FALLBACK DE TEXTO
        # =================================================

        if not descripcion:

            if (
                "/reel/" in post_url
                or
                "/reels/" in post_url
            ):
                descripcion = (
                    "Reel reciente de Super Farmacia"
                )

            else:
                descripcion = (
                    "Publicación reciente de Super Farmacia"
                )

        await post_page.close()

        await browser.close()

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

        print(
            "posts.json actualizado correctamente."
        )


asyncio.run(main())
