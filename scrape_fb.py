import asyncio
import json
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


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


async def expandir_ver_mas(article):

    try:

        botones = article.get_by_text(
            "Ver más",
            exact=True
        )

        cantidad = await botones.count()

        for i in range(cantidad):

            try:
                await botones.nth(i).click(
                    timeout=2000
                )

                await asyncio.sleep(0.5)

            except:
                pass

    except:
        pass


async def obtener_descripcion(article):

    # Primera opción:
    # bloque específico del mensaje

    try:

        mensaje = article.locator(
            '[data-ad-preview="message"]'
        )

        if await mensaje.count() > 0:

            texto = (
                await mensaje.first.inner_text()
            ).strip()

            if texto:
                return texto

    except:
        pass


    # Segunda opción:
    # buscar bloques de texto razonables

    try:

        bloques = article.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        candidatos = []

        for i in range(cantidad):

            try:

                texto = (
                    await bloques.nth(i).inner_text()
                ).strip()

                if len(texto) < 20:
                    continue

                ignorar = [
                    "Super Farmacia Virgen de Copacabana",
                    "Todas las reacciones:",
                    "Comentar",
                    "Compartir",
                    "Enviar",
                    "Seguir página"
                ]

                if any(
                    x.lower() in texto.lower()
                    for x in ignorar
                ):
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

    try:

        imagenes = article.locator("img")

        cantidad = await imagenes.count()

        candidatas = []

        for i in range(cantidad):

            try:

                datos = await imagenes.nth(i).evaluate("""
                    el => {

                        let src =
                            el.currentSrc ||
                            el.src ||
                            "";

                        const srcset =
                            el.getAttribute("srcset");

                        if (srcset) {

                            const opciones =
                                srcset
                                .split(",")
                                .map(x => x.trim())
                                .map(x => {
                                    const p = x.split(" ");
                                    return {
                                        src: p[0],
                                        size: parseInt(p[1]) || 0
                                    };
                                })
                                .sort((a,b) => b.size - a.size);

                            if (opciones.length) {
                                src = opciones[0].src;
                            }
                        }

                        return {
                            src: src,
                            width:
                                el.naturalWidth ||
                                el.width ||
                                0,
                            height:
                                el.naturalHeight ||
                                el.height ||
                                0
                        };
                    }
                """)

                src = datos["src"]
                ancho = datos["width"]
                alto = datos["height"]

                if not src:
                    continue

                # excluir logos, avatares e iconos
                if ancho < 400 or alto < 300:
                    continue

                area = ancho * alto

                candidatas.append(
                    (area, src)
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

    except:
        return ""


async def obtener_link(article):

    try:

        enlaces = article.locator("a")

        cantidad = await enlaces.count()

        for i in range(cantidad):

            href = await enlaces.nth(i).get_attribute(
                "href"
            )

            if not href:
                continue

            if (
                "/posts/" in href
                or "/photos/" in href
                or "/videos/" in href
                or "story_fbid=" in href
            ):

                if href.startswith("/"):
                    href = (
                        "https://www.facebook.com"
                        + href
                    )

                return href

    except:
        pass

    return FACEBOOK_URL


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


        # Scroll progresivo para cargar posts

        for _ in range(6):

            await page.mouse.wheel(
                0,
                1400
            )

            await page.wait_for_timeout(
                1800
            )


        articles = page.locator(
            '[role="article"]'
        )

        total = await articles.count()

        print(
            "Artículos encontrados:",
            total
        )

        posts = []


        for i in range(total):

            if len(posts) >= 3:
                break

            article = articles.nth(i)

            try:

                # Expandir descripción

                await expandir_ver_mas(
                    article
                )


                # Texto completo del artículo
                # para las métricas

                texto_total = (
                    await article.inner_text()
                ).strip()


                # Descripción

                descripcion = (
                    await obtener_descripcion(
                        article
                    )
                )


                if not descripcion:
                    continue


                # Limpiar solamente residuos conocidos

                descripcion = descripcion.replace(
                    "... Ver más",
                    ""
                ).replace(
                    "Ver más",
                    ""
                ).strip()


                # Imagen

                imagen = (
                    await obtener_imagen(
                        article
                    )
                )


                if not imagen:
                    continue


                # Link

                link = (
                    await obtener_link(
                        article
                    )
                )


                # Reacciones

                likes = extraer_numero(
                    texto_total,
                    [
                        r"Todas las reacciones:\s*([\d.,KkMm]+)",
                        r"([\d.,KkMm]+)\s+reacciones",
                        r"([\d.,KkMm]+)\s+Me gusta"
                    ]
                )


                # Comentarios

                comentarios = extraer_numero(
                    texto_total,
                    [
                        r"([\d.,KkMm]+)\s+comentarios",
                        r"([\d.,KkMm]+)\s+comentario"
                    ]
                )


                # Compartidos

                compartidos = extraer_numero(
                    texto_total,
                    [
                        r"([\d.,KkMm]+)\s+veces compartido",
                        r"([\d.,KkMm]+)\s+compartidos",
                        r"([\d.,KkMm]+)\s+compartido"
                    ]
                )


                post = {

                    "text":
                        descripcion[:2500],

                    "image":
                        imagen,

                    "url":
                        link,

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


                posts.append(post)

                print(
                    f"Publicación {len(posts)} capturada"
                )


            except Exception as e:

                print(
                    "Error en publicación:",
                    str(e)
                )


        await browser.close()


        # Seguridad:
        # si Facebook no devuelve nada,
        # conserva posts.json anterior

        if not posts:

            print(
                "No se encontraron publicaciones."
            )

            print(
                "Se mantiene el posts.json anterior."
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
