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

    # quitar parámetros innecesarios
    try:
        if "?" in href and "story_fbid=" not in href:
            href = href.split("?")[0]
    except:
        pass

    return href


# =========================================================
# EXTRAER TIMESTAMP DESDE URL
# =========================================================

def timestamp_desde_url(url):
    if not url:
        return 0

    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        if "story_fbid" in qs:
            valor = qs["story_fbid"][0]

            # Facebook IDs grandes pueden contener timestamp parcial,
            # pero no siempre es confiable.
            # Por eso solo se usa como fallback.
            if valor.isdigit():
                return int(valor[-10:])

    except:
        pass

    return 0


# =========================================================
# EXTRAER FECHA DE UN ARTÍCULO
# =========================================================

async def extraer_fecha_articulo(articulo):
    candidatos = []

    # time tag
    try:
        times = articulo.locator("time")

        for i in range(await times.count()):
            try:
                dt = await times.nth(i).get_attribute("datetime")

                if dt:
                    candidatos.append(dt)
            except:
                pass
    except:
        pass

    # abbr tag
    try:
        abbrs = articulo.locator("abbr")

        for i in range(await abbrs.count()):
            try:
                data_utime = await abbrs.nth(i).get_attribute("data-utime")

                if data_utime and data_utime.isdigit():
                    return int(data_utime)

                title = await abbrs.nth(i).get_attribute("title")

                if title:
                    candidatos.append(title)
            except:
                pass
    except:
        pass

    # aria-label y title de enlaces
    try:
        links = articulo.locator("a")

        for i in range(await links.count()):
            try:
                aria = await links.nth(i).get_attribute("aria-label")
                title = await links.nth(i).get_attribute("title")

                if aria:
                    candidatos.append(aria)

                if title:
                    candidatos.append(title)
            except:
                pass
    except:
        pass

    # intentar timestamp en atributos
    try:
        html = await articulo.inner_html()

        matches = re.findall(
            r'(?:"timestamp"|data-utime)[^0-9]{0,20}([0-9]{10})',
            html
        )

        if matches:
            return max(int(x) for x in matches)

    except:
        pass

    # si no encontramos timestamp real, retornamos 0
    return 0


# =========================================================
# DETECTAR SI ESTÁ FIJADA
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
# BUSCAR POSTS CANDIDATOS
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

        fecha = await extraer_fecha_articulo(articulo)

        for url in urls:
            candidatos.append({
                "url": url,
                "timestamp": fecha,
                "fijada": fijada,
                "indice": i
            })

    return candidatos


# =========================================================
# ELEGIR MÁS RECIENTE
# =========================================================

def elegir_mas_reciente(candidatos):
    if not candidatos:
        return None

    # primero descartamos fijadas si hay otras
    no_fijadas = [
        c for c in candidatos
        if not c["fijada"]
    ]

    if no_fijadas:
        candidatos = no_fijadas

    # si tenemos timestamps reales
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

    # fallback:
    # asumimos que Facebook devuelve artículos recientes primero
    candidatos.sort(
        key=lambda x: x["indice"]
    )

    return candidatos[0]


# =========================================================
# EXPANDIR VER MÁS
# =========================================================

async def expandir_ver_mas(page):
    for _ in range(5):
        encontrado = False

        elementos = page.locator(
            'div[role="button"], span[role="button"], span, div'
        )

        cantidad = await elementos.count()

        for i in range(min(cantidad, 500)):
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
                        await el.evaluate("e => e.click()")

                        await page.wait_for_timeout(1200)

                        encontrado = True

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

                    const tag = child.tagName.toLowerCase();

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

    texto = texto.replace("... Ver más", "")
    texto = texto.replace("Ver más", "")

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# =========================================================
# DESCRIPCIÓN
# =========================================================

async def obtener_descripcion(page):
    try:
        mensajes = page.locator(
            '[data-ad-preview="message"]'
        )

        candidatos = []

        for i in range(await mensajes.count()):
            texto = await texto_con_emojis(
                mensajes.nth(i)
            )

            if texto:
                candidatos.append(texto)

        if candidatos:
            return limpiar_texto(
                max(candidatos, key=len)
            )

    except:
        pass

    # fallback
    try:
        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():
            texto = await meta.first.get_attribute(
                "content"
            )

            if texto:
                return limpiar_texto(texto)

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

                    for (const item of srcset.split(",")) {

                        const partes =
                            item.trim().split(/\\s+/);

                        const url =
                            partes[0];

                        const size =
                            parseInt(partes[1]) || 0;

                        opciones.push({
                            url: url,
                            score: size * size
                        });
                    }
                }

                opciones.sort(
                    (a,b) => b.score - a.score
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
                datos["width"]
                *
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
        respuesta = await context.request.get(url)

        if respuesta.ok:
            contenido = await respuesta.body()

            with open(
                ruta,
                "wb"
            ) as archivo:
                archivo.write(contenido)

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

        page = await context.new_page()

        print("Abriendo Facebook...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(10000)

        # hacer pequeños scrolls para que cargue publicaciones
        for _ in range(4):
            await page.mouse.wheel(
                0,
                1000
            )

            await page.wait_for_timeout(
                1500
            )

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
                "No se encontró ninguna publicación."
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

        # =====================================================
        # ABRIR PUBLICACIÓN INDIVIDUAL
        # =====================================================

        post_page = await context.new_page()

        await post_page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await post_page.wait_for_timeout(
            8000
        )

        await expandir_ver_mas(
            post_page
        )

        await post_page.wait_for_timeout(
            1500
        )

        descripcion = await obtener_descripcion(
            post_page
        )

        likes, comentarios, compartidos = (
            await obtener_metricas(
                post_page
            )
        )

        imagen_url = await obtener_mejor_imagen(
            post_page
        )

        imagen_final = ""

        if imagen_url:
            imagen_final = await descargar_imagen(
                context,
                imagen_url
            )

        # si es Reel y no hay texto, dejamos al menos algo
        if not descripcion:

            if "/reel/" in post_url or "/reels/" in post_url:
                descripcion = "Reel reciente de Super Farmacia"
            else:
                descripcion = "Publicación reciente de Super Farmacia"

        await post_page.close()
        await browser.close()

        resultado = [
            {
                "text": descripcion,
                "image": imagen_final,
                "url": post_url,
                "date": "Publicación reciente",
                "likes": likes,
                "comments_count": comentarios,
                "shares": compartidos,
                "scraped_at": datetime.now(
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
