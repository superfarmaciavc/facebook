import asyncio
import json
from datetime import datetime, timezone
from playwright.async_api import async_playwright

FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"

async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080},
            locale="es-ES"
        )

        print("Abriendo Facebook...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(8000)

        # Hace scroll para cargar publicaciones
        for _ in range(5):
            await page.mouse.wheel(0, 1800)
            await page.wait_for_timeout(2000)

        articles = page.locator('[role="article"]')

        total = await articles.count()

        print("Publicaciones encontradas:", total)

        posts = []

        for i in range(total):

            if len(posts) >= 3:
                break

            article = articles.nth(i)

            try:

                text = (await article.inner_text()).strip()

                if len(text) < 20:
                    continue

                # Buscar una imagen grande de la publicación
                image_url = ""

                images = article.locator("img")
                image_count = await images.count()

                for j in range(image_count):

                    src = await images.nth(j).get_attribute("src")

                    if not src:
                        continue

                    if "scontent" in src or "fbcdn" in src:

                        image_url = src
                        break

                if not image_url:
                    continue

                # Buscar enlace de la publicación
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
                        or "story_fbid" in href
                    ):

                        if href.startswith("/"):
                            href = "https://www.facebook.com" + href

                        post_url = href
                        break

                posts.append({
                    "text": text[:1500],
                    "image": image_url,
                    "url": post_url,
                    "date": "Publicación reciente",
                    "likes": "—",
                    "comments_count": "—",
                    "shares": "—",
                    "comments": [],
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })

            except Exception as e:
                print("Error:", e)

        await browser.close()

        # Si Facebook bloquea el acceso,
        # no reemplaza el archivo anterior
        if len(posts) == 0:

            print("No se encontraron publicaciones.")
            return

        with open("posts.json", "w", encoding="utf-8") as f:

            json.dump(
                posts,
                f,
                ensure_ascii=False,
                indent=2
            )

        print("posts.json actualizado con", len(posts), "publicaciones")


asyncio.run(main())
