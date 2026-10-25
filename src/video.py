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

import itertools
import re
import subprocess
import sys
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

# Hasta donde se deja llegar al guion, hablado. NO es el tope de Facebook: es
# el tope menos un margen, y el margen existe porque el ritmo real cambia con
# el texto -la puntuacion, el largo de las frases-. Un reel calculado en 89
# segundos que la voz dice en 91 no se puede publicar, y eso se descubre
# DESPUES de haber pagado la voz, que es lo unico caro de armar un reel.
#
# **Baja de 85,5 a 82 el 2026-10-25, al agrandar `PAUSA`.** El calculo de
# este archivo mide el TEXTO, por caracteres, y no cuenta el silencio entre
# renglones; ese silencio es tiempo real igual. Subir la pausa de 0,28 a 0,55
# le agrega a un reel de veinte renglones unos 5,4 segundos que el calculo no
# ve, asi que el techo tiene que devolverlos.
#
# El numero esta medido sobre las 243 frases del banco, no elegido al ojo:
# con la pausa de hoy el peor caso da 86 segundos reales, cuatro debajo de
# los 90 que admiten Facebook e Instagram, y la mediana queda en 80. Con el
# techo en 85,5 el peor caso daria 90 justos. Hay una prueba que lo recorre y
# que se pone en rojo si alguien sube la pausa sin bajar el techo.
TOPE_CON_MARGEN = 82.0

# Cuánto dura un renglón cuando NO hay voz: sin audio no hay nada que medir y
# tiene que durar lo que tardaría en leerse.
#
# El número está medido, no estimado. La primera versión usaba 17 caracteres
# por segundo, que es el TOPE que se usa en subtitulado -lo máximo que un
# adulto alcanza a leer, no lo cómodo-. Leyendo el mismo texto en voz alta a
# 150 palabras por minuto salen 10,6 c/s, y `say` a su velocidad de fábrica
# ronda los 12,4. Con el tope, el reel mudo pasa el texto bastante más rápido
# que la versión con voz y el mismo post se lee distinto según cómo se armó.
# 14 c/s queda cómodo de leer y cerca de lo que tarda una voz.
SEGUNDOS_POR_CARACTER = 0.072
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


def unidades_de(texto: str, tope: int = UNIDAD_MAXIMA) -> List[str]:
    """Un texto cualquiera partido en lo que se muestra de a una vez."""
    salida: List[str] = []
    for oracion in CORTE_FUERTE.split(" ".join((texto or "").split())):
        if not oracion.strip():
            continue
        if len(oracion) <= tope:
            salida.append(oracion.strip())
        else:
            salida += _pedazos(oracion, tope)
    return salida


def guion(frase: Frase, tope: int = UNIDAD_MAXIMA) -> List[str]:
    """Lo que se dice y se muestra: la frase y después su reflexión.

    Las dos cosas y no solo la frase: una frase sola son seis segundos de
    video, y lo que sostiene un reel es la explicación, que el banco ya tiene
    escrita y validada. Aun así son unos 30 segundos hablados: para un minuto
    hace falta un capítulo entero, que es `guion_de_tema`.
    """
    return unidades_de(frase.texto, tope) + unidades_de(frase.reflexion, tope)


# Lo que puede durar un reel largo, medido con la regla de este archivo
# (`duracion_del_guion` por `VOZ_MAS_LENTA`).
#
# **Estuvo en 72 por un numero equivocado, y se corrigio el 2026-10-25
# midiendo contra el mp4 que esta en el repo.** Aca decia que la regla «MIDE
# CORTO, un 17%», y de ahi salia el 72. No es asi: `data/reels/ultimo.mp4`
# dura 47,2 segundos y la regla calcula 48,7 para el guion con el que se
# armo, o sea que mide LARGO un 3%. El 17% venia de comparar contra un
# calculo viejo, de antes de que `VOZ_MAS_LENTA` subiera a 1,75 el
# 2026-10-23 -que es justamente el cambio que corrigio ese error-. Se estaba
# descontando dos veces la misma correccion.
#
# Lo que costaba: el reel del dia salia de 52 a 70 segundos reales (mediana
# 63) cuando el usuario lo habia pedido de mas de un minuto, y pidiendolo de
# 80 a 90 no habia forma de llegar.
#
# **86 y no 90, y el margen esta contado.** Con 86 el peor de las 243 frases
# da 83 segundos reales. Si algun dia la voz tardara un 6% MAS de lo
# calculado -hoy tarda un 3% MENOS- ese peor caso daria 88,6, todavia debajo
# de los 90 que admiten Facebook e Instagram. Con 88 daria 90,5 y se caeria,
# despues de haber pagado la voz.
#
# Son 243 frases medidas, no un numero al ojo: con este tope las 243 pasan el
# minuto, 49 caen entre 80 y 90 y ninguna llega a 90. La mediana es 76: la
# escalera se queda sin material antes que sin techo, asi que subirlo mas no
# mueve la mediana, solo acerca el peor caso al limite.
#
# **Es el MISMO numero que `TOPE_CON_MARGEN`, y eso no es ahorro de lineas:
# es la misma pregunta.** Las dos rutas -una frase con `--largo` y un
# capitulo con `--tema`- terminan en el mismo `armar`, que mide la voz de
# verdad y se niega arriba de 90. Tenerlo escrito dos veces es como se
# descubre tarde que una de las dos copias quedo vieja, que es exactamente lo
# que acaba de pasar: el capitulo tenia el margen bien desde el 23/10 y la
# frase se quedo con un 72 sacado de una cuenta equivocada.
TOPE_LARGO = TOPE_CON_MARGEN


# Cuanto se equivoca la regla de este archivo al medir lo HABLADO, sin contar
# las pausas. Medido contra `data/reels/ultimo.mp4`, que esta en el repo: la
# regla calcula 48,7 s para el guion con el que se armo y el archivo dura
# 47,2. O sea que mide un 3% LARGO.
#
# **Es UNA medicion.** Por eso no se usa para corregir `VOZ_MAS_LENTA` -eso
# seria reescribir la regla con un solo dato- sino para elegir los topes con
# margen y para poder preguntar «cuanto va a durar esto de verdad» sin pagar
# la voz. Hay una prueba que lo vuelve a medir contra el archivo.
MIDE_LARGO = 0.97


def segundos_reales(unidades: Sequence[str]) -> float:
    """Lo que va a durar el reel de verdad, antes de pagar la voz.

    Son DOS cosas y hasta el 2026-10-25 se contaba una sola:

      1. lo hablado, que es la regla de este archivo corregida por
         `MIDE_LARGO`;
      2. el silencio entre renglones, que el calculo NO ve -su regla es por
         caracteres- y que con `PAUSA` en 0,55 son unos 11 segundos de un
         reel de veinte renglones.

    Se cuenta solo lo que `PAUSA` AGREGO sobre `PAUSA_CALIBRADA`, porque la
    pausa que habia cuando se midio el archivo ya esta adentro de
    `MIDE_LARGO`. Sumarla entera seria contarla dos veces, que es exactamente
    el error que tuvo el tope hasta hoy.

    Es una prediccion y no una promesa: quien decide es `armar`, que mide la
    voz ya sintetizada y se niega arriba de `TOPE_SEGUNDOS`.
    """
    unidades = list(unidades)
    hablado = duracion_del_guion(unidades) * VOZ_MAS_LENTA * MIDE_LARGO
    return hablado + (PAUSA - PAUSA_CALIBRADA) * len(unidades)


