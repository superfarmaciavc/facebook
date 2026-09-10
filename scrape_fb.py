import asyncio
import json
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright


FACEBOOK_URL = "https://www.facebook.com/SuperFarmaciaVC/"
MAX_POSTS = 3


# =========================================================
# TEXTO CON EMOJIS
# =========================================================

async def texto_con_emojis(locator):
    try:
        return await locator.evaluate("""
        element => {

            function recorrer(node) {

                let salida = "";

                for (const child of node.childNodes) {

                    if (child.nodeType === Node.TEXT_NODE) {
                        salida += child.textContent;
                        continue;
                    }

                    if (child.nodeType !== Node.ELEMENT_NODE) {
                        continue;
                    }

                    const tag = child.tagName.toLowerCase();

                    if (tag === "br") {
                        salida += "\\n";
                        continue;
                    }

                    if (tag === "img") {

                        const emoji =
                            child.getAttribute("alt") ||
                            child.getAttribute("aria-label") ||
                            "";

                        salida += emoji;
                        continue;
                    }

                    const aria =
                        child.getAttribute("aria-label");

                    if (
                        aria &&
                        aria.length <= 12 &&
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
                .replace(/\\n{3,}/g, "\\n\\n")
                .trim();
        }
        """)

    except:
        return ""


# =========================================================
# BOTÓN VER MÁS
# =========================================================

async def expandir_ver_mas(article):
    try:

        botones = article.get_by_text(
            re.compile(r"^(Ver más|See more)$", re.I)
        )

        cantidad = await botones.count()

        for i in range(cantidad):
            try:
                await botones.nth(i).click(timeout=2500)
                await asyncio.sleep(0.8)
            except:
                pass

    except:
        pass


# =========================================================
# DESCRIPCIÓN
# =========================================================

async def obtener_descripcion(article):

    # Selector principal
    try:
        mensaje = article.locator(
            '[data-ad-preview="message"]'
        )

        if await mensaje.count() > 0:

            texto = await texto_con_emojis(
                mensaje.first
            )

            if texto:
                return texto

    except:
        pass


    # Alternativa
    try:

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

                texto = texto.strip()

                if len(texto) < 30:
                    continue

                basura = [
                    "Todas las reacciones",
                    "Comentar",
                    "Compartir",
                    "Enviar",
                    "Seguir página",
                    "Super Farmacia Virgen de Copacabana"
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

    except:
        pass

    return ""


# =========================================================
# IMAGEN
# =========================================================

async def obtener_imagen(article):

    try:

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

                                let size = 0;

                                if (partes.length > 1) {
                                    size =
                                        parseInt(partes[1]) || 0;
                                }

                                return {
                                    src: partes[0],
                                    size: size
                                };
                            })
                            .sort(
                                (a,b) =>
                                b.size - a.size
                            );

                        if (opciones.length) {
                            mejor = opciones[0].src;
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
                            0,
                        alt:
                            img.getAttribute("alt") ||
                            ""
                    };
                }
                """)

                src = datos["src"]
                ancho = datos["width"]
                alto = datos["height"]

                if not src:
                    continue

                # Excluir emojis, avatares, logos pequeños
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


# =========================================================
# LINK DEL POST
# =========================================================

async def obtener_link(article):

    try:

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

    except:
        pass

    return FACEBOOK_URL


# =========================================================
# MÉTRICAS
# =========================================================

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


# =========================================================
# PROCESAR POST
# =========================================================

async def procesar_post(article):

    await expandir_ver_mas(article)

    await asyncio.sleep(0.5)

    descripcion = await obtener_descripcion(
        article
    )

    if not descripcion:
        return None

    descripcion = (
        descripcion
        .replace("... Ver más", "")
        .replace("Ver más", "")
        .strip()
    )

    imagen = await obtener_imagen(
        article
    )

    if not imagen:
        return None

    link = await obtener_link(
        article
    )

    texto_total = ""

    try:
        texto_total = (
            await article.inner_text()
        )
    except:
        pass

    try:

        aria = await article.locator(
            "[aria-label]"
        ).evaluate_all("""
        els =>
            els.map(
                x => x.getAttribute("aria-label")
            )
            .filter(Boolean)
            .join("\\n")
        """)

        texto_total += "\\n" + aria

    except:
        pass

    likes = extraer_numero(
        texto_total,
        [
            r"Todas las reacciones:\\s*([\\d.,KkMm]+)",
            r"([\\d.,KkMm]+)\\s+reacciones",
            r"([\\d.,KkMm]+)\\s+reacción",
            r"([\\d.,KkMm]+)\\s+Me gusta"
        ]
    )

    comentarios = extraer_numero(
        texto_total,
        [
            r"([\\d.,KkMm]+)\\s+comentarios",
            r"([\\d.,KkMm]+)\\s+comentario"
        ]
    )

    compartidos = extraer_numero(
        texto_total,
        [
            r"([\\d.,KkMm]+)\\s+veces compartido",
            r"([\\d.,KkMm]+)\\s+compartidos",
            r"([\\d.,KkMm]+)\\s+compartido"
        ]
    )

    return {
        "text": descripcion,
        "image": imagen,
        "url": link,
        "date": "Publicación reciente",
        "likes": likes,
        "comments_count": comentarios,
        "shares": compartidos,
        "scraped_at": datetime.now(
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

        textos_usados = set()
        urls_usadas = set()

        # Hasta 20 scrolls para intentar obtener 3 posts
        for scroll in range(20):

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

                    post = await procesar_post(
                        article
                    )

                    if not post:
                        continue

                    clave_texto = (
                        post["text"][:180]
                    )

                    if clave_texto in textos_usados:
                        continue

                    if (
                        post["url"]
                        and
                        post["url"] in urls_usadas
                    ):
                        continue

                    posts.append(post)

                    textos_usados.add(
                        clave_texto
                    )

                    if post["url"]:
                        urls_usadas.add(
                            post["url"]
                        )

                    print(
                        f"POST {len(posts)} CAPTURADO"
                    )

                except Exception as e:

                    print(
                        "Error en post:",
                        e
                    )

            if len(posts) >= MAX_POSTS:
                break

            # bajar más
            await page.evaluate("""
                window.scrollBy(
                    0,
                    window.innerHeight * 1.7
                )
            """)

            await page.wait_for_timeout(
                2500
            )

        await browser.close()

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
            f"FINAL: {len(posts[:3])} publicaciones guardadas"
        )


asyncio.run(main())
