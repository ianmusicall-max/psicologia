"""El banco de frases: leerlo, validarlo contra la línea editorial y elegir la siguiente.

Cada archivo de `frases/` es un tema de la página y un capítulo del libro. Este
módulo es el único que sabe cómo está escrito ese archivo; el dibujo, la
publicación y el libro reciben objetos, no diccionarios.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

from .config import Pagina

ROOT = Path(__file__).resolve().parent.parent
CARPETA = ROOT / "frases"
PUBLICADAS = ROOT / "data" / "publicadas.json"

# Largo del texto del flyer. Por debajo de 25 no es una frase, es un eslogan;
# por encima de 180 ya no entra legible en 1080x1350 y en el teléfono se lee
# como un párrafo. Las 81 del banco van de 55 a 136.
MINIMO = 25
MAXIMO = 180
REFLEXION_MINIMO = 80
REFLEXION_MAXIMO = 700
HASHTAGS = 5

# ---------------------------------------------------------------------------
# La línea editorial, como código. Cada grupo tiene su razón en
# LINEA_EDITORIAL.md; aquí está lo que de verdad rebota una frase.
# Se compara sin acentos ni mayúsculas y por palabra entera: "loca" no se
# lleva puesto a "colocar".
# ---------------------------------------------------------------------------

# Diagnósticos usados como adjetivo de una persona. La página no etiqueta a
# nadie: ni al lector ni a su ex.
ETIQUETAS = ("narcisista", "narcisistas", "toxico", "toxica", "toxicos", "toxicas",
             "psicopata", "psicopatas", "bipolar", "borderline", "trastorno",
             "trastornos", "enfermo mental", "enferma mental", "loco", "loca")
# Pseudociencia. Una página de psicología que habla de energías es otra cosa.
PSEUDO = ("energia", "energias", "vibra", "vibras", "universo", "ley de atraccion",
          "manifestar", "manifiesta", "karma", "chakra", "chakras", "frecuencia vibratoria")
# Positividad tóxica: la que convierte el dolor en una falla de actitud.
POSITIVISMO = ("todo pasa por algo", "piensa positivo", "pensar positivo",
               "pensamiento positivo", "buena vibra", "buenas vibras",
               "actitud positiva", "si quieres puedes", "querer es poder")
# Promesas. Nada aquí cura, sana ni es para siempre.
PROMESAS = ("cura", "curar", "curate", "sanar", "sana tu", "sanacion", "para siempre",
            "nunca mas", "garantizado", "en 7 dias", "en siete dias", "en una semana",
            "elimina", "milagro", "milagroso", "milagrosa")
# Vergüenza: la que le dice al lector que su problema es falta de carácter.
VERGUENZA = ("excusas", "excusa", "debil", "flojo", "floja", "falta de voluntad",
             "no hay excusa", "es tu culpa", "por flojera")
# Crisis. Sobre esto no se escribe en un flyer; se dan recursos. Son raíces,
# no palabras enteras: agarran "suicidio", "suicida", "autolesión".
CRISIS = ("suicid", "autolesi", "quitarse la vida", "quitarte la vida", "matarte")
# Citas. Una frase con raya es una cita, y aquí no se cita: se escribe. Es la
# regla que hace posible el libro.
#
# Dos patrones y no uno, porque los dos casos se reconocen distinto. El de
# arriba va sobre el texto sin acentos: la raya de atribución y las fórmulas
# que presentan una frase ajena. El de abajo va sobre el texto TAL CUAL,
# porque lo que delata una atribución es la mayúscula del nombre que sigue:
# «frase de prueba» es lengua común y «frase de Freud» es una cita, y en
# minúsculas las dos se ven iguales. Un verbo suelto tampoco cuenta: «alguien
# te lo dijo primero» es una frase del banco, no una atribución.
CITA = re.compile(r"[—–]|(?<!\w)(como dice|como decia|autor desconocido|anonimo)(?!\w)")
ATRIBUCION = re.compile(r"\b(frase|cita|palabras) de [A-ZÁÉÍÓÚÑ]")

GRUPOS = (("etiqueta a una persona", ETIQUETAS), ("pseudociencia", PSEUDO),
          ("positividad tóxica", POSITIVISMO), ("promesa", PROMESAS),
          ("vergüenza", VERGUENZA))


def _plano(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar."""
    sin = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin if unicodedata.category(c) != "Mn").lower()


