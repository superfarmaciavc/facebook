import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"


# =========================================================
# LIMPIAR / VALIDAR LINK DE POST
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
# BUSCAR LINK DEL ÚLTIMO POST
# =========================================================

async def obtener_ultimo_post(page):

    print("Buscando última publicación...")

    for intento in range(6):

        articulos = page.locator(
            '[role="article"]'
        )

        cantidad = await articulos.count()

        print(
            "Artículos visibles:",
            cantidad
        )

        for i in range(cantidad):

            article = articulos.nth(i)

            links = article.locator("a")

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
                            "Último post encontrado:",
                            url
                        )

                        return url

                except:
                    pass

        await page.evaluate(
            """
            window.scrollBy(
                0,
                window.innerHeight * 1.2
            )
            """
        )

        await page.wait_for_timeout(
            2000
        )

    return None


# =========================================================
# EXPANDIR "VER MÁS"
# =========================================================

async def expandir_ver_mas(page):

    print("Buscando 'Ver más'...")

    for intento in range(6):

        encontro = False

        selectores = [
            'div[role="button"]',
            'span[role="button"]',
            'span',
            'div'
        ]

        for selector in selectores:

            try:

                elementos = page.locator(
                    selector
                )

                cantidad = await elementos.count()

                for i in range(
                    min(cantidad, 500)
                ):

                    elemento = elementos.nth(i)

                    try:

                        texto = (
                            await elemento.inner_text()
                        ).strip()

                        if texto.lower() in [
                            "ver más",
                            "see more"
                        ]:

                            if await elemento.is_visible():

                                print(
                                    "Haciendo clic en Ver más..."
                                )

                                await elemento.evaluate(
                                    "el => el.click()"
                                )

                                await page.wait_for_timeout(
                                    2000
                                )

                                encontro = True

                    except:
                        pass

            except:
                pass

        if not encontro:
            break


# =========================================================
# TEXTO + EMOJIS
# =========================================================

async def texto_con_emojis(locator):

    try:

        return await locator.evaluate(
        """
        element => {

            function leer(node) {

                let salida = "";

                for (
                    const child
                    of node.childNodes
                ) {

                    if (
                        child.nodeType ===
                        Node.TEXT_NODE
                    ) {

                        salida +=
                            child.textContent || "";

                        continue;
                    }


                    if (
                        child.nodeType !==
                        Node.ELEMENT_NODE
                    ) {

                        continue;
                    }


                    const tag =
                        child.tagName
                        .toLowerCase();


                    if (tag === "br") {

                        salida += "\\n";

                        continue;
                    }


                    /*
                    Facebook puede mostrar
                    emojis como imágenes.
                    */

                    if (tag === "img") {

                        const emoji =
                            child.getAttribute("alt") ||
                            child.getAttribute("aria-label") ||
                            child.getAttribute("title") ||
                            "";

                        salida += emoji;

                        continue;
                    }


                    const aria =
                        child.getAttribute(
                            "aria-label"
                        );


                    /*
                    Algunos emojis quedan
                    dentro de spans.
                    */

                    if (
                        aria &&
                        aria.length <= 20 &&
                        /[^a-zA-Z0-9\\s]/u
                        .test(aria)
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
        """
        )

    except:

        return ""


# =========================================================
# DESCRIPCIÓN DEL POST INDIVIDUAL
# =========================================================

async def obtener_descripcion(page):

    await page.wait_for_timeout(
        1500
    )


    # --------------------------
    # MÉTODO 1
    # --------------------------

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
                candidatos.append(
                    texto
                )


        if candidatos:

            descripcion = max(
                candidatos,
                key=len
            )

            return limpiar_texto(
                descripcion
            )

    except:
        pass


    # --------------------------
    # MÉTODO 2
    # --------------------------

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


                candidatos.append(
                    texto
                )

            except:
                pass


        if candidatos:

            descripcion = max(
                candidatos,
                key=len
            )

            return limpiar_texto(
                descripcion
            )

    except:
        pass


    # --------------------------
    # MÉTODO 3 - META DESCRIPTION
    # --------------------------

    try:

        meta = page.locator(
            'meta[property="og:description"]'
        )

        if await meta.count():

            texto = await meta.first.get_attribute(
                "content"
            )

            if texto:

                return limpiar_texto(
                    texto
                )

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
# CONSEGUIR IMAGEN EN MEJOR CALIDAD
# =========================================================

