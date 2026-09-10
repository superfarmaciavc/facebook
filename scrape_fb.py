import asyncio
import json
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


async def expandir_ver_mas(article):
    """
    Intenta pulsar todos los 'Ver más' dentro del post.
    """

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
    """
    Reconstruye texto, saltos de línea y emojis.
    Facebook puede representar algunos emojis como
    imágenes, aria-label o texto normal.
    """

    try:

        texto = await locator.evaluate("""
        element => {

            function leer(node) {

                let resultado = "";

                for (const child of node.childNodes) {

                    /* TEXTO NORMAL */
                    if (child.nodeType === Node.TEXT_NODE) {

                        resultado += child.textContent || "";

                        continue;
                    }


                    if (child.nodeType !== Node.ELEMENT_NODE) {
                        continue;
                    }


                    const tag =
                        child.tagName.toLowerCase();


                    /* SALTO DE LÍNEA */
                    if (tag === "br") {

                        resultado += "\\n";

                        continue;
                    }


                    /* EMOJIS COMO IMG */
                    if (tag === "img") {

                        const alt =
                            child.getAttribute("alt");

                        const aria =
                            child.getAttribute("aria-label");

                        const title =
                            child.getAttribute("title");

                        const valor =
                            alt ||
                            aria ||
                            title ||
                            "";

                        if (valor) {
                            resultado += valor;
                        }

                        continue;
                    }


                    /*
                    Algunos emojis/iconos están
                    dentro de span con aria-label.
                    */
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
                .replace(/[ \\t]+\\n/g, "\\n")
                .replace(/\\n[ \\t]+/g, "\\n")
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)

        return texto.strip()

    except Exception:
        return ""


async def obtener_descripcion(article):

    /*
    Primero buscamos el bloque específico del mensaje.
    */

    try:

        mensajes = article.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        if cantidad:

            candidatos = []

            for i in range(cantidad):

                texto = await obtener_texto_completo(
                    mensajes.nth(i)
                )

                if texto:
                    candidatos.append(texto)

            if candidatos:
                return max(
                    candidatos,
                    key=len
                )

    except:
        pass


    /*
    Método alternativo:
    buscar bloques grandes de texto.
    */

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


                texto_lower = texto.lower()


                basura = [
                    "todas las reacciones",
                    "comentar",
                    "compartir",
                    "seguir página",
                    "super farmacia virgen de copacabana"
                ]


                if any(
                    item in texto_lower
                    for item in basura
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
                img => {

                    let src =
                        img.currentSrc ||
                        img.src ||
                        "";

                    const srcset =
                        img.getAttribute("srcset");


                    /*
                    Elegir la imagen más grande
                    de srcset cuando exista.
                    */

                    if (srcset) {

                        const opciones =
                            srcset
                            .split(",")
                            .map(x => x.trim())
                            .map(x => {

                                const partes =
                                    x.split(/\\s+/);

                                const numero =
                                    parseInt(partes[1]) || 0;

                                return {
                                    src: partes[0],
                                    size: numero
                                };
                            })
                            .sort(
                                (a,b) =>
                                b.size - a.size
                            );


                        if (opciones.length) {
                            src = opciones[0].src;
                        }
                    }


                    return {

                        src: src,

                        width:
                            img.naturalWidth ||
                            img.width ||
                            0,

                        height:
                            img.naturalHeight ||
                            img.height ||
                            0
                    };
                }
                """)


                if not datos["src"]:
                    continue


                /*
                Excluir logo, avatar,
                botones y emojis.
                */

                if datos["width"] < 500:
                    continue

                if datos["height"] < 350:
                    continue


                area = (
                    datos["width"]
                    *
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
            key=lambda x: x[0],
            reverse=True
        )


        return candidatas[0][1]

    except:
        return ""


async def obtener_link(article):

    try:

        links = article.locator("a")

        cantidad = await links.count()


        for i in range(cantidad):

            href = await links.nth(i).get_attribute(
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
            10000
        )


        /*
        Buscamos publicaciones.
        */

        articles = page.locator(
            '[role="article"]'
        )


        cantidad = await articles.count()


        print(
            "Artículos encontrados:",
            cantidad
        )


        if cantidad == 0:

            print(
                "No se encontró ninguna publicación."
            )

            await browser.close()

            return


        post_encontrado = None


        /*
        Probamos los primeros artículos
        hasta encontrar uno con imagen +
        descripción.
        */

        for i in range(
            min(cantidad, 6)
        ):

            article = articles.nth(i)


            try:

                await expandir_ver_mas(
                    article
                )


                await page.wait_for_timeout(
                    1000
                )


                descripcion = (
                    await obtener_descripcion(
                        article
                    )
                )


                imagen = (
                    await obtener_imagen(
                        article
                    )
                )


                if not descripcion:
                    continue


                if not imagen:
                    continue


                /*
                Eliminar únicamente texto
                de interfaz residual.
                */

                descripcion = (
                    descripcion
                    .replace("... Ver más", "")
                    .replace("Ver más", "")
                    .strip()
                )


                texto_metricas = ""

                try:
                    texto_metricas = (
                        await article.inner_text()
                    )
                except:
                    pass


                try:

                    aria = await article.locator(
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


                    texto_metricas += (
                        "\\n" + aria
                    )

                except:
                    pass


                likes = extraer_numero(
                    texto_metricas,
                    [
                        r"Todas las reacciones:\\s*([\\d.,KkMm]+)",
                        r"([\\d.,KkMm]+)\\s+reacciones",
                        r"([\\d.,KkMm]+)\\s+reacción"
                    ]
                )


                comentarios = extraer_numero(
                    texto_metricas,
                    [
                        r"([\\d.,KkMm]+)\\s+comentarios",
                        r"([\\d.,KkMm]+)\\s+comentario"
                    ]
                )


                compartidos = extraer_numero(
                    texto_metricas,
                    [
                        r"([\\d.,KkMm]+)\\s+veces compartido",
                        r"([\\d.,KkMm]+)\\s+compartidos",
                        r"([\\d.,KkMm]+)\\s+compartido"
                    ]
                )


                link = await obtener_link(
                    article
                )


                post_encontrado = {

                    "text":
                        descripcion,

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


                print(
                    "Última publicación capturada."
                )


                print(
                    "Texto:",
                    descripcion
                )


                break


            except Exception as e:

                print(
                    "Error procesando artículo:",
                    str(e)
                )


        await browser.close()


        /*
        Si Facebook no permitió leer
        ningún post, conservar archivo anterior.
        */

        if not post_encontrado:

            print(
                "No se pudo capturar la publicación."
            )

            print(
                "Se conserva posts.json anterior."
            )

            return


        /*
        Guardar como una lista
        para mantener compatibilidad
        con tu index.html actual.
        */

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
            "posts.json actualizado correctamente."
        )


asyncio.run(main())
