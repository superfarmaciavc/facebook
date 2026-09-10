import asyncio
import json
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


# =========================================================
# EXPANDIR "VER MÁS"
# =========================================================

async def expandir_ver_mas(article):

    for intento in range(5):

        try:
            botones = article.locator(
                'div[role="button"], span[role="button"], div, span'
            ).filter(
                has_text=re.compile(
                    r"^\s*(Ver más|See more)\s*$",
                    re.I
                )
            )

            cantidad = await botones.count()

            if cantidad == 0:
                return

            hizo_click = False

            for i in range(cantidad):

                try:
                    boton = botones.nth(i)

                    if await boton.is_visible():
                        await boton.evaluate(
                            "el => el.click()"
                        )

                        hizo_click = True

                        await asyncio.sleep(1.5)

                except:
                    pass

            if not hizo_click:
                return

        except:
            return


# =========================================================
# LEER TEXTO CONSERVANDO EMOJIS
# =========================================================

async def leer_texto_con_emojis(locator):

    try:
        return await locator.evaluate("""
        element => {

            function recorrer(node) {

                let salida = "";

                for (const child of node.childNodes) {

                    if (child.nodeType === Node.TEXT_NODE) {
                        salida += child.textContent || "";
                        continue;
                    }

                    if (child.nodeType !== Node.ELEMENT_NODE) {
                        continue;
                    }

                    const tag =
                        child.tagName.toLowerCase();

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

                    const aria =
                        child.getAttribute("aria-label");

                    if (
                        aria &&
                        aria.length <= 20 &&
                        /[^a-zA-Z0-9\\s]/u.test(aria)
                    ) {
                        salida += aria;
                        continue;
                    }

                    salida += recorrer(child);

                    if (
                        tag === "div" ||
                        tag === "p"
                    ) {
                        salida += "\\n";
                    }
                }

                return salida;
            }

            return recorrer(element)
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
# OBTENER DESCRIPCIÓN COMPLETA
# =========================================================

async def obtener_descripcion(article):

    await asyncio.sleep(2)

    # Método principal
    try:

        mensajes = article.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        candidatos = []

        for i in range(cantidad):

            try:
                texto = await leer_texto_con_emojis(
                    mensajes.nth(i)
                )

                if texto:
                    candidatos.append(texto)

            except:
                pass

        if candidatos:

            texto = max(
                candidatos,
                key=len
            )

            return limpiar_descripcion(texto)

    except:
        pass


    # Método alternativo
    try:

        bloques = article.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        candidatos = []

        for i in range(cantidad):

            try:
                texto = await leer_texto_con_emojis(
                    bloques.nth(i)
                )

                texto = texto.strip()

                if len(texto) < 30:
                    continue

                basura = [
                    "Todas las reacciones",
                    "Comentar",
                    "Compartir",
                    "Enviar",
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

            texto = max(
                candidatos,
                key=len
            )

            return limpiar_descripcion(texto)

    except:
        pass


    return ""


def limpiar_descripcion(texto):

    texto = texto.replace(
        "... Ver más",
        ""
    )

    texto = texto.replace(
        "Ver más",
        ""
    )

    texto = texto.strip()

    return texto


# =========================================================
# OBTENER MEJOR IMAGEN
# =========================================================

async def obtener_imagen(article):

    imagenes = article.locator("img")

    candidatas = []

    cantidad = await imagenes.count()


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


# =========================================================
# OBTENER LINK DEL POST
# =========================================================

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


# =========================================================
# PROCESAR EL ÚLTIMO POST
# =========================================================

async def procesar_post(article):

    await expandir_ver_mas(
        article
    )

    await asyncio.sleep(2)

    descripcion = await obtener_descripcion(
        article
    )

    imagen = await obtener_imagen(
        article
    )


    if not descripcion:
        print(
            "No se pudo obtener la descripción."
        )
        return None


    if not imagen:
        print(
            "No se pudo obtener la imagen."
        )
        return None


    link = await obtener_link(
        article
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
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción"
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
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido"
        ]
    )


    return {

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


# =========================================================
# PRINCIPAL
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


        print(
            "Abriendo página de Facebook..."
        )


        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )


        await page.wait_for_timeout(
            10000
        )


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


        # Buscar el primer artículo válido
        for i in range(
            min(cantidad, 8)
        ):

            article = articles.nth(i)

            try:

                resultado = await procesar_post(
                    article
                )


                if resultado:

                    post_encontrado = resultado

                    print(
                        "Último post capturado."
                    )

                    print(
                        "DESCRIPCIÓN CAPTURADA:"
                    )

                    print(
                        resultado["text"]
                    )

                    break


            except Exception as e:

                print(
                    "Error procesando artículo:",
                    e
                )


        await browser.close()


        if not post_encontrado:

            print(
                "No se pudo capturar una publicación válida."
            )

            print(
                "Se conserva el posts.json anterior."
            )

            return


        # Se guarda como lista para mantener
        # compatibilidad con tu index.html

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
