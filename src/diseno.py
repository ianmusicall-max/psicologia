"""El flyer de una frase: 1080x1350, papel cálido, la frase grande y una palabra en color.

Todo se mide ANTES de dibujar. Un bucle que achica «hasta que entre» y al
llegar al piso dibuja igual deja el texto encimado, y eso se ve en Facebook y
no aquí (lección del repo de salud, 2026-10-13). Si no entra, se levanta un
error: el validador acota el texto a 180 caracteres y a ese largo siempre
entra, así que el error solo puede venir de un cambio en estas constantes.
"""
from __future__ import annotations

import re
import random
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .config import Pagina
from .frases import Frase, Tema, PALABRA, destacadas

ROOT = Path(__file__).resolve().parent.parent
FUENTES = ROOT / "assets" / "fonts"
FLYERS = ROOT / "data" / "flyers"
# Donde van los dibujos que son para MIRAR y no para publicar: los cuatro
# modelos de la misma frase. Aparte de FLYERS a propósito, que es la carpeta
# de la que sale lo que se sube.
MUESTRAS = ROOT / "data" / "estilos"

W, H = 1080, 1350
# El tamaño al que se publica: W*ESCALA_PUBLICAR x H*ESCALA_PUBLICAR. Subido
# de 2 a 4 el 2026-11-05 a pedido del usuario ("sube la calidad por 2 a las
# imágenes"): 4320x5400 en vez de 2160x2700. Una sola constante y no un 2 o
# un 4 suelto en cada lugar que dibuja para publicar -`dibujar_todas.py`
# también la usa-, para que el día que vuelva a cambiar no haya que
# encontrar todos los lugares donde quedó copiada.
ESCALA_PUBLICAR = 4
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


# ---------------------------------------------------------------------------
# El estilo manuscrito: la hoja escrita con plumón. Es el de la página de la
# tercera edad y no se parece a los otros cuatro, así que tiene sus propias
# medidas en vez de reusar las de arriba.
# ---------------------------------------------------------------------------

# Inclinada y de lapicero, que son dos pedidos del usuario y se probaron en
# ese orden. `Kalam-Bold` fue la primera -inclinada, pero de plumón-, y
# `PatrickHand` la segunda -de lapicero, pero derecha-. La que cumple las dos
# es esta: el mismo trazo inclinado de Kalam en el peso fino.
#
# Y se lee más que las dos, que es lo que hay que cuidar en una página para
# gente de setenta años. Medido con la altura de la x y los pixeles de tinta
# de "xnueve": Lora-SemiBold a 80 px, que es lo que publica la otra página,
# da 42 y 4.950; esta a 96 con su trazo da 50 y 6.535.
MAN_FUENTE = "Kalam-Regular.ttf"
# El trazo de un lapicero es más parejo y un poco más grueso que el contorno
# de la fuente. Un pelo de más en cada letra es lo que lo separa de "una
# tipografía que imita letra". Subirlo convierte el lapicero en plumón: ahí
# está la diferencia con `Kalam-Bold`, que se descartó por eso.
MAN_TRAZO = 0.0
# Cuánto se mueve cada palabra respecto del renglón, en partes del cuerpo.
MAN_PULSO = 0.016
# La columna es ANGOSTA a propósito: con el margen de los otros estilos la
# frase sale en dos renglones largos y deja de parecer escrita a mano.
MAN_MARGEN = 180
MAN_ZONA_Y, MAN_ZONA_ALTO = 300, 760
MAN_INTERLINEA = 1.30
MAN_MAXIMO, MAN_MINIMO = 104, 40
MAN_FIRMA, MAN_FIRMA_Y = 34, H - 120
MAN_RAYA_PUNTOS = 9             # en cuántos tramos se quiebra el subrayado
# El papel envejecido (2026-11-05, pedido con una foto de referencia). Lo
# que tiene la referencia es GRANO -la fibra del papel, claro y oscuro al
# lado sin cambiar de tono- y no manchas de otro color: la primera versión
# mezclaba hacia un marrón y salían manchas de humo, y el usuario avisó que
# no era la misma textura. Ahora las dos capas son ruido de LUMINOSIDAD -el
# mismo delta en los tres canales, como ya hacía el grano viejo- en dos
# escalas: una fina, casi de un pixel, y una más ancha para que no se vea
# como estática de televisión. Ninguna cambia el color del papel, solo su
# brillo, que es lo que distingue una fibra de una mancha.
GRANO_FUERZA, GRANO_PANO = 19, 256
HILO_FUERZA, HILO_PANO = 4, (56, 70)
# El leve oscurecido hacia las esquinas, como una foto de papel bajo luz
# pareja y no de estudio. Mezclado hacia negro y no hacia un color: así
# oscurece sin teñir, y el centro queda intacto.
VINETA_FUERZA = 14


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


