import asyncio
import json
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"
MAX_POSTS = 3


# ---------------------------------------------------------
# TEXTO + EMOJIS
# ---------------------------------------------------------

async def texto_con_emojis(locator):

    try:
        return await locator.evaluate("""
        element => {

            function recorrer(node) {

                let resultado = "";

                for (const child of node.childNodes) {

                    if (child.nodeType === Node.TEXT_NODE) {
                        resultado += child.textContent;
                    }

                    else if (child.nodeType === Node.ELEMENT_NODE) {

                        const tag = child.tagName.toLowerCase();

                        // Facebook suele mostrar emojis como imágenes
                        if (tag === "img") {

                            const alt =
                                child.getAttribute("alt") ||
                                child.getAttribute("aria-label") ||
                                "";

                            if (alt) {
                                resultado += alt;
                            }

                        }

                        else if (tag === "br") {
                            resultado += "\\n";
                        }

                        else {

                            const interno = recorrer(child);

                            resultado += interno;

                            if (
                                tag === "div" ||
                                tag === "p"
                            ) {
                                resultado += "\\n";
                            }
                        }
                    }
                }

                return resultado;
            }

            return recorrer(element)
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)

    except:
        return ""


# ---------------------------------------------------------
# VER MÁS
# ---------------------------------------------------------

async def expandir_ver_mas(article):

    try:

        botones = article.get_by_text(
            re.compile(r"^(Ver más|See more)$", re.I)
        )

        cantidad = await botones.count()

        for i in range(cantidad):

            try:

                await botones.nth(i).click(
                    timeout=2000
                )

                await asyncio.sleep(0.6)

            except:
                pass

    except:
        pass


# ---------------------------------------------------------
# DESCRIPCIÓN
# ---------------------------------------------------------

async def obtener_descripcion(article):

    # Selector principal
    mensaje = article.locator(
        '[data-ad-preview="message"]'
    )

    if await mensaje.count():

        texto = await texto_con_emojis(
            mensaje.first
        )

        if texto:
            return texto


    # Alternativa
    bloques = article.locator(
        'div[dir="auto"]'
    )

    cantidad = await bloques.count()

    candidatos = []

    for i in range(cantidad):

        try:

            texto = await texto_con_emojis(
                bloques.nth(i)
            )

            if len(texto) < 30:
                continue

            basura = [
                "Todas las reacciones",
                "Comentar",
                "Compartir",
                "Seguir página"
            ]

            if any(
                x.lower() in texto.lower()
                for x in basura
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

    return ""


# ---------------------------------------------------------
# IMAGEN
# ---------------------------------------------------------

async def obtener_imagen(article):

    imagenes = article.locator("img")

    cantidad = await imagenes.count()

    candidatas = []


    for i in range(cantidad):

        try:

            datos = await imagenes.nth(i).evaluate("""
            img => {

                let mejor =
                    img.currentSrc ||
                    img.src ||
                    "";

                const srcset =
                    img.getAttribute("srcset");

                if (srcset) {

                    const opciones =
                        srcset
                        .split(",")
                        .map(x => x.trim())
                        .map(x => {

                            const partes =
                                x.split(/\\s+/);

                            return {
                                url: partes[0],
                                size:
                                    parseInt(partes[1]) || 0
                            };
                        })
                        .sort(
                            (a,b) =>
                            b.size - a.size
                        );

                    if (opciones.length) {
                        mejor =
                            opciones[0].url;
                    }
                }

                return {
                    src: mejor,
                    width: img.naturalWidth || 0,
                    height: img.naturalHeight || 0,
                    alt: img.alt || ""
                };
            }
            """)


            # Evitar emojis / avatares / iconos
            if datos["width"] < 450:
                continue

            if datos["height"] < 300:
                continue

            area = (
                datos["width"] *
                datos["height"]
            )

            candidatas.append(
                (
                    area,
                    datos["src"]
                )
            )

        except:
            pass


    if not candidatas:
        return ""


    candidatas.sort(
        reverse=True,
        key=lambda x: x[0]
    )


    return candidatas[0][1]


# ---------------------------------------------------------
# LINK DEL POST
# ---------------------------------------------------------

async def obtener_link(article):

    enlaces = article.locator("a")

    cantidad = await enlaces.count()


    for i in range(cantidad):

        try:

            href = await enlaces.nth(i).get_attribute(
                "href"
            )

            if not href:
                continue


            if (
                "/posts/" in href
                or "/videos/" in href
                or "/photos/" in href
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


    return ""


# ---------------------------------------------------------
# MÉTRICAS
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# PRINCIPAL
# ---------------------------------------------------------

async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )


        context = await browser.new_context(

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


        page = await context.new_page()


        print("Abriendo Facebook...")


        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await page.wait_for_timeout(
            8000
        )


        posts = []

        urls_usadas = set()

        textos_usados = set()


        # -------------------------------------------------
        # HACER SCROLL Y ACUMULAR POSTS
        # -------------------------------------------------

        for scroll in range(15):

            articles = page.locator(
                '[role="article"]'
            )

            cantidad = await articles.count()


            print(
                f"Scroll {scroll + 1}: "
                f"{cantidad} artículos visibles"
            )


            for i in range(cantidad):

                if len(posts) >= MAX_POSTS:
                    break


                article = articles.nth(i)


                try:

                    await expandir_ver_mas(
                        article
                    )


                    descripcion = (
                        await obtener_descripcion(
                            article
                        )
                    )


                    if not descripcion:
                        continue


                    descripcion = descripcion.replace(
                        "... Ver más",
                        ""
                    ).replace(
                        "Ver más",
                        ""
                    ).strip()


                    # Evitar mismo post repetido
                    clave_texto = descripcion[:150]


                    if clave_texto in textos_usados:
                        continue


                    imagen = await obtener_imagen(
                        article
                    )


                    if not imagen:
                        continue


                    url = await obtener_link(
                        article
                    )


                    if url and url in urls_usadas:
                        continue


                    # Obtener todo el artículo para métricas
                    texto_total = (
                        await article.inner_text()
                    )


                    # también leer aria-labels
                    labels = await article.locator(
                        "[aria-label]"
                    ).evaluate_all("""
                    els =>
                        els.map(
                            x => x.getAttribute("aria-label")
                        )
                        .filter(Boolean)
                        .join("\\n")
                    """)


                    metricas = (
                        texto_total
                        + "\\n"
                        + labels
                    )


                    likes = extraer_numero(
                        metricas,
                        [
                            r"Todas las reacciones:\\s*([\\d.,KkMm]+)",
                            r"([\\d.,KkMm]+)\\s+reacciones",
                            r"([\\d.,KkMm]+)\\s+reacción"
                        ]
                    )


                    comentarios = extraer_numero(
                        metricas,
                        [
                            r"([\\d.,KkMm]+)\\s+comentarios",
                            r"([\\d.,KkMm]+)\\s+comentario"
                        ]
                    )


                    compartidos = extraer_numero(
                        metricas,
                        [
                            r"([\\d.,KkMm]+)\\s+veces compartido",
                            r"([\\d.,KkMm]+)\\s+compartidos",
                            r"([\\d.,KkMm]+)\\s+compartido"
                        ]
                    )


                    posts.append({

                        "text":
                            descripcion,

                        "image":
                            imagen,

                        "url":
                            url or FACEBOOK_URL,

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
                    })


                    textos_usados.add(
                        clave_texto
                    )


                    if url:
                        urls_usadas.add(
                            url
                        )


                    print(
                        "POST",
                        len(posts),
                        "CAPTURADO"
                    )


                except Exception as e:

                    print(
                        "Error:",
                        e
                    )


            if len(posts) >= MAX_POSTS:
                break


            # bajar la página
            await page.evaluate("""
                window.scrollBy(
                    0,
                    window.innerHeight * 1.5
                )
            """)


            await page.wait_for_timeout(
                2500
            )


        await browser.close()


        # -------------------------------------------------
        # GUARDAR
        # -------------------------------------------------

        if not posts:

            print(
                "No se encontraron publicaciones."
            )

            print(
                "Se conserva posts.json anterior."
            )

            return


        with open(
            "posts.json",
            "w",
            encoding="utf-8"
        ) as archivo:

            json.dump(
                posts[:3],
                archivo,
                ensure_ascii=False,
                indent=2
            )


        print(
            "FINAL:"
            f" {len(posts[:3])}"
            " publicaciones guardadas"
        )


asyncio.run(main())
