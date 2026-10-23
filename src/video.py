"""El reel: la frase leída sobre un fondo, con el texto apareciendo renglón a renglón.

Es el formato de la referencia que mandó el usuario: vertical, el texto en el
medio, una línea a la vez, sobre algo que se mueve despacio.

**Lo que cuesta y lo que no**, que es lo que decide cómo está hecho esto:

- El armado es gratis: ffmpeg, que ya está en la Mac. No hay ninguna API.
- El fondo puede ser gratis: por defecto NO se usa ningún video, se dibuja el
  papel de la marca con una deriva lenta. Así un reel sale hoy, sin descargar
  nada y sin que se vea de otra página. Un clip de naturaleza es una mejora,
  no un requisito: va con `--fondo`.
- La voz es lo único que se decide. Grabada por el usuario es gratis y es la
  mejor; `say` del Mac es gratis y suena sintético; una voz de IA sería la
  primera API paga del repo. Sin voz, el reel sale mudo y se lee igual.

**El texto se mide antes de dibujar**, como el flyer: se elige el cuerpo más
grande con el que TODAS las unidades entran en dos renglones de 900 px. Un
bucle que achica «hasta que entre» y al llegar al piso dibuja igual deja el
texto encimado, y eso se ve en Facebook y no acá.

**El color del texto depende del fondo y no del gusto.** Sobre un video, el
amarillo con contorno es lo único que se lee pase lo que pase debajo; sobre el
papel de la marca, el amarillo desaparece y va la tinta. Por eso son dos temas
y se elige solo según haya fondo o no.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import Pagina
from .frases import Frase

ROOT = Path(__file__).resolve().parent.parent
FUENTES = ROOT / "assets" / "fonts"
REELS = ROOT / "data" / "reels"
FONDOS = ROOT / "data" / "fondos"

ANCHO, ALTO = 1080, 1920
FPS = 30
MARGEN = 90
COLUMNA = ANCHO - 2 * MARGEN          # 900 px de texto
RENGLONES = 2                          # por unidad; una tercera se lee como párrafo
CUERPOS = (112, 104, 96, 88, 80, 72, 64)

# Facebook e Instagram cortan el reel a los 90 segundos. Una frase con su
# reflexión son unas 170 palabras, o sea unos 70: entra, pero no sobra tanto
# como para no mirarlo.
TOPE_SEGUNDOS = 90

# Leído en voz alta, en español, unos 17 caracteres por segundo. Es lo que se
# usa cuando NO hay voz: sin audio no hay nada que medir y el renglón tiene que
# durar lo que tardaría en leerse.
SEGUNDOS_POR_CARACTER = 0.058
MINIMO_POR_UNIDAD = 1.5
COLA = 0.8                             # aire al final, para que no corte seco

# Una unidad es lo que se muestra de una vez. El número no es de gusto: se
# midió sobre las 153 frases del banco. Con 84 caracteres la letra tiene que
# bajar a 48 px -diminuta en un cuadro de 1920- y con 40 el 96% sale a 88 px
# o más. Unidades cortas además cambian más seguido, que es lo que hace la
# referencia: fragmentos de media frase, no párrafos.
UNIDAD_MAXIMA = 40

TEMAS = {
    # amarillo con contorno negro: es lo que se lee sobre cualquier cosa que
    # pase debajo, y es lo que hace la referencia.
    "video": {"color": "#F5C542", "contorno": "#000000", "grosor": 4, "sombra": 2},
    # sobre el papel de la marca el amarillo desaparece: va la tinta, sin
    # contorno, que sobre un fondo liso se vería como un sticker.
    "papel": {"color": "", "contorno": "", "grosor": 0, "sombra": 0},
}


class VideoError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# El guion: qué se muestra y cuándo.
# ---------------------------------------------------------------------------

CORTE_FUERTE = re.compile(r"(?<=[.!?])\s+")
CORTE_SUAVE = re.compile(r"(?<=[,;:])\s+")


# Dónde se puede cortar una oración sin comas. El corte se elige, no se toma
# el primero que entra: un trozo que termina en «con» o en «del» deja la frase
# colgando, y uno que empieza con «que» o «porque» se lee solo.
ARRANCAN = {"que", "si", "porque", "aunque", "cuando", "mientras", "pero",
            "sino", "donde", "para", "y", "o", "ni", "como", "hasta", "desde"}
NO_TERMINAN = {"el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
               "al", "a", "en", "con", "sin", "por", "para", "su", "tu", "mi", "mis",
               "lo", "le", "se", "que", "y", "o", "ni", "no", "más", "muy",
               # los auxiliares piden su participio, y estos tres piden su «de»
               "es", "son", "era", "eran", "fue", "ha", "han", "he", "has",
               "había", "habían", "está", "están", "ser", "después", "antes", "dentro"}


def _pelada(palabra: str) -> str:
    return palabra.lower().strip(",;:.¿?¡!«»\"'")


def _cortar(texto: str, tope: int) -> List[str]:
    """Parte en dos por el mejor lugar, y repite mientras no entre.

    El puntaje es el desequilibrio entre las dos mitades, con premio si lo que
    sigue arranca con un conector y castigo si lo que queda atrás termina en
    una palabra que pide la siguiente. Sin esto el corte cae donde toque -«del
    / que crees», «exigirse con / dureza»- y se lee mal aunque entre.
    """
    texto = texto.strip()
    if len(texto) <= tope:
        return [texto] if texto else []
    palabras = texto.split()
    if len(palabras) < 2:
        return [texto]
    # Los lugares donde el renglón no queda colgando. Es un FILTRO y no un
    # castigo: con un castigo, una frase donde todos los demás cortes están
    # muy desbalanceados elige igual el que deja «...a lo» al final, y eso es
    # lo que se lee mal. Si no hubiera ninguno -frases de dos palabras- se
    # vuelve a mirar todos, porque partir mal es mejor que no partir.
    lugares = [i for i in range(1, len(palabras))
               if _pelada(palabras[i - 1]) not in NO_TERMINAN]
    if not lugares:
        lugares = list(range(1, len(palabras)))
    mejor, puntaje = lugares[0], None
    for i in lugares:
        izquierda, derecha = " ".join(palabras[:i]), " ".join(palabras[i:])
        p = abs(len(izquierda) - len(derecha)) / len(texto)
        if _pelada(palabras[i]) in ARRANCAN:
            p -= 0.50
        if puntaje is None or p < puntaje:
            mejor, puntaje = i, p
    return (_cortar(" ".join(palabras[:mejor]), tope)
            + _cortar(" ".join(palabras[mejor:]), tope))


def _pedazos(texto: str, tope: int) -> List[str]:
    """Parte una oración larga: primero por sus comas, después por donde mejor
    se lea. Lo que entra junto se junta."""
    partidas: List[str] = []
    for parte in (x for x in CORTE_SUAVE.split(texto.strip()) if x):
        partidas += _cortar(parte, tope)
    # Juntar al final y no al principio: juntando primero quedan trozos de
    # cuatro palabras sueltos al lado de uno lleno.
    unidades: List[str] = []
    for parte in partidas:
        if unidades and len(unidades[-1]) + 1 + len(parte) <= tope:
            unidades[-1] = "%s %s" % (unidades[-1], parte)
        else:
            unidades.append(parte)
    return unidades


def guion(frase: Frase, tope: int = UNIDAD_MAXIMA) -> List[str]:
    """Lo que se dice y se muestra: la frase y después su reflexión.

    Las dos cosas y no solo la frase: una frase sola son seis segundos de
    video, y lo que sostiene un reel de un minuto es la explicación, que el
    banco ya tiene escrita y validada.
    """
    unidades: List[str] = []
    for texto in (frase.texto, frase.reflexion):
        for oracion in CORTE_FUERTE.split(" ".join((texto or "").split())):
            if not oracion.strip():
                continue
            if len(oracion) <= tope:
                unidades.append(oracion.strip())
            else:
                unidades += _pedazos(oracion, tope)
    return unidades


def tiempos(unidades: Sequence[str], total: Optional[float] = None) -> List[Tuple[float, float]]:
    """Cuándo entra y cuándo sale cada unidad.

    Con `total` -la duración de la voz- se reparte proporcional a lo que mide
    cada unidad, que es lo más cerca que se puede estar sin tener los tiempos
    palabra por palabra. Sin voz, cada una dura lo que tardaría en leerse.
    """
    largos = [max(len(u), 1) for u in unidades]
    if total:
        suma = sum(largos)
        duraciones = [total * n / suma for n in largos]
    else:
        duraciones = [max(MINIMO_POR_UNIDAD, n * SEGUNDOS_POR_CARACTER) for n in largos]
    salida, t = [], 0.0
    for d in duraciones:
        salida.append((t, t + d))
        t += d
    return salida


def duracion_del_guion(unidades: Sequence[str], total: Optional[float] = None) -> float:
    marcas = tiempos(unidades, total)
    return (marcas[-1][1] if marcas else 0.0) + COLA


# ---------------------------------------------------------------------------
# El dibujo del texto. Se mide con PIL y la misma fuente que después usa
# libass, para no adivinar cuántas letras entran.
# ---------------------------------------------------------------------------

def _fuente(tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / "Lora-Italic.ttf"), tam)


def _ancho(texto: str, f) -> int:
    return int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(texto, font=f))


def renglones(unidad: str, tam: int, columna: int = COLUMNA) -> List[str]:
    """Reparte la unidad en renglones que entren en la columna."""
    f = _fuente(tam)
    lineas, actual = [], ""
    for palabra in unidad.split():
        prueba = "%s %s" % (actual, palabra) if actual else palabra
        if actual and _ancho(prueba, f) > columna:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def reparto(unidades: Sequence[str], columna: int = COLUMNA,
            renglones_max: int = RENGLONES) -> Tuple[int, List[List[str]]]:
    """El cuerpo más grande con el que TODAS las unidades entran, y sus renglones.

    Es la misma idea que el flyer: se mide antes de dibujar. Un cuerpo por
    unidad se vería como seis videos distintos pegados.
    """
    for tam in CUERPOS:
        partido = [renglones(u, tam, columna) for u in unidades]
        if all(len(l) <= renglones_max for l in partido) and \
                all(_ancho(x, _fuente(tam)) <= columna for l in partido for x in l):
            return tam, partido
    # Con tres renglones entra cualquier unidad del tope: el aviso es que se
    # lee como párrafo y no como subtítulo.
    tam = CUERPOS[-1]
    return tam, [renglones(u, tam, columna) for u in unidades]


# ---------------------------------------------------------------------------
# El archivo de subtítulos. Se queman con libass, que es lo que entiende de
# contornos y de tipografía; `drawtext` no sabe partir ni centrar igual.
# ---------------------------------------------------------------------------

def _ass_color(html: str) -> str:
    """De #RRGGBB al &HAABBGGRR de ASS, que va al revés."""
    r, g, b = (int(html[i:i + 2], 16) for i in (1, 3, 5))
    return "&H00%02X%02X%02X" % (b, g, r)