def primera_oracion(texto: str) -> str:
    """La primera oracion de un texto. "" si no hay."""
    partes = [p for p in CORTE_FUERTE.split(" ".join((texto or "").split())) if p.strip()]
    return partes[0] if partes else ""


def guion_largo(frase: Frase, tema, tope: float = TOPE_LARGO,
                unidad: int = UNIDAD_MAXIMA) -> List[str]:
    """Lo mas largo que el reel puede decir de esa frase sin pasarse.

    La frase y su reflexion son unos 47 segundos: no llegan al minuto. Para
    llegar NO se estira el texto -eso seria relleno- sino que se le suma lo
    que el banco ya tiene escrito alrededor, en este orden:

      1. la tesis del capitulo, que presenta el asunto, al principio
      2. el principio de la frase, que es la idea en una linea, al final

    Y se prueba de lo mas largo a lo mas corto, quedandose con lo PRIMERO que
    entra. Es la misma forma que los flyers: elegir la escala mas grande con
    la que el texto entra, decidido ANTES de dibujar, y no achicar hasta que
    quepa. Asi el reel nunca se corta por la mitad.

    **La fuente no entra nunca.** Son referencias academicas -«Frijda (1986),
    tendencias de accion»- y leerlas en voz alta no es un reel, es una
    bibliografia. Hay una prueba que lo exige.
    """
    def medir(unidades):
        return duracion_del_guion(unidades) * VOZ_MAS_LENTA

    def partes(texto):
        return unidades_de(texto, unidad) if texto else []

    base = guion(frase, unidad)
    tesis = partes(getattr(tema, "tesis", ""))
    media = partes(primera_oracion(getattr(tema, "tesis", "")))
    principio = partes(frase.principio)
    for candidato in (tesis + base + principio, tesis + base,
                      media + base + principio, media + base,
                      base + principio, base):
        if medir(candidato) <= tope:
            return candidato
    return base


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


# Cuánto más tarda una voz que la lectura. MEDIDO, no estimado: el capítulo de
# autoestima da 58 segundos leído y la voz onyx lo dijo en 100, o sea un 72%
# más. La primera versión suponía un 20% y el reel se pasaba del tope de
# Facebook por diez segundos, después de haber pagado las 28 voces.
#
# Tiene sentido que sea tanto: `INSTRUCCIONES` le pide ritmo pausado y que
# deje respirar las frases. Una voz apurada entraría de sobra y sonaría a
# publicidad.
VOZ_MAS_LENTA = 1.75

# El mínimo que se busca cuando el reel es un capítulo: que pase el minuto
# HABLADO, que es lo que se pidió. Está en segundos LEÍDOS porque es lo único
# que se puede saber antes de sintetizar la voz.
OBJETIVO = 60.0 / VOZ_MAS_LENTA


def _combinacion(costos: Sequence[float], minimo: float) -> Tuple[int, ...]:
    """Cuáles de las partes llenan mejor el reel sin pasarse del tope.

    Se eligen por combinación y no una detrás de otra, y eso no es
    refinamiento: en orden, una frase larga deja veinte segundos sin usar que
    una posterior llenaría, y `elegir` y `reconexión` quedaban en 57 segundos
    hablados con casi treinta libres.

    Se elige QUÉ partes entran, no en qué orden: el guion se arma después en
    el orden del libro, así que la tesis sigue abriendo y cada frase sigue
    desarrollando lo que la anterior dejó planteado.

    La preferencia, en este orden: que pase el minuto, que esté la tesis, y
    que sea lo más largo que entre. La tesis va segunda y no primera a
    propósito: si ocupa tanto que no deja lugar a ninguna frase, se va. Una
    tesis sola es un resumen sin un solo ejemplo, y lo que sostiene el reel
    son las frases. Le pasa a `ruptura`, cuyas reflexiones son las más largas
    del banco: su tesis son 43 segundos hablados y cada frase entre 49 y 58,
    así que cualquier par se pasa del tope y lo que sale es una frase sola.
    """
    mejor: Optional[Tuple[Tuple, Tuple[int, ...]]] = None
    for cuantas in range(1, len(costos) + 1):
        entro_alguna = False
        for cuales in itertools.combinations(range(len(costos)), cuantas):
            total = sum(costos[i] for i in cuales) + COLA
            if total * VOZ_MAS_LENTA > TOPE_CON_MARGEN:
                continue
            entro_alguna = True
            # La tesis se prefiere SOLO entre las que ya pasan el minuto. Si
            # ninguna lo pasa, lo que importa es el largo: la tesis de
            # `ruptura` sola son 43 segundos hablados y cualquiera de sus
            # frases llega a 58.
            pasa = total >= minimo
            clave = (pasa, pasa and 0 in cuales, total)
            if mejor is None or clave > mejor[0]:
                mejor = (clave, cuales)
        # Si ninguna combinación de este tamaño entró, una más grande tampoco
        # va a entrar: sumar una parte más solo agrega segundos.
        if not entro_alguna:
            break
    if mejor is None:
        # Nada entra en el tope. Hoy no pasa -la parte más larga del banco son
        # 58 segundos hablados contra 85 de tope- pero si algún día pasa, sale
        # la más corta sola: un reel corto se ve y se arregla, y uno sin una
        # palabra escrita parece otra cosa.
        return (min(range(len(costos)), key=lambda i: costos[i]),)
    return mejor[1]


def guion_de_tema(tema, segundos: float = OBJETIVO, desde: int = 0,
                  tope: int = UNIDAD_MAXIMA) -> List[str]:
    """Un capítulo en un reel: su tesis y las frases que entren.

    Para pasar el minuto no hacen falta frases más largas sino MÁS frases.
    Una frase con su reflexión son unos 45 segundos hablados; la tesis del
    capítulo y una o dos frases pasan el minuto con texto que ya está
    escrito, validado por la línea editorial y ordenado -la tesis presenta el
    asunto y cada frase lo desarrolla-, que es lo mismo que hace el libro con
    ese material.

    Nunca se corta una frase por la mitad: entra entera o no entra. Media
    reflexión termina en el aire y el reel se lee como un error.
    """
    partes = [unidades_de(tema.tesis, tope)]
    partes += [unidades_de(f.texto, tope) + unidades_de(f.reflexion, tope)
               for f in list(tema.frases)[desde:]]
    # Lo que mide cada parte por separado, sin la cola, que se suma una vez
    # sola al final. Sale de `duracion_del_guion` y no de una cuenta repetida
    # acá: dos copias de la misma fórmula es como se descubre tarde que una
    # de las dos quedó vieja.
    costos = [duracion_del_guion(p) - COLA for p in partes]
    unidades: List[str] = []
    for i in _combinacion(costos, segundos):
        unidades += partes[i]
    return unidades


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
        # `\fad` desvanece la entrada y la salida. Medido en la referencia:
        # el texto tarda unos cinco cuadros a 25 fps en aparecer del todo, o
        # sea unos 200 ms. Sin esto el renglon salta de golpe y se nota como
        # un cartel, no como algo que acompana a la voz.
        #
        # El fundido se acota a una parte del renglon: en uno corto, 250 ms
        # de entrada y 250 de salida se comerian casi todo el tiempo en que
        # se tendria que leer.
        dura = max(hasta - desde, 0.01)
        fundido = int(min(FUNDIDO_TEXTO, dura * 1000 * 0.25))
        cuerpo.append("Dialogue: 0,%s,%s,Frase,,0,0,0,,{\\fad(%d,%d)}%s"
                      % (_ass_tiempo(desde), _ass_tiempo(hasta),
                         fundido, fundido, "\\N".join(lineas)))
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

