import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"
MAX_POSTS = 3


def limpiar_url(href):
    if not href:
        return None

    if href.startswith("/"):
        href = urljoin("https://www.facebook.com", href)

    if "facebook.com" not in href:
        return None

    patrones = [
        "/posts/",
        "/photos/",
        "/videos/",
        "story_fbid="
    ]

    if not any(x in href for x in patrones):
        return None

    # Mantener parámetros en story_fbid
    if "story_fbid=" not in href:
        href = href.split("?")[0]

    return href


def extraer_numero(texto, patrones):
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)

        if match:
            return match.group(1)

    return "—"


async def cerrar_ventanas(page):
    textos = [
        "Permitir todas las cookies",
        "Allow all cookies",
        "Ahora no",
        "Not now",
        "Cerrar"
    ]

    for texto in textos:
        try:
            boton = page.get_by_text(texto, exact=True)

            if await boton.count():
                await boton.first.click(timeout=1500)
                await page.wait_for_timeout(500)
        except:
            pass


async def expandir_ver_mas(page):
    # Intentar varias veces porque puede haber más de un botón
    for _ in range(4):
        try:
            botones = page.get_by_text(
                re.compile(r"^(Ver más|See more)$", re.I)
            )

            cantidad = await botones.count()

            if cantidad == 0:
                break

            for i in range(cantidad):
                try:
                    await botones.nth(i).click(timeout=2000)
                    await page.wait_for_timeout(700)
                except:
                    pass

        except:
            break


async def buscar_urls_publicaciones(page):
    urls = []

    for intento in range(10):

        # Expandir textos visibles
        await expandir_ver_mas(page)

        links = page.locator("a")
        cantidad = await links.count()

        for i in range(cantidad):
            try:
                href = await links.nth(i).get_attribute("href")
                url = limpiar_url(href)

                if url and url not in urls:
                    urls.append(url)

            except:
                pass

        print(
            f"Scroll {intento + 1}: "
            f"{len(urls)} publicaciones encontradas"
        )

        if len(urls) >= MAX_POSTS:
            break

        # Scroll progresivo
        await page.evaluate(
            "window.scrollBy(0, window.innerHeight * 1.4)"
        )

        await page.wait_for_timeout(2500)

    return urls[:MAX_POSTS]


async def obtener_descripcion(page):
    # Primero: selector habitual del mensaje de Facebook
    try:
        mensajes = page.locator(
            '[data-ad-preview="message"]'
        )

        if await mensajes.count():

            textos = []

            for i in range(await mensajes.count()):
                try:
                    txt = (
                        await mensajes.nth(i).inner_text()
                    ).strip()

                    if txt:
                        textos.append(txt)
                except:
                    pass

            if textos:
                return max(textos, key=len)

    except:
        pass

    # Segundo método
    candidatos = []

    try:
        bloques = page.locator('div[dir="auto"]')
        cantidad = await bloques.count()

        for i in range(cantidad):
            try:
                texto = (
                    await bloques.nth(i).inner_text()
                ).strip()

                if len(texto) < 30:
                    continue

                basura = [
                    "Super Farmacia Virgen de Copacabana",
                    "Todas las reacciones",
                    "Me gusta",
                    "Comentar",
                    "Compartir",
                    "Seguir"
                ]

                if any(
                    b.lower() in texto.lower()
                    for b in basura
                ):
                    continue

                candidatos.append(texto)

            except:
                pass

    except:
        pass

    if candidatos:
        return max(candidatos, key=len)

    return ""


async def obtener_mejor_imagen(page):
    imagenes = page.locator("img")

    candidatas = []

    for i in range(await imagenes.count()):
        try:
            datos = await imagenes.nth(i).evaluate("""
            el => ({
                src: el.currentSrc || el.src || "",
                w: el.naturalWidth || 0,
                h: el.naturalHeight || 0,
                rw: el.getBoundingClientRect().width || 0,
                rh: el.getBoundingClientRect().height || 0
            })
            """)

            src = datos["src"]

            if not src:
                continue

            # Evitar avatar, logos e iconos
            if datos["w"] < 500 or datos["h"] < 350:
                continue

            area = datos["w"] * datos["h"]

            candidatas.append(
                (area, src)
            )

        except:
            pass

    if not candidatas:
        return None

    candidatas.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return candidatas[0][1]


async def descargar_imagen(context, url, numero):
    os.makedirs("posts", exist_ok=True)

    ruta = f"posts/post{numero}.jpg"

    try:
        respuesta = await context.request.get(url)

        if respuesta.ok:
            contenido = await respuesta.body()

            with open(ruta, "wb") as f:
                f.write(contenido)

            return ruta

    except Exception as e:
        print("Error descargando imagen:", e)

    return url


async def procesar_publicacion(context, url, numero):
    page = await context.new_page()

    try:
        print("Abriendo:", url)

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(6000)

        await cerrar_ventanas(page)

        # ESTE ES EL PASO IMPORTANTE
        await expandir_ver_mas(page)

        await page.wait_for_timeout(1500)

        texto_total = await page.locator(
            "body"
        ).inner_text()

        descripcion = await obtener_descripcion(page)

        # Quitar solo residuos de interfaz
        descripcion = descripcion.replace(
            "... Ver más", ""
        ).replace(
            "Ver más", ""
        ).strip()

        imagen_url = await obtener_mejor_imagen(page)

        if not descripcion or not imagen_url:
            print(
                f"Post {numero}: información incompleta"
            )
            return None

        # Guardar la imagen dentro de GitHub
        imagen_local = await descargar_imagen(
            context,
            imagen_url,
            numero
        )

        likes = extraer_numero(
            texto_total,
            [
                r"Todas las reacciones:\s*([\d.,KkMm]+)",
                r"([\d.,KkMm]+)\s+reacciones",
                r"([\d.,KkMm]+)\s+reacción"
            ]
        )

        comentarios = extraer_numero(
            texto_total,
            [
                r"([\d.,KkMm]+)\s+comentarios",
                r"([\d.,KkMm]+)\s+comentario"
            ]
        )

        compartidos = extraer_numero(
            texto_total,
            [
                r"([\d.,KkMm]+)\s+veces compartido",
                r"([\d.,KkMm]+)\s+compartidos",
                r"([\d.,KkMm]+)\s+compartido"
            ]
        )

        return {
            "text": descripcion,
            "image": imagen_local,
            "url": url,
            "date": "Publicación reciente",
            "likes": likes,
            "comments_count": comentarios,
            "shares": compartidos,
            "scraped_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

    except Exception as e:
        print(
            f"Error en post {numero}:",
            e
        )

        return None

    finally:
        await page.close()


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

        print("Abriendo página principal...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(7000)

        await cerrar_ventanas(page)

        urls = await buscar_urls_publicaciones(
            page
        )

        await page.close()

        print(
            "URLs encontradas:",
            len(urls)
        )

        posts = []

        for numero, url in enumerate(
            urls,
            start=1
        ):
            post = await procesar_publicacion(
                context,
                url,
                numero
            )

            if post:
                posts.append(post)

        await browser.close()

        if not posts:
            print(
                "No se obtuvieron publicaciones. "
                "Se conserva posts.json anterior."
            )
            return

        with open(
            "posts.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                posts[:3],
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"LISTO: {len(posts[:3])} publicaciones guardadas."
        )


asyncio.run(main())
