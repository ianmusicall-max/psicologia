"""Los siete textos de la semana, en primera persona.

Son otra cosa que las frases del banco y conviene tenerlo claro antes de
tocar nada. Una frase de `frases/` es una linea citable mas su reflexion, y la
usan el flyer, el capitulo del libro y el reel. Un texto de aca es un monologo
de una pieza: no se cita, no se parte, no entra en un flyer, y habla en
primera persona. Por eso vive en su propia carpeta y no en `frases/`, que
`frases.leer()` lee entera.

Lo que los ata al libro es `capitulo`: cada texto sale de un capitulo escrito,
asi que quien llega por el reel encuentra adentro, desarrollado, lo que oyo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
ARCHIVO = ROOT / "textos" / "semana.yaml"

# En el orden de `date.weekday()`: 0 es lunes. Sin tildes a proposito, que es
# como se escriben los `id` y como se teclean en la linea de comandos.
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


class SemanaError(Exception):
    pass


@dataclass(frozen=True)
class Texto:
    id: str
    dia: str
    capitulo: str
    titulo: str
    texto: str


def leer(archivo: Optional[Path] = None) -> List[Texto]:
    """Los textos del archivo, en el orden en que estan escritos."""
    ruta = Path(archivo) if archivo else ARCHIVO
    if not ruta.exists():
        return []
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or []
    salida = []
    for d in datos:
        faltan = [c for c in ("id", "dia", "capitulo", "titulo", "texto") if not d.get(c)]
        if faltan:
            raise SemanaError("al texto %r le faltan: %s"
                              % (d.get("id", "?"), ", ".join(faltan)))
        salida.append(Texto(id=str(d["id"]), dia=str(d["dia"]),
                            capitulo=str(d["capitulo"]), titulo=str(d["titulo"]),
                            texto=" ".join(str(d["texto"]).split())))
    return salida


def por_id(ident: str, textos: Optional[List[Texto]] = None) -> Optional[Texto]:
    for t in (textos if textos is not None else leer()):
        if t.id == ident:
            return t
    return None


def del_dia(dia: Optional[date] = None, textos: Optional[List[Texto]] = None) -> Optional[Texto]:
    """El texto que le toca a ese dia de la semana.

    Por `weekday()` y no por el orden del archivo: asi el lunes sale el del
    lunes aunque alguien reordene las lineas, que es lo que de verdad se pide
    cuando se dice «uno por dia».
    """
    cual = DIAS[(dia or date.today()).weekday()]
    for t in (textos if textos is not None else leer()):
        if t.dia == cual:
            return t
    return None