# La referencia que mandó el usuario tiene una voz MASCULINA: medida sobre su
# audio, la mediana del tono es 122 Hz, que está de lleno en el rango de hombre
# (85-180) y lejos del de mujer (165-255). Por eso la preferencia arranca por
# las masculinas y no por Paulina, que era el valor anterior.
#
# El orden va de más neutro-latino a menos: un lector peruano oye «Jorge» como
# claramente español. Las variantes mejoradas de macOS se llaman igual con un
# agregado -«Juan (Mejorada)», «Juan (Premium)»- y suenan bastante mejor, así
# que se eligen antes si están instaladas.
VOCES = ("Juan", "Carlos", "Diego", "Enrique", "Jorge",
         "Paulina", "Monica", "Mónica", "Francisca", "Soledad")
VOZ_MAC = "Juan"
# El aire entre un renglón y el siguiente. Lo pidió el usuario el 2026-10-25:
# «hace la voz más pausada». No se puede pedir más lento -`eleven_v4` no tiene
# control de velocidad ni de estilo, solo estabilidad y parecido- así que lo
# que se agranda es el silencio entre renglones, que es nuestro y no cuesta
# nada.
#
# Es casi el doble de los 0,28 que había, y el efecto es grande porque son
# unos 20 renglones: un reel gana cerca de 5 segundos de silencio. Eso NO es
# relleno, es lo que se pidió, y de paso es lo que termina de llevar el reel
# al largo que el usuario quiere -la mediana pasa de 76 a 82 segundos reales-.
#
# **Cambiarlo obliga a mirar `TOPE_CON_MARGEN`**: el cálculo de este archivo
# NO cuenta las pausas -su regla es por caracteres- así que cada décima que
# se le suma acá es tiempo real que el cálculo no ve. Hay una prueba que lo
# ata: sube la pausa sin bajar el techo y se pone en rojo.
PAUSA = 0.55

# La pausa que estaba puesta cuando se calibró la regla de este archivo
# contra un reel de verdad (`data/reels/ultimo.mp4`, el del 2026-10-24). No
# es historia: es lo que permite saber cuánto tiempo REAL agrega haber
# subido `PAUSA`, que es exactamente `(PAUSA - PAUSA_CALIBRADA)` por renglón.
# Sin este número habría que volver a medir un reel cada vez.
PAUSA_CALIBRADA = 0.28


def _correr(orden: List[str], que: str, espera: int = 300) -> None:
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=espera)
    except subprocess.TimeoutExpired:
        # Aparte del resto: el mensaje de `TimeoutExpired` es el comando
        # entero y no dice que lo que paso fue que tardo. Le paso a un clip
        # de 4K largo en la Mac del usuario.
        raise VideoError("%s tardo mas de %d segundos y lo corte" % (que, espera))
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
    # `--file-format=WAVE` y no el AIFF por defecto: AIFF es big-endian por
    # convención y pedirle datos LEI16 adentro es lo que hace que algunos
    # macOS escriban un archivo que después ffmpeg no abre.
    _correr(["say", "-v", voz, "-o", str(ruta), "--file-format=WAVE",
             "--data-format=LEI16@22050", texto],
            "hablar con `say` (solo existe en Mac)")
    return ruta


def voz_preferida(instaladas: Optional[List[str]] = None) -> str:
    """La mejor voz en español que esté instalada, según `VOCES`.

    Se elige y no se clava porque una voz que no está da «Voice not found», que
    se lee como si `say` estuviera roto. Entre dos variantes del mismo nombre
    gana la más larga: «Juan (Mejorada)» antes que «Juan».
    """
    hay = instaladas if instaladas is not None else voces_en_espanol()
    for quien in VOCES:
        parecidas = [v for v in hay if v == quien or v.startswith(quien + " ")]
        if parecidas:
            return sorted(parecidas, key=len)[-1]
    return hay[0] if hay else VOZ_MAC


def voces_en_espanol() -> List[str]:
    """Las voces en español instaladas. Para decir cuáles hay cuando falta una.

    Una voz que no está da «Voice not found», que se lee como si `say`
    estuviera roto. Casi siempre es que esa voz no se descargó todavía:
    Ajustes del sistema → Accesibilidad → Contenido hablado → Voz del sistema.
    """
    try:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    salida = []
    for linea in (r.stdout or "").splitlines():
        if "es_" not in linea and "es-" not in linea:
            continue
        # El formato es «Nombre   es_MX   # ejemplo». El nombre puede tener
        # paréntesis y espacios -«Juan (Mejorada)»- así que se corta por el
        # código de idioma y no por el primer espacio.
        corte = min((linea.find(x) for x in ("es_", "es-") if linea.find(x) > 0),
                    default=-1)
        if corte > 0:
            salida.append(linea[:corte].strip())
    return salida


# ---------------------------------------------------------------------------
# La voz de IA. Es la ÚNICA llamada paga de todo el repo.
#
# Se eligió OpenAI y no otra porque la cuenta y la clave ya existen -son las
# mismas de las fotos y de los Reels de la página de salud-, así que no hay
# que dar de alta nada. Lo que la hace «cinematográfica» no es el modelo sino
# `INSTRUCCIONES`: sin eso lee como un locutor de noticias.
#
# **El precio no se escribe acá.** Las fuentes de terceros no coinciden y
# OpenAI no publica una tarifa por carácter para este modelo. Se anotan los
# caracteres y los segundos en `data/voz.jsonl` y el costo se mira en el panel
# de OpenAI, que es la misma decisión que ya se tomó en la página de salud:
# inventar un número haría que el informe dijera que gastaste lo que no.
# ---------------------------------------------------------------------------