def politica(texto: str) -> List[str]:
    """Qué de la línea editorial rompe este texto. Lista vacía si nada."""
    plano = _plano(texto)
    problemas = []
    for motivo, palabras in GRUPOS:
        for p in palabras:
            if re.search(r"(?<!\w)%s(?!\w)" % re.escape(p), plano):
                problemas.append("%s: «%s»" % (motivo, p))
    for raiz in CRISIS:
        if raiz in plano:
            problemas.append("crisis: «%s» no va en un flyer, va con recursos" % raiz)
    if CITA.search(plano) or ATRIBUCION.search(texto):
        problemas.append("cita: una raya o un «dijo» convierten la frase en una cita ajena")
    return problemas


@dataclass
class Frase:
    id: str
    texto: str
    principio: str
    fuente: str
    reflexion: str
    tema: str
    destacar: List[str] = field(default_factory=list)
    sensible: Optional[bool] = None


# Los dos ejes de la página. `nucleo` son los temas que su descripción
# promete -amor propio, vínculos, comunicación, elegir, ruptura-; `apoyo` son
# los que sostienen a esos sin ser el motivo por el que alguien la sigue.
# La cuota de abajo hace que dos de cada tres posts sean del núcleo.
EJES = ("nucleo", "apoyo")
NUCLEO_DE_CADA = 3      # ...de cada tres
NUCLEO_CUANTOS = 2      # ...son del núcleo


@dataclass
class Tema:
    tema: str
    capitulo: int
    titulo: str
    tesis: str
    eje: str = "apoyo"
    hashtags: List[str] = field(default_factory=list)
    sensible: bool = False
    frases: List[Frase] = field(default_factory=list)
    archivo: str = ""

    def es_sensible(self, frase: Frase) -> bool:
        return self.sensible if frase.sensible is None else bool(frase.sensible)