def _ass_tiempo(segundos: float) -> str:
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def ass(unidades: Sequence[str], marcas: Sequence[Tuple[float, float]],
        pagina: Pagina, tema: str = "video") -> str:
    """El guion como subtítulos ASS, ya con el cuerpo medido."""
    if tema not in TEMAS:
        raise VideoError("no existe el tema %r; hay %s" % (tema, ", ".join(sorted(TEMAS))))
    estilo = TEMAS[tema]
    tam, partido = reparto(unidades)
    color = estilo["color"] or pagina.color("tinta", "#1F2933")
    contorno = estilo["contorno"] or pagina.color("fondo", "#F3EFE6")
    cabeza = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: %d" % ANCHO,
        "PlayResY: %d" % ALTO, "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Alignment 5 es centrado en los dos ejes: el texto queda en el medio,
        # que es donde lo pone la referencia y donde no se lo come la interfaz
        # de Instagram -abajo van los botones y el nombre de la cuenta-.
        "Style: Frase,Lora,%d,%s,%s,%s,&H00000000,0,-1,0,0,100,100,0,0,1,%d,%d,5,%d,%d,0,1"
        % (tam, _ass_color(color), _ass_color(color), _ass_color(contorno),
           estilo["grosor"], estilo["sombra"], MARGEN, MARGEN),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    cuerpo = []
    for lineas, (desde, hasta) in zip(partido, marcas):
        cuerpo.append("Dialogue: 0,%s,%s,Frase,,0,0,0,,%s"
                      % (_ass_tiempo(desde), _ass_tiempo(hasta), "\\N".join(lineas)))
    return "\n".join(cabeza + cuerpo) + "\n"