API_VOZ = "https://api.openai.com/v1/audio/speech"
MODELO_VOZ = "gpt-4o-mini-tts"
# Grave y de hombre, que es lo que mide la referencia (122 Hz de mediana).
VOZ_IA = "onyx"
INSTRUCCIONES = (
    "Habla en español neutro latinoamericano, con voz grave y cálida. "
    "Tono reflexivo y sereno, como quien le cuenta algo importante a un amigo "
    "en voz baja. Ritmo pausado, sin prisa. Deja respirar las frases y marca "
    "las pausas de los puntos. No suenes a locutor de noticias ni a publicidad: "
    "sin entusiasmo, sin subir al final de las frases."
)
# ---------------------------------------------------------------------------
# El color de la voz.
#
# «Que suene cinematográfica» no es la voz que se elige: es cómo se procesa
# después. Medido sobre la referencia que mandó el usuario, separando la voz
# de la música: su voz tiene 35 dB de caída entre los graves (120-250 Hz) y
# los agudos (2-4 kHz). Es una voz oscura, de micrófono cercano, con los
# agudos bajados. Las cinco voces de OpenAI salen de fábrica mucho más
# brillantes que eso, y por eso ninguna «se parecía».
#
# Cada cadena está medida sobre ruido rosa, descontando la ganancia general
# -si no, la más fuerte gana por volumen y no por timbre-. Lo que agrega cada
# una de inclinación graves-agudos:
#
#     calida  +3 dB      cine  +6 dB      honda  +9 dB
#
# No se busca clavar los 35 dB de la referencia: ese número incluye el timbre
# propio de esa persona, que no se puede copiar con un ecualizador. Lo que se
# ofrece es un abanico para elegir de oído, que es la única forma de decidir
# esto.
#
# La compresión no es decorativa: una voz cercana e íntima es una voz con poco
# rango dinámico. Sin ella el ecualizador solo la oscurece.
COLORES = {
    # Como sale de OpenAI.
    "nada": "",
    "calida": ("highpass=f=70,equalizer=f=150:t=q:w=1.0:g=3,treble=g=-3:f=4000,"
               "acompressor=threshold=-18dB:ratio=2:attack=15:release=250"),
    "cine": ("highpass=f=70,equalizer=f=130:t=q:w=0.9:g=6,"
             "equalizer=f=450:t=q:w=1.2:g=-2,treble=g=-6:f=3500,"
             "acompressor=threshold=-20dB:ratio=3:attack=10:release=200"),
    "honda": ("highpass=f=65,equalizer=f=120:t=q:w=0.8:g=8,"
              "equalizer=f=450:t=q:w=1.2:g=-3,treble=g=-9:f=3000,"
              "acompressor=threshold=-22dB:ratio=4:attack=8:release=180"),
}
# El que se usa si no se pide otro. Arranca en «nada» a propósito: hasta que
# el usuario elija uno de oído, el reel suena como el que ya vio.
COLOR = "nada"


def filtro_de_color(color: Optional[str]) -> str:
    """La cadena de ffmpeg de ese color. Un nombre que no existe es un error.

    Se valida acá y no al armar el video: un color mal escrito dejaría la voz
    sin procesar y el reel saldría igual que antes, sin que nada avise. Es el
    peor final posible para algo que se está eligiendo de oído.
    """
    if color is None:
        color = COLOR
    if color not in COLORES:
        raise VideoError("no conozco el color de voz %r. Hay: %s"
                         % (color, ", ".join(sorted(COLORES))))
    return COLORES[color]


# Un reel son unos 1.000 caracteres. El tope existe para que un argumento mal
# escrito no se lleve la cuenta por delante, que ya pasó con las imágenes.
TOPE_CARACTERES = 6000
REGISTRO = ROOT / "data" / "voz.jsonl"
# El mismo camino, pero sin que una prueba lo pueda cambiar. Sirve para saber
# si `REGISTRO` es el archivo de verdad o uno temporal: ver `_anotar`.
_REGISTRO_REAL = REGISTRO
CACHE_VOZ = ROOT / "data" / "voz_cache"


def _llave(texto: str, voz: str, modelo: str, instrucciones: str) -> str:
    """La pedida ENTERA como llave: si cambia una coma, es otro audio.

    Lo único grave sería devolver el audio de otro texto, así que entra todo
    lo que cambia lo que se oye. Es la misma cache que la de las fotos en la
    página de salud, y por el mismo motivo: lo que ya se pagó no se vuelve a
    pagar.
    """
    import hashlib
    crudo = "\n".join((modelo, voz, instrucciones, texto))
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:32]


def _anotar(caracteres: int, segundos: float, voz: str, modelo: str,
            proveedor: str = "openai") -> None:
    """Lo gastado, sin precio. El precio lo pone el panel de cada proveedor.

    Lleva `proveedor` desde que hay dos: son dos facturas distintas y un
    registro que las mezcla no sirve para cotejar ninguna de las dos.
    """
    import json
    from datetime import datetime
    try:
        # Una prueba que pida una voz de mentira NO puede ensuciar el registro
        # de gasto de verdad: el informe diria que se gasto lo que no, y el
        # numero dejaria de servir para cotejar con la factura. Paso: el
        # archivo acabo con 22 pedidos de una voz llamada `vid1`, que es la de
        # los tests, y la primera vez que se quiso contar el gasto no se pudo.
        #
        # La condicion mira el ARCHIVO y no solo si corre una prueba: una que
        # apunta `REGISTRO` a un temporal esta comprobando justamente que esto
        # anote, y tiene que poder. Lo que se corta es escribir en el de
        # verdad desde una prueba.
        if "unittest" in sys.modules and REGISTRO == _REGISTRO_REAL:
            return
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"cuando": datetime.now().isoformat(timespec="seconds"),
                                "proveedor": proveedor,
                                "modelo": modelo, "voz": voz,
                                "caracteres": caracteres,
                                "segundos": round(segundos, 2)}) + "\n")
    except OSError:
        # Que no se pueda anotar no puede tumbar un reel que ya está hecho.
        pass


def decir_con_ia(texto: str, ruta: Path, voz: str = VOZ_IA,
                 modelo: str = MODELO_VOZ, instrucciones: str = INSTRUCCIONES,
                 cache: Optional[Path] = None, pedir=None) -> Path:
    """Una unidad leída por la IA. Devuelve el archivo.

    Mira la cache ANTES de pedir la clave: un audio que ya está en disco no
    necesita cuenta, y el día que la clave falte o esté vencida es justo
    cuando más conviene poder seguir.
    """
    import os
    import shutil
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    guardado = Path(cache or CACHE_VOZ) / ("%s.wav" % _llave(texto, voz, modelo, instrucciones))
    if guardado.exists() and guardado.stat().st_size > 0:
        shutil.copyfile(guardado, ruta)
        return ruta
    if len(texto) > TOPE_CARACTERES:
        raise VideoError("son %d caracteres y el tope es %d" % (len(texto), TOPE_CARACTERES))
    clave = os.environ.get("OPENAI_API_KEY")
    if not clave:
        raise VideoError("falta OPENAI_API_KEY en el .env")
    pedir = pedir or _pedir_voz
    audio = pedir(clave, {"model": modelo, "voice": voz, "input": texto,
                          "instructions": instrucciones, "response_format": "wav"})
    if not audio:
        raise VideoError("OpenAI devolvió un audio vacío")
    # Aparte y renombrar: si se corta a la mitad, lo que queda es un
    # `.parcial` y no una entrada de la cache que después se lea como buena.
    tmp = ruta.with_suffix(".parcial")
    tmp.write_bytes(audio)
    tmp.replace(ruta)
    guardado.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(ruta, guardado)
    except OSError:
        pass
    _anotar(len(texto), duracion(ruta), voz, modelo)
    return ruta


