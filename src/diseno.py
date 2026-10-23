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
              centrado: bool = False, resaltado: Optional[str] = None) -> int:
    """Dibuja los renglones y devuelve dónde terminó.

    Con `resaltado`, la palabra marcada no cambia de color: lleva una mancha
    detrás, como un marcador. La mancha se dibuja ANTES que el texto en cada
    renglón, porque pintada encima lo taparía; por eso cada renglón se recorre
    dos veces en vez de dibujarse de una.
    """
    espacio = _ancho(draw, " ", f)
    alto = f.size
    for linea in lineas:
        largo = sum(_ancho(draw, tokens[i], f) for i in linea) + espacio * (len(linea) - 1)
        x0_linea = x0 + (ancho - largo) // 2 if centrado else x0
        if resaltado:
            x = x0_linea
            for i in linea:
                w = _ancho(draw, tokens[i], f)
                if flags[i]:
                    draw.rectangle([x - alto * 0.06, y + alto * 0.26,
                                    x + w + alto * 0.06, y + alto * 1.02], fill=resaltado)
                x += w + espacio
        x = x0_linea
        for i in linea:
            color = tinta if resaltado else (acento if flags[i] else tinta)
            draw.text((x, y), tokens[i], font=f, fill=color)
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


def _estilo_marcador(draw, frase, tema, pagina, e, c):
    """La palabra marcada con resaltador en vez de en color. Es el gesto de
    alguien subrayando un libro, que es lo que la pagina quiere provocar."""
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    ancho = (W - 2 * MARGEN) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, ZONA_ALTO * e, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    y = ZONA_Y * e + (ZONA_ALTO * e - paso * len(lineas)) // 2
    _escribir(draw, tokens, lineas, flags, f, MARGEN * e, y, ancho, paso,
              c["tinta"], c["acento"], resaltado=_mezclar(c["fondo"], c["acento"], 0.34))
    _pie(draw, pagina, tema, e, c["suave"])


def _estilo_ficha(draw, frase, tema, pagina, e, c):
    """Papel rayado limpio: el cuaderno sin fingir letra manuscrita.

    Las rayas se dibujan DESPUES de medir el texto, a su mismo paso, para que
    los renglones caigan sobre la linea. Con un paso fijo, el texto flota
    entre dos rayas y se nota enseguida que el papel es de mentira.
    """
    margen_izq = 150
    ancho = (W - margen_izq - MARGEN) * e
    tokens, tam, lineas, flags = _texto_medido(draw, frase, ancho, (ZONA_ALTO - 40) * e, e)
    f = _fuente("Lora-SemiBold.ttf", tam * e)
    paso = int(tam * e * INTERLINEA)
    y0 = ZONA_Y * e + ((ZONA_ALTO - 40) * e - paso * len(lineas)) // 2
    raya = _mezclar(c["fondo"], c["suave"], 0.38)
    primera, ultima = y0 - 3 * paso, y0 + paso * (len(lineas) + 3)
    y = y0 + int(tam * e * 1.06)
    tope = max(primera, 210 * e)
    while y > tope:
        y -= paso
    # El while termina POR DEBAJO del tope, asi que sin este paso de vuelta la
    # primera raya cae sobre el encabezado y lo tacha.
    if y < tope:
        y += paso
    while y < min(ultima, (PIE_Y - 40) * e):
        draw.rectangle([MARGEN * e, y, (W - MARGEN) * e, y + 1 * e], fill=raya)
        y += paso
    draw.rectangle([(margen_izq - 34) * e, 150 * e, (margen_izq - 34) * e + 2 * e,
                    (PIE_Y - 30) * e], fill=_mezclar(c["fondo"], c["acento"], 0.55))
    _cabecera(draw, pagina, tema, e, c["tinta"], c["acento"])
    _escribir(draw, tokens, lineas, flags, f, margen_izq * e, y0, ancho, paso,
              c["tinta"], c["acento"])
    _pie(draw, pagina, tema, e, c["suave"], con_regla=False)


# Los cuatro repartos que quedaron, elegidos por el usuario sobre once. Los
# otros siete se borraron en vez de dejarlos apagados: un renderer sin camino
# envejece sin que nadie lo note y despues nadie sabe si se puede tocar.
ESTILOS = {"regla": _estilo_regla, "marco": _estilo_marco,
           "ficha": _estilo_ficha, "marcador": _estilo_marcador}
POR_DEFECTO = "regla"


def estilo_del_turno(dia, hora: int, horas: Optional[List[int]] = None) -> str:
    """El estilo de ESE post. Dentro de un dia, cada post lleva uno distinto.

    Sale de la fecha y de la hora, no de cuantos se publicaron. Asi volver a
    dibujar el mismo post da el mismo estilo -el flyer aprobado es el que
    sale- y un dia salteado no corre la rueda.

    El dia entra en la cuenta ADEMAS de la hora, y no es decoracion: sin eso,
    las 8 llevarian siempre el mismo estilo y no habria forma de separar el
    estilo de la hora. Con el corrimiento, cada estilo pasa por todas las
    horas a lo largo de la semana.

    `horas` son las de ESE dia y no la parrilla completa. Con la rampa, un dia
    de cuatro posts usa cuatro de las ocho horas; contando el lugar sobre las
    ocho, esos cuatro caian en posiciones pares y salian solo DOS estilos
    distintos en todo el dia. Contando sobre las del dia, salen cuatro.
    """
    nombres = list(ESTILOS)
    orden = list(horas or [])
    lugar = orden.index(hora) if hora in orden else int(hora)
    return nombres[(lugar + dia.toordinal()) % len(nombres)]


def _colores(pagina: Pagina, estilo: str) -> dict:
    """La paleta, que es la misma para los cuatro: el crema de la marca.

    Sigue siendo una funcion y no cuatro constantes sueltas porque es el lugar
    donde un estilo nuevo pediria su variante, y porque `pagina` puede traer
    otra paleta sin tocar el dibujo.
    """
    fondo = pagina.color("fondo", "#F3EFE6")
    tinta = pagina.color("tinta", "#1F2933")
    acento = pagina.color("acento", "#B5654A")
    suave = pagina.color("suave", "#8C8F93")
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