# ---------------------------------------------------------------------------
# El fondo de papel: el de la marca, con una deriva lenta. Es el que sale
# cuando no hay ningún video, para que un reel no dependa de descargar nada.
# ---------------------------------------------------------------------------

SOBREMEDIDA = 1.15                     # de más, para poder derivar sin bordes


def papel(pagina: Pagina, ruta: Path) -> Path:
    """Dibuja el fondo quieto. El movimiento lo pone ffmpeg."""
    w, h = int(ANCHO * SOBREMEDIDA), int(ALTO * SOBREMEDIDA)
    fondo = pagina.color("fondo", "#F3EFE6")
    acento = pagina.color("acento", "#B5654A")
    img = Image.new("RGB", (w, h), fondo)
    # Una mancha de acento muy diluida arriba a la izquierda y otra abajo a la
    # derecha: el papel liso se ve como un error de codificación.
    mancha = Image.new("RGB", (w, h), fondo)
    d = ImageDraw.Draw(mancha)
    d.ellipse([-w * 0.3, -h * 0.2, w * 0.7, h * 0.35], fill=acento)
    d.ellipse([w * 0.4, h * 0.72, w * 1.3, h * 1.2], fill=acento)
    img = Image.blend(img, mancha.filter(ImageFilter.GaussianBlur(w // 6)), 0.10)
    # Viñeta: oscurece los bordes, que es lo que hace que el texto del medio
    # se despegue sin tener que ponerle una caja detrás.
    vineta = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vineta).ellipse([-w * 0.25, -h * 0.1, w * 1.25, h * 1.1], fill=255)
    vineta = vineta.filter(ImageFilter.GaussianBlur(w // 8))
    img = Image.composite(img, Image.blend(img, Image.new("RGB", (w, h), "#000000"), 0.30), vineta)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    img.save(ruta, format="PNG")
    return ruta


def marca(pagina: Pagina, titulo: str, ruta: Path, tema: str = "papel") -> Path:
    """El encabezado y el pie, en un PNG transparente que va QUIETO encima.

    Quieto y no dibujado en el fondo: el fondo deriva, y un rótulo que deriva
    con él se va de cuadro. Son las mismas dos marcas del flyer -el nombre
    arriba con su raya de acento, el capítulo abajo-, que es lo que hace que un
    reel y un flyer se vean de la misma página.
    """
    img = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sobre_video = tema == "video"
    tinta = "#FFFFFF" if sobre_video else pagina.color("tinta", "#1F2933")
    suave = "#E8E2D6" if sobre_video else pagina.color("suave", "#8C8F93")
    acento = "#F5C542" if sobre_video else pagina.color("acento", "#B5654A")
    f_nombre = ImageFont.truetype(str(FUENTES / "Montserrat-Bold.ttf"), 34)
    nombre = (pagina.firma or pagina.nombre).upper()
    sep = 5
    ancho = sum(_ancho(c, f_nombre) for c in nombre) + sep * (len(nombre) - 1)
    x = (ANCHO - ancho) // 2
    for c in nombre:
        d.text((x, 150), c, font=f_nombre, fill=tinta)
        x += _ancho(c, f_nombre) + sep
    d.rectangle([(ANCHO - 140) // 2, 212, (ANCHO + 140) // 2, 218], fill=acento)
    f_pie = ImageFont.truetype(str(FUENTES / "Lora-Italic.ttf"), 38)
    d.text(((ANCHO - _ancho(titulo, f_pie)) // 2, ALTO - 220), titulo, font=f_pie, fill=suave)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    img.save(ruta, format="PNG")
    return ruta


# ---------------------------------------------------------------------------
# La voz. Dos caminos, y la diferencia entre ellos no es el timbre sino el
# sincronismo.
# ---------------------------------------------------------------------------

VOZ_MAC = "Paulina"        # la voz en español latino que trae macOS
PAUSA = 0.28               # el aire entre un renglón y el siguiente


def _correr(orden: List[str], que: str) -> None:
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude %s: %s" % (que, e))
    if r.returncode != 0:
        raise VideoError("falló %s: %s" % (que, (r.stderr or "")[-300:]))


def decir(texto: str, ruta: Path, voz: str = VOZ_MAC) -> Path:
    """Una unidad leída por `say`, el sintetizador que ya trae la Mac.

    Suena sintético y se nota; la voz del usuario grabada es mejor y es igual
    de gratis. Esto existe para poder sacar un reel hoy y para probar el
    formato sin tener que grabar nada.
    """
    _correr(["say", "-v", voz, "-o", str(ruta), "--data-format=LEI16@22050", texto],
            "hablar con `say` (solo existe en Mac)")
    return ruta


def voz_por_unidades(unidades: Sequence[str], carpeta: Path, voz: str = VOZ_MAC,
                     decir_fn=None) -> Tuple[Path, List[float]]:
    """Lee cada unidad por separado y las pega con un silencio en el medio.

    Por separado y no de un tirón, que es lo que de verdad importa acá: así se
    sabe cuánto dura CADA renglón y el subtítulo cae exacto donde se lo dice.
    Leyendo todo junto hay que repartir el tiempo a ojo, proporcional al largo,
    y en un minuto el desfase se acumula hasta notarse.
    """
    decir_fn = decir_fn or decir
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    silencio = carpeta / "silencio.wav"
    _correr(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
             "-t", "%.2f" % PAUSA, str(silencio)], "armar el silencio")
    lista, duraciones = [], []
    for i, unidad in enumerate(unidades):
        crudo = carpeta / ("voz-%02d.aiff" % i)
        decir_fn(unidad, crudo, voz)
        parejo = carpeta / ("voz-%02d.wav" % i)
        _correr(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(crudo),
                 "-ar", "48000", "-ac", "2", str(parejo)], "emparejar la voz")
        duraciones.append(duracion(parejo) + PAUSA)
        lista += [parejo, silencio]
    # El demuxer concat pide todos los archivos con el mismo formato, que es
    # para lo que se pasaron todos a 48 kHz estéreo arriba.
    guion_concat = carpeta / "voz.txt"
    guion_concat.write_text("".join("file '%s'\n" % x.as_posix() for x in lista),
                            encoding="utf-8")
    entera = carpeta / "voz.m4a"
    _correr(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
             "-safe", "0", "-i", str(guion_concat), "-c:a", "aac", "-b:a", "128k",
             str(entera)], "pegar la voz")
    return entera, duraciones


def tiempos_exactos(duraciones: Sequence[float]) -> List[Tuple[float, float]]:
    """Las marcas cuando se sabe cuánto dura cada renglón, sin repartir nada."""
    salida, t = [], 0.0
    for d in duraciones:
        salida.append((t, t + d))
        t += d
    return salida


# ---------------------------------------------------------------------------
# El armado.
# ---------------------------------------------------------------------------

def duracion(ruta: Path) -> float:
    """Cuánto dura un archivo, preguntándole a ffprobe."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(ruta)],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude medir %s: %s" % (Path(ruta).name, e))
    try:
        return float((r.stdout or "").strip())
    except ValueError:
        raise VideoError("ffprobe no supo decir cuánto dura %s" % Path(ruta).name)


def _deriva(total: float) -> str:
    """El recorte que se mueve despacio sobre un fondo más grande que el cuadro.

    Es una deriva y no un zoom: `zoompan` sobre una imagen quieta tiembla, y
    un temblor de un píxel en un video de un minuto se nota.
    """
    return ("crop=%d:%d:x='(iw-ow)/2+(iw-ow)/2*sin(t/14)':y='(ih-oh)/2+(ih-oh)/2*sin(t/19)'"
            % (ANCHO, ALTO))


def comando(subtitulos: Path, salida: Path, total: float, fondo: Path,
            rotulos: Optional[Path] = None, voz: Optional[Path] = None) -> List[str]:
    """El ffmpeg que arma el reel. Devuelve la lista, para poder mirarla sin correrla.

    Tres capas y en este orden: el fondo que deriva, los rótulos de la página
    QUIETOS encima, y los subtítulos quemados al final.
    """
    entradas: List[str] = []
    cuantas = 0                        # el índice de cada entrada, contado y no deducido
    es_imagen = Path(fondo).suffix.lower() in (".png", ".jpg", ".jpeg")
    if es_imagen:
        entradas += ["-loop", "1", "-i", str(fondo)]
        cadena = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,%s,fps=%d,setsar=1[bg]"
                  % (int(ANCHO * SOBREMEDIDA), int(ALTO * SOBREMEDIDA), _deriva(total), FPS))
    else:
        # El clip se repite si es más corto que el guion, y se oscurece un poco:
        # sobre un video claro, hasta el amarillo con contorno cuesta.
        entradas += ["-stream_loop", "-1", "-i", str(fondo)]
        cadena = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                  "fps=%d,eq=brightness=-0.10:saturation=0.95,setsar=1[bg]"
                  % (ANCHO, ALTO, ANCHO, ALTO, FPS))
    cuantas += 1
    if rotulos:
        entradas += ["-loop", "1", "-i", str(rotulos)]
        cadena += ";[bg][%d:v]overlay=0:0[marcado]" % cuantas
        cuantas += 1
        ultima = "marcado"
    else:
        ultima = "bg"
    audio = cuantas
    if voz:
        entradas += ["-i", str(voz)]
    else:
        entradas += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    # `fontsdir` es lo que hace que libass encuentre la Lora del repo sin
    # instalarla en el sistema: sin eso, en otra computadora el reel sale con
    # otra tipografía y nadie se entera hasta verlo.
    cadena += ";[%s]ass='%s':fontsdir='%s'[v]" % (ultima, subtitulos.as_posix(),
                                                  FUENTES.as_posix())
    return (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + entradas +
            ["-filter_complex", cadena, "-map", "[v]", "-map", "%d:a" % audio,
             "-t", "%.2f" % total,
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", str(salida)])


def armar(frase: Frase, pagina: Pagina, titulo: str = "", salida: Optional[Path] = None,
          fondo: Optional[Path] = None, voz: Optional[Path] = None,
          carpeta: Optional[Path] = None,
          marcas: Optional[List[Tuple[float, float]]] = None) -> Path:
    """El reel entero. Devuelve el archivo.

    Sin `fondo` dibuja el papel de la marca; sin `voz` sale mudo y el texto
    dura lo que tardaría en leerse.
    """
    carpeta = Path(carpeta or REELS)
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = Path(salida or carpeta / ("%s.mp4" % frase.id))
    unidades = guion(frase)
    if not unidades:
        raise VideoError("la frase %s no tiene nada que decir" % frase.id)
    if marcas is None:
        marcas = tiempos(unidades, duracion(voz) if voz else None)
    total = (marcas[-1][1] if marcas else 0.0) + COLA
    if total > TOPE_SEGUNDOS:
        raise VideoError("el reel duraría %.0f s y el tope de Facebook e Instagram "
                         "son %d" % (total, TOPE_SEGUNDOS))
    tema = "video" if fondo else "papel"
    if fondo is None:
        fondo = papel(pagina, carpeta / ("%s-fondo.png" % frase.id))
    rotulos = marca(pagina, titulo, carpeta / ("%s-marca.png" % frase.id), tema)
    sub = carpeta / ("%s.ass" % frase.id)
    sub.write_text(ass(unidades, marcas, pagina, tema), encoding="utf-8")
    try:
        r = subprocess.run(comando(sub, salida, total, fondo, rotulos, voz),
                           capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude llamar a ffmpeg: %s" % e)
    if r.returncode != 0 or not salida.exists():
        raise VideoError("ffmpeg falló: %s" % (r.stderr or "")[-400:])
    return salida
