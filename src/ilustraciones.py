"""El dibujo chico debajo de la frase: una ilustración minimalista por frase,
generada con IA y guardada en disco para no volver a pagarla.

Por qué con semilla NO alcanza (al contrario que el papel o el subrayado a
mano): un modelo de imágenes no es una función pura de un número, así que la
única forma de que «el flyer que se aprueba y el que se publica sean el mismo
archivo» es generarla UNA vez y guardarla. De ahí que todo este módulo gire
alrededor de la caché y no de la llamada: `ilustracion_de` primero mira el
disco, y solo pide una nueva si no hay nada guardado con ese nombre.

Es por frase y no por capítulo -244 llamadas en vez de 29- porque así lo
pidió el usuario, visto el costo: unos $5 a $10 en total, pagados una sola
vez por frase.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Callable, Optional

from .frases import Frase, Tema

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "ilustraciones"

API = "https://api.openai.com/v1/images/generations"
MODELO = "gpt-image-2"
# "medium" y no "high": es un dibujo chico y decorativo, no la pieza central
# del flyer -eso lo sigue siendo la frase-. A tamaño chico la diferencia con
# "high" no se nota y "high" cuesta entre 4 y 15 veces más por imagen.
CALIDAD = "medium"
TAMANO = "1024x1024"

# El estilo es UNA frase fija y no algo que cada llamada arme distinto: si el
# encargo cambiara de una frase a otra, 243 ilustraciones no se leerían como
# la misma página. Lo único que cambia por frase es la ESCENA.
ESTILO = (
    "Minimalist flat vector illustration, in the style of a modern editorial "
    "icon: simple geometric shapes, clean lines, generous negative space, "
    "no outlines around the shapes, no gradients, no shading, no text, no "
    "letters, no words, no logos, no watermark. A small warm and muted color "
    "palette (dusty terracotta, warm cream, soft navy ink, warm gray), the "
    "same family of colors across every illustration of this set. Centered "
    "composition, the subject small and simple enough to read at thumbnail "
    "size. Transparent background."
)


class IlustracionError(RuntimeError):
    pass


def _archivo(frase_id: str, cache: Optional[Path] = None) -> Path:
    return Path(cache or CACHE) / ("%s.png" % frase_id)


def guardada(frase_id: str, cache: Optional[Path] = None) -> Optional[Path]:
    """La ilustración ya generada de esa frase, o None si no hay ninguna.

    Un archivo de 0 bytes -el que deja una escritura cortada a mitad de
    camino- no cuenta como guardado: `_archivo` lo volvería a usar, y un PNG
    vacío no se pega en ningún lado.
    """
    archivo = _archivo(frase_id, cache)
    if archivo.exists() and archivo.stat().st_size > 0:
        return archivo
    return None


def _escena(frase: Frase, tema: Tema) -> str:
    """Lo único que cambia entre una ilustración y otra: de qué habla ESTA
    frase, no cómo se dibuja -eso es `ESTILO`, y es el mismo para las 243-.

    Se arma del título del capítulo y de las palabras destacadas de la frase
    y no del texto entero: el texto es un aforismo, no una descripción de
    escena, y pedirle al modelo que "ilustre" la frase tal cual suele volver
    con un cartel o una persona hablando -lo primero lleva texto, que el
    estilo prohíbe, y lo segundo no es lo que el usuario mostró de ejemplo-.
    """
    pistas = ", ".join(frase.destacar) if frase.destacar else tema.titulo
    return ("A simple symbolic scene about \"%s\" (chapter: %s). Depict the "
            "idea through a small universal scene or object, metaphorically: "
            "for example two small figures, a plant, a path, hands, a house, "
            "a door, whatever best represents the idea without literally "
            "drawing words. %s" % (pistas, tema.titulo, ESTILO))


def _pedir(clave: str, cuerpo: dict) -> bytes:
    import requests
    try:
        r = requests.post(API, json=cuerpo, timeout=120,
                          headers={"Authorization": "Bearer %s" % clave})
    except requests.RequestException as e:
        raise IlustracionError("no se pudo llegar a OpenAI: %s" % e)
    if r.status_code != 200:
        raise IlustracionError("OpenAI contestó %d: %s" % (r.status_code, r.text[:300]))
    try:
        b64 = r.json()["data"][0]["b64_json"]
    except (KeyError, IndexError, ValueError) as e:
        raise IlustracionError("no entendí la respuesta de OpenAI: %s" % e)
    try:
        return base64.b64decode(b64)
    except (ValueError, TypeError) as e:
        raise IlustracionError("la imagen que mandó OpenAI no se pudo leer: %s" % e)


def ilustracion_de(frase: Frase, tema: Tema, cache: Optional[Path] = None,
                   pedir: Optional[Callable] = None) -> Path:
    """La ilustración de esa frase: la del disco si ya existe, o una nueva.

    Levanta `IlustracionError` si no hay clave o si OpenAI falla. Quien llama
    y no quiere perder un turno por eso usa `para()`, más abajo, que la
    atrapa.
    """
    ya = guardada(frase.id, cache)
    if ya is not None:
        return ya
    clave = os.environ.get("OPENAI_API_KEY")
    if not clave:
        raise IlustracionError("falta OPENAI_API_KEY en el .env")
    pedir = pedir or _pedir
    crudo = pedir(clave, {
        "model": MODELO,
        "prompt": _escena(frase, tema),
        "size": TAMANO,
        "quality": CALIDAD,
        "background": "transparent",
    })
    archivo = _archivo(frase.id, cache)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = archivo.with_suffix(".parcial")
    tmp.write_bytes(crudo)
    tmp.replace(archivo)
    return archivo


def para(pagina, frase: Frase, tema: Tema, cache: Optional[Path] = None,
        pedir: Optional[Callable] = None) -> Optional[Path]:
    """La ilustración de este turno, o None si la página no las lleva o si
    algo falló al pedirla.

    Es la que usan `bot.py` y `publicar_turno.py`, y no `ilustracion_de`
    directo: un problema con OpenAI -la clave vencida, la API caída- no puede
    costar el turno. Publicar sin el dibujo chico es mucho mejor que no
    publicar nada, que es la misma razón por la que `historias.del_flyer`
    nunca levanta error.
    """
    if not getattr(pagina, "ilustraciones", False):
        return None
    try:
        return ilustracion_de(frase, tema, cache, pedir)
    except IlustracionError as e:
        print("No se pudo conseguir la ilustración de %s: %s" % (frase.id, e))
        return None
