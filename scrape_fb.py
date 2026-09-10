async def expandir_ver_mas(article):

    try:
        # Busca cualquier elemento visible que diga Ver más
        botones = article.locator(
            'div[role="button"], span[role="button"], span, div'
        ).filter(
            has_text=re.compile(r"^\s*(Ver más|See more)\s*$", re.I)
        )

        cantidad = await botones.count()

        for i in range(cantidad):
            try:
                boton = botones.nth(i)

                if await boton.is_visible():
                    await boton.evaluate("el => el.click()")
                    await asyncio.sleep(2)

            except:
                pass

    except Exception as e:
        print("No se pudo expandir Ver más:", e)


async def obtener_descripcion(article):

    # Esperar a que Facebook termine de expandir
    await asyncio.sleep(2)

    try:
        mensajes = article.locator(
            '[data-ad-preview="message"]'
        )

        cantidad = await mensajes.count()

        candidatos = []

        for i in range(cantidad):

            try:
                texto = await mensajes.nth(i).evaluate("""
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

                            if (child.tagName === "BR") {
                                salida += "\\n";
                                continue;
                            }

                            if (child.tagName === "IMG") {
                                salida +=
                                    child.getAttribute("alt") ||
                                    child.getAttribute("aria-label") ||
                                    "";
                                continue;
                            }

                            salida += leer(child);
                        }

                        return salida;
                    }

                    return leer(element).trim();
                }
                """)

                if texto:
                    candidatos.append(texto)

            except:
                pass


        if candidatos:

            texto = max(
                candidatos,
                key=len
            )

            texto = (
                texto
                .replace("... Ver más", "")
                .replace("Ver más", "")
                .strip()
            )

            return texto

    except Exception as e:
        print("Error leyendo descripción:", e)

    return ""