# ---------------------------------------------------------------------------
# ElevenLabs.
#
# Se agregó porque el usuario escuchó las cinco voces de OpenAI y ninguna se
# parecía a la del reel de referencia, y la medición le daba la razón: esa voz
# tiene 35 dB de caída de graves a agudos y las de OpenAI salen mucho más
# brillantes. El color (`COLORES`) acerca el timbre pero no cambia QUIÉN lee.
#
# Convive con OpenAI, no la reemplaza: `decir_con_ia` queda igual y sigue
# siendo la que se usa si no se pide otra cosa. Son dos facturas distintas y
# por eso el registro anota de cuál es cada pedido.
# ---------------------------------------------------------------------------

API_ELEVEN = "https://api.elevenlabs.io/v1"

# El MISMO modelo con el que el usuario eligió la voz, que es el punto: probó
# «Milo» en el panel con Eleven v4 y le gustó cómo sonó. Con otro modelo la
# misma voz suena distinto, así que lo que aprobó no sería lo que sale.
MODELO_ELEVEN = "eleven_v4"

# Una indicación de actuación, entre corchetes, al principio del texto. v4 las
# entiende; `[sighs]` es un suspiro, que es lo que el usuario puso en el panel
# ([suspirando], porque la interfaz está en español: a la API van en inglés,
# que es como están documentadas).
#
# «Suspira» a secas salió demasiado marcado: el usuario lo escuchó con la
# etiqueta en las diez oraciones y pidió «solo a veces y poco». Lo de POCO se
# arregla acá -es una indicación más suave, un suspiro contenido y no uno
# entero- y lo de A VECES con `ETIQUETA_CADA`.
#
# Se agrega DESPUÉS de traducir, nunca antes: si viajara con el texto, el
# traductor la tomaría por palabras y devolvería «[sighing]» o la borraría.
ETIQUETA_INICIAL = "[sighs softly]"

# Cada cuántas oraciones se repite. 1 sería en todas -lo que sonó de más- y
# un número muy grande la deja solo en la primera, donde el tono se pierde a
# los pocos segundos porque estas indicaciones afectan sobre todo a lo que
# viene justo después.
#
# Con 4, un capítulo de diez oraciones lleva tres: la primera, la quinta y la
# novena. Eso es «a veces».
ETIQUETA_CADA = 4


def oraciones_con_etiqueta(oraciones: Sequence[str], etiqueta: str,
                           cada: int = ETIQUETA_CADA) -> List[str]:
    """Las oraciones con la indicación de actuación puesta cada tantas.

    Empieza siempre por la primera: es la que fija el tono de todo lo demás.
    Con `cada` en 0 o sin etiqueta, devuelve las oraciones tal cual.
    """
    if not etiqueta or cada <= 0:
        return list(oraciones)
    return ["%s %s" % (etiqueta, o) if i % cada == 0 else o
            for i, o in enumerate(oraciones)]

# Eleven v4 NO tiene los controles de estilo ni de velocidad -lo dice su
# documentación- así que mandarlos sería mandar algo que el modelo ignora o
# rechaza. Quedan los dos que el usuario movió en el panel.
AJUSTES_ELEVEN = {"stability": 0.55, "similarity_boost": 0.85}

# La voz se guarda por ID y NO por nombre. Los nombres se repiten entre
# cuentas y los de la biblioteca compartida se pueden renombrar; el id no
# cambia nunca.
#
# La eligió el usuario el 2026-10-23, escuchándolas, después de descartar las
# cinco de OpenAI y los cuatro procesados.
VOZ_ELEVEN = "GUDYcgRAONiI1nXDcNQQ"

def _ajustes_como_texto(ajustes: dict) -> str:
    """Los ajustes en la llave de la cache: cambian lo que se oye.

    Sin esto, bajar la estabilidad y volver a pedir devolvería el audio viejo
    desde la cache y parecería que el ajuste no hace nada.
    """
    return ",".join("%s=%s" % (k, ajustes[k]) for k in sorted(ajustes))


def voces_de_eleven(clave: Optional[str] = None) -> List[dict]:
    """Las voces de la cuenta. Solo lee."""
    import os
    import requests
    clave = clave or os.environ.get("ELEVENLABS_API_KEY")
    if not clave:
        raise VideoError("falta ELEVENLABS_API_KEY en el .env")
    try:
        r = requests.get("%s/voices" % API_ELEVEN, timeout=60,
                         headers={"xi-api-key": clave})
    except requests.RequestException as e:
        raise VideoError("no se pudo llegar a ElevenLabs: %s" % e)
    if r.status_code != 200:
        raise VideoError("ElevenLabs contestó %d: %s" % (r.status_code, r.text[:200]))
    return r.json().get("voices", [])


# Errores de ElevenLabs que no se explican solos. El texto crudo de la API
# dice QUE pasó pero no QUÉ hacer, y éste en particular manda a buscar el
# problema donde no está: la clave funciona, el plan también permite usar la
# API, y aun así esa voz no se puede.
PISTAS_ELEVEN = {
    "paid_plan_required":
        "El plan gratuito permite la API pero NO con las voces de la "
        "biblioteca, que es de donde salió ésta. Son dos cosas distintas y "
        "se parecen: la clave está bien. Hay que pasar a Starter, o usar una "
        "de las voces que vienen de fábrica en la cuenta.",
    "quota_exceeded":
        "Se acabaron los créditos del mes. Lo que ya está en data/voz_cache "
        "se sigue usando sin gastar.",
    "voice_not_found":
        "Esa voz no está en tu cuenta. Las de la biblioteca hay que "
        "agregarlas primero con «Add» para que la API las vea.",
}


def _pista_de_eleven(texto: str) -> str:
    for clave, pista in PISTAS_ELEVEN.items():
        if clave in texto:
            return "\n%s" % pista
    return ""


