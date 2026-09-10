import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


def normalizar_link(href):
    if not href:
        return None

    if href.startswith("/"):
        href = urljoin("https://www.facebook.com", href)

    patrones = [
        "/posts/",
        "/photos/",
        "/videos/",
        "story_fbid="
    ]

    if not any(p in href for p in patrones):
        return None

    return href


async def obtener_ultimo_post(page):
    articulos = page.locator('[role="article"]')
    cantidad = await articulos.count()

    for i in range(min(cantidad, 8)):
        articulo = articulos.nth(i)
        links = articulo.locator("a")

        for j in range(await links.count()):
            try:
                href = await links.nth(j).get_attribute("href")
                url = normalizar_link(href)

                if url:
                    return url
            except:
                pass

    return None


async def expandir_ver_mas(page):
    for _ in range(5):
        encontrado = False

        try:
            elementos = page.locator(
                'div[role="button"], span[role="button"], span, div'
            )

            cantidad = await elementos.count()

            for i in range(min(cantidad, 500)):
                try:
                    el = elementos.nth(i)
                    texto = (await el.inner_text()).strip()

                    if texto.lower() in ["ver más", "see more"]:
                        if await el.is_visible():
                            await el.evaluate("e => e.click()")
                            await page.wait_for_timeout(1500)
                            encontrado = True
                except:
                    pass
        except:
            pass

        if not encontrado:
            break


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

                    if (tag === "div" || tag === "p") {
                        salida += "\\n";
                    }
                }

                return salida;
            }

            return leer(element)
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)
    except:
        return ""


async def obtener_descripcion(page):
    try:
        mensajes = page.locator('[data-ad-preview="message"]')

        candidatos = []

        for i in range(await mensajes.count()):
            texto = await texto_con_emojis(mensajes.nth(i))

            if texto:
                candidatos.append(texto)

        if candidatos:
            texto = max(candidatos, key=len)

            return (
                texto
                .replace("... Ver más", "")
                .replace("Ver más", "")
                .strip()
            )
    except:
        pass

    return ""


async def abrir_foto_principal(page):
    """
    Busca la imagen grande del post y hace clic para abrir el visor.
    """

    imagenes = page.locator("img")
    candidatas = []

    for i in range(await imagenes.count()):
        try:
            datos = await imagenes.nth(i).evaluate("""
            img => ({
                width: img.naturalWidth || 0,
                height: img.naturalHeight || 0,
                area:
                    (img.naturalWidth || 0) *
                    (img.naturalHeight || 0)
            })
            """)

            if datos["width"] < 500:
                continue

            if datos["height"] < 350:
                continue

            candidatas.append(
                (datos["area"], i)
            )

        except:
            pass

    if not candidatas:
        return False

    candidatas.sort(reverse=True)

    indice = candidatas[0][1]

    try:
        imagen = imagenes.nth(indice)

        await imagen.scroll_into_view_if_needed()

        await page.wait_for_timeout(500)

        await imagen.click(
            timeout=5000,
            force=True
        )

        await page.wait_for_timeout(3000)

        return True

    except:
        return False


async def obtener_imagen_del_visor(page):
    """
    Una vez abierto el visor, busca la imagen
    de mayor resolución disponible.
    """

    candidatos = []

    # Primero revisar src/srcset en las imágenes visibles
    imagenes = page.locator("img")

    for i in range(await imagenes.count()):
        try:
            datos = await imagenes.nth(i).evaluate("""
            img => {

                let mejor = img.currentSrc || img.src || "";

                const srcset = img.getAttribute("srcset");

                if (srcset) {
                    const opciones =
                        srcset
                        .split(",")
                        .map(x => x.trim())
                        .map(x => {
                            const partes = x.split(/\\s+/);

                            return {
                                url: partes[0],
                                size: parseInt(partes[1]) || 0
                            };
                        })
                        .sort((a,b) => b.size - a.size);

                    if (opciones.length) {
                        mejor = opciones[0].url;
                    }
                }

                const r = img.getBoundingClientRect();

                return {
                    src: mejor,
                    width: img.naturalWidth || 0,
                    height: img.naturalHeight || 0,
                    visible:
                        r.width > 300 &&
                        r.height > 250 &&
                        r.top < window.innerHeight &&
                        r.bottom > 0
                };
            }
            """)

            if not datos["src"]:
                continue

            if not datos["visible"]:
                continue

            if datos["width"] < 700:
                continue

            if datos["height"] < 500:
                continue

            area = datos["width"] * datos["height"]

            candidatos.append(
                (area, datos["src"])
            )

        except:
            pass

    if candidatos:
        candidatos.sort(
            key=lambda x: x[0],
            reverse=True
        )

        print("Imagen encontrada desde el visor.")
        return candidatos[0][1]

    # Fallback a og:image
    try:
        og = page.locator('meta[property="og:image"]')

        if await og.count():
            src = await og.first.get_attribute("content")

            if src:
                return src
    except:
        pass

    return ""


async def descargar_imagen(context, url):
    os.makedirs("posts", exist_ok=True)

    ruta = "posts/ultima_publicacion.jpg"

    try:
        respuesta = await context.request.get(url)

        if respuesta.ok:
            contenido = await respuesta.body()

            with open(ruta, "wb") as archivo:
                archivo.write(contenido)

            print("Imagen guardada:", ruta)

            return ruta

    except Exception as e:
        print("Error descargando imagen:", e)

    return url


def extraer_numero(texto, patrones):
    for patron in patrones:
        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return "—"


async def obtener_metricas(page):
    try:
        texto = await page.locator("body").inner_text()
    except:
        texto = ""

    likes = extraer_numero(
        texto,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones"
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
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido"
        ]
    )

    return likes, comentarios, compartidos


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
            locale="es-ES"
        )

        # -------------------------------------------------
        # ABRIR FACEBOOK
        # -------------------------------------------------

        page = await context.new_page()

        print("Abriendo Facebook...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(10000)

        # -------------------------------------------------
        # ENCONTRAR ÚLTIMO POST
        # -------------------------------------------------

        post_url = await obtener_ultimo_post(page)

        if not post_url:
            print("No se encontró el último post.")
            await browser.close()
            return

        await page.close()

        # -------------------------------------------------
        # ABRIR POST
        # -------------------------------------------------

        post_page = await context.new_page()

        print("Abriendo publicación...")

        await post_page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await post_page.wait_for_timeout(8000)

        # -------------------------------------------------
        # EXPANDIR DESCRIPCIÓN
        # -------------------------------------------------

        await expandir_ver_mas(post_page)

        await post_page.wait_for_timeout(1500)

        descripcion = await obtener_descripcion(
            post_page
        )

        # -------------------------------------------------
        # MÉTRICAS
        # -------------------------------------------------

        likes, comentarios, compartidos = (
            await obtener_metricas(post_page)
        )

        # -------------------------------------------------
        # ABRIR FOTO PRINCIPAL
        # -------------------------------------------------

        print("Abriendo foto principal...")

        foto_abierta = await abrir_foto_principal(
            post_page
        )

        if foto_abierta:
            print("Visor abierto.")

        # -------------------------------------------------
        # SACAR IMAGEN DE MÁXIMA CALIDAD
        # -------------------------------------------------

        imagen_url = await obtener_imagen_del_visor(
            post_page
        )

        if not imagen_url:
            print("No se encontró imagen.")
            await browser.close()
            return

        imagen_final = await descargar_imagen(
            context,
            imagen_url
        )

        await post_page.close()
        await browser.close()

        # -------------------------------------------------
        # GUARDAR JSON
        # -------------------------------------------------

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
