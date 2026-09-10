import asyncio
import json
from datetime import datetime, timezone
from playwright.async_api import async_playwright

FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


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

        # Scroll para cargar varias publicaciones
        for _ in range(5):
            await page.mouse.wheel(0, 1500)
            await page.wait_for_timeout(2000)

        articles = page.locator('[role="article"]')

        total = await articles.count()

        print("Artículos encontrados:", total)

        posts = []

        for i in range(total):

            if len(posts) >= 3:
                break

            article = articles.nth(i)

            try:

                # ---------------------------------
                # DESCRIPCIÓN DEL POST
                # ---------------------------------

                descripcion = ""

                message = article.locator(
                    '[data-ad-preview="message"]'
                )

                if await message.count() > 0:
                    descripcion = (
                        await message.first.inner_text()
                    ).strip()

                # Alternativa si Facebook cambia selector
                if not descripcion:

                    bloques = article.locator('div[dir="auto"]')

                    cantidad = await bloques.count()

                    candidatos = []

                    for x in range(cantidad):

                        try:
                            texto = (
                                await bloques.nth(x).inner_text()
                            ).strip()

                            if len(texto) > 40:
                                candidatos.append(texto)

                        except:
                            pass

                    if candidatos:
                        descripcion = max(
                            candidatos,
                            key=len
                        )

                if not descripcion:
                    continue


                # ---------------------------------
                # IMAGEN REAL DEL POST
                # ---------------------------------

                imagen_url = ""

                imgs = article.locator("img")

                cantidad_imgs = await imgs.count()

                candidatas = []

                for x in range(cantidad_imgs):

                    img = imgs.nth(x)

                    try:

                        datos = await img.evaluate("""
                        el => {
                            const srcset = el.getAttribute('srcset');

                            let mejor = el.currentSrc || el.src || '';

                            if (srcset) {
                                const opciones = srcset
                                    .split(',')
                                    .map(x => x.trim().split(' '));

                                if (opciones.length) {
                                    mejor =
                                        opciones[opciones.length - 1][0];
                                }
                            }

                            return {
                                src: mejor,
                                w: el.naturalWidth || 0,
                                h: el.naturalHeight || 0
                            };
                        }
                        """)

                        if not datos["src"]:
                            continue

                        # Excluir logos, avatares e iconos
                        if datos["w"] < 400 or datos["h"] < 300:
                            continue

                        area = datos["w"] * datos["h"]

                        candidatas.append(
                            (area, datos["src"])
                        )

                    except:
                        pass

                if not candidatas:
                    continue

                candidatas.sort(
                    reverse=True,
                    key=lambda x: x[0]
                )

                imagen_url = candidatas[0][1]


                # ---------------------------------
                # TEXTO COMPLETO PARA MÉTRICAS
                # ---------------------------------

                texto_total = (
                    await article.inner_text()
                )


                # ---------------------------------
                # REACCIONES
                # ---------------------------------

                likes = "—"
                comments = "—"
                shares = "—"

                import re

                patrones_like = [
                    r"Todas las reacciones:\s*([\d.,KkMm]+)",
                    r"([\d.,KkMm]+)\s+reacciones"
                ]

                for patron in patrones_like:
                    m = re.search(
                        patron,
                        texto_total,
                        re.IGNORECASE
                    )
                    if m:
                        likes = m.group(1)
                        break


                patrones_comments = [
                    r"([\d.,KkMm]+)\s+comentarios",
                    r"([\d.,KkMm]+)\s+comentario"
                ]

                for patron in patrones_comments:
                    m = re.search(
                        patron,
                        texto_total,
                        re.IGNORECASE
                    )
                    if m:
                        comments = m.group(1)
                        break


                patrones_shares = [
                    r"([\d.,KkMm]+)\s+veces compartido",
                    r"([\d.,KkMm]+)\s+compartidos"
                ]

                for patron in patrones_shares:
                    m = re.search(
                        patron,
                        texto_total,
                        re.IGNORECASE
                    )
                    if m:
                        shares = m.group(1)
                        break


                # ---------------------------------
                # LINK DEL POST
                # ---------------------------------

                post_url = FACEBOOK_URL

                links = article.locator("a")

                cantidad_links = await links.count()

                for x in range(cantidad_links):

                    href = await links.nth(x).get_attribute("href")

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


                posts.append({
                    "text": descripcion,
                    "image": imagen_url,
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
                    f"Post {len(posts)} capturado"
                )

            except Exception as e:

                print("Error:", e)


        await browser.close()


        if not posts:

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
            f"posts.json actualizado con {len(posts)} publicaciones"
        )


asyncio.run(main())