def _pedir_voz_eleven(clave: str, voz: str, cuerpo: dict) -> bytes:
    import requests
    try:
        r = requests.post("%s/text-to-speech/%s" % (API_ELEVEN, voz),
                          params={"output_format": "mp3_44100_128"},
                          json=cuerpo, timeout=180,
                          headers={"xi-api-key": clave,
                                   "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise VideoError("no se pudo llegar a ElevenLabs: %s" % e)
    if r.status_code != 200:
        raise VideoError("ElevenLabs contestó %d: %s%s"
                         % (r.status_code, r.text[:300],
                            _pista_de_eleven(r.text)))
    return r.content


def decir_con_eleven(texto: str, ruta: Path, voz: str = "",
                     modelo: str = MODELO_ELEVEN,
                     ajustes: Optional[dict] = None,
                     cache: Optional[Path] = None, pedir=None) -> Path:
    """Una unidad leída por ElevenLabs. Misma forma que `decir_con_ia`.

    Mira la cache ANTES de pedir la clave, por lo mismo que la de OpenAI: un
    audio que ya está en disco no necesita cuenta.
    """
    import os
    import shutil
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    voz = voz or VOZ_ELEVEN
    if not voz:
        raise VideoError(
            "no hay ninguna voz de ElevenLabs elegida. Para ver las de tu "
            "cuenta: scripts/probar_voces.py --eleven --listar")
    ajustes = dict(ajustes or AJUSTES_ELEVEN)
    # La llave lleva el modelo, la voz, los ajustes y el texto. El modelo de
    # ElevenLabs nunca coincide con el de OpenAI, así que las dos caches
    # conviven en la misma carpeta sin pisarse.
    guardado = Path(cache or CACHE_VOZ) / (
        "%s.mp3" % _llave(texto, voz, modelo, _ajustes_como_texto(ajustes)))
    if guardado.exists() and guardado.stat().st_size > 0:
        shutil.copyfile(guardado, ruta)
        return ruta
    if len(texto) > TOPE_CARACTERES:
        raise VideoError("son %d caracteres y el tope es %d" % (len(texto), TOPE_CARACTERES))
    clave = os.environ.get("ELEVENLABS_API_KEY")
    if not clave:
        raise VideoError("falta ELEVENLABS_API_KEY en el .env")
    pedir = pedir or _pedir_voz_eleven
    audio = pedir(clave, voz, {"text": texto, "model_id": modelo,
                               "voice_settings": ajustes})
    if not audio:
        raise VideoError("ElevenLabs devolvió un audio vacío")
    tmp = ruta.with_suffix(".parcial")
    tmp.write_bytes(audio)
    tmp.replace(ruta)
    guardado.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(ruta, guardado)
    except OSError:
        pass
    _anotar(len(texto), duracion(ruta), voz, modelo, proveedor="elevenlabs")
    return ruta


def en_cache_eleven(texto: str, voz: str = "", modelo: str = MODELO_ELEVEN,
                    ajustes: Optional[dict] = None,
                    cache: Optional[Path] = None) -> bool:
    voz = voz or VOZ_ELEVEN
    if not voz:
        return False
    llave = _llave(texto, voz, modelo,
                   _ajustes_como_texto(dict(ajustes or AJUSTES_ELEVEN)))
    guardado = Path(cache or CACHE_VOZ) / ("%s.mp3" % llave)
    return guardado.exists() and guardado.stat().st_size > 0


def en_cache(texto: str, voz: str = VOZ_IA, modelo: str = MODELO_VOZ,
             instrucciones: str = INSTRUCCIONES, cache: Optional[Path] = None) -> bool:
    """Si ese renglón ya está pagado. Sirve para decir qué costaría antes de pedirlo."""
    guardado = Path(cache or CACHE_VOZ) / ("%s.wav" % _llave(texto, voz, modelo, instrucciones))
    return guardado.exists() and guardado.stat().st_size > 0


def _pedir_voz(clave: str, cuerpo: dict) -> bytes:
    import requests
    try:
        r = requests.post(API_VOZ, json=cuerpo, timeout=180,
                          headers={"Authorization": "Bearer %s" % clave})
    except requests.RequestException as e:
        raise VideoError("no se pudo llegar a OpenAI: %s" % e)
    if r.status_code != 200:
        raise VideoError("OpenAI contestó %d: %s" % (r.status_code, r.text[:200]))
    return r.content


def voz_por_unidades(unidades: Sequence[str], carpeta: Path, voz: str = VOZ_MAC,
                     decir_fn=None, color: Optional[str] = None) -> Tuple[Path, List[float]]:
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
    _correr([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
             "-t", "%.2f" % PAUSA, str(silencio)], "armar el silencio")
    lista, duraciones = [], []
    for i, unidad in enumerate(unidades):
        # Dos nombres y no uno: `say` escribe el crudo y ffmpeg lo pasa a 48
        # kHz estéreo, y con el mismo nombre ffmpeg se niega a escribir sobre
        # su propia entrada.
        crudo = carpeta / ("voz-%02d-crudo.wav" % i)
        decir_fn(unidad, crudo, voz)
        parejo = carpeta / ("voz-%02d.wav" % i)
        _correr([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(crudo),
                 "-ar", "48000", "-ac", "2", str(parejo)], "emparejar la voz")
        duraciones.append(duracion(parejo) + PAUSA)
        lista += [parejo, silencio]
    # El demuxer concat pide todos los archivos con el mismo formato, que es
    # para lo que se pasaron todos a 48 kHz estéreo arriba.
    #
    # Y los pide con ruta ABSOLUTA. El concat resuelve cada `file` relativo a
    # la carpeta de la propia lista, no al directorio desde el que se corre:
    # con una ruta relativa el camino sale duplicado
    # -`data/reels/x-voz/data/reels/x-voz/voz-00.wav`- y ffmpeg no encuentra
    # nada. No se vio antes porque todas las pruebas usan carpetas temporales,
    # que ya son absolutas; se vio al correrlo en GitHub con `--carpeta
    # data/reels`.
    guion_concat = carpeta / "voz.txt"
    guion_concat.write_text(
        "".join("file '%s'\n" % x.resolve().as_posix() for x in lista),
        encoding="utf-8")
    entera = carpeta / "voz.m4a"
    # El color se aplica a la voz ENTERA y no renglón por renglón, que es lo
    # que de verdad importa acá: el compresor tiene memoria -ataque y
    # relajación- y por renglón arrancaría de cero en cada uno, así que la
    # misma frase sonaría más cerca o más lejos según dónde cayó el corte.
    #
    # Y después de pegar, no antes: así los silencios de en medio también
    # pasan por el compresor y no se oye un salto al entrar cada renglón.
    filtro = filtro_de_color(color)
    orden = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
             "-safe", "0", "-i", str(guion_concat)]
    if filtro:
        orden += ["-af", filtro]
    orden += ["-c:a", "aac", "-b:a", "128k", str(entera)]
    _correr(orden, "pegar la voz")
    return entera, duraciones


def agrupar_en_oraciones(unidades: Sequence[str]) -> List[List[str]]:
    """Los renglones del subtítulo, juntados otra vez por oración.

    Hace falta cuando la voz habla OTRO idioma que el subtítulo: de cada
    oración sale un audio, así que la oración es la unidad más chica donde
    los dos se pueden hacer coincidir. Dentro, los renglones se reparten.

    Se agrupa mirando el punto final porque `unidades_de` parte primero por
    oración (`CORTE_FUERTE`) y recién después subdivide las largas: el último
    renglón de cada oración conserva su signo y los del medio no.
    """
    grupos: List[List[str]] = []
    actual: List[str] = []
    for u in unidades:
        actual.append(u)
        if u.rstrip().endswith((".", "!", "?", "…", '."', '".')):
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def marcas_por_oracion(grupos: Sequence[Sequence[str]],
                       duraciones: Sequence[float]) -> List[Tuple[float, float]]:
    """Cuándo entra y sale cada renglón, cuando el audio va por oración.

    Cada oración ocupa lo que dura su audio, y adentro los renglones se
    reparten proporcional a lo que miden. Es lo más cerca que se puede estar
    sin tener los tiempos palabra por palabra, y el error queda ACOTADO a la
    oración: un renglón que se adelanta no arrastra a los de las oraciones
    siguientes, que es lo que pasaría repartiendo sobre el total.
    """
    if len(grupos) != len(duraciones):
        raise VideoError(
            "son %d oraciones y %d audios: no se pueden hacer coincidir"
            % (len(grupos), len(duraciones)))
    marcas: List[Tuple[float, float]] = []
    t = 0.0
    for renglones, dura in zip(grupos, duraciones):
        largos = [max(len(r), 1) for r in renglones]
        suma = sum(largos)
        dentro = t
        for n in largos:
            trozo = dura * n / suma
            marcas.append((dentro, dentro + trozo))
            dentro += trozo
        t += dura
    return marcas


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

_FFMPEG = None
DURACION = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
TIEMPO = re.compile(r"time=\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")


def ffmpeg() -> str:
    """Dónde está ffmpeg. Se busca, no se asume.

    En orden: la variable FFMPEG del entorno, el PATH, y por último el binario
    que trae el paquete `imageio-ffmpeg`, que se instala con pip y no necesita
    Homebrew ni permiso de administrador. Esa última es la que hace que esto
    funcione en una Mac donde nunca se instaló nada: pasó, y el error era
    «[Errno 2] No such file or directory: 'ffmpeg'», que no dice qué hacer.
    """
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    import os
    import shutil
    _FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not _FFMPEG:
        try:
            import imageio_ffmpeg
            _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:                        # noqa: BLE001
            raise VideoError(
                "no encuentro ffmpeg, que es lo que arma el video.\n"
                "Se instala sin Homebrew y sin contraseña:\n"
                "    .venv/bin/pip install imageio-ffmpeg\n"
                "O, si ya lo tenés en otro lado, pasale la ruta en FFMPEG.")
    return _FFMPEG


def duracion(ruta: Path) -> float:
    """Cuánto dura un archivo.

    Se le pregunta a ffmpeg y no a ffprobe: el ffmpeg que trae
    `imageio-ffmpeg` -el camino sin Homebrew- no incluye ffprobe, así que
    pedirlo dejaría a media Mac sin poder armar un reel.
    """
    ruta = Path(ruta)
    try:
        r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(ruta)],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude medir %s: %s" % (ruta.name, e))
    m = DURACION.search(r.stderr or "")
    if m and not (r.stderr or "").count("Duration: N/A"):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    # Algunos archivos no declaran la duración en la cabecera. Decodificarlos
    # entero y mirar el último `time=` es lento pero siempre contesta.
    try:
        r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(ruta), "-f", "null", "-"],
                           capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude medir %s: %s" % (ruta.name, e))
    marcas = TIEMPO.findall(r.stderr or "")
    if not marcas:
        raise VideoError("ffmpeg no supo decir cuánto dura %s" % ruta.name)
    h, m2, seg = marcas[-1]
    return int(h) * 3600 + int(m2) * 60 + float(seg)