ID = re.compile(r"^[a-z]{3}-\d{2}$")
PALABRA = re.compile(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+")


def palabras(texto: str) -> List[str]:
    """Las palabras del texto sin signos, en minúsculas. Para buscar las destacadas."""
    return [w.lower() for w in PALABRA.findall(texto)]


def destacadas(frase: Frase) -> List[bool]:
    """Para cada palabra del texto, si va en color. Una entrada de `destacar`
    puede ser varias palabras seguidas ("dos veces"); se marca la secuencia."""
    ws = palabras(frase.texto)
    marca = [False] * len(ws)
    for item in frase.destacar:
        sec = palabras(item)
        if not sec:
            continue
        for i in range(len(ws) - len(sec) + 1):
            if ws[i:i + len(sec)] == sec:
                for j in range(i, i + len(sec)):
                    marca[j] = True
    return marca


def validar(frase: Frase) -> List[str]:
    """Todo lo que impediría publicar esta frase. Vacío si está bien."""
    p = []
    if not ID.match(frase.id):
        p.append("id «%s»: tiene que ser tres letras, guion y dos dígitos" % frase.id)
    t = frase.texto.strip()
    if len(t) < MINIMO:
        p.append("texto de %d caracteres: menos de %d es un eslogan" % (len(t), MINIMO))
    if len(t) > MAXIMO:
        p.append("texto de %d caracteres: más de %d no entra en el flyer" % (len(t), MAXIMO))
    if t and t[-1] not in ".?!»":
        p.append("el texto tiene que terminar en punto, signo o comillas")
    if '"' in t:
        p.append("comillas rectas en el texto: para citar algo dentro van «»")
    for problema in politica(t):
        p.append("texto, " + problema)
    for problema in politica(frase.reflexion):
        p.append("reflexión, " + problema)
    r = frase.reflexion.strip()
    if len(r) < REFLEXION_MINIMO:
        p.append("reflexión de %d caracteres: es el caption y la semilla del capítulo, pide al menos %d"
                 % (len(r), REFLEXION_MINIMO))
    if len(r) > REFLEXION_MAXIMO:
        p.append("reflexión de %d caracteres: más de %d es un artículo, no un caption"
                 % (len(r), REFLEXION_MAXIMO))
    if not frase.principio.strip():
        p.append("sin principio: el libro necesita saber qué sostiene la frase")
    if not frase.fuente.strip():
        p.append("sin fuente: una frase sin respaldo es una opinión con tipografía")
    ws = palabras(t)
    for item in frase.destacar:
        sec = palabras(item)
        if not any(ws[i:i + len(sec)] == sec for i in range(len(ws) - len(sec) + 1)):
            p.append("destacar «%s»: no está en el texto" % item)
    return p


def validar_tema(tema: Tema) -> List[str]:
    p = []
    if tema.eje not in EJES:
        p.append("%s: eje «%s»: tiene que ser %s" % (tema.tema, tema.eje, " o ".join(EJES)))
    if not tema.titulo.strip():
        p.append("%s: sin título de capítulo" % tema.tema)
    if len(tema.tesis.strip()) < 80:
        p.append("%s: la tesis del capítulo es demasiado corta" % tema.tema)
    if len(tema.hashtags) != HASHTAGS - 2:
        p.append("%s: el tema aporta %d hashtags y la página pone 2, tienen que ser %d en total"
                 % (tema.tema, len(tema.hashtags), HASHTAGS))
    for h in tema.hashtags:
        if not re.match(r"^[\wáéíóúüñ]+$", h):
            p.append("%s: hashtag «%s» con espacios o signos" % (tema.tema, h))
    for problema in politica(tema.tesis):
        p.append("%s, tesis, %s" % (tema.tema, problema))
    return p


def _tema(datos: dict, archivo: str) -> Tema:
    tema = Tema(
        tema=str(datos["tema"]),
        capitulo=int(datos["capitulo"]),
        titulo=str(datos.get("titulo") or ""),
        eje=str(datos.get("eje") or "apoyo"),
        tesis=str(datos.get("tesis") or "").strip(),
        hashtags=[str(h) for h in (datos.get("hashtags") or [])],
        sensible=bool(datos.get("sensible", False)),
        archivo=archivo,
    )
    for d in datos.get("frases") or []:
        tema.frases.append(Frase(
            id=str(d.get("id") or ""),
            texto=str(d.get("texto") or "").strip(),
            principio=str(d.get("principio") or "").strip(),
            fuente=str(d.get("fuente") or "").strip(),
            reflexion=" ".join(str(d.get("reflexion") or "").split()),
            tema=tema.tema,
            destacar=[str(x) for x in (d.get("destacar") or [])],
            sensible=d.get("sensible"),
        ))
    return tema


def leer(carpeta: Optional[Path] = None) -> List[Tema]:
    """Todos los temas, en orden de capítulo.

    El valor por defecto se resuelve ACÁ y no en la firma. Un `carpeta: Path =
    CARPETA` se evalúa al importar el módulo, así que queda clavado: cambiar
    `frases.CARPETA` después no cambia nada, y lo que de verdad corre es el
    camino viejo. Lo mismo vale para las funciones de abajo.
    """
    temas = []
    for ruta in sorted(Path(carpeta or CARPETA).glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        temas.append(_tema(datos, ruta.name))
    temas.sort(key=lambda t: t.capitulo)
    return temas


def todas(temas: Iterable[Tema]) -> List[Frase]:
    return [f for t in temas for f in t.frases]


def revisar(temas: Iterable[Tema], pagina: Optional[Pagina] = None) -> List[str]:
    """Todos los problemas del banco entero, con el id delante de cada uno.

    Con la página delante revisa además que ningún tema repita uno de los
    hashtags fijos. Esa colisión no rompe nada visible -`hashtags` quita el
    repetido- pero deja el post con cuatro etiquetas en vez de cinco, y eso
    no se nota mirando un caption.
    """
    temas = list(temas)
    problemas = []
    vistos: Dict[str, str] = {}
    capitulos: Dict[int, str] = {}
    fijos = {_plano(h) for h in (pagina.hashtags_fijos if pagina else [])}
    for t in temas:
        problemas += validar_tema(t)
        for h in t.hashtags:
            if _plano(h) in fijos:
                problemas.append("%s: el hashtag «%s» ya es uno de los fijos de la página, "
                                 "así que el post saldría con cuatro y no con cinco" % (t.tema, h))
        if t.capitulo in capitulos:
            problemas.append("capítulo %d repetido: %s y %s" % (t.capitulo, capitulos[t.capitulo], t.tema))
        capitulos[t.capitulo] = t.tema
        for f in t.frases:
            if f.id in vistos:
                problemas.append("%s: id repetido (también en %s)" % (f.id, vistos[f.id]))
            vistos[f.id] = t.tema
            problemas += ["%s: %s" % (f.id, x) for x in validar(f)]
    return problemas


# ---------------------------------------------------------------------------
# Lo publicado y la siguiente.
# ---------------------------------------------------------------------------

def publicadas(ruta: Optional[Path] = None) -> Dict[str, dict]:
    """{id: {"dia", "post_id", "pagina"}} de lo que ya salió."""
    ruta = Path(ruta or PUBLICADAS)
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def anotar_publicada(frase_id: str, dia: date, post_id: str, pagina: str,
                     ruta: Optional[Path] = None, extra: Optional[Dict] = None) -> None:
    """Relee antes de escribir: si dos procesos anotan seguido, ninguno pisa al otro.

    `extra` guarda con QUÉ salió el post: el tema, el eje, el estilo, la hora
    y el id de Instagram. Sin eso no se puede comparar nada después: el post
    ya salió y Facebook no sabe con qué diseño se dibujó.
    """
    ruta = Path(ruta or PUBLICADAS)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    actual = publicadas(ruta)
    actual[frase_id] = dict({"dia": dia.isoformat(), "post_id": post_id, "pagina": pagina},
                            **(extra or {}))
    tmp = ruta.with_suffix(".parcial")
    tmp.write_text(json.dumps(actual, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(ruta)


def toca_nucleo(temas: Iterable[Tema], ya: Dict[str, dict]) -> bool:
    """Si el turno que sigue tiene que buscar primero un tema del núcleo.

    La cuota se cumple turno a turno y no contando al final: así los temas de
    la página quedan INTERCALADOS con los de apoyo en vez de salir todos
    primero, y si un día se corta la racha, lo que alcanzó a salir también
    respeta la proporción.
    """
    eje_de = {f.id: t.eje for t in temas for f in t.frases}
    nucleo = sum(1 for fid in ya if eje_de.get(fid) == "nucleo")
    apoyo = sum(1 for fid in ya if eje_de.get(fid) == "apoyo")
    return nucleo < NUCLEO_CUANTOS * (apoyo + 1)


def siguiente(temas: Iterable[Tema], ya: Dict[str, dict]) -> Optional[Frase]:
    """La próxima frase a publicar: del tema que hace más que no sale, la
    primera que todavía no salió.

    Rotar por tema es lo que evita diez días seguidos de duelo. Entre temas
    que nunca salieron manda el orden de capítulo; entre los que ya salieron,
    el que publicó hace más tiempo. Es determinista: depende de lo publicado
    y no del reloj, así que mirarla dos veces el mismo día da la misma frase.

    Encima de esa rotación va la cuota del núcleo. **No es un filtro**: si
    ningún tema del núcleo tiene frases pendientes, sale el que haya. Perder
    un día de publicación sería mucho peor que romper la proporción.
    """
    temas = list(temas)
    candidatos = []
    for t in temas:
        pendientes = [f for f in t.frases if f.id not in ya]
        if not pendientes:
            continue
        ultima = max((ya[f.id]["dia"] for f in t.frases if f.id in ya), default="")
        candidatos.append((ultima, t.capitulo, t.eje, pendientes[0]))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0], c[1]))
    if toca_nucleo(temas, ya):
        del_nucleo = [c for c in candidatos if c[2] == "nucleo"]
        if del_nucleo:
            return del_nucleo[0][3]
    return candidatos[0][3]


def por_id(temas: Iterable[Tema], frase_id: str) -> Optional[Frase]:
    for f in todas(temas):
        if f.id == frase_id:
            return f
    return None


def tema_de(temas: Iterable[Tema], frase: Frase) -> Tema:
    for t in temas:
        if t.tema == frase.tema:
            return t
    raise KeyError(frase.tema)


# ---------------------------------------------------------------------------
# El caption.
# ---------------------------------------------------------------------------

def hashtags(tema: Tema, pagina: Pagina) -> List[str]:
    """Cinco: los dos fijos de la página y los tres del tema, sin repetir."""
    vistos, lista = set(), []
    for h in list(pagina.hashtags_fijos) + list(tema.hashtags):
        clave = _plano(h)
        if clave in vistos:
            continue
        vistos.add(clave)
        lista.append("#" + h)
    return lista[:HASHTAGS]


def caption(frase: Frase, tema: Tema, pagina: Pagina) -> str:
    """La frase, la reflexión, el pie si el tema es sensible y los hashtags."""
    partes = [frase.texto, frase.reflexion]
    if tema.es_sensible(frase) and pagina.pie_sensible:
        partes.append(pagina.pie_sensible)
    partes.append(" ".join(hashtags(tema, pagina)))
    return "\n\n".join(p for p in partes if p)
