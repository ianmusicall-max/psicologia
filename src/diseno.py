"""El flyer de una frase: 1080x1350, papel cálido, la frase grande y una palabra en color.

Todo se mide ANTES de dibujar. Un bucle que achica «hasta que entre» y al
llegar al piso dibuja igual deja el texto encimado, y eso se ve en Facebook y
no aquí (lección del repo de salud, 2026-10-13). Si no entra, se levanta un
error: el validador acota el texto a 180 caracteres y a ese largo siempre
entra, así que el error solo puede venir de un cambio en estas constantes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .config import Pagina
from .frases import Frase, Tema, PALABRA, destacadas

ROOT = Path(__file__).resolve().parent.parent
FUENTES = ROOT / "assets" / "fonts"
FLYERS = ROOT / "data" / "flyers"

W, H = 1080, 1350
MARGEN = 96
ARRIBA = 92            # línea base del encabezado
ZONA_Y = 230           # donde empieza la zona de la frase
ZONA_ALTO = 870        # ...y cuánto mide (termina en 1100)
PIE_Y = H - 118        # el pie
RAYA = (120, 6)        # la raya de acento sobre la frase
RAYA_AIRE = 44         # aire entre la raya y la primera línea
INTERLINEA = 1.22
CUERPO_MIN = 40
ENCABEZADO = 24
PIE = 24
ESPACIADO = 3          # entre letras del encabezado

# Frase corta, letra grande; frase larga, un poco más chica. Es lo mismo que
# la caja de cierre de los flyers de salud: el tamaño se administra solo.
def cuerpo_maximo(texto: str) -> int:
    n = len(texto)
    if n <= 60:
        return 88
    if n <= 110:
        return 80
    return 72


def _fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / nombre), tam)


def _ancho(draw, texto: str, f) -> int:
    return int(draw.textlength(texto, font=f))


def _partir(draw, tokens: List[str], f, ancho: int) -> List[List[int]]:
    """Reparte los tokens (palabras con sus signos) en renglones que entren
    en `ancho`. Devuelve índices, no texto, para poder colorear cada uno."""
    espacio = _ancho(draw, " ", f)
    lineas: List[List[int]] = [[]]
    x = 0
    for i, tok in enumerate(tokens):
        w = _ancho(draw, tok, f)
        if lineas[-1] and x + espacio + w > ancho:
            lineas.append([])
            x = 0
        x += (espacio if lineas[-1] else 0) + w
        lineas[-1].append(i)
    return lineas


def reparto(draw, tokens: List[str], ancho: int, alto: int, tam_max: int,
            escala: int = 1) -> Tuple[int, List[List[int]]]:
    """La letra más grande con la que la frase entra en la zona, y sus renglones.

    Mira las dos cosas: que ninguna palabra sea más ancha que la columna y
    que los renglones quepan en el alto. Si ni con el mínimo entra, falla
    en vez de dibujar encimado.
    """
    for tam in range(tam_max, CUERPO_MIN - 1, -2):
        f = _fuente("Lora-SemiBold.ttf", tam * escala)
        if any(_ancho(draw, t, f) > ancho for t in tokens):
            continue
        lineas = _partir(draw, tokens, f, ancho)
        if len(lineas) * tam * escala * INTERLINEA <= alto:
            return tam, lineas
    raise ValueError("la frase no entra en el flyer ni con el cuerpo mínimo: %r" % " ".join(tokens))


def _banderas(frase: Frase, tokens: List[str]) -> List[bool]:
    """Para cada token, si va en color: si alguna de sus palabras está destacada."""
    marcas = destacadas(frase)
    flags, k = [], 0
    for tok in tokens:
        n = len(PALABRA.findall(tok))
        flags.append(any(marcas[k:k + n]))
        k += n
    return flags


def _espaciado(draw, xy, texto: str, f, color, escala: int, derecha: bool = False) -> None:
    """Dibuja letra por letra con aire entre ellas (para el encabezado)."""
    sep = ESPACIADO * escala
    total = sum(_ancho(draw, c, f) for c in texto) + sep * (len(texto) - 1)
    x, y = xy
    if derecha:
        x -= total
    for c in texto:
        draw.text((x, y), c, font=f, fill=color)
        x += _ancho(draw, c, f) + sep


def render(frase: Frase, tema: Tema, pagina: Pagina, escala: int = 2) -> Image.Image:
    """El flyer. `escala` 2 es el que se publica (2160x2700); 1 sirve para mirar."""
    e = escala
    fondo = pagina.color("fondo", "#F3EFE6")
    tinta = pagina.color("tinta", "#1F2933")
    acento = pagina.color("acento", "#B5654A")
    suave = pagina.color("suave", "#8C8F93")

    img = Image.new("RGB", (W * e, H * e), fondo)
    draw = ImageDraw.Draw(img)

    # Encabezado: la página a la izquierda, el capítulo a la derecha.
    f_enc = _fuente("Montserrat-Bold.ttf", ENCABEZADO * e)
    _espaciado(draw, (MARGEN * e, ARRIBA * e), pagina.nombre.upper(), f_enc, tinta, e)
    f_cap = _fuente("Montserrat-Regular.ttf", ENCABEZADO * e)
    _espaciado(draw, ((W - MARGEN) * e, ARRIBA * e), "CAPÍTULO %d" % tema.capitulo,
               f_cap, acento, e, derecha=True)

    # La frase, medida antes de dibujar.
    tokens = frase.texto.split()
    ancho = (W - 2 * MARGEN) * e
    alto = ZONA_ALTO * e - (RAYA[1] + RAYA_AIRE) * e
    tam, lineas = reparto(draw, tokens, ancho, alto, cuerpo_maximo(frase.texto), e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    bloque = (RAYA[1] + RAYA_AIRE) * e + paso * len(lineas)
    y = ZONA_Y * e + (ZONA_ALTO * e - bloque) // 2
    draw.rectangle([MARGEN * e, y, MARGEN * e + RAYA[0] * e, y + RAYA[1] * e], fill=acento)
    y += (RAYA[1] + RAYA_AIRE) * e

    flags = _banderas(frase, tokens)
    espacio = _ancho(draw, " ", f)
    for linea in lineas:
        x = MARGEN * e
        for i in linea:
            draw.text((x, y), tokens[i], font=f, fill=acento if flags[i] else tinta)
            x += _ancho(draw, tokens[i], f) + espacio
        y += paso

    # Pie: una regla fina, la firma a la izquierda y el título del capítulo a
    # la derecha. Si los dos no entran, el título cede: la firma es la página.
    draw.rectangle([MARGEN * e, PIE_Y * e, (W - MARGEN) * e, PIE_Y * e + 2 * e], fill=suave)
    f_pie = _fuente("Montserrat-Regular.ttf", PIE * e)
    firma = pagina.firma or pagina.nombre
    draw.text((MARGEN * e, (PIE_Y + 22) * e), firma, font=f_pie, fill=suave)
    f_tit = _fuente("Lora-Italic.ttf", (PIE + 4) * e)
    w_tit = _ancho(draw, tema.titulo, f_tit)
    if MARGEN * e + _ancho(draw, firma, f_pie) + 40 * e + w_tit <= (W - MARGEN) * e:
        draw.text(((W - MARGEN) * e - w_tit, (PIE_Y + 19) * e), tema.titulo, font=f_tit, fill=suave)
    return img


def guardar(img: Image.Image, ruta: Path) -> Path:
    """JPG de calidad alta. Escribe aparte y renombra: si el disco se llena a
    mitad de camino no queda un archivo de 0 bytes que después se suba."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".parcial")
    img.save(tmp, format="JPEG", quality=92, subsampling=0)
    tmp.replace(ruta)
    return ruta


def dibujar(frase: Frase, tema: Tema, pagina: Pagina, carpeta=None,
            escala: int = 2) -> Path:
    """El valor por defecto se resuelve acá y no en la firma: en la firma se
    evalúa al importar y `diseno.FLYERS` dejaría de mandar."""
    return guardar(render(frase, tema, pagina, escala),
                   Path(carpeta or FLYERS) / ("%s.jpg" % frase.id))
