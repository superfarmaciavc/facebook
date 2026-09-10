import asyncio
import json
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


def buscar_numero(texto, palabras):
    if not texto:
        return "—"

    for palabra in palabras:
        patrones = [
            rf"([\d.,KkMm]+)\s+{palabra}",
            rf"{palabra}\s+([\d.,KkMm]+)"
        ]

        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)

            if match:
                return match.group(1)

    return "—"


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="es-ES"
        )

        page = await context.new_page()

        print("Abriendo Facebook...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(10000)

        # Cargar varias publicaciones
        for _ in range(5):
            await page.mouse.wheel(0, 1600)
            await page.wait_for_timeout(1800)

        articles = page.locator('[role="article"]')

        total = await articles.count()

        print("Artículos encontrados:", total)

        posts = []

        for i in range(total):

            if len(posts) >= 3:
                break

            article = articles.nth(i)

            try:

                texto_completo = (
                    await article.inner_text()
                ).strip()

                if len(texto_completo) < 20:
                    continue

                # --------------------------------
                # TEXTO REAL DE LA PUBLICACIÓN
                # --------------------------------

                mensaje = ""

                mensaje_locator = article.locator(
                    '[data-ad-preview="message"]'
                )

                if await mensaje_locator.count() > 0:
                    mensaje = (
                        await mensaje_locator.first.inner_text()
                    ).strip()

                # Alternativa
                if not mensaje:

                    candidatos = article.locator(
                        'div[dir="auto"]'
                    )

                    cantidad = await candidatos.count()

                    textos = []

                    for x in range(cantidad):

                        try:
                            txt = (
                                await candidatos.nth(x).inner_text()
                            ).strip()

                            if (
                                len(txt) >= 25
                                and "Super Farmacia Virgen" not in txt
                                and "Todas las reacciones" not in txt
                                and "Ver más" != txt
                            ):
                                textos.append(txt)

                        except:
                            pass

                    if textos:
                        mensaje = max(
                            textos,
                            key=len
                        )

                if not mensaje:
                    continue

                # --------------------------------
                # BUSCAR LA IMAGEN MÁS GRANDE
                # --------------------------------

                images = article.locator("img")

                image_count = await images.count()

                mejores_imagenes = []

                for j in range(image_count):

                    img = images.nth(j)

                    try:

                        datos = await img.evaluate("""
                        el => ({
                            src: el.currentSrc || el.src || "",
                            width: el.naturalWidth || el.width || 0,
                            height: el.naturalHeight || el.height || 0
                        })
                        """)

                        src = datos["src"]

                        width = datos["width"]
                        height = datos["height"]

                        if not src:
                            continue

                        # Excluir iconos / fotos de perfil
                        if width < 300 or height < 250:
                            continue

                        area = width * height

                        mejores_imagenes.append(
                            (area, src)
                        )

                    except:
                        continue

                if not mejores_imagenes:
                    continue

                mejores_imagenes.sort(
                    reverse=True,
                    key=lambda x: x[0]
                )

                image_url = mejores_imagenes[0][1]

                # --------------------------------
                # LINK DE LA PUBLICACIÓN
                # --------------------------------

                post_url = FACEBOOK_URL

                links = article.locator("a")

                link_count = await links.count()

                for j in range(link_count):

                    href = await links.nth(j).get_attribute("href")

                    if not href:
                        continue

                    if (
                        "/posts/" in href
                        or "/photos/" in href
                        or "/videos/" in href
                        or "story_fbid=" in href
                    ):

                        if href.startswith("/"):
                            href = "https://www.facebook.com" + href

                        post_url = href
                        break

                # --------------------------------
                # INTERACCIONES
                # --------------------------------

                texto_interacciones = texto_completo

                likes = buscar_numero(
                    texto_interacciones,
                    [
                        "reacciones",
                        "reacción",
                        "Me gusta"
                    ]
                )

                comments = buscar_numero(
                    texto_interacciones,
                    [
                        "comentarios",
                        "comentario"
                    ]
                )

                shares = buscar_numero(
                    texto_interacciones,
                    [
                        "veces compartido",
                        "compartidos",
                        "compartido"
                    ]
                )

                posts.append({
                    "text": mensaje[:1800],
                    "image": image_url,
                    "url": post_url,
                    "date": "Publicación reciente",
                    "likes": likes,
                    "comments_count": comments,
                    "shares": shares,
                    "scraped_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                })

                print(
                    "Publicación",
                    len(posts),
                    "capturada"
                )

            except Exception as e:
                print("Error:", e)

        await browser.close()

        if len(posts) == 0:

            print(
                "No se encontraron publicaciones. "
                "Se conserva posts.json anterior."
            )

            return

        with open(
            "posts.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                posts,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            "posts.json actualizado:",
            len(posts),
            "publicaciones"
        )


asyncio.run(main())