def _deriva(total: float) -> str:
    """El recorte que se mueve despacio sobre un fondo más grande que el cuadro.

    Es una deriva y no un zoom: `zoompan` sobre una imagen quieta tiembla, y
    un temblor de un píxel en un video de un minuto se nota.
    """
    return ("crop=%d:%d:x='(iw-ow)/2+(iw-ow)/2*sin(t/14)':y='(ih-oh)/2+(ih-oh)/2*sin(t/19)'"
            % (ANCHO, ALTO))


# Cuánto dura cada clip antes de cortar al siguiente. Sale de mirar la
# referencia: no es UN video de fondo sino varios que se van turnando, y es
# buena parte de por qué no se hace largo. Con escenas mucho más cortas el
# corte compite con el texto; mucho más largas y vuelve a ser un fondo fijo.
# Cada cuanto se cambia de clip. MEDIDO en la referencia que mando el
# usuario: tiene 14 cortes en 83 segundos y la mediana entre uno y otro es de
# 4,1 s -el reparto va de 2,7 a 5,5-. Antes estaba en 7, que se veia bastante
# mas lento que el ejemplo.
#
# Los cortes son SECOS, sin fundido entre clips: se comprobo cuadro a cuadro
# alrededor de un corte y no hay ni una imagen mezclada. Lo que si se
# desvanece es el texto (`FUNDIDO_TEXTO`).
ESCENA = 4.0

# Cuanto tarda un renglon en aparecer y en irse, en milisegundos. Tambien
# medido en la referencia: unos cinco cuadros a 25 fps.
FUNDIDO_TEXTO = 250

# La música va MUY abajo cuando hay voz: es una cama, no un tema.
#
# El número está medido, no elegido. Sobre el audio de la referencia que mandó
# el usuario, su cama está 17 dB bajo la voz. Se armó el mismo reel con 0,14,
# 0,07 y 0,05 y se midió igual: dan -11, -16 y -19 dB. Queda 0,07.
#
# No es el -17 dB «de manual» porque las dos pistas pasan antes por `loudnorm`,
# que empareja la sonoridad del PROGRAMA, y una voz con pausas cada renglón
# tiene una mediana más baja que su sonoridad integrada. Lo que importa es que
# la proporción que se oye sea la de la referencia, no que el número coincida
# con el de un manual.
MUSICA_CON_VOZ = 0.07
MUSICA_SOLA = 0.50
ENTRADA = 1.5              # el fundido de entrada
SALIDA = 2.5               # y el de salida, que evita el corte seco

# El volumen al que Facebook e Instagram dejan todo lo que se sube: si el reel
# viene más bajo lo suben igual, y si viene más alto lo bajan. Dejarlo acá hace
# que un reel grabado con tu voz y otro hecho con `say` suenen parejo, que si
# no dependen de cuánto levante el micrófono.
SONORIDAD = "I=-14:TP=-1.5:LRA=11"
# A la música se la empareja antes de bajarla, con menos rango dinámico: una
# cama que sube y baja sola compite con la voz.
SONORIDAD_MUSICA = "I=-16:TP=-2:LRA=7"

# La cama que viene con el repo, generada con ffmpeg: un acorde sostenido con
# oleadas muy lentas. Está acá y no se baja de ningún lado por lo mismo que el
# fondo de papel -que un reel salga hoy sin depender de una descarga- y además
# porque es original: una pista con derechos le hace perder alcance a TODA la
# cuenta, no solo a ese post.
# Piano, no el colchon grave de antes. El usuario pidio «un leve piano como
# el video de referencia», y la medicion le daba la razon: `calma.m4a` no
# tenia nada arriba de 1 kHz -la diferencia de firma con la referencia era de
# 26,8 dB- y un piano se reconoce justamente por sus armonicos. El nuevo queda
# a 4,6 dB. Se genera con `scripts/hacer_musica.py` y es original.
MUSICA = ROOT / "assets" / "musica" / "piano.m4a"


def escenas(clips: Sequence[Path], total: float, escena: float = ESCENA) -> List[Path]:
    """Qué clip va en cada tramo, turnándolos hasta cubrir el guion."""
    cuantas = max(1, int(total / escena + 0.999))
    return [Path(clips[i % len(clips)]) for i in range(cuantas)]


