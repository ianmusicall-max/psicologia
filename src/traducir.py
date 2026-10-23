"""El español del banco pasado a inglés, para que la voz lo lea.

El reel sale con la VOZ en inglés y los SUBTÍTULOS en español: lo decidió el
usuario el 2026-10-23. Así que el banco se sigue escribiendo en español -es
donde está la línea editorial y donde se revisa cada frase- y lo único que se
traduce es lo que se va a oír.

**Se traduce ORACIÓN POR ORACIÓN y no el texto entero de un tirón**, y eso no
es un capricho: de cada oración sale un audio, y de la duración de ese audio
sale cuándo entra y cuándo sale su subtítulo en español. Si se tradujera todo
junto no habría forma de saber qué pedazo del audio corresponde a qué
subtítulo, y el texto iría por un lado y la voz por otro.

Pero las oraciones se mandan JUNTAS en una sola llamada, numeradas. Traducir
de a una pierde el contexto -una frase que empieza con «Eso» no se puede
traducir sin la anterior- y además cuesta una llamada por oración.

Lo traducido se guarda en disco: una tanda de reels del mismo capítulo no
vuelve a pagarlo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "traducciones"

API = "https://api.openai.com/v1/chat/completions"
MODELO = "gpt-4o-mini"

# Lo que importa del encargo, en orden de lo que más rompe el reel:
#
# 1. La MISMA cantidad de renglones. De cada uno sale un audio y un tiempo; si
#    vuelven cinco donde se mandaron seis, el subtítulo se corre y no hay
#    forma de arreglarlo después.
# 2. Que NO se alargue. El reel tiene un tope de 90 segundos y lo que se mide
#    para entrar es la voz. Una traducción explicativa se pasa.
# 3. El tono. Son aforismos, no un manual: frases cortas, directas, de alguien
#    que le cuenta algo a otro en voz baja.
ENCARGO = (
    "You translate Spanish to English for a short narrated video.\n"
    "Rules:\n"
    "1. Return EXACTLY one line per numbered input line, in the same order, "
    "numbered the same way. Never merge or split lines.\n"
    "2. Keep each line about as short as the Spanish. Do not explain, do not "
    "add words. A longer line makes the video overrun.\n"
    "3. Natural, idiomatic English. These are aphorisms about psychology and "
    "relationships: plain, direct, spoken to one person.\n"
    "4. Keep the punctuation that ends each line.\n"
    "Return only the numbered lines, nothing else."
)

NUMERADA = re.compile(r"^\s*(\d+)[.)]\s*(.+)$")


class TraducirError(RuntimeError):
    pass


def _llave(oraciones: List[str], modelo: str) -> str:
    crudo = "\n".join([modelo, ENCARGO] + list(oraciones))
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:32]


def guardada(oraciones: List[str], modelo: str = MODELO,
             cache: Optional[Path] = None) -> Optional[List[str]]:
    sitio = Path(cache or CACHE) / ("%s.json" % _llave(oraciones, modelo))
    if not sitio.exists() or sitio.stat().st_size == 0:
        return None
    try:
        datos = json.loads(sitio.read_text(encoding="utf-8"))
    except ValueError:
        return None
    # Una traducción con otra cantidad de renglones no sirve ni aunque esté
    # guardada: desincroniza el subtítulo.
    if len(datos) != len(oraciones):
        return None
    return datos


def _pedir(clave: str, cuerpo: dict) -> str:
    import requests
    try:
        r = requests.post(API, json=cuerpo, timeout=120,
                          headers={"Authorization": "Bearer %s" % clave})
    except requests.RequestException as e:
        raise TraducirError("no se pudo llegar a OpenAI: %s" % e)
    if r.status_code != 200:
        raise TraducirError("OpenAI contestó %d: %s" % (r.status_code, r.text[:200]))
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise TraducirError("no entendí la respuesta de OpenAI: %s" % e)


def _leer_numeradas(texto: str, cuantas: int) -> List[str]:
    """Las líneas numeradas de la respuesta, en orden.

    Se leen por su número y no por el orden en que vienen, porque un modelo
    que se saltea la 4 dejaría todo lo de abajo corrido un lugar, y eso en el
    reel se ve como un subtítulo que no corresponde a lo que se oye.
    """
    por_numero = {}
    for linea in texto.splitlines():
        m = NUMERADA.match(linea)
        if m:
            por_numero[int(m.group(1))] = m.group(2).strip()
    faltan = [i for i in range(1, cuantas + 1) if i not in por_numero]
    if faltan:
        raise TraducirError(
            "la traducción volvió incompleta: faltan %d de %d renglones (%s)"
            % (len(faltan), cuantas, ", ".join(str(x) for x in faltan[:5])))
    return [por_numero[i] for i in range(1, cuantas + 1)]


def a_ingles(oraciones: List[str], modelo: str = MODELO,
             cache: Optional[Path] = None, pedir=None) -> List[str]:
    """Las mismas oraciones en inglés, una por una y en el mismo orden."""
    oraciones = [" ".join(o.split()) for o in oraciones if o and o.strip()]
    if not oraciones:
        return []
    ya = guardada(oraciones, modelo, cache)
    if ya is not None:
        return ya
    clave = os.environ.get("OPENAI_API_KEY")
    if not clave:
        raise TraducirError("falta OPENAI_API_KEY en el .env")
    numeradas = "\n".join("%d. %s" % (i, o) for i, o in enumerate(oraciones, 1))
    pedir = pedir or _pedir
    contenido = pedir(clave, {
        "model": modelo,
        "messages": [{"role": "system", "content": ENCARGO},
                     {"role": "user", "content": numeradas}],
        "temperature": 0.3,
    })
    salida = _leer_numeradas(contenido, len(oraciones))
    sitio = Path(cache or CACHE) / ("%s.json" % _llave(oraciones, modelo))
    try:
        sitio.parent.mkdir(parents=True, exist_ok=True)
        tmp = sitio.with_suffix(".parcial")
        tmp.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
        tmp.replace(sitio)
    except OSError:
        # Que no se pueda guardar no puede tumbar un reel ya traducido.
        pass
    return salida
