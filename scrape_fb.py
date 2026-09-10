import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


# =========================================================
# NORMALIZAR LINK DE POST
# =========================================================

def normalizar_link(href):

    if not href:
        return None

    if href.startswith("/"):
        href = urljoin(
            "https://www.facebook.com",
            href
        )

    patrones = [
        "/posts/",
        "/photos/",
        "/videos/",
        "story_fbid="
    ]

    if not any(
        patron in href
        for patron in patrones
    ):
        return None

    return href


# =========================================================
# BUSCAR EL ÚLTIMO POST
# =========================================================

async def obtener_ultimo_post(page):

    articulos = page.locator(
        '[role="article"]'
    )

    cantidad = await articulos.count()

    print(
        "Artículos encontrados:",
        cantidad
    )

    for i in range(
        min(cantidad, 8)
    ):

        articulo = articulos.nth(i)

        links = articulo.locator("a")

        cantidad_links = await links.count()

        for j in range(cantidad_links):

            try:

                href = await links.nth(j).get_attribute(
                    "href"
                )

                url = normalizar_link(
                    href
                )

                if url:

                    print(
                        "Post encontrado:",
                        url
                    )

                    return url

            except:
                pass

    return None


# =========================================================
# EXPANDIR "VER MÁS"
# =========================================================

async def expandir_ver_mas(page):

    for _ in range(5):

        encontrado = False

        try:

            botones = page.locator(
                'div[role="button"], span[role="button"], span, div'
            )

            cantidad = await botones.count()

            for i in range(
                min(cantidad, 500)
            ):

                try:

                    boton = botones.nth(i)

                    texto = (
                        await boton.inner_text()
                    ).strip()

                    if texto.lower() in [
                        "ver más",
                        "see more"
                    ]:

                        if await boton.is_visible():

                            await boton.evaluate(
                                "el => el.click()"
                            )

                            await page.wait_for_timeout(
                                1500
                            )

                            encontrado = True

                except:
                    pass

        except:
            pass

        if not encontrado:
            break


# =========================================================
# LEER TEXTO CON EMOJIS
# =========================================================

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

                    salida += leer(child);

                    if (
                        tag === "div" ||
                        tag === "p"
                    ) {
                        salida += "\\n";
                    }
                }

                return salida;
            }

            return leer(element)
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
# OBTENER DESCRIPCIÓN
# =========================================================

async def obtener_descripcion(page):

    await page.wait_for_timeout(
        1500
    )

    # Método principal
    try:

        mensajes = page.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        candidatos = []

        for i in range(cantidad):

            texto = await texto_con_emojis(
                mensajes.nth(i)
            )

            if texto:
                candidatos.append(texto)

        if candidatos:

            return limpiar_texto(
                max(
                    candidatos,
                    key=len
                )
            )

    except:
        pass


    # Método alternativo
    try:

        bloques = page.locator(
            'div[dir="auto"]'
        )

        cantidad = await bloques.count()

        candidatos = []

        for i in range(cantidad):

            try:

                texto = await texto_con_emojis(
                    bloques.nth(i)
                )

                if len(texto) < 40:
                    continue

                basura = [
                    "todas las reacciones",
                    "comentar",
                    "compartir",
                    "iniciar sesión",
                    "crear cuenta"
                ]

                if any(
                    palabra in texto.lower()
                    for palabra in basura
                ):
                    continue

                candidatos.append(texto)

            except:
                pass

        if candidatos:

            return limpiar_texto(
                max(
                    candidatos,
                    key=len
                )
            )

    except:
        pass


    # Último recurso: meta description
    try:

        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():

            texto = await meta.first.get_attribute(
                "content"
            )

            if texto:
                return limpiar_texto(texto)

    except:
        pass

    return ""