async def obtener_mejor_imagen(page):

    candidatos = []


    # =====================================================
    # 1. OG:IMAGE
    # =====================================================

    try:

        og_image = page.locator(
            'meta[property="og:image"]'
        )

        if await og_image.count():

            src = await og_image.first.get_attribute(
                "content"
            )

            if src:

                candidatos.append(
                    (
                        999999999,
                        src
                    )
                )

    except:
        pass


    # =====================================================
    # 2. IMÁGENES DEL POST
    # =====================================================

    imagenes = page.locator("img")

    cantidad = await imagenes.count()


    for i in range(cantidad):

        try:

            datos = await imagenes.nth(i).evaluate(
            """
            img => {

                const candidatos = [];

                if (img.currentSrc) {
                    candidatos.push({
                        url: img.currentSrc,
                        size:
                            (img.naturalWidth || 0)
                            *
                            (img.naturalHeight || 0)
                    });
                }


                if (img.src) {
                    candidatos.push({
                        url: img.src,
                        size:
                            (img.naturalWidth || 0)
                            *
                            (img.naturalHeight || 0)
                    });
                }


                const srcset =
                    img.getAttribute(
                        "srcset"
                    );


                if (srcset) {

                    const opciones =
                        srcset.split(",");

                    opciones.forEach(
                        opcion => {

                            const partes =
                                opcion
                                .trim()
                                .split(/\\s+/);

                            const numero =
                                parseInt(
                                    partes[1]
                                ) || 0;

                            candidatos.push({
                                url: partes[0],
                                size:
                                    numero *
                                    numero
                            });
                        }
                    );
                }


                candidatos.sort(
                    (a,b) =>
                    b.size - a.size
                );


                return {

                    src:
                        candidatos.length
                        ? candidatos[0].url
                        : "",

                    width:
                        img.naturalWidth || 0,

                    height:
                        img.naturalHeight || 0
                };
            }
            """
            )


            if not datos["src"]:
                continue


            # Evitar avatares e iconos
            if (
                datos["width"] < 500 or
                datos["height"] < 350
            ):
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
# DESCARGAR IMAGEN
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
                "Imagen guardada:",
                ruta
            )


            return ruta

    except Exception as e:

        print(
            "No se pudo descargar imagen:",
            e
        )


    # Si falla descarga,
    # dejamos URL Facebook
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
        ).evaluate_all(
        """
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
        """
        )


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
                "(Windows NT 10.0; "
                "Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 "
                "Safari/537.36"
            )
        )


        # =================================================
        # ABRIR PÁGINA PRINCIPAL
        # =================================================

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


        # =================================================
        # OBTENER LINK DEL ÚLTIMO POST
        # =================================================

        post_url = await obtener_ultimo_post(
            page
        )


        if not post_url:

            print(
                "No se encontró "
                "el último post."
            )

            await browser.close()

            return


        await page.close()


        # =================================================
        # ABRIR POST INDIVIDUAL
        # =================================================

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


        # =================================================
        # EXPANDIR TEXTO
        # =================================================

        await expandir_ver_mas(
            post_page
        )


        await post_page.wait_for_timeout(
            2000
        )


        # =================================================
        # DESCRIPCIÓN
        # =================================================

        descripcion = await obtener_descripcion(
            post_page
        )


        print(
            "\nDESCRIPCIÓN:"
        )

        print(
            descripcion
        )


        # =================================================
        # IMAGEN
        # =================================================

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


        # =================================================
        # MÉTRICAS
        # =================================================

        (
            likes,
            comentarios,
            compartidos
        ) = await obtener_metricas(
            post_page
        )


        await post_page.close()

        await browser.close()


        # =================================================
        # VALIDACIÓN
        # =================================================

        if not descripcion:

            print(
                "No se pudo obtener "
                "la descripción completa."
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


        # =================================================
        # GUARDAR
        # =================================================

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
            "\nposts.json actualizado correctamente."
        )


asyncio.run(main())
