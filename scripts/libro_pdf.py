#!/usr/bin/env python3
"""El libro armado: la tapa, el PDF para imprimir, el PDF para pantalla y el EPUB.

    libro_pdf.py                 los cuatro, en libro/salida/
    libro_pdf.py --solo-pdf      sin el EPUB
    libro_pdf.py --ver           que haria, sin escribir nada

**Salen DOS PDF y no uno, y esa es la decision que mas plata mueve.** En
impresion por demanda, el color no se cobra por pagina: alcanza con que UNA
tenga color para que el libro entero se facture como libro a color, y eso
multiplica varias veces el costo por ejemplar. Asi que:

    ...-impresion.pdf   todo en negro, que es lo que va a la imprenta
    ...-pantalla.pdf    con el acento en rojo, para leer y para mandar
    ...-portada.pdf     la tapa sola, blanca, para mirar y para el ebook
    ...-cubierta.pdf    contratapa + lomo + tapa: ESTA es la que se imprime
    ...epub             el ebook, donde el color no cuesta nada

La cubierta es la unica que conserva el rojo en la version de imprenta, y no
es una excepcion olvidada: la tapa se imprime a color siempre y no cambia el
precio del ejemplar. Lo que se cobra a color es el interior.

Es el MISMO diseno: lo unico que cambia es el tinte del acento. Por eso
`armar_pdf` recibe un color y no hay dos maquetas.

El diseno lo eligio el usuario el 2026-10-28 sobre tres alternativas
dibujadas: numero de capitulo grande, apartados con filete, el epigrafe con
una barra al margen, y un pictograma por capitulo. Lo que NO se tomo de la
referencia que trajo -una plantilla de catalogo- fue el cuerpo en sans y los
bloques de color: esa plantilla es casi toda fotos y bloques de cuatro
renglones, y esto son 49.000 palabras de texto seguido.

Dos familias y no una, tambien a proposito: la serif es el TEXTO y la sans son
los ROTULOS -numero, apartado, titulillo, folio-. Cada una tiene un trabajo.
Lo que el libro tenia antes era una sans usada sin motivo, que es otra cosa.

Lo demas que importa si alguien lo toca:

- **El texto no se edita aca.** Sale de `libro/capitulos/*.md` tal como esta.
- **Las fuentes se buscan y si no estan se usa Times.** No viajan en el
  repositorio, asi que en otra maquina puede no haberlas y el libro tiene que
  salir igual.
- **El indice lleva los numeros de pagina de verdad**: el documento se arma
  DOS veces (`multiBuild`).
- **Cada capitulo abre en pagina impar**, como en cualquier libro.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab import rl_config  # noqa: E402
from reportlab.lib.colors import HexColor, black, white  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch, mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas as cv  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame,  # noqa: E402
                                PageBreak, PageTemplate, Paragraph, Spacer)
from reportlab.platypus.doctemplate import ActionFlowable  # noqa: E402
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402
from reportlab.platypus.tables import TableStyle  # noqa: E402

from src import libro, pictogramas  # noqa: E402

CAPITULOS = ROOT / "libro" / "capitulos"
SALIDA = ROOT / "libro" / "salida"

# Del modulo y no copiado: estaba escrito en los dos lados, y dos copias del
# mismo texto es como se descubre tarde que una de las dos esta vieja. Paso
# justo con esto, que quedo en voseo aca despues de arreglarlo alla.
SUBTITULO = libro.SUBTITULO
AUTOR = "José Luis Del Carpio Chirinos"

TINTA = HexColor("#1F2933")
GRIS = HexColor("#737373")
# El acento. Es el rojo de las referencias que trajo el usuario, bajado de
# tono: el de la portada que mando es casi puro y en un libro de no ficcion
# grita. En el PDF de imprenta se reemplaza por negro.
ROJO = HexColor("#9E2B25")

# 6 x 9 pulgadas: la medida del libro de bolsillo de no ficcion y la que toman
# las imprentas por demanda sin recortar nada.
MEDIDA = (6 * inch, 9 * inch)
# El de adentro es mas ancho: ahi va la encuadernacion. Y los dos son anchos a
# proposito: con 19 y 15 el renglon daba unos 80 caracteres, demasiado para
# una pagina de 6 pulgadas. Con estos quedan unos 68.
ADENTRO, AFUERA = 22 * mm, 18 * mm
ARRIBA, ABAJO = 18 * mm, 18 * mm

F = "/usr/share/fonts/truetype/crosextra/"
FUENTES = {
    "LibroSerif": F + "Caladea-Regular.ttf",
    "LibroSerif-Bold": F + "Caladea-Bold.ttf",
    "LibroSerif-Italic": F + "Caladea-Italic.ttf",
    "LibroSerif-BoldItalic": F + "Caladea-BoldItalic.ttf",
    "LibroSans": F + "Carlito-Regular.ttf",
    "LibroSans-Bold": F + "Carlito-Bold.ttf",
}

# El espacio que va entre letra y letra para espaciar un rotulo. reportlab no
# tiene `charSpace` ni en el estilo ni en el lienzo, asi que el aire va DENTRO
# del texto. Es el espacio duro (U+00A0) y no uno fino: los finos (U+2009,
# U+202F) no estan en Caladea, y una fuente que no tiene el glifo no dibuja
# nada. Con el fino, los rotulos salieron con las letras PEGADAS.
FINO = " "


def espaciar(texto: str) -> str:
    """El texto con aire entre las letras, como se compone un rotulo chico."""
    return (FINO * 2).join(FINO.join(p) for p in texto.split(" ") if p)


def registrar_fuentes():
    """(serif, sans) ya registradas, o las de Times si no estan."""
    try:
        for nombre, ruta in FUENTES.items():
            if not Path(ruta).exists():
                raise FileNotFoundError(ruta)
            pdfmetrics.registerFont(TTFont(nombre, ruta))
    except Exception as e:                                # noqa: BLE001
        print("  Sin las fuentes del libro (%s); uso Times." % e)
        return "Times-Roman", "Helvetica"
    pdfmetrics.registerFontFamily(
        "LibroSerif", normal="LibroSerif", bold="LibroSerif-Bold",
        italic="LibroSerif-Italic", boldItalic="LibroSerif-BoldItalic")
    pdfmetrics.registerFontFamily("LibroSans", normal="LibroSans",
                                  bold="LibroSans-Bold")
    # La fuente con la que arranca cada pagina. Sin esto el PDF declara
    # Helvetica en todas -aunque no la use- y Helvetica no viaja dentro del
    # archivo: una imprenta puede rechazar un PDF con una fuente sin
    # incrustar, y no hay forma de explicarle que no se usa.
    rl_config.canvas_basefontname = "LibroSerif"
    return "LibroSerif", "LibroSans"


def _variante(fuente, cual):
    if fuente in ("Times-Roman", "Helvetica"):
        return {"Times-Roman": {"bold": "Times-Bold", "italic": "Times-Italic"},
                "Helvetica": {"bold": "Helvetica-Bold",
                              "italic": "Helvetica-Oblique"}}[fuente][cual]
    return fuente + ("-Bold" if cual == "bold" else "-Italic")


# --------------------------------------------------------------------------
# De markdown a parrafos.
# --------------------------------------------------------------------------

def en_linea(texto: str) -> str:
    """`**negrita**` y `*cursiva*` al marcado de reportlab, escapando el resto."""
    texto = html.escape(texto, quote=False)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto, flags=re.S)
    texto = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", texto, flags=re.S)
    return texto


def bloques(md: str):
    """(clase, texto) por bloque: titulo, apartado, epigrafe, parrafo, filete.

    Las lineas de un parrafo vienen cortadas a 79 columnas, asi que se juntan;
    y un epigrafe largo son varias lineas con `>` que son UN solo bloque.
    """
    clase, junta = None, []
    for linea in md.splitlines() + [""]:
        pelada = linea.strip()
        if pelada.startswith("# "):
            nueva, texto = "titulo", pelada[2:]
        elif pelada.startswith("## "):
            nueva, texto = "apartado", pelada[3:]
        elif pelada.startswith(">"):
            nueva, texto = "epigrafe", pelada.lstrip(">").strip()
        elif pelada == "---":
            nueva, texto = "filete", ""
        elif pelada:
            nueva, texto = "parrafo", pelada
        else:
            nueva, texto = None, ""
        if nueva != clase and junta:
            yield clase, " ".join(junta)
            junta = []
        clase = nueva
        if nueva == "filete":
            yield "filete", ""
            clase = None
        elif nueva:
            junta.append(texto)
    if junta:
        yield clase, " ".join(junta)


# --------------------------------------------------------------------------
# El documento.
# --------------------------------------------------------------------------

class Libro(BaseDocTemplate):
    """Margenes espejados, titulillos y folio, e indice con paginas de verdad."""

    def __init__(self, destino, serif, sans, acento):
        super().__init__(str(destino), pagesize=MEDIDA, title=libro.TITULO,
                         author=AUTOR, subject=SUBTITULO)
        self.serif, self.sans, self.acento = serif, sans, acento
        self.capitulo = ""
        self.abre_en = -1
        self.en_blanco = -1
        # Hasta que empiece el primer capitulo no se adorna nada: la portadilla
        # y el indice van sin titulillo ni folio.
        self.cuerpo_desde = 10 ** 9
        ancho = MEDIDA[0] - ADENTRO - AFUERA
        alto = MEDIDA[1] - ARRIBA - ABAJO

        def marco(x, cual):
            return Frame(x, ABAJO, ancho, alto, id=cual, leftPadding=0,
                         rightPadding=0, topPadding=0, bottomPadding=0)

        # UNA plantilla por paridad. Lo que decide si se adorna es
        # `cuerpo_desde`, no la plantilla, asi que agregar una seccion al libro
        # no obliga a duplicar nada.
        self.addPageTemplates([
            PageTemplate(id="impar", frames=[marco(ADENTRO, "impar")],
                         onPageEnd=self.adornar),
            PageTemplate(id="par", frames=[marco(AFUERA, "par")],
                         onPageEnd=self.adornar),
        ])

    def handle_pageBegin(self):
        """Elige la plantilla por paridad ANTES de que se arme el marco.

        Una pagina impar queda a la derecha en el libro abierto, asi que ahi el
        margen ancho va a la izquierda. Tocar `self.frame` a mano no sirve:
        reportlab inicializa el marco dentro de `_handle_pageBegin` y uno
        puesto por afuera llega sin la mitad de sus atributos.
        """
        quiere = "impar" if (self.page + 1) % 2 else "par"
        if self.pageTemplate.id != quiere:
            self.pageTemplate = self.pageTemplates[0 if quiere == "impar" else 1]
        self._handle_pageBegin()

    def adornar(self, lienzo, doc):
        if doc.page < doc.cuerpo_desde:
            return
        if doc.page in (doc.abre_en, doc.en_blanco):
            return      # la que abre capitulo y la que quedo en blanco, limpias
        lienzo.saveState()
        arriba = MEDIDA[1] - ARRIBA + 7 * mm
        lienzo.setFont(doc.sans, 7.2)
        lienzo.setFillColor(GRIS)
        if doc.page % 2:
            lienzo.drawRightString(MEDIDA[0] - AFUERA, arriba,
                                   espaciar(doc.capitulo.upper()))
        else:
            lienzo.drawString(AFUERA, arriba, espaciar(libro.TITULO.upper()))
        lienzo.setFillColor(doc.acento)
        lienzo.setFont(_variante(doc.sans, "bold"), 8.5)
        lienzo.drawCentredString(MEDIDA[0] / 2, ABAJO - 9 * mm, str(doc.page))
        lienzo.restoreState()

    def afterFlowable(self, flowable):
        if getattr(flowable, "es_capitulo", False):
            self.capitulo = flowable.titulo_corto
            self.abre_en = self.page
            self.cuerpo_desde = min(self.cuerpo_desde, self.page)
            self.notify("TOCEntry", (0, flowable.titulo_corto, self.page))


class AbreEnImpar(ActionFlowable):
    """Si la pagina que viene es par, mete una en blanco.

    Asi cada capitulo empieza del lado derecho del libro abierto. Va DESPUES
    del `PageBreak`: cuando esto corre ya estamos arriba de la pagina nueva.

    No se puede hacer con un espaciador: un espaciador no sabe en que pagina
    esta. Esto si, porque `apply` recibe el documento.
    """

    def apply(self, doc):
        if doc.page % 2 == 0:
            doc.en_blanco = doc.page      # esa no lleva titulillo ni folio
            doc.handle_pageBreak()


class Apertura(Flowable):
    """El pictograma, el numero grande y la palabra CAPÍTULO, en una pieza.

    Van juntos y no como tres parrafos porque los tres se alinean entre si: el
    numero cuelga del margen, el rotulo se apoya en su linea de base y el
    dibujo queda arriba de los dos. Repartido en tres flowables, reportlab
    podria partirlos en dos paginas.
    """

    # Nunca se separa de lo que sigue: el numero de capitulo al pie de una
    # pagina y el titulo arriba de la siguiente seria lo peor de los dos.
    keepWithNext = 1

    def __init__(self, numero, sans, acento, alto=32 * mm):
        super().__init__()
        self.numero, self.sans, self.acento = numero, sans, acento
        self.alto = alto
        # El aire va EN la pieza y no en un `Spacer` suelto: un espaciador
        # entre dos flowables rompe la cadena de `keepWithNext`, porque el
        # espaciador no se queda con nadie.
        self.spaceAfter = 7 * mm

    def wrap(self, ancho, alto):
        self.ancho = ancho
        return (ancho, self.alto)

    def draw(self):
        c = self.canv
        pictogramas.dibujar(c, self.numero, 13 * mm, self.alto - 7 * mm,
                            11 * mm, self.acento)
        c.setFillColor(self.acento)
        c.setFont(_variante(self.sans, "bold"), 54)
        c.drawString(0, 0, str(self.numero))
        ancho_num = c.stringWidth(str(self.numero),
                                  _variante(self.sans, "bold"), 54)
        c.setFillColor(GRIS)
        c.setFont(self.sans, 7.5)
        c.drawString(ancho_num + 7 * mm, 26, espaciar("CAPÍTULO"))
        c.setStrokeColor(self.acento)
        c.setLineWidth(1.6)
        c.line(ancho_num + 7 * mm, 16, ancho_num + 30 * mm, 16)


class Apartado(Flowable):
    """El rotulo del apartado con su filete debajo.

    El filete va pegado al rotulo -no a la caja- asi que los dos viajan en la
    misma pieza: si se separaran, una pagina podria terminar con el rotulo
    abajo y el filete arriba de la siguiente.
    """

    # Un rotulo solo al pie de una pagina es el defecto que mas se nota al
    # hojear: el apartado empieza en una hoja y su texto en la otra.
    keepWithNext = 1

    def __init__(self, texto, sans, acento, cuerpo=10):
        super().__init__()
        self.texto, self.sans, self.acento, self.cuerpo = texto, sans, acento, cuerpo
        self.spaceBefore = 9 * mm
        self.spaceAfter = 3 * mm

    def wrap(self, ancho, alto):
        self.ancho = ancho
        return (ancho, self.cuerpo + 12)

    def draw(self):
        c = self.canv
        c.setFillColor(self.acento)
        c.setFont(_variante(self.sans, "bold"), self.cuerpo)
        c.drawString(0, 10, self.texto.upper())
        c.setStrokeColor(self.acento)
        c.setLineWidth(1.8)
        c.line(0, 2, 34, 2)


class Epigrafe(Flowable):
    """La frase del banco, en cursiva y con una barra al margen.

    La barra se dibuja DESPUES de saber cuanto mide el texto, que es lo que
    hace que llegue justo hasta el ultimo renglon y ni un milimetro mas.
    """

    SANGRIA = 9 * mm
    keepWithNext = 1

    def __init__(self, texto, estilo, acento):
        super().__init__()
        self.parrafo = Paragraph(texto, estilo)
        self.acento = acento
        self.spaceBefore = 2 * mm
        self.spaceAfter = 4 * mm

    def wrap(self, ancho, alto):
        self.ancho = ancho
        _, self.alto = self.parrafo.wrap(ancho - self.SANGRIA, alto)
        return (ancho, self.alto)

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.acento)
        c.setLineWidth(1.2)
        c.line(3 * mm, 2, 3 * mm, self.alto - 3)
        self.parrafo.drawOn(c, self.SANGRIA, 0)


def estilos(serif, sans, acento, tinta=TINTA):
    cursiva = _variante(serif, "italic")
    cuerpo = ParagraphStyle(
        "cuerpo", fontName=serif, fontSize=10.5, leading=15.2,
        alignment=TA_JUSTIFY, spaceAfter=0, textColor=tinta,
        # Partir en silabas es lo que evita los rios de espacios del texto
        # justificado. Si `pyphen` no esta, reportlab lo ignora y sale igual.
        hyphenationLang="es", embeddedHyphenation=1, uriWasteReduce=0.3)
    return {
        "cuerpo": cuerpo,
        # El primer parrafo de un apartado va sin sangria y los siguientes con
        # sangria y sin espacio: es como se separan los parrafos en un libro.
        "primero": ParagraphStyle("primero", parent=cuerpo, firstLineIndent=0),
        "seguido": ParagraphStyle("seguido", parent=cuerpo,
                                  firstLineIndent=5 * mm),
        "epigrafe": ParagraphStyle("epigrafe", parent=cuerpo, fontName=cursiva,
                                   fontSize=10.5, leading=15,
                                   firstLineIndent=0),
        "capitulo": ParagraphStyle("capitulo", fontName=serif, fontSize=21,
                                   leading=26, textColor=tinta,
                                   spaceBefore=0, spaceAfter=9 * mm),
        "filete": ParagraphStyle("filete", fontName=serif, fontSize=11,
                                 alignment=TA_CENTER, textColor=GRIS,
                                 spaceBefore=6 * mm, spaceAfter=6 * mm),
        "titulazo": ParagraphStyle("titulazo", fontName=serif, fontSize=23,
                                   leading=30, alignment=TA_CENTER,
                                   textColor=tinta),
        "subtitulazo": ParagraphStyle("subtitulazo", fontName=cursiva,
                                      fontSize=11.5, leading=17,
                                      alignment=TA_CENTER, textColor=acento),
        "autor": ParagraphStyle("autor", fontName=sans, fontSize=9,
                                alignment=TA_CENTER, textColor=GRIS),
        "credito": ParagraphStyle("credito", fontName=serif, fontSize=8.5,
                                  leading=14, alignment=TA_CENTER,
                                  textColor=GRIS),
        "indice": ParagraphStyle("indice", fontName=serif, fontSize=10.5,
                                 leading=19, textColor=tinta),
    }


class Capitulo(Paragraph):
    """Un titulo de capitulo que ademas se anuncia: ver `afterFlowable`."""

    es_capitulo = True

    def __init__(self, texto, estilo, titulo_corto):
        super().__init__(texto, estilo)
        self.titulo_corto = titulo_corto


def armar_pdf(destino: Path, acento=ROJO, tinta=TINTA) -> Path:
    """`tinta` y `acento` aparte, y no un solo color.

    En la version de imprenta los DOS son negro puro, y eso no es un detalle:
    `TINTA` es #1F2933, un azul grisaceo, y una impresora por demanda mira si
    hay algun pixel que no sea gris para decidir si el libro entero se cobra
    como libro a color. Se vio releyendo el PDF y buscando operadores `rg` con
    componentes distintos, no leyendo el codigo: a ojo, ese azul ES negro.
    """
    serif, sans = registrar_fuentes()
    est = estilos(serif, sans, acento, tinta)
    doc = Libro(destino, serif, sans, acento)
    hist = [
        Spacer(1, 52 * mm),
        Paragraph(en_linea(libro.TITULO), est["titulazo"]),
        Spacer(1, 9 * mm),
        Paragraph(SUBTITULO, est["subtitulazo"]),
        Spacer(1, 40 * mm),
        Paragraph(espaciar(AUTOR.upper()), est["autor"]),
        PageBreak(),
        Spacer(1, 75 * mm),
        Paragraph("%s<br/><br/>%s<br/><br/>%s"
                  % (libro.TITULO, AUTOR, espaciar("PRIMERA EDICIÓN")),
                  est["credito"]),
        PageBreak(),
        Spacer(1, 8 * mm),
        Apartado("Índice", sans, acento, cuerpo=11),
        Spacer(1, 7 * mm),
    ]
    indice = TableOfContents()
    indice.levelStyles = [est["indice"]]
    # SIN puntitos. La fila de puntos es el adorno mas viejo de la tipografia
    # de libro: el titulo a la izquierda y el numero a la derecha ya dicen lo
    # que hay que decir.
    indice.dotsMinLevel = 99
    # El indice se dibuja sobre una tabla, y una tabla de reportlab arranca en
    # Helvetica aunque no la use: eso deja una fuente SIN INCRUSTAR declarada
    # en el PDF, y una imprenta puede rechazarlo por eso.
    indice.tableStyle = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("FONT", (0, 0), (-1, -1), serif),
    ])
    hist += [indice, PageBreak(), AbreEnImpar()]

    capitulos = sorted(CAPITULOS.glob("[0-9]*.md"))
    for ruta in capitulos:
        numero = int(ruta.name.split("-")[0])
        primero_del_apartado = True
        for clase, texto in bloques(ruta.read_text(encoding="utf-8")):
            if clase == "titulo":
                nombre = (texto.partition("·")[2] or texto).strip()
                # SIN espaciador delante: el capitulo abre en el borde de
                # arriba de la caja. Antes bajaba 12 mm y el titulo quedaba
                # cerca de la mitad de la hoja, que es lo que el usuario
                # marco el 2026-10-28.
                hist += [Apertura(numero, sans, acento),
                         Capitulo(en_linea(nombre), est["capitulo"],
                                  "%d. %s" % (numero, nombre))]
                primero_del_apartado = True
            elif clase == "apartado":
                hist.append(Apartado(texto, sans, acento))
                primero_del_apartado = True
            elif clase == "epigrafe":
                hist.append(Epigrafe(en_linea(texto), est["epigrafe"], acento))
                primero_del_apartado = True
            elif clase == "filete":
                hist.append(Paragraph("·", est["filete"]))
                primero_del_apartado = True
            elif clase == "parrafo":
                hist.append(Paragraph(
                    en_linea(texto),
                    est["primero"] if primero_del_apartado else est["seguido"]))
                primero_del_apartado = False
        hist.append(PageBreak())
        if ruta != capitulos[-1]:
            hist.append(AbreEnImpar())

    doc.multiBuild(hist)
    return destino


# --------------------------------------------------------------------------
# La tapa.
# --------------------------------------------------------------------------

def cayendo(c, x, y, alto, color, giro=-12, grosor=0.055):
    """Una persona cayendo: el cuerpo horizontal, la espalda arqueada.

    Rotar una figura PARADA no la hace caer -se probaron cinco giros y a mitad
    de camino la cabeza se pierde entre los miembros-. Una caida tiene su
    propia anatomia: los brazos arriba y atras, que es por donde los lleva el
    aire, y las piernas abiertas.

    Y la POSTURA es la decision, no el dibujo. Con los brazos pegados al
    cuerpo seria una caida; asi, abierta, es dejarse caer. En español se dice
    CAER enamorado, y eso es lo que la tapa dice.
    """
    c.saveState()
    c.translate(x, y)
    c.rotate(giro)
    c.scale(alto, alto)
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(grosor)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.circle(0.42, 0.10, 0.068, stroke=0, fill=1)
    hombro, cadera = (0.27, 0.06), (-0.17, -0.02)
    for desde, hasta in [
            ((0.30, 0.07), (0.07, 0.11)), ((0.07, 0.11), cadera),
            (hombro, (0.09, 0.30)), ((0.09, 0.30), (0.19, 0.50)),
            (hombro, (0.31, -0.20)), ((0.31, -0.20), (0.15, -0.33)),
            (cadera, (-0.40, 0.13)), ((-0.40, 0.13), (-0.58, 0.03)),
            (cadera, (-0.37, -0.21)), ((-0.37, -0.21), (-0.21, -0.37))]:
        p = c.beginPath()
        p.moveTo(*desde)
        p.lineTo(*hasta)
        c.drawPath(p)
    c.restoreState()


def _envolver(texto, fuente, cuerpo, ancho):
    """El texto cortado en los renglones que entran en `ancho`.

    Uno solo para la tapa, el lomo y la contratapa. Con una copia por panel,
    el dia que una aprenda algo -a partir una palabra larga, por ejemplo- las
    otras no lo aprenden, y eso se ve impreso.
    """
    linea, lineas = "", []
    for p in texto.split():
        prueba = (linea + " " + p).strip()
        if pdfmetrics.stringWidth(prueba, fuente, cuerpo) > ancho and linea:
            lineas.append(linea)
            linea = p
        else:
            linea = prueba
    lineas.append(linea)
    return lineas


def _centrado(c, texto, fuente, cuerpo, interlinea, y, color, ancho):
    lineas = _envolver(texto, fuente, cuerpo, ancho)
    c.setFillColor(color)
    c.setFont(fuente, cuerpo)
    for i, l in enumerate(lineas):
        c.drawCentredString(MEDIDA[0] / 2, y - i * interlinea, l)
    return y - (len(lineas) - 1) * interlinea


def dibujar_tapa(c, serif, sans, acento, tinta):
    """La tapa, dibujada desde (0,0) sobre una pagina de MEDIDA.

    Aparte de `armar_portada` porque la cubierta completa la vuelve a dibujar
    corrida al lugar que le toca, y la tapa suelta y la tapa de la cubierta no
    pueden ser dos dibujos distintos: el dia que se cambie una, la otra sale
    vieja y nadie se entera hasta que llega el ejemplar de prueba.
    """
    cayendo(c, MEDIDA[0] / 2, MEDIDA[1] * 0.70, 52 * mm, acento)
    # El titulo a 40 y no a 46: a 46 los renglones llegaban casi al margen y
    # la tapa se veia apretada. Una tapa necesita el aire tanto como el
    # tamano, y lo que decide si se lee no es el cuerpo sino el contraste.
    ancho = MEDIDA[0] - 40 * mm
    ultima = _centrado(c, libro.TITULO, serif, 40, 48, MEDIDA[1] * 0.345,
                       tinta, ancho)
    _centrado(c, SUBTITULO, _variante(serif, "italic"), 12.5, 18, ultima - 30,
              acento, ancho - 16 * mm)
    c.setFont(sans, 9)
    c.setFillColor(GRIS)
    c.drawCentredString(MEDIDA[0] / 2, 22 * mm, espaciar(AUTOR.upper()))


def armar_portada(destino: Path, acento=ROJO, tinta=TINTA) -> Path:
    """La tapa sola, BLANCA, como la pidio el usuario.

    Blanca y no crema: el crema de la pagina se ve lindo en pantalla y en una
    miniatura de tienda se apaga contra el fondo de la lista. El blanco corta.

    Esta es la que sirve para mirar, para el EPUB y para una tienda que pida
    solo la tapa. La que se manda a imprimir es `armar_cubierta`.
    """
    serif, sans = registrar_fuentes()
    c = cv.Canvas(str(destino), pagesize=MEDIDA)
    c.setFillColor(white)
    c.rect(0, 0, MEDIDA[0], MEDIDA[1], stroke=0, fill=1)
    dibujar_tapa(c, serif, sans, acento, tinta)
    c.showPage()
    c.save()
    return destino


# --------------------------------------------------------------------------
# La cubierta completa: contratapa, lomo y tapa en UNA sola pagina.
# --------------------------------------------------------------------------
#
# Es lo que pide una imprenta por demanda, y lo que bloqueaba subir el libro:
# con la tapa sola no se puede imprimir nada.

# El grosor del papel, por hoja. No se elige: lo publica la imprenta, y el
# lomo es ese numero por la cantidad de paginas. Un lomo mal medido corre el
# dibujo entero y el titulo de la tapa termina sobre el pliegue.
PAPEL = {"crema": 0.0025 * inch, "blanco": 0.002252 * inch}
# Los bordes de afuera llevan sangrado: la guillotina no corta en el mismo
# lugar en todos los ejemplares.
SANGRA = 0.125 * inch
# Y no se escribe a menos de un cuarto de pulgada del corte.
SEGURO = 0.25 * inch
# En el lomo el margen es mas chico, porque el lomo entero mide milimetros.
SEGURO_LOMO = 0.0625 * inch
# El rectangulo que la imprenta se reserva para el codigo de barras, en la
# esquina de abajo a la derecha de la contratapa. Tiene que quedar BLANCO: si
# cae texto ahi, el codigo se imprime encima y la contratapa queda ilegible.
BARRAS = (2 * inch, 1.2 * inch)
# Con menos paginas que esto el lomo es mas fino que una letra y no se
# escribe: el texto corrido un milimetro cae sobre el pliegue, y un milimetro
# es todo lo que la imprenta garantiza.
LOMO_MINIMO = 79

# El texto de la contratapa. Va aca y no en los capitulos porque no es parte
# del libro: es lo que lee alguien que lo tiene en la mano y todavia no lo
# compro.
CONTRATAPA = [
    "Hay cosas sobre el amor que nadie se sienta a explicar.",
    "Que la intensidad del principio no predice nada. Que una pelea no se "
    "gana. Que la gente cambia, pero casi nunca porque se lo pidan. Que lo "
    "que sostiene un v\u00ednculo no es espectacular: es aparecer, decir lo "
    "que pasa, pedir lo que uno quiere y reparar r\u00e1pido.",
    "Veintinueve cap\u00edtulos sobre apego, elecci\u00f3n de pareja, celos, "
    "l\u00edmites, rupturas, duelo, soledad, h\u00e1bitos y miedo, escritos "
    "a partir de lo que la investigaci\u00f3n en psicolog\u00eda sabe, y de "
    "lo que todav\u00eda no sabe. Con nombres, estudios y la parte "
    "inc\u00f3moda incluida.",
    "No promete una f\u00f3rmula. Propone algo m\u00e1s \u00fatil: entender "
    "por qu\u00e9 pasa lo que pasa, para poder elegir distinto.",
]
# La escalera de cuerpos de la contratapa, de mayor a menor. Se elige el mas
# grande con el que el texto ENTRA, medido antes de dibujar. Un bucle que
# achica hasta el piso y despues dibuja igual deja el texto encima del codigo
# de barras, y eso se ve en el ejemplar impreso y no aca.
ESCALERA = ((13, 10.5), (12, 10), (11.5, 9.5), (11, 9), (10, 8.5))


def lomo(paginas: int, papel: str = "crema") -> float:
    """El ancho del lomo: el grosor de la hoja por la cantidad de hojas."""
    if papel not in PAPEL:
        raise ValueError("papel desconocido: %s (hay %s)"
                         % (papel, ", ".join(sorted(PAPEL))))
    return paginas * PAPEL[papel]


def medida_de_cubierta(paginas: int, papel: str = "crema"):
    """(ancho, alto) de la hoja entera, con el sangrado de los cuatro bordes."""
    return (2 * SANGRA + 2 * MEDIDA[0] + lomo(paginas, papel),
            2 * SANGRA + MEDIDA[1])


def paginas_de(pdf: Path) -> int:
    """Las paginas del PDF ya armado.

    Se cuentan sobre el ARCHIVO y no sobre un contador de la corrida: el lomo
    es el grosor del papel por ese numero, asi que tiene que salir de lo que
    de verdad se va a imprimir.
    """
    from pypdf import PdfReader
    return len(PdfReader(str(pdf)).pages)


def _alto_de_contratapa(serif, primero, cuerpo, ancho, aire):
    """Lo que ocupa el texto de la contratapa, antes de dibujarlo."""
    alto = 0.0
    for i, parrafo in enumerate(CONTRATAPA):
        c_, f_ = ((primero, _variante(serif, "italic")) if i == 0
                  else (cuerpo, serif))
        alto += len(_envolver(parrafo, f_, c_, ancho)) * c_ * 1.55 + aire
    return alto


def cuerpo_de_contratapa(serif, ancho, disponible, aire):
    """El cuerpo mas grande con el que el texto entra, o se niega.

    Negarse y no dibujar en chiquito hasta el piso: la escalera tiene un
    ultimo escalon, y por debajo de ese el texto se mete en el hueco del
    codigo de barras. Una cubierta asi se ve recien en el ejemplar impreso, y
    para entonces ya se pago. Un error aca cuesta un minuto.
    """
    for primero, cuerpo in ESCALERA:
        if _alto_de_contratapa(serif, primero, cuerpo, ancho, aire) <= disponible:
            return primero, cuerpo
    raise ValueError(
        "el texto de la contratapa no entra arriba del codigo de barras ni "
        "con el cuerpo mas chico (%g pt): sobran %.0f mm. Hay que acortarlo."
        % (ESCALERA[-1][1],
           (_alto_de_contratapa(serif, *ESCALERA[-1], ancho, aire)
            - disponible) / mm))


def _contratapa(c, x0, y0, serif, sans, acento, tinta):
    """Lo que se lee por detras, y el hueco del codigo de barras.

    El hueco no es un margen de cortesia: la imprenta imprime el codigo ahi
    encima. Por eso el texto se mide contra ese limite y no contra el borde
    de la hoja.
    """
    # Un dedo mas adentro que el minimo de la imprenta: el cuarto de pulgada
    # es lo que NO se puede pasar, no una medida de diseno. Empezando justo
    # ahi el renglon sale de 70 caracteres y la contratapa se lee apretada.
    izq = x0 + SEGURO + 5 * mm
    ancho = MEDIDA[0] - 2 * (SEGURO + 5 * mm)
    arriba = y0 + MEDIDA[1] - SEGURO - 22 * mm
    # El piso: el alto del codigo de barras mas un dedo de aire.
    piso = y0 + SEGURO + BARRAS[1] + 8 * mm

    c.setFont(sans, 8)
    c.setFillColor(acento)
    c.drawString(izq, arriba, espaciar("VEINTINUEVE CAP\u00cdTULOS"))
    y = arriba - 5 * mm
    c.setStrokeColor(acento)
    c.setLineWidth(0.7)
    c.line(izq, y, izq + 20 * mm, y)
    y -= 13 * mm

    aire = 4.5 * mm
    primero, cuerpo = cuerpo_de_contratapa(serif, ancho, y - piso, aire)
    for i, parrafo in enumerate(CONTRATAPA):
        cu, fu = ((primero, _variante(serif, "italic")) if i == 0
                  else (cuerpo, serif))
        c.setFont(fu, cu)
        c.setFillColor(tinta)
        for linea in _envolver(parrafo, fu, cu, ancho):
            y -= cu * 1.55
            c.drawString(izq, y, linea)
        y -= aire

    # El autor abajo a la IZQUIERDA: a la derecha esta el codigo de barras.
    c.setFont(sans, 8)
    c.setFillColor(GRIS)
    c.drawString(izq, y0 + SEGURO + 6 * mm, espaciar(AUTOR.upper()))
    # Devuelve donde TERMINO el texto y donde no podia pasar. Es lo que se
    # mira en la prueba: contar pixeles dentro del hueco del codigo no
    # alcanza, porque el ultimo renglon de un parrafo es corto y puede
    # pasarse de largo sin pisar justo ese rectangulo.
    return y, piso


def _lomo(c, x, grueso, alto, serif, sans, acento, tinta, paginas):
    """El titulo y el autor de costado, leyendose de arriba abajo.

    De arriba abajo y con las letras mirando a la tapa: asi se lee derecho
    cuando el libro esta parado en un estante, que es la unica posicion en
    que alguien va a mirar el lomo.
    """
    if paginas < LOMO_MINIMO:
        return False
    util = grueso - 2 * SEGURO_LOMO
    largo = alto - 2 * SANGRA - 2 * SEGURO_LOMO
    for cuerpo in (11, 10, 9, 8, 7):
        titulo = libro.TITULO
        firma = espaciar(AUTOR.upper())
        ancho = (pdfmetrics.stringWidth(titulo, serif, cuerpo)
                 + 10 * mm
                 + pdfmetrics.stringWidth(firma, sans, cuerpo * 0.72))
        if cuerpo <= util and ancho <= largo:
            break
    else:
        return False
    c.saveState()
    c.translate(x + grueso / 2, alto / 2)
    c.rotate(-90)
    c.setFont(serif, cuerpo)
    c.setFillColor(tinta)
    desde = -ancho / 2
    c.drawString(desde, -cuerpo * 0.35, titulo)
    c.setFont(sans, cuerpo * 0.72)
    c.setFillColor(GRIS)
    c.drawString(desde + ancho
                 - pdfmetrics.stringWidth(firma, sans, cuerpo * 0.72),
                 -cuerpo * 0.3, firma)
    c.restoreState()
    return True


def _guias(c, ancho, alto, grueso):
    """El corte, los pliegues del lomo y la caja del codigo, para MIRAR.

    No van en el archivo que se manda a imprimir: se imprimirian. Por eso hay
    que pedirlas con --guias y no salen solas.
    """
    c.setStrokeColor(HexColor("#C86A6A"))
    c.setLineWidth(0.4)
    c.setDash(3, 3)
    c.rect(SANGRA, SANGRA, ancho - 2 * SANGRA, alto - 2 * SANGRA,
           stroke=1, fill=0)
    for x in (SANGRA + MEDIDA[0], SANGRA + MEDIDA[0] + grueso):
        c.line(x, 0, x, alto)
    c.rect(SANGRA + MEDIDA[0] - SEGURO - BARRAS[0], SANGRA + SEGURO,
           *BARRAS, stroke=1, fill=0)
    c.setDash()


def armar_cubierta(destino: Path, paginas: int, papel: str = "crema",
                   acento=ROJO, tinta=TINTA, guias: bool = False) -> Path:
    """La hoja entera que va a la imprenta: contratapa, lomo y tapa.

    **Esta SI lleva el acento en rojo, al contrario que el interior.** En
    impresion por demanda la tapa se imprime a color siempre y no cambia lo
    que cuesta el ejemplar; lo que se cobra a color es el INTERIOR, y por eso
    el interior tiene su version en negro y esta no.

    `paginas` no tiene valor por defecto a proposito: es el numero del que
    sale el lomo, y una cubierta con el lomo de otro libro no sirve para
    nada. Que lo tenga que pasar quien llama obliga a contarlo.
    """
    serif, sans = registrar_fuentes()
    grueso = lomo(paginas, papel)
    ancho, alto = medida_de_cubierta(paginas, papel)
    c = cv.Canvas(str(destino), pagesize=(ancho, alto))
    c.setFillColor(white)
    c.rect(0, 0, ancho, alto, stroke=0, fill=1)

    c.saveState()
    c.translate(SANGRA + MEDIDA[0] + grueso, SANGRA)
    dibujar_tapa(c, serif, sans, acento, tinta)
    c.restoreState()

    _contratapa(c, SANGRA, SANGRA, serif, sans, acento, tinta)
    _lomo(c, SANGRA + MEDIDA[0], grueso, alto, serif, sans, acento, tinta,
          paginas)
    if guias:
        _guias(c, ancho, alto, grueso)
    c.showPage()
    c.save()
    return destino


# --------------------------------------------------------------------------

def armar_epub(destino: Path) -> Path:
    """Con pandoc, del mismo texto. Sin medida de pagina: la elige el lector."""
    junto = destino.with_suffix(".md")
    partes = ["---", "title: %s" % libro.TITULO, "subtitle: %s" % SUBTITULO,
              "author: %s" % AUTOR, "lang: es", "---", ""]
    for ruta in sorted(CAPITULOS.glob("[0-9]*.md")):
        partes.append(ruta.read_text(encoding="utf-8").rstrip())
        partes.append("")
    junto.write_text("\n".join(partes), encoding="utf-8")
    subprocess.run(["pandoc", str(junto), "-o", str(destino),
                    "--toc", "--toc-depth=1", "--split-level=1"],
                   check=True, capture_output=True)
    junto.unlink()
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-pdf", action="store_true", help="sin el EPUB")
    ap.add_argument("--papel", choices=sorted(PAPEL), default="crema",
                    help="el papel del interior: de el sale el ancho del lomo")
    ap.add_argument("--guias", action="store_true",
                    help="dibujar el corte y la caja del codigo en la "
                         "cubierta (para mirar, NO para imprimir)")
    ap.add_argument("--ver", action="store_true", help="decir que haria")
    args = ap.parse_args(argv)

    capitulos = sorted(CAPITULOS.glob("[0-9]*.md"))
    palabras = sum(len(r.read_text(encoding="utf-8").split()) for r in capitulos)
    sin_dibujo = [int(r.name.split("-")[0]) for r in capitulos
                  if int(r.name.split("-")[0]) not in pictogramas.DIBUJOS]
    print("%d capitulos, %d palabras, %d pictogramas."
          % (len(capitulos), palabras, len(pictogramas.DIBUJOS)))
    if sin_dibujo:
        print("  Sin pictograma: %s (abren sin dibujo)." % sin_dibujo)
    if not capitulos:
        print("No hay capitulos escritos en %s." % CAPITULOS)
        return 1
    if args.ver:
        print("Con --ver no escribi nada.")
        return 0

    SALIDA.mkdir(parents=True, exist_ok=True)
    base = unicodedata.normalize("NFKD", libro.TITULO.lower())
    base = "".join(ch for ch in base if not unicodedata.combining(ch))
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")

    # En la de imprenta, tinta Y acento en negro puro. Alcanza UN pixel que no
    # sea gris para que el libro entero se facture como libro a color.
    for sufijo, acento, tinta, para in (
            ("-impresion", black, black, "para la imprenta"),
            ("-pantalla", ROJO, TINTA, "para leer y mandar")):
        pdf = armar_pdf(SALIDA / (base + sufijo + ".pdf"), acento, tinta)
        print("PDF %-12s %s (%.1f MB)"
              % (para, pdf.name, pdf.stat().st_size / 1e6))
    tapa = armar_portada(SALIDA / (base + "-portada.pdf"))
    print("Tapa:         %s" % tapa.name)

    # La cubierta va DESPUES y cuenta las paginas del PDF de imprenta: el
    # lomo es el grosor del papel por esas paginas, asi que no se puede
    # dibujar antes de saber cuantas quedaron.
    try:
        hojas = paginas_de(SALIDA / (base + "-impresion.pdf"))
    except ImportError:
        print("Sin cubierta:  hace falta pypdf para contar las paginas, y sin"
              " ese numero el lomo seria un invento.")
    else:
        cub = armar_cubierta(SALIDA / (base + "-cubierta.pdf"), hojas,
                             args.papel, guias=args.guias)
        a, h = medida_de_cubierta(hojas, args.papel)
        print("Cubierta:     %s" % cub.name)
        print("              %d paginas en papel %s, lomo %.2f mm, "
              "hoja %.1f x %.1f mm%s"
              % (hojas, args.papel, lomo(hojas, args.papel) / mm,
                 a / mm, h / mm, "  (CON guias, no imprimir)"
                 if args.guias else ""))
        if hojas % 2:
            print("              Son %d, impar: la imprenta agrega una hoja"
                  " en blanco al final." % hojas)
    if not args.solo_pdf:
        try:
            epub = armar_epub(SALIDA / (base + ".epub"))
            print("EPUB:         %s (%.1f MB)"
                  % (epub.name, epub.stat().st_size / 1e6))
        except (OSError, subprocess.CalledProcessError) as e:
            print("Sin EPUB: hace falta pandoc (%s)" % e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