def limpiar_texto(texto):

    texto = texto.replace(
        "... Ver más",
        ""
    )

    texto = texto.replace(
        "Ver más",
        ""
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# =========================================================
# BUSCAR IMAGEN DE MAYOR CALIDAD
# =========================================================

async def obtener_mejor_imagen(page):

    candidatos = []

    # 1. og:image
    try:

        og = page.locator(
            'meta[property="og:image"]'
        )

        if await og.count():

            src = await og.first.get_attribute(
                "content"
            )

            if src:

                candidatos.append(
                    (
                        10**15,
                        src
                    )
                )

                print(
                    "og:image encontrado"
                )

    except:
        pass


    # 2. imágenes del DOM
    imagenes = page.locator("img")

    cantidad = await imagenes.count()

    for i in range(cantidad):

        try:

            datos = await imagenes.nth(i).evaluate("""
            img => {

                let opciones = [];

                if (img.currentSrc) {
                    opciones.push({
                        url: img.currentSrc,
                        score:
                            (img.naturalWidth || 0) *
                            (img.naturalHeight || 0)
                    });
                }

                if (img.src) {
                    opciones.push({
                        url: img.src,
                        score:
                            (img.naturalWidth || 0) *
                            (img.naturalHeight || 0)
                    });
                }

                const srcset =
                    img.getAttribute("srcset");

                if (srcset) {

                    srcset.split(",").forEach(
                        item => {

                            const partes =
                                item
                                .trim()
                                .split(/\\s+/);

                            const numero =
                                parseInt(
                                    partes[1]
                                ) || 0;

                            opciones.push({
                                url: partes[0],
                                score:
                                    numero * numero
                            });
                        }
                    );
                }

                opciones.sort(
                    (a,b) =>
                    b.score - a.score
                );

                return {
                    src:
                        opciones.length
                        ? opciones[0].url
                        : "",

                    width:
                        img.naturalWidth || 0,

                    height:
                        img.naturalHeight || 0
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
                datos["width"]
                *
                datos["height"]
            )

            candidatos.append(
                (
                    area,
                    datos["src"]
                )
            )

        except:
            pass


    if not candidatos:
        return ""


    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    print(
        "Imagen de mejor calidad encontrada."
    )

    return candidatos[0][1]


# =========================================================
# DESCARGAR IMAGEN A GITHUB
# =========================================================

async def descargar_imagen(
    context,
    url
):

    os.makedirs(
        "posts",
        exist_ok=True
    )

    ruta = (
        "posts/"
        "ultima_publicacion.jpg"
    )

    try:

        respuesta = (
            await context.request.get(
                url
            )
        )

        if respuesta.ok:

            contenido = (
                await respuesta.body()
            )

            with open(
                ruta,
                "wb"
            ) as archivo:

                archivo.write(
                    contenido
                )

            print(
                "Imagen descargada:",
                ruta
            )

            return ruta

    except Exception as e:

        print(
            "Error descargando imagen:",
            e
        )

    return url


# =========================================================
# MÉTRICAS
# =========================================================

def extraer_numero(
    texto,
    patrones
):

    for patron in patrones:

        resultado = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if resultado:
            return resultado.group(1)

    return "—"


async def obtener_metricas(page):

    try:

        texto = await page.locator(
            "body"
        ).inner_text()

    except:
        texto = ""


    try:

        aria = await page.locator(
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

        texto += (
            "\\n"
            + aria
        )

    except:
        pass


    likes = extraer_numero(
        texto,
        [
            r"Todas las reacciones:\s*([\d.,KkMm]+)",
            r"([\d.,KkMm]+)\s+reacciones",
            r"([\d.,KkMm]+)\s+reacción"
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
            r"([\d.,KkMm]+)\s+veces compartido",
            r"([\d.,KkMm]+)\s+compartidos",
            r"([\d.,KkMm]+)\s+compartido"
        ]
    )

    return (
        likes,
        comentarios,
        compartidos
    )


# =========================================================
# MAIN
# =========================================================

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


        # -----------------------------------------
        # ABRIR PÁGINA PRINCIPAL
        # -----------------------------------------

        page = await context.new_page()

        print(
            "Abriendo Facebook..."
        )

        await page.goto(
            FACEBOOK_URL,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await page.wait_for_timeout(
            10000
        )


        # -----------------------------------------
        # BUSCAR ÚLTIMO POST
        # -----------------------------------------

        post_url = await obtener_ultimo_post(
            page
        )

        if not post_url:

            print(
                "No se encontró el último post."
            )

            await browser.close()

            return

        await page.close()


        # -----------------------------------------
        # ABRIR EL POST INDIVIDUAL
        # -----------------------------------------

        post_page = await context.new_page()

        print(
            "Abriendo publicación individual..."
        )

        await post_page.goto(
            post_url,
            wait_until="domcontentloaded",
            timeout=90000
        )

        await post_page.wait_for_timeout(
            8000
        )


        # -----------------------------------------
        # EXPANDIR DESCRIPCIÓN
        # -----------------------------------------

        await expandir_ver_mas(
            post_page
        )

        await post_page.wait_for_timeout(
            2000
        )


        # -----------------------------------------
        # TEXTO
        # -----------------------------------------

        descripcion = await obtener_descripcion(
            post_page
        )

        print(
            "Descripción obtenida:"
        )

        print(
            descripcion
        )


        # -----------------------------------------
        # IMAGEN
        # -----------------------------------------

        imagen_url = await obtener_mejor_imagen(
            post_page
        )

        if imagen_url:

            imagen_final = await descargar_imagen(
                context,
                imagen_url
            )

        else:

            imagen_final = ""


        # -----------------------------------------
        # MÉTRICAS
        # -----------------------------------------

        (
            likes,
            comentarios,
            compartidos
        ) = await obtener_metricas(
            post_page
        )


        await post_page.close()

        await browser.close()


        # -----------------------------------------
        # VALIDACIÓN
        # -----------------------------------------

        if not descripcion:

            print(
                "No se pudo obtener la descripción."
            )

            print(
                "Se conserva posts.json anterior."
            )

            return


        if not imagen_final:

            print(
                "No se pudo obtener imagen."
            )

            print(
                "Se conserva posts.json anterior."
            )

            return


        # -----------------------------------------
        # GUARDAR POSTS.JSON
        # -----------------------------------------

        resultado = [
            {
                "text":
                    descripcion,

                "image":
                    imagen_final,

                "url":
                    post_url,

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
