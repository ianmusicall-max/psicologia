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

from PIL import Image, ImageChops, ImageDraw, ImageFont

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


def _rgb(color: str):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _mezclar(uno: str, otro: str, cuanto: float) -> str:
    """`cuanto` de 0 a 1: 0 devuelve el primero, 1 el segundo."""
    a, b = _rgb(uno), _rgb(otro)
    return "#%02x%02x%02x" % tuple(int(round(a[i] + (b[i] - a[i]) * cuanto)) for i in range(3))


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


def _escribir(draw, tokens, lineas, flags, f, x0, y, ancho, paso, tinta, acento,
              centrado: bool = False) -> int:
    """Dibuja los renglones y devuelve dónde terminó."""
    espacio = _ancho(draw, " ", f)
    for linea in lineas:
        largo = sum(_ancho(draw, tokens[i], f) for i in linea) + espacio * (len(linea) - 1)
        x = x0 + (ancho - largo) // 2 if centrado else x0
        for i in linea:
            draw.text((x, y), tokens[i], font=f, fill=acento if flags[i] else tinta)
            x += _ancho(draw, tokens[i], f) + espacio
        y += paso
    return y


def _cabecera(draw, pagina, tema, e, tinta, acento):
    f_enc = _fuente("Montserrat-Bold.ttf", ENCABEZADO * e)
    _espaciado(draw, (MARGEN * e, ARRIBA * e), pagina.nombre.upper(), f_enc, tinta, e)
    f_cap = _fuente("Montserrat-Regular.ttf", ENCABEZADO * e)
    _espaciado(draw, ((W - MARGEN) * e, ARRIBA * e), "CAPÍTULO %d" % tema.capitulo,
               f_cap, acento, e, derecha=True)


def _pie(draw, pagina, tema, e, suave, con_regla: bool = True):
    if con_regla:
        draw.rectangle([MARGEN * e, PIE_Y * e, (W - MARGEN) * e, PIE_Y * e + 2 * e], fill=suave)
    f_pie = _fuente("Montserrat-Regular.ttf", PIE * e)
    firma = pagina.firma or pagina.nombre
    draw.text((MARGEN * e, (PIE_Y + 22) * e), firma, font=f_pie, fill=suave)
    f_tit = _fuente("Lora-Italic.ttf", (PIE + 4) * e)
    w_tit = _ancho(draw, tema.titulo, f_tit)
    if MARGEN * e + _ancho(draw, firma, f_pie) + 40 * e + w_tit <= (W - MARGEN) * e:
        draw.text(((W - MARGEN) * e - w_tit, (PIE_Y + 19) * e), tema.titulo, font=f_tit, fill=suave)


def _texto_medido(draw, frase, ancho, alto, e):
    tokens = frase.texto.split()
    tam, lineas = reparto(draw, tokens, ancho, alto, cuerpo_maximo(frase.texto), e)
    return tokens, tam, lineas, _banderas(frase, tokens)


# ---------------------------------------------------------------------------
# Los estilos. Cada uno recibe el lienzo ya pintado y pone lo suyo; lo que
# comparten -medir antes de dibujar, la palabra en el acento, el encabezado-
# vive arriba, para que agregar un estilo no sea copiar un renderer entero.
# ---------------------------------------------------------------------------

def _estilo_regla(draw, frase, tema, pagina, e, c):
    """El de siempre: una regla de acento y el texto alineado a la izquierda."""
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    ancho = (W - 2 * MARGEN) * e
    alto = ZONA_ALTO * e - (RAYA[1] + RAYA_AIRE) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, alto, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    bloque = (RAYA[1] + RAYA_AIRE) * e + paso * len(lineas)
    y = ZONA_Y * e + (ZONA_ALTO * e - bloque) // 2
    draw.rectangle([MARGEN * e, y, MARGEN * e + RAYA[0] * e, y + RAYA[1] * e], fill=c["acento"])
    _escribir(draw, tokens, lineas, flags, f, MARGEN * e, y + (RAYA[1] + RAYA_AIRE) * e,
              ancho, paso, c["tinta"], c["acento"])
    _pie(draw, pagina, tema, e, c["suave"])


