#!/usr/bin/env python3
"""El libro en PDF para imprimir y en EPUB para vender como ebook.

    libro_pdf.py                 los dos, en libro/salida/
    libro_pdf.py --solo-pdf      nada mas el PDF
    libro_pdf.py --ver           que haria, sin escribir nada

Lo pidio el usuario el 2026-10-28: «hagamos el libro en un PDF como para
imprimir o venderlo en ebook». Son dos formatos y dos cosas distintas, y por
eso se hacen los dos:

- **El PDF tiene medida fija** (15,24 x 22,86 cm, las 6 x 9 pulgadas que es la
  medida mas comun del libro de bolsillo y la que acepta la impresion por
  demanda). Los margenes son ESPEJADOS -mas ancho del lado de la encuadernacion
  en cada pagina- porque un libro impreso se cose por el medio y un margen
  parejo se come el texto del lado interno.
- **El EPUB no tiene medida.** El lector elige cuerpo y pantalla, asi que un
  PDF vendido como ebook se lee pesimo en un telefono. Lo arma `pandoc` del
  mismo texto, asi que los dos dicen exactamente lo mismo.

La salida va a `libro/salida/`, que esta en .gitignore: se regenera de los
capitulos en un segundo y un PDF de un mega por version dejaria el repositorio
inmanejable, que es la razon por la que `data/` entero esta ignorado.

Lo que importa si alguien lo toca:

- **El texto no se edita aca.** Sale de `libro/capitulos/*.md` tal como esta.
  Si algo hay que arreglar, se arregla ahi y se vuelve a generar: dos copias
  del mismo texto es como se descubre tarde que una de las dos esta vieja.
- **Las fuentes se buscan y si no estan se usa Times.** Caladea tiene redonda,
  cursiva, negrita y negrita cursiva, que es lo minimo para un libro. No viaja
  en el repositorio, asi que en otra maquina puede no estar y el PDF tiene que
  salir igual.
- **El indice lleva los numeros de pagina de verdad.** Para eso el documento se
  arma DOS veces (`multiBuild`): en la primera se anota en que pagina cae cada
  capitulo y en la segunda se escribe el indice. Un indice sin numeros no sirve
  para un libro impreso.
- **Cada capitulo abre en pagina impar**, como en cualquier libro, y en esa
  pagina no va el titulillo de arriba.
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
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch, mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak,  # noqa: E402
                                PageTemplate, Paragraph, Spacer)
from reportlab.platypus.doctemplate import ActionFlowable  # noqa: E402
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402
from reportlab.platypus.tables import TableStyle  # noqa: E402

from src import libro  # noqa: E402

CAPITULOS = ROOT / "libro" / "capitulos"
SALIDA = ROOT / "libro" / "salida"

SUBTITULO = "Ideas para quererte, elegir mejor y entenderte con quien querés"
AUTOR = "José Luis Del Carpio Chirinos"

# 6 x 9 pulgadas. Es la medida del libro de bolsillo de no ficción y la que
# toman las imprentas por demanda sin recortar nada.
MEDIDA = (6 * inch, 9 * inch)
# El de adentro es mas ancho que el de afuera: ahi va la encuadernacion.
#
# Y los dos son anchos a proposito. Con 19 y 15 el renglon daba unos 80
# caracteres, que para una pagina de 6 pulgadas es demasiado largo: el ojo
# pierde el renglon al volver. Con estos quedan unos 68, que es la medida de
# un libro de no ficcion. Cuesta unas veinte paginas mas y se lee mejor.
ADENTRO, AFUERA = 22 * mm, 18 * mm
ARRIBA, ABAJO = 18 * mm, 18 * mm

# Donde buscar las fuentes del libro. Si no estan, se cae a Times, que viene
# dentro del PDF por definicion.
FUENTES = {
    "LibroSerif": "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf",
    "LibroSerif-Bold": "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
    "LibroSerif-Italic": "/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf",
    "LibroSerif-BoldItalic": "/usr/share/fonts/truetype/crosextra/Caladea-BoldItalic.ttf",
    "LibroSans": "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
    "LibroSans-Bold": "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
}


def registrar_fuentes() -> tuple:
    """Devuelve (serif, sans) ya registradas, o las de Times si no estan."""
    try:
        for nombre, ruta in FUENTES.items():
            if not Path(ruta).exists():
                raise FileNotFoundError(ruta)
            pdfmetrics.registerFont(TTFont(nombre, ruta))
    except Exception as e:                                    # noqa: BLE001
        print("  Sin las fuentes del libro (%s); uso Times." % e)
        return "Times-Roman", "Helvetica"
    pdfmetrics.registerFontFamily(
        "LibroSerif", normal="LibroSerif", bold="LibroSerif-Bold",
        italic="LibroSerif-Italic", boldItalic="LibroSerif-BoldItalic")
    pdfmetrics.registerFontFamily("LibroSans", normal="LibroSans",
                                  bold="LibroSans-Bold")
    # La fuente con la que arranca cada pagina. Sin esto el PDF declara
    # Helvetica en todas -aunque no la use para nada- y Helvetica no viaja
    # dentro del archivo: una imprenta puede rechazar un PDF con una fuente
    # sin incrustar, y no hay forma de explicarle que no se usa.
    rl_config.canvas_basefontname = "LibroSerif"
    return "LibroSerif", "LibroSans"


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

    def __init__(self, destino, serif, sans):
        super().__init__(str(destino), pagesize=MEDIDA, title=libro.TITULO,
                         author=AUTOR, subject=SUBTITULO)
        self.serif, self.sans = serif, sans
        self.capitulo = ""
        self.abre_en = -1
        self.en_blanco = -1
        # Hasta que empiece el primer capitulo no se adorna nada: la portada y
        # el indice van sin titulillo ni folio. Arranca en infinito y lo baja
        # `afterFlowable` cuando ve el primer capitulo.
        self.cuerpo_desde = 10 ** 9
        ancho = MEDIDA[0] - ADENTRO - AFUERA
        alto = MEDIDA[1] - ARRIBA - ABAJO

        def marco(x, cual):
            return Frame(x, ABAJO, ancho, alto, id=cual, leftPadding=0,
                         rightPadding=0, topPadding=0, bottomPadding=0)

        # UNA plantilla por paridad, y no una por seccion: lo unico que cambia
        # entre las dos es de que lado queda el margen ancho. Lo que decide si
        # se adorna es `cuerpo_desde`, no la plantilla, asi que agregar una
        # seccion al libro no obliga a duplicar nada.
        self.addPageTemplates([
            PageTemplate(id="impar", frames=[marco(ADENTRO, "impar")],
                         onPageEnd=self.adornar),
            PageTemplate(id="par", frames=[marco(AFUERA, "par")],
                         onPageEnd=self.adornar),
        ])

    def handle_pageBegin(self):
        """Elige la plantilla por paridad ANTES de que se arme el marco.

        Una pagina impar queda a la derecha en el libro abierto, asi que ahi
        el margen ancho va a la izquierda; en la par, al reves. Tocar
        `self.frame` a mano no sirve: reportlab inicializa el marco dentro de
        `_handle_pageBegin` y un marco puesto por afuera llega sin la mitad de
        sus atributos.
        """
        quiere = "impar" if (self.page + 1) % 2 else "par"
        if self.pageTemplate.id != quiere:
            self.pageTemplate = self.pageTemplates[0 if quiere == "impar" else 1]
        self._handle_pageBegin()

    def adornar(self, lienzo, doc):
        if doc.page < doc.cuerpo_desde:
            return                      # portada e indice, sin nada
        if doc.page in (doc.abre_en, doc.en_blanco):
            return      # la que abre capitulo y la que quedo en blanco, limpias
        lienzo.saveState()
        lienzo.setFont(doc.sans, 8)
        lienzo.setFillGray(0.35)
        impar = doc.page % 2
        # El titulillo: en la impar el capitulo, en la par el libro. Asi el
        # lector sabe donde esta mirando cualquiera de las dos paginas.
        arriba = MEDIDA[1] - ARRIBA + 6 * mm
        if impar:
            lienzo.drawRightString(MEDIDA[0] - AFUERA, arriba, doc.capitulo)
        else:
            lienzo.drawString(AFUERA, arriba, libro.TITULO)
        lienzo.setFillGray(0.2)
        lienzo.setFont(doc.sans, 9)
        lienzo.drawCentredString(MEDIDA[0] / 2, ABAJO - 8 * mm, str(doc.page))
        lienzo.restoreState()

    def afterFlowable(self, flowable):
        """Anota los capitulos para el indice y para la pagina sin titulillo."""
        if getattr(flowable, "es_capitulo", False):
            self.capitulo = flowable.titulo_corto
            self.abre_en = self.page
            self.cuerpo_desde = min(self.cuerpo_desde, self.page)
            self.notify("TOCEntry", (0, flowable.titulo_corto, self.page))


class AbreEnImpar(ActionFlowable):
    """Si la pagina que viene es par, mete una en blanco.

    Asi cada capitulo empieza del lado derecho del libro abierto, que es como
    abre un capitulo en cualquier libro impreso. Va DESPUES del `PageBreak`:
    cuando esto corre ya estamos arriba de la pagina nueva, y lo unico que hay
    que decidir es si hace falta una mas.

    No se puede hacer con un espaciador: un espaciador no sabe en que pagina
    esta. Esto si, porque `apply` recibe el documento.
    """

    def apply(self, doc):
        if doc.page % 2 == 0:
            doc.en_blanco = doc.page      # esa no lleva titulillo ni folio
            doc.handle_pageBreak()


def estilos(serif, sans):
    cuerpo = ParagraphStyle(
        "cuerpo", fontName=serif, fontSize=10.5, leading=15.2,
        alignment=TA_JUSTIFY, spaceAfter=0,
        # Partir en silabas es lo que hace que un texto justificado no quede
        # con rios de espacios. Si `pyphen` no esta instalado, reportlab lo
        # ignora y el texto sale igual, nada mas que mas flojo.
        hyphenationLang="es", embeddedHyphenation=1, uriWasteReduce=0.3)
    return {
        "cuerpo": cuerpo,
        # El primer parrafo de un apartado va sin sangria y los siguientes con
        # sangria y sin espacio: es como se separan los parrafos en un libro.
        "primero": ParagraphStyle("primero", parent=cuerpo, firstLineIndent=0),
        "seguido": ParagraphStyle("seguido", parent=cuerpo,
                                  firstLineIndent=5 * mm),
        "epigrafe": ParagraphStyle(
            "epigrafe", parent=cuerpo, fontName=serif + "-Italic"
            if serif != "Times-Roman" else "Times-Italic",
            fontSize=10, leading=14, leftIndent=7 * mm, rightIndent=4 * mm,
            firstLineIndent=0, spaceBefore=2 * mm, spaceAfter=4 * mm),
        "apartado": ParagraphStyle(
            "apartado", fontName=sans + "-Bold" if sans != "Helvetica"
            else "Helvetica-Bold", fontSize=11, leading=14,
            spaceBefore=8 * mm, spaceAfter=3 * mm),
        "numero": ParagraphStyle("numero", fontName=sans, fontSize=9,
                                 leading=12, alignment=TA_CENTER,
                                 textColor="#7a7a7a", spaceAfter=3 * mm),
        "capitulo": ParagraphStyle(
            "capitulo", fontName=serif + "-Bold" if serif != "Times-Roman"
            else "Times-Bold", fontSize=19, leading=23, alignment=TA_CENTER,
            spaceAfter=12 * mm),
        "filete": ParagraphStyle("filete", fontName=sans, fontSize=10,
                                 alignment=TA_CENTER, textColor="#9a9a9a",
                                 spaceBefore=5 * mm, spaceAfter=5 * mm),
        "titulazo": ParagraphStyle(
            "titulazo", fontName=serif + "-Bold" if serif != "Times-Roman"
            else "Times-Bold", fontSize=26, leading=31, alignment=TA_CENTER),
        "subtitulazo": ParagraphStyle(
            "subtitulazo", fontName=serif + "-Italic" if serif != "Times-Roman"
            else "Times-Italic", fontSize=13, leading=18, alignment=TA_CENTER),
        "autor": ParagraphStyle("autor", fontName=sans, fontSize=12,
                                alignment=TA_CENTER),
        "credito": ParagraphStyle("credito", fontName=serif, fontSize=9,
                                  leading=13, alignment=TA_CENTER,
                                  textColor="#555555"),
        "indice": ParagraphStyle("indice", fontName=serif, fontSize=10.5,
                                 leading=18),
    }


class Capitulo(Paragraph):
    """Un titulo de capitulo que ademas se anuncia: ver `afterFlowable`."""

    es_capitulo = True

    def __init__(self, texto, estilo, titulo_corto):
        super().__init__(texto, estilo)
        self.titulo_corto = titulo_corto


def armar_pdf(destino: Path) -> Path:
    serif, sans = registrar_fuentes()
    est = estilos(serif, sans)
    doc = Libro(destino, serif, sans)
    hist = [
        Spacer(1, 38 * mm),
        Paragraph(libro.TITULO, est["titulazo"]),
        Spacer(1, 8 * mm),
        Paragraph(SUBTITULO, est["subtitulazo"]),
        Spacer(1, 26 * mm),
        Paragraph(AUTOR, est["autor"]),
        PageBreak(),
        Spacer(1, 60 * mm),
        Paragraph("%s<br/><br/>%s<br/><br/>Primera edición" % (libro.TITULO, AUTOR),
                  est["credito"]),
        PageBreak(),
        Paragraph("Índice", est["capitulo"]),
    ]
    indice = TableOfContents()
    indice.levelStyles = [est["indice"]]
    indice.dotsMinLevel = 0
    # El indice se dibuja sobre una tabla, y una tabla de reportlab arranca en
    # Helvetica aunque no la use. Eso deja una fuente SIN INCRUSTAR declarada
    # en el PDF, y una imprenta puede rechazarlo por eso: no hay forma de
    # explicarle que no se usa.
    indice.tableStyle = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("FONT", (0, 0), (-1, -1), serif),
    ])
    hist += [indice, PageBreak(), AbreEnImpar()]

    capitulos = sorted(CAPITULOS.glob("[0-9]*.md"))
    for ruta in capitulos:
        md = ruta.read_text(encoding="utf-8")
        primero_del_apartado = True
        for clase, texto in bloques(md):
            if clase == "titulo":
                # «Capítulo 16 · Los que estaban antes» se parte: el número
                # arriba y chico, el nombre grande. Es como abre un capítulo en
                # un libro, y además deja el índice con el nombre solo.
                numero, _, nombre = texto.partition("·")
                nombre = nombre.strip() or texto
                # En el indice va con su numero («2. La mente que...»): sin
                # el, el lector que busca «el capitulo 12» tiene que contar
                # renglones.
                enumerado = "%s. %s" % (
                    (re.search(r"\d+", numero) or [""])[0], nombre)
                hist += [Spacer(1, 14 * mm),
                         Paragraph(numero.strip().upper(), est["numero"]),
                         Capitulo(en_linea(nombre), est["capitulo"],
                                  enumerado.lstrip(". "))]
                primero_del_apartado = True
            elif clase == "apartado":
                hist.append(Paragraph(en_linea(texto), est["apartado"]))
                primero_del_apartado = True
            elif clase == "epigrafe":
                hist.append(Paragraph(en_linea(texto), est["epigrafe"]))
                primero_del_apartado = True
            elif clase == "filete":
                hist.append(Paragraph("* * *", est["filete"]))
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


class AbreEnImpar(ActionFlowable):
    """Si la pagina que viene es par, mete una en blanco.

    Asi cada capitulo empieza del lado derecho del libro abierto, que es como
    abre un capitulo en cualquier libro impreso. Va DESPUES del `PageBreak`:
    cuando esto corre ya estamos arriba de la pagina nueva, y lo unico que
    hay que decidir es si hace falta una mas.

    No se puede hacer con un espaciador: un espaciador no sabe en que pagina
    esta. Esto si, porque `apply` recibe el documento.
    """

    def apply(self, doc):
        if doc.page % 2 == 0:
            doc.en_blanco = doc.page      # esa no lleva titulillo ni folio
            doc.handle_pageBreak()


def armar_epub(destino: Path) -> Path:
    """Con pandoc, del mismo texto. Sin medida de pagina: la elige el lector."""
    junto = destino.with_suffix(".md")
    partes = ["---",
              "title: %s" % libro.TITULO,
              "subtitle: %s" % SUBTITULO,
              "author: %s" % AUTOR,
              "lang: es",
              "---", ""]
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
    ap.add_argument("--ver", action="store_true", help="decir que haria")
    args = ap.parse_args(argv)

    capitulos = sorted(CAPITULOS.glob("[0-9]*.md"))
    palabras = sum(len(r.read_text(encoding="utf-8").split()) for r in capitulos)
    print("%d capitulos, %d palabras." % (len(capitulos), palabras))
    if not capitulos:
        print("No hay capitulos escritos en %s." % CAPITULOS)
        return 1
    if args.ver:
        print("Con --ver no escribi nada.")
        return 0

    SALIDA.mkdir(parents=True, exist_ok=True)
    # Sin tildes y con guiones: el archivo viaja por correo, por la web y por
    # el lector de ebooks de alguien mas, y un nombre con «ó» se rompe en
    # alguno de los tres.
    base = unicodedata.normalize("NFKD", libro.TITULO.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    pdf = armar_pdf(SALIDA / (base + ".pdf"))
    print("PDF:  %s (%.1f MB)" % (pdf, pdf.stat().st_size / 1e6))
    if not args.solo_pdf:
        try:
            epub = armar_epub(SALIDA / (base + ".epub"))
            print("EPUB: %s (%.1f MB)" % (epub, epub.stat().st_size / 1e6))
        except (OSError, subprocess.CalledProcessError) as e:
            print("Sin EPUB: hace falta pandoc (%s)" % e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