def _raya_a_mano(draw, x0, x1, y, color, grosor: int, semilla: str) -> None:
    """Un subrayado de plumón: ni recto ni parejo ni horizontal.

    El azar lleva SEMILLA, y la semilla es el id de la frase más la palabra.
    Sin eso, el flyer que aprobaste en Telegram y el que se publica después
    serían dos archivos distintos, y volver a dibujar un post daría otro
    trazo cada vez.

    El temblor y la inclinación salen del grosor, que sale del cuerpo, así
    que el trazo se ve igual en el flyer de mirar y en el de 2160 px.
    """
    r = random.Random(semilla)
    inclina = r.uniform(-0.6, 0.6) * grosor
    puntos = []
    for i in range(MAN_RAYA_PUNTOS + 1):
        t = i / MAN_RAYA_PUNTOS
        puntos.append((x0 + (x1 - x0) * t,
                       y + inclina * t + r.uniform(-0.45, 0.45) * grosor))
    draw.line(puntos, fill=color, width=grosor, joint="curve")


def _escribir(draw, tokens, lineas, flags, f, x0, y, ancho, paso, tinta, acento,
              centrado: bool = False, resaltado: Optional[str] = None,
              subrayado: Optional[str] = None, semilla: str = "",
              trazo: int = 0) -> int:
    """Dibuja los renglones y devuelve dónde terminó.

    Con `resaltado`, la palabra marcada no cambia de color: lleva una mancha
    detrás, como un marcador. La mancha se dibuja ANTES que el texto en cada
    renglón, porque pintada encima lo taparía; por eso cada renglón se recorre
    dos veces en vez de dibujarse de una.

    Con `subrayado`, va una raya a mano DEBAJO, que se dibuja después del
    texto: del mismo color, así que da igual si se tocan. Es el gesto del
    estilo manuscrito, donde no hay un segundo color con el que destacar.

    Los tres modos viven acá y no en cada estilo a propósito: dibujar token
    por token con su espacio es la parte que se rompe callada, y copiada en
    cinco lugares se arregla en uno solo.
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
        # El pulso: a mano, las palabras no se apoyan todas en el mismo
        # renglón. Son décimas del cuerpo y con semilla, como el subrayado;
        # sin esto la letra se ve dibujada por una máquina que imita letra.
        pulso = [round(random.Random(semilla + "pulso" + tokens[i]).uniform(
            -MAN_PULSO, MAN_PULSO) * alto) if subrayado else 0 for i in linea]
        x = x0_linea
        for k, i in enumerate(linea):
            color = tinta if (resaltado or subrayado) else (acento if flags[i] else tinta)
            draw.text((x, y + pulso[k]), tokens[i], font=f, fill=color,
                      stroke_width=trazo, stroke_fill=color)
            x += _ancho(draw, tokens[i], f) + espacio
        if subrayado:
            asc, desc = f.getmetrics()
            x = x0_linea
            for k, i in enumerate(linea):
                w = _ancho(draw, tokens[i], f)
                if flags[i]:
                    _raya_a_mano(draw, x - alto * 0.03, x + w + alto * 0.03,
                                 y + pulso[k] + asc + desc * 0.34, subrayado,
                                 max(3, round(alto * 0.055)), semilla + tokens[i])
                x += w + espacio
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
def _vineta(size: Tuple[int, int]) -> Image.Image:
    """Un paño chico con un circulo mas claro al medio y mas oscuro hacia las
    cuatro esquinas, agrandado despues: calcular la distancia al centro
    pixel por pixel en un flyer de 2160 tarda demasiado, y en un paño de unos
    pocos puntos por lado el costo es el mismo de siempre, unos milisegundos.
    """
    gw, gh = 18, 22
    diag = ((gw - 1) ** 2 + (gh - 1) ** 2) ** 0.5
    centro_x, centro_y = (gw - 1) / 2, (gh - 1) / 2
    datos = bytearray(gw * gh)
    for y in range(gh):
        for x in range(gw):
            d = ((x - centro_x) ** 2 + (y - centro_y) ** 2) ** 0.5 / (diag / 2)
            # Al cuadrado: la caida es suave al centro y se nota solo cerca
            # del borde, no a mitad de camino.
            datos[y * gw + x] = min(255, round(255 * min(1.0, d) ** 2))
    return Image.frombytes("L", (gw, gh), bytes(datos)).resize(size, Image.BICUBIC)


def _papel(fondo: str, size: Tuple[int, int], semilla: str) -> Image.Image:
    """El fondo, que no es un color plano sino un papel: grano de fibra en
    dos escalas y una esquina un poco mas oscura que el centro.

    Se dibuja ANTES del texto y no encima: en un papel de verdad la tinta
    queda sobre la fibra, no al reves.

    Va con semilla, como el subrayado y por lo mismo: el flyer que se aprueba
    y el que se publica tienen que ser el mismo archivo.
    """
    r = random.Random("papel" + semilla)
    img = Image.new("RGB", size, fondo)

    # El hilo: una grilla chica agrandada con interpolacion, para que la
    # fibra no quede perfectamente pareja de punta a punta -el papel de
    # verdad tampoco lo es-. Mas ancha que el grano de abajo y mas floja.
    gw, gh = HILO_PANO
    hilo = Image.frombytes("L", (gw, gh), bytes(
        128 + r.randint(-HILO_FUERZA, HILO_FUERZA) for _ in range(gw * gh)))
    hilo = hilo.resize(size, Image.BICUBIC)
    img = ImageChops.add(img, hilo.convert("RGB"), scale=1, offset=-128)

    # El grano fino: un paño chico de ruido por pixel, repetido en vez de
    # sortear los seis millones de pixeles de un flyer de 2160 -lo segundo
    # tarda segundos y aca se dibujan doce por dia-.
    n = GRANO_PANO
    pano = Image.frombytes("L", (n, n), bytes(
        128 + r.randint(-GRANO_FUERZA, GRANO_FUERZA) for _ in range(n * n)))
    ruido = Image.new("L", size)
    for x in range(0, size[0], n):
        for y in range(0, size[1], n):
            ruido.paste(pano, (x, y))
    img = ImageChops.add(img, ruido.convert("RGB"), scale=1, offset=-128)

    oscurecido = Image.new("RGB", size, _mezclar(fondo, "#000000", 0.22))
    alfa = _vineta(size).point(lambda v: v * VINETA_FUERZA // 255)
    return Image.composite(oscurecido, img, alfa)


def _estilo_manuscrito(draw, frase, tema, pagina, e, c):
    """La hoja escrita a mano con plumón: la frase entre comillas, centrada,
    y la palabra destacada subrayada.

    Tres cosas lo separan de los otros cuatro, y las tres son a propósito:

    - **No lleva encabezado ni regla de pie.** Lo que se imita es una hoja
      escrita, no una tarjeta de marca. Lo único que queda es la firma abajo,
      con la misma letra, porque un flyer que se comparte sin firma deja de
      ser de la página.
    - **La palabra destacada no cambia de color: va subrayada.** Un plumón
      tiene un color solo. Por eso este estilo no usa `acento`.
    - **La columna es angosta** (`MAN_MARGEN`, 180 contra 96). Es lo que
      parte la frase en renglones cortos; con el margen de los otros estilos
      salen dos renglones largos y el efecto se pierde.

    No entra en la rueda diaria: ver `ROTAN`.
    """
    tinta = c["tinta"]
    tokens = frase.texto.split()
    flags = _banderas(frase, tokens)
    # Las comillas se pegan al primer y al último token DESPUÉS de calcular
    # las banderas: `_banderas` cuenta palabras, y una comilla no lo es, pero
    # el ancho de cada token sí cambia y hay que medirlo con ellas puestas.
    pintar = list(tokens)
    pintar[0] = "\u201c" + pintar[0]
    pintar[-1] = pintar[-1] + "\u201d"

    ancho = (W - 2 * MAN_MARGEN) * e
    for tam in range(MAN_MAXIMO, MAN_MINIMO - 1, -2):
        f = _fuente(MAN_FUENTE, tam * e)
        if any(_ancho(draw, t, f) > ancho for t in pintar):
            continue
        lineas = _partir(draw, pintar, f, ancho)
        paso = int(tam * e * MAN_INTERLINEA)
        if len(lineas) * paso <= MAN_ZONA_ALTO * e:
            break
    else:
        raise ValueError("la frase no entra en el flyer ni con el cuerpo mínimo: %r"
                         % frase.texto)

    y = MAN_ZONA_Y * e + (MAN_ZONA_ALTO * e - len(lineas) * paso) // 2
    # El acento viaja aunque este estilo no lo use: es `_escribir` el que tiene
    # que saber que con `subrayado` no hay segundo color. Pasándole la tinta en
    # su lugar, el día que alguien borre esa condición no fallaría nada.
    _escribir(draw, pintar, lineas, flags, f, MAN_MARGEN * e, y, ancho, paso,
              tinta, c["acento"], centrado=True, subrayado=tinta, semilla=frase.id,
              trazo=round(tam * e * MAN_TRAZO))

    firma = pagina.firma or pagina.nombre
    f_firma = _fuente(MAN_FUENTE, MAN_FIRMA * e)
    draw.text(((W * e - _ancho(draw, firma, f_firma)) // 2, MAN_FIRMA_Y * e),
              firma, font=f_firma, fill=tinta)


ESTILOS = {"regla": _estilo_regla, "marco": _estilo_marco,
           "ficha": _estilo_ficha, "marcador": _estilo_marcador,
           "manuscrito": _estilo_manuscrito}
POR_DEFECTO = "regla"

# Los que entran en la RUEDA diaria, que no son todos los que existen.
#
# `manuscrito` no está, y esa ausencia es el punto: `estilo_del_turno` rotaba
# sobre `list(ESTILOS)`, así que agregar un estilo para OTRA página le habría
# cambiado los flyers a la que rota, sin que nadie lo hubiera pedido y sin que
# nada fallara. Un estilo nuevo entra en la rueda solo si alguien lo escribe
# acá.
ROTAN = ("regla", "marco", "ficha", "marcador")

# Los que llevan el papel envejecido (manchas, grano y viñeta) en vez del
# fondo plano. Va acá y no adentro del estilo porque el estilo recibe el
# lápiz y no la hoja: es la hoja la que cambia, no cómo se escribe sobre ella.
CON_PAPEL = ("manuscrito",)


def _rotar(lista: List, dia, hora: int, horas: Optional[List[int]] = None):
    """El elemento de `lista` que le toca a ESE turno: la fecha y la hora
    deciden, no el orden en que se publican.

    Es la cuenta que ya usaba `estilo_del_turno`, separada para que una
    segunda rotación -los papeles de la página de la tercera edad- la
    comparta sin copiarla. Mismo motivo que siempre: una cuenta copiada es
    una cuenta que un día se desincroniza de la original.
    """
    orden = list(horas or [])
    lugar = orden.index(hora) if hora in orden else int(hora)
    return lista[(lugar + dia.toordinal()) % len(lista)]


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
    return _rotar(list(ROTAN), dia, hora, horas)


def estilo_de(pagina: Pagina, dia, hora: int, horas_del_dia: Optional[List[int]] = None) -> str:
    """El modelo de ESE turno, mirando si la página rota o usa uno fijo.

    Es una línea, y por eso mismo estaba copiada en tres lugares: el publicador
    de cada hora, el calendario y ahora el botón del bot. Copiada, el día que
    la rotación cambie se arregla una y las otras siguen con la cuenta vieja:
    el bot mostraría un flyer y el turno publicaría otro.
    """
    if not getattr(pagina, "rotar_estilos", False):
        return getattr(pagina, "estilo", None) or POR_DEFECTO
    return estilo_del_turno(dia, hora, horas_del_dia)


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


def fondo_del_turno(fondos: List[str], dia, hora: int,
                    horas: Optional[List[int]] = None) -> str:
    """El papel de ESE turno, de una lista de colores a rotar.

    Misma cuenta que `estilo_del_turno` y por la misma razón: sale de la
    fecha y la hora, así que volver a dibujar el mismo post da el mismo
    papel, y un día entero no repite color -mientras la lista tenga al
    menos tantos colores como turnos tiene el día-.
    """
    return _rotar(fondos, dia, hora, horas)


def fondo_de(pagina: Pagina, dia, hora: int,
            horas_del_dia: Optional[List[int]] = None) -> str:
    """El papel de ESE turno, mirando si la página tiene varios para rotar.

    Sin `pagina.fondos` -la página de siempre, hoy- se queda con el único
    fondo de su paleta, intacto. Es la misma forma que `estilo_de`, y por lo
    mismo: para que el día que esto se copie a un tercer lugar no se repita
    la cuenta a mano.
    """
    if not pagina.fondos:
        return pagina.color("fondo", "#F3EFE6")
    return fondo_del_turno(pagina.fondos, dia, hora, horas_del_dia)


def render(frase: Frase, tema: Tema, pagina: Pagina, escala: int = ESCALA_PUBLICAR,
           estilo: Optional[str] = None, fondo: Optional[str] = None) -> Image.Image:
    """El flyer. `escala` ESCALA_PUBLICAR (4) es el que se publica (4320x5400);
    1 sirve para mirar.

    `estilo` elige el reparto: lo que cambia es la forma, nunca lo que dice.
    `fondo`, si se pasa, reemplaza el de la paleta -es lo que usa la rotación
    de papeles de `fondo_de`-. Sin él, se dibuja con el de siempre.
    """
    e = escala
    estilo = estilo or getattr(pagina, "estilo", None) or POR_DEFECTO
    if estilo not in ESTILOS:
        raise ValueError("no existe el estilo %r; hay %s" % (estilo, ", ".join(sorted(ESTILOS))))
    c = _colores(pagina, estilo)
    if fondo:
        c = dict(c, fondo=fondo)
    tamano = (W * e, H * e)
    if estilo in CON_PAPEL:
        img = _papel(c["fondo"], tamano, frase.id)
    else:
        img = Image.new("RGB", tamano, c["fondo"])
    draw = ImageDraw.Draw(img)
    ESTILOS[estilo](draw, frase, tema, pagina, e, c)
    return img


CALIDAD_JPG = 85

def guardar(img: Image.Image, ruta: Path) -> Path:
    """JPG de calidad alta. Escribe aparte y renombra: si el disco se llena a
    mitad de camino no queda un archivo de 0 bytes que después se suba.

    `CALIDAD_JPG` bajó de 92 a 85 el 2026-11-05, al subir ESCALA_PUBLICAR: a
    4320x5400 el papel con grano (CON_PAPEL) pesa casi 10 MB con calidad 92
    -medido sobre una muestra, siempre en esa franja porque lo que pesa es el
    grano y no el texto-, y el límite de la API de Facebook para una foto son
    10 MB. Publicar ahí es apostar el turno a que la frase de ese día no
    empuje el archivo un poco más. A 85 la misma muestra da unos 7,3 MB, con
    margen real, y a este tamaño y con este contenido -letra y grano, no una
    foto- no se nota la diferencia. La página sin papel pesa una fracción de
    eso con cualquiera de los dos números.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".parcial")
    img.save(tmp, format="JPEG", quality=CALIDAD_JPG, subsampling=0)
    tmp.replace(ruta)
    return ruta


def dibujar(frase: Frase, tema: Tema, pagina: Pagina, carpeta=None,
            escala: int = ESCALA_PUBLICAR, estilo: Optional[str] = None,
            fondo: Optional[str] = None) -> Path:
    """El valor por defecto se resuelve acá y no en la firma: en la firma se
    evalúa al importar y `diseno.FLYERS` dejaría de mandar."""
    return guardar(render(frase, tema, pagina, escala, estilo, fondo),
                   Path(carpeta or FLYERS) / ("%s.jpg" % frase.id))