def _estilo_tinta(draw, frase, tema, pagina, e, c):
    """Fondo oscuro. En el feed es lo que más corta, porque casi todo es claro."""
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    ancho = (W - 2 * MARGEN) * e
    alto = ZONA_ALTO * e - (RAYA[1] + RAYA_AIRE) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, alto, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    bloque = (RAYA[1] + RAYA_AIRE) * e + paso * len(lineas)
    y = ZONA_Y * e + (ZONA_ALTO * e - bloque) // 2
    draw.rectangle([MARGEN * e, y, MARGEN * e + RAYA[0] * e, y + RAYA[1] * e], fill=c["acento"])
    _escribir(draw, tokens, lineas, flags, f, MARGEN * e, y + (RAYA[1] + RAYA_AIRE) * e,
              ancho, paso, c["tinta"], c["acento"])
    _pie(draw, pagina, tema, e, c["suave"])


def _estilo_comillas(draw, frase, tema, pagina, e, c):
    """Una comilla enorme detrás, apenas visible, y el texto centrado."""
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    marca = _mezclar(c["fondo"], c["acento"], 0.22)
    f_marca = _fuente("Lora-SemiBold.ttf", 520 * e)
    draw.text((MARGEN * e - 30 * e, ZONA_Y * e - 150 * e), "\u201c", font=f_marca, fill=marca)
    ancho = (W - 2 * (MARGEN + 40)) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, ZONA_ALTO * e, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    y = ZONA_Y * e + (ZONA_ALTO * e - paso * len(lineas)) // 2
    y = _escribir(draw, tokens, lineas, flags, f, (MARGEN + 40) * e, y, ancho, paso,
                  c["tinta"], c["acento"], centrado=True)
    draw.rectangle([(W // 2 - 60) * e, y + 40 * e, (W // 2 + 60) * e, y + 40 * e + 4 * e],
                   fill=c["acento"])
    _pie(draw, pagina, tema, e, c["suave"])


def _estilo_marco(draw, frase, tema, pagina, e, c):
    """Como la página de un libro: un filete alrededor y el texto centrado."""
    borde, grueso = 56, 2
    draw.rectangle([borde * e, borde * e, (W - borde) * e, (H - borde) * e],
                   outline=c["suave"], width=grueso * e)
    draw.rectangle([(borde + 10) * e, (borde + 10) * e, (W - borde - 10) * e, (H - borde - 10) * e],
                   outline=_mezclar(c["fondo"], c["suave"], 0.45), width=1 * e)
    f_enc = _fuente("Montserrat-Bold.ttf", ENCABEZADO * e)
    rotulo = "CAPÍTULO %d" % tema.capitulo
    sep = ESPACIADO * e
    total = sum(_ancho(draw, x, f_enc) for x in rotulo) + sep * (len(rotulo) - 1)
    _espaciado(draw, ((W - total) // 2 * e, (borde + 54) * e), rotulo, f_enc, c["acento"], e)
    ancho = (W - 2 * (borde + 64)) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, (ZONA_ALTO - 60) * e, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    y = (ZONA_Y + 10) * e + ((ZONA_ALTO - 60) * e - paso * len(lineas)) // 2
    _escribir(draw, tokens, lineas, flags, f, (borde + 64) * e, y, ancho, paso,
              c["tinta"], c["acento"], centrado=True)
    f_tit = _fuente("Lora-Italic.ttf", (PIE + 4) * e)
    w_tit = _ancho(draw, tema.titulo, f_tit)
    draw.text(((W * e - w_tit) // 2, (H - borde - 96) * e), tema.titulo, font=f_tit, fill=c["suave"])
    f_pie = _fuente("Montserrat-Regular.ttf", PIE * e)
    firma = (pagina.firma or pagina.nombre).upper()
    _espaciado(draw, ((W - total) // 2 * e, (H - borde - 54) * e), firma, f_pie, c["suave"], e)


def _estilo_banda(draw, frase, tema, pagina, e, c):
    """Una banda de color abajo con el tema. El texto respira arriba."""
    alto_banda = 300
    draw.rectangle([0, (H - alto_banda) * e, W * e, H * e], fill=c["acento"])
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    ancho = (W - 2 * MARGEN) * e
    alto = (H - alto_banda - ZONA_Y - 60) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, alto, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    y = ZONA_Y * e + (alto - paso * len(lineas)) // 2
    draw.rectangle([MARGEN * e, (ZONA_Y - 60) * e, MARGEN * e + RAYA[0] * e,
                    (ZONA_Y - 60) * e + RAYA[1] * e], fill=c["acento"])
    _escribir(draw, tokens, lineas, flags, f, MARGEN * e, y, ancho, paso,
              c["tinta"], c["acento"])
    f_tit = _fuente("Lora-Italic.ttf", 40 * e)
    draw.text((MARGEN * e, (H - alto_banda + 86) * e), tema.titulo, font=f_tit, fill=c["fondo"])
    f_pie = _fuente("Montserrat-Bold.ttf", PIE * e)
    _espaciado(draw, (MARGEN * e, (H - alto_banda + 170) * e),
               (pagina.firma or pagina.nombre).upper(), f_pie,
               _mezclar(c["acento"], c["fondo"], 0.75), e)


# ---------------------------------------------------------------------------
# El reparto de la palabra gigante: la frase se parte en tres -lo que viene
# antes, la palabra destacada y lo que sigue- y la del medio ocupa el ancho.
# Es el recurso de las referencias que mando el usuario, y funciona con los
# datos que el banco ya tiene: `destacar` dice cual es esa palabra.
# ---------------------------------------------------------------------------

FOTOS = ROOT / "assets" / "fotos"
TIT_MARGEN = 72
TIT_CHICO = 34          # las dos lineas chicas
TIT_GRANDE_MAX = 210    # la palabra del medio
TIT_GRANDE_MIN = 72
TIT_AIRE = 14
# El claro del degradado no se elige a ojo: el texto va blanco, asi que el
# punto mas claro del fondo tiene que dejar contraste suficiente. Con #7C94A1
# -el primero que se probo- el blanco quedaba en 3,2 y se lee flojo.
DEGRADADO = ("#1F2E38", "#5C7482")
VELO_MINIMO = 0.22      # el tinte que toda foto lleva, para que sea una pagina y no un collage
VELO_MAXIMO = 0.78
VELO_BANDA = 0.45       # la franja de arriba donde cae el texto
VELO_CLARO = 0.85       # el percentil que se mira: los claros, no el promedio
# Para que el blanco tenga 4,5 de contraste, el fondo debajo no puede pasar de
# 119. Sale de despejar la formula de contraste de la WCAG, no de ojo. Se usa
# 117 y no 119 porque la mezcla redondea a enteros y justo en el limite caia
# del lado de afuera: lo agarro la prueba, con 4,4978.
VELO_TECHO = 117


def _degradado(ancho: int, alto: int, de: str, a: str) -> Image.Image:
    """Un degradado vertical, dibujado chico y agrandado: una barra por fila
    sobre el lienzo entero son miles de rectangulos y tarda."""
    tira = Image.new("RGB", (1, alto))
    pa, pb = _rgb(de), _rgb(a)
    for y in range(alto):
        t = y / max(alto - 1, 1)
        tira.putpixel((0, y), tuple(int(round(pa[i] + (pb[i] - pa[i]) * t)) for i in range(3)))
    return tira.resize((ancho, alto), Image.BILINEAR)


def _grano(img: Image.Image, fuerza: float = 0.22) -> Image.Image:
    """La textura que hace que un fondo plano parezca una foto.

    `effect_noise` lo genera de una, en C: hacerlo pixel por pixel en Python
    sobre 2160x2700 son seis millones de llamadas y tarda minutos.
    """
    ruido = Image.effect_noise(img.size, 18).convert("RGB")
    return Image.blend(img, ImageChops.overlay(img, ruido), fuerza)


def _foto_de(frase_id: str, ancho: int, alto: int) -> Optional[Image.Image]:
    """Una foto de assets/fotos recortada al lienzo, elegida por el id.

    Elegida por el id y no al azar: el mismo post dibujado dos veces tiene que
    dar la misma imagen, o el flyer que aprobaste no es el que sale.
    """
    fotos = sorted(x for x in FOTOS.glob("*") if x.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not fotos:
        return None
    elegida = fotos[sum(ord(c) for c in frase_id) % len(fotos)]
    img = Image.open(elegida).convert("RGB")
    escala = max(ancho / img.width, alto / img.height)
    img = img.resize((max(int(img.width * escala), ancho), max(int(img.height * escala), alto)),
                     Image.LANCZOS)
    izq, arriba = (img.width - ancho) // 2, (img.height - alto) // 2
    return img.crop((izq, arriba, izq + ancho, arriba + alto))


def _percentil(gris: Image.Image, parte: float) -> int:
    """El valor por debajo del cual queda `parte` de los pixeles."""
    histograma = gris.histogram()
    corte = sum(histograma) * parte
    acumulado = 0
    for valor, cuantos in enumerate(histograma):
        acumulado += cuantos
        if acumulado >= corte:
            return valor
    return 255


def _cuanto_velo(img: Image.Image, color: str) -> float:
    """Cuanto hay que oscurecer ESTA foto para que el blanco se lea encima.

    No es un numero fijo. Un numero fijo tiene que servir para el peor caso
    -una foto casi blanca- y entonces apaga de mas todas las demas: las fotos
    oscuras salen como manchas. Aca se mide la franja donde cae el texto y se
    oscurece lo justo.

    Se mira el percentil 85 y no el promedio: una foto oscura con un cielo
    claro arriba tiene buen promedio y el texto desaparece igual sobre el
    cielo. Es la misma leccion que el fondo de las tarjetas en el repo de
    salud, donde la mediana se quedaba corta.
    """
    franja = img.crop((0, 0, img.width, int(img.height * VELO_BANDA))).convert("L")
    claro = _percentil(franja, VELO_CLARO)
    if claro <= VELO_TECHO:
        return VELO_MINIMO
    fondo = Image.new("RGB", (1, 1), color).convert("L").getpixel((0, 0))
    hace_falta = (claro - VELO_TECHO) / max(claro - fondo, 1)
    return min(max(hace_falta, VELO_MINIMO), VELO_MAXIMO)


def _velo(img: Image.Image, color: str, cuanto: Optional[float] = None) -> Image.Image:
    """Oscurece la foto para que el texto blanco se lea encima.

    Sin esto, una foto clara deja el texto invisible, y eso no se ve hasta que
    el post ya salio.
    """
    if cuanto is None:
        cuanto = _cuanto_velo(img, color)
    return Image.blend(img, Image.new("RGB", img.size, color), cuanto)


def _tres_partes(frase: Frase):
    """(antes, palabra, despues) partiendo por lo que `destacar` marca."""
    tokens = frase.texto.split()
    flags = _banderas(frase, tokens)
    if not any(flags):
        return "", frase.texto, ""
    i = flags.index(True)
    j = len(flags) - 1 - flags[::-1].index(True)
    return " ".join(tokens[:i]), " ".join(tokens[i:j + 1]), " ".join(tokens[j + 1:])


def _grande_que_entra(draw, palabra: str, ancho: int, e: int):
    """El cuerpo mas grande con el que la palabra entra en UN renglon.

    No se parte: partida deja de ser el golpe de vista que es todo el recurso.
    Si ni con el minimo entra -una palabra larguisima- se devuelve el minimo y
    la palabra se dibuja mas chica, nunca saliendose.
    """
    for tam in range(TIT_GRANDE_MAX, TIT_GRANDE_MIN - 1, -2):
        if _ancho(draw, palabra, _fuente("ArchivoBlack-Regular.ttf", tam * e)) <= ancho:
            return tam
    for tam in range(TIT_GRANDE_MIN, 23, -2):
        if _ancho(draw, palabra, _fuente("ArchivoBlack-Regular.ttf", tam * e)) <= ancho:
            return tam
    return 24


def _lineas_chicas(draw, texto: str, f, ancho: int) -> List[str]:
    """Los renglones ya armados. `_partir` devuelve indices -los necesita el
    coloreado palabra por palabra de los otros estilos- y aca hacen falta
    cadenas, porque estas lineas van todas del mismo color."""
    if not texto:
        return []
    tokens = texto.split()
    return [" ".join(tokens[i] for i in linea) for linea in _partir(draw, tokens, f, ancho)]


def _titular(draw, frase, tema, pagina, e, c, arriba: bool = False):
    """El bloque de las tres partes. Lo comparten el estilo con foto y el de
    degradado: lo unico que cambia entre los dos es lo que hay detras."""
    ancho = (W - 2 * TIT_MARGEN) * e
    antes, palabra, despues = _tres_partes(frase)
    tam = _grande_que_entra(draw, palabra, ancho, e)
    f_g = _fuente("ArchivoBlack-Regular.ttf", tam * e)
    f_c = _fuente("Montserrat-Bold.ttf", TIT_CHICO * e)
    paso_c = int(TIT_CHICO * e * 1.3)
    l_antes = _lineas_chicas(draw, antes, f_c, ancho)
    l_despues = _lineas_chicas(draw, despues, f_c, ancho)
    alto_g = int(tam * e * 1.02)
    alto = paso_c * len(l_antes) + TIT_AIRE * e + alto_g + TIT_AIRE * e + paso_c * len(l_despues)
    y = (ZONA_Y - 120) * e if arriba else (H * e - alto) // 2

    for linea in l_antes:
        w = _ancho(draw, linea, f_c)
        draw.text(((W * e - w) // 2, y), linea, font=f_c, fill=c["tinta"])
        y += paso_c
    y += TIT_AIRE * e
    w = _ancho(draw, palabra, f_g)
    draw.text(((W * e - w) // 2, y - int(tam * e * 0.12)), palabra, font=f_g, fill=c["acento"])
    y += alto_g + TIT_AIRE * e
    for linea in l_despues:
        w = _ancho(draw, linea, f_c)
        draw.text(((W * e - w) // 2, y), linea, font=f_c, fill=c["tinta"])
        y += paso_c


def _firma_clara(draw, pagina, tema, e, color):
    f = _fuente("Montserrat-Bold.ttf", PIE * e)
    _espaciado(draw, (TIT_MARGEN * e, (H - 96) * e), (pagina.firma or pagina.nombre).upper(),
               f, color, e)
    f_cap = _fuente("Montserrat-Regular.ttf", PIE * e)
    _espaciado(draw, ((W - TIT_MARGEN) * e, (H - 96) * e), "CAPÍTULO %d" % tema.capitulo,
               f_cap, color, e, derecha=True)


def _estilo_palabra(draw, frase, tema, pagina, e, c):
    _titular(draw, frase, tema, pagina, e, c)
    _firma_clara(draw, pagina, tema, e, c["suave"])


def _estilo_foto(draw, frase, tema, pagina, e, c):
    _titular(draw, frase, tema, pagina, e, c, arriba=True)
    _firma_clara(draw, pagina, tema, e, c["suave"])


ESTILOS = {"regla": _estilo_regla, "tinta": _estilo_tinta, "comillas": _estilo_comillas,
           "marco": _estilo_marco, "banda": _estilo_banda,
           "palabra": _estilo_palabra, "foto": _estilo_foto}
# Los que se dibujan sobre una imagen y no sobre el color de la marca.
CON_IMAGEN = ("palabra", "foto")
POR_DEFECTO = "regla"


def _colores(pagina: Pagina, estilo: str) -> dict:
    """La paleta del estilo. `tinta` la da vuelta: fondo oscuro y texto claro.

    El acento se aclara sobre el fondo oscuro. Medido: el terracota de la
    marca sobre tinta da 3,46 de contraste, que es el mínimo justo para texto
    grande; aclarado da 6,3. La palabra destacada no tiene que ser legible a
    duras penas, tiene que SALTAR, porque es lo único que ese color hace.
    """
    fondo = pagina.color("fondo", "#F3EFE6")
    tinta = pagina.color("tinta", "#1F2933")
    acento = pagina.color("acento", "#B5654A")
    suave = pagina.color("suave", "#8C8F93")
    if estilo == "tinta":
        return {"fondo": tinta, "tinta": fondo, "acento": _mezclar(acento, fondo, 0.42),
                "suave": _mezclar(tinta, fondo, 0.45)}
    if estilo in CON_IMAGEN:
        # Sobre una foto o un degradado, el texto va claro y la palabra del
        # medio un punto mas clara todavia: es lo que la hace saltar sin
        # meter un color que la foto no tiene.
        return {"fondo": DEGRADADO[0], "tinta": "#FFFFFF", "acento": "#DCEAF2",
                "suave": _mezclar("#FFFFFF", DEGRADADO[0], 0.35)}
    return {"fondo": fondo, "tinta": tinta, "acento": acento, "suave": suave}


def render(frase: Frase, tema: Tema, pagina: Pagina, escala: int = 2,
           estilo: Optional[str] = None) -> Image.Image:
    """El flyer. `escala` 2 es el que se publica (2160x2700); 1 sirve para mirar.

    `estilo` elige el reparto: lo que cambia es la forma, nunca lo que dice.
    """
    e = escala
    estilo = estilo or getattr(pagina, "estilo", None) or POR_DEFECTO
    if estilo not in ESTILOS:
        raise ValueError("no existe el estilo %r; hay %s" % (estilo, ", ".join(sorted(ESTILOS))))
    c = _colores(pagina, estilo)
    if estilo in CON_IMAGEN:
        foto = _foto_de(frase.id, W * e, H * e) if estilo == "foto" else None
        if foto is not None:
            img = _velo(foto, DEGRADADO[0], 0.42)
        else:
            # Sin fotos en assets/fotos, «foto» cae al degradado en vez de
            # fallar: un turno perdido seria peor que un fondo mas simple.
            img = _grano(_degradado(W * e, H * e, *DEGRADADO))
    else:
        img = Image.new("RGB", (W * e, H * e), c["fondo"])
    draw = ImageDraw.Draw(img)
    ESTILOS[estilo](draw, frase, tema, pagina, e, c)
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
            escala: int = 2, estilo: Optional[str] = None) -> Path:
    """El valor por defecto se resuelve acá y no en la firma: en la firma se
    evalúa al importar y `diseno.FLYERS` dejaría de mandar."""
    return guardar(render(frase, tema, pagina, escala, estilo),
                   Path(carpeta or FLYERS) / ("%s.jpg" % frase.id))
