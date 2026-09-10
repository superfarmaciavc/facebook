import asyncio
import json
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


async def expandir_ver_mas(article):
    for _ in range(5):
        try:
            botones = article.get_by_text(
                re.compile(r"^(Ver más|See more)$", re.I)
            )

            cantidad = await botones.count()

            if cantidad == 0:
                return

            for i in range(cantidad):
                try:
                    await botones.nth(i).click(
                        timeout=2500,
                        force=True
                    )
                    await asyncio.sleep(0.7)
                except:
                    pass

        except:
            return


async def obtener_texto_completo(locator):
    try:
        return await locator.evaluate("""
        element => {

            function leer(node) {

                let resultado = "";

                for (const child of node.childNodes) {

                    if (child.nodeType === Node.TEXT_NODE) {
                        resultado += child.textContent || "";
                        continue;
                    }

                    if (child.nodeType !== Node.ELEMENT_NODE) {
                        continue;
                    }

                    const tag = child.tagName.toLowerCase();

                    if (tag === "br") {
                        resultado += "\\n";
                        continue;
                    }

                    if (tag === "img") {

                        const valor =
                            child.getAttribute("alt") ||
                            child.getAttribute("aria-label") ||
                            child.getAttribute("title") ||
                            "";

                        resultado += valor;
                        continue;
                    }

                    const aria =
                        child.getAttribute("aria-label");

                    if (
                        aria &&
                        aria.length <= 20 &&
                        /[^\\w\\s]/u.test(aria)
                    ) {
                        resultado += aria;
                        continue;
                    }

                    resultado += leer(child);

                    if (
                        tag === "div" ||
                        tag === "p"
                    ) {
                        resultado += "\\n";
                    }
                }

                return resultado;
            }

            return leer(element)
                .replace(/\\u00a0/g, " ")
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)

    except:
        return ""


async def obtener_descripcion(article):

    try:
        mensaje = article.locator(
            '[data-ad-preview="message"]'
        )

        if await mensaje.count():

            texto = await obtener_texto_completo(
                mensaje.first
            )

            if texto:
                return texto

    except:
        pass


    try:
        bloques = article.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        candidatos = []

        for i in range(cantidad):

            try:
                texto = await obtener_texto_completo(
                    bloques.nth(i)
                )

                if len(texto) < 25:
                    continue

                if "Todas las reacciones" in texto:
                    continue

                candidatos.append(texto)

            except:
                pass

        if candidatos:
            return max(
                candidatos,
                key=len
            )

    except:
        pass

    return ""


async def obtener_imagen(article):

    imagenes = article.locator("img")

    candidatas = []

    for i in range(await imagenes.count()):

        try:
            datos = await imagenes.nth(i).evaluate("""
            img => ({
                src: img.currentSrc || img.src || "",
                width: img.naturalWidth || 0,
                height: img.naturalHeight || 0
            })
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

            candidatas.append(
                (area, datos["src"])
            )

        except:
            pass

    if not candidatas:
        return ""

    candidatas.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return candidatas[0][1]


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

        page = await context.new_page()

        print("Abriendo Facebook...")

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(10000)

        articles = page.locator(
            '[role="article"]'
        )

        cantidad = await articles.count()

        print(
            "Artículos encontrados:",
            cantidad
        )

        post_encontrado = None


        for i in range(min(cantidad, 6)):

            article = articles.nth(i)

            try:

                await expandir_ver_mas(
                    article
                )

                await page.wait_for_timeout(1000)

                descripcion = await obtener_descripcion(
                    article
                )

                imagen = await obtener_imagen(
                    article
                )

                if not descripcion:
                    continue

                if not imagen:
                    continue

                descripcion = (
                    descripcion
                    .replace("... Ver más", "")
                    .replace("Ver más", "")
                    .strip()
                )

                texto_metricas = (
                    await article.inner_text()
                )

                likes = extraer_numero(
                    texto_metricas,
                    [
                        r"Todas las reacciones:\s*([\d.,KkMm]+)",
                        r"([\d.,KkMm]+)\s+reacciones"
                    ]
                )

                comentarios = extraer_numero(
                    texto_metricas,
                    [
                        r"([\d.,KkMm]+)\s+comentarios",
                        r"([\d.,KkMm]+)\s+comentario"
                    ]
                )

                compartidos = extraer_numero(
                    texto_metricas,
                    [
                        r"([\d.,KkMm]+)\s+compartidos",
                        r"([\d.,KkMm]+)\s+compartido"
                    ]
                )

                post_encontrado = {
                    "text": descripcion,
                    "image": imagen,
                    "url": FACEBOOK_URL,
                    "date": "Publicación reciente",
                    "likes": likes,
                    "comments_count": comentarios,
                    "shares": compartidos,
                    "scraped_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }

                print("Último post capturado.")
                print(descripcion)

                break

            except Exception as e:
                print("Error:", e)


        await browser.close()


        if not post_encontrado:

            print(
                "No se pudo capturar el post."
            )

            return


        with open(
            "posts.json",
            "w",
            encoding="utf-8"
        ) as archivo:

            json.dump(
                [post_encontrado],
                archivo,
                ensure_ascii=False,
                indent=2
            )


        print(
            "posts.json actualizado."
        )


asyncio.run(main())