def comando(subtitulos: Path, salida: Path, total: float, fondo,
            rotulos: Optional[Path] = None, voz: Optional[Path] = None,
            musica: Optional[Path] = None, escena: float = ESCENA) -> List[str]:
    """El ffmpeg que arma el reel. Devuelve la lista, para poder mirarla sin correrla.

    Las capas, en orden: el fondo -una imagen que deriva, o varios clips que se
    van cortando-, los rótulos de la página QUIETOS encima si los hay, y los
    subtítulos quemados al final.
    """
    entradas: List[str] = []
    cuantas = 0                        # el índice de cada entrada, contado y no deducido
    clips = [Path(x) for x in (fondo if isinstance(fondo, (list, tuple)) else [fondo])]
    es_imagen = clips[0].suffix.lower() in (".png", ".jpg", ".jpeg")
    if es_imagen:
        entradas += ["-loop", "1", "-i", str(clips[0])]
        cadena = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,%s,fps=%d,setsar=1[bg]"
                  % (int(ANCHO * SOBREMEDIDA), int(ALTO * SOBREMEDIDA), _deriva(total), FPS))
        cuantas += 1
    else:
        # Cada tramo es una entrada propia, con `-stream_loop` para que un clip
        # más corto que el tramo no deje el cuadro en negro. Se oscurece y se
        # baja el color: sobre un clip claro, hasta el amarillo con contorno
        # cuesta, y la referencia también tiene la imagen apagada.
        trozos = escenas(clips, total, escena)
        partes = []
        for i, clip in enumerate(trozos):
            entradas += ["-stream_loop", "-1", "-i", str(clip)]
            partes.append(
                "[%d:v]trim=duration=%.2f,setpts=PTS-STARTPTS,"
                "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                "fps=%d,eq=brightness=-0.16:saturation=0.90,setsar=1[e%d]"
                % (i, escena, ANCHO, ALTO, ANCHO, ALTO, FPS, i))
            cuantas += 1
        cadena = ";".join(partes) + ";%sconcat=n=%d:v=1:a=0[bg]" % (
            "".join("[e%d]" % i for i in range(len(trozos))), len(trozos))
    if rotulos:
        entradas += ["-loop", "1", "-i", str(rotulos)]
        cadena += ";[bg][%d:v]overlay=0:0[marcado]" % cuantas
        cuantas += 1
        ultima = "marcado"
    else:
        ultima = "bg"
    # `fontsdir` es lo que hace que libass encuentre la Lora del repo sin
    # instalarla en el sistema: sin eso, en otra computadora el reel sale con
    # otra tipografía y nadie se entera hasta verlo.
    cadena += ";[%s]ass='%s':fontsdir='%s'[v]" % (ultima, subtitulos.as_posix(),
                                                  FUENTES.as_posix())

    pista_voz = cuantas
    if voz:
        entradas += ["-i", str(voz)]
    else:
        entradas += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    cuantas += 1
    if musica:
        # Se repite si es más corta que el reel: una cama que se corta a la
        # mitad se nota más que no tenerla.
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        # La música se empareja ANTES de bajarla, y eso es lo que hace que el
        # 0.14 signifique algo: sin esto, el volumen de la cama dependía de
        # cuán fuerte viniera el archivo. Un tema bajo quedaba inaudible y uno
        # fuerte tapaba la voz, y la única forma de arreglarlo era volver a
        # exportar el mp3.
        cadena += (";[%d:a]aformat=sample_fmts=fltp:sample_rates=48000:"
                   "channel_layouts=stereo,loudnorm=%s,volume=%.2f,"
                   "afade=t=in:d=%.1f,afade=t=out:st=%.2f:d=%.1f[mus]"
                   % (cuantas, SONORIDAD_MUSICA, MUSICA_CON_VOZ if voz else MUSICA_SOLA,
                      ENTRADA, max(0.0, total - SALIDA), SALIDA))
        # `normalize=0` no es un detalle: por defecto `amix` divide por la
        # cantidad de entradas, o sea que la voz saldría a la mitad y habría
        # que compensarla subiéndola, que es como se llega a un reel que
        # satura en el teléfono.
        # La voz se empareja igual que la música, y por el mismo motivo: el
        # 0.14 es una proporción ENTRE LAS DOS. Emparejando solo la música, el
        # resultado depende de cuán fuerte hable la voz -una grabación tuya y
        # la de OpenAI no salen al mismo nivel- y la cama se va de lugar. Se
        # midió: con la voz sin emparejar la cama quedaba a -6 dB en vez de
        # -17, o sea compitiendo con lo que se dice.
        cadena += (";[%d:a]aformat=sample_fmts=fltp:sample_rates=48000:"
                   "channel_layouts=stereo,loudnorm=%s[vz];"
                   "[vz][mus]amix=inputs=2:duration=first:normalize=0[a]"
                   % (pista_voz, SONORIDAD_MUSICA))
        cuantas += 1
        salida_audio = "[a]"
    elif voz:
        cadena += ";[%d:a]aformat=sample_fmts=fltp:sample_rates=48000:" \
                  "channel_layouts=stereo[a]" % pista_voz
        salida_audio = "[a]"
    else:
        # Sin voz y sin música no hay nada que nivelar, y `loudnorm` sobre
        # silencio es trabajo para nada.
        salida_audio = "%d:a" % pista_voz
    if salida_audio == "[a]":
        cadena = cadena[:-len("[a]")] + ",loudnorm=%s[a]" % SONORIDAD
    return ([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"] + entradas +
            ["-filter_complex", cadena, "-map", "[v]", "-map", salida_audio,
             "-t", "%.2f" % total,
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
             "-movflags", "+faststart", str(salida)])


def armar(frase: Frase, pagina: Pagina, titulo: str = "", salida: Optional[Path] = None,
          fondo=None, voz: Optional[Path] = None, carpeta: Optional[Path] = None,
          marcas: Optional[List[Tuple[float, float]]] = None,
          rotular: Optional[bool] = None, musica: Optional[Path] = None,
          unidades: Optional[Sequence[str]] = None) -> Path:
    """El reel entero. Devuelve el archivo.

    Sin `fondo` dibuja el papel de la marca; `fondo` puede ser un clip o una
    lista de clips, que se van turnando. Sin `voz` sale mudo y el texto dura lo
    que tardaría en leerse.

    `rotular` pone el nombre de la página arriba y el capítulo abajo. Por
    defecto va SOLO sobre el papel: ahí hacen falta -si no es una hoja en
    blanco- y sobre video la referencia que pidió el usuario no los tiene.
    """
    carpeta = Path(carpeta or REELS)
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = Path(salida or carpeta / ("%s.mp4" % frase.id))
    unidades = list(unidades) if unidades else guion(frase)
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
    if rotular is None:
        rotular = tema == "papel"
    rotulos = (marca(pagina, titulo, carpeta / ("%s-marca.png" % frase.id), tema)
               if rotular else None)
    sub = carpeta / ("%s.ass" % frase.id)
    sub.write_text(ass(unidades, marcas, pagina, tema), encoding="utf-8")
    try:
        r = subprocess.run(comando(sub, salida, total, fondo, rotulos, voz, musica),
                           capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as e:
        raise VideoError("no pude llamar a ffmpeg: %s" % e)
    if r.returncode != 0 or not salida.exists():
        raise VideoError("ffmpeg falló: %s" % (r.stderr or "")[-400:])
    return salida
