"""Cuántos posts salen cada día y a qué horas.

El ritmo sube por etapas y después queda fijo. La rampa está en
`config/pagina.yaml` y se cuenta desde el primer día que se publicó, no desde
una fecha escrita a mano: así empieza sola el día que arranca la prueba y no
hay que acordarse de cambiar nada.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from .config import Pagina


def dia_de_la_prueba(desde: Optional[date], hoy: date) -> int:
    """Qué número de día es hoy. El primero es 1."""
    if desde is None:
        return 1
    return max(1, hoy.toordinal() - desde.toordinal() + 1)


def posts_del_dia(pagina: Pagina, desde: Optional[date], hoy: date) -> int:
    """Cuántos posts salen ese día, según la rampa."""
    n = dia_de_la_prueba(desde, hoy)
    acumulado = 0
    for etapa in pagina.arranque:
        acumulado += int(etapa.get("dias") or 0)
        if n <= acumulado:
            return int(etapa.get("posts") or 0)
    return pagina.posts_por_dia


def horas_del_dia(pagina: Pagina, desde: Optional[date], hoy: date) -> List[int]:
    """Las horas de ese día, repartidas parejo sobre la parrilla completa.

    No son las primeras N de la lista: con cuatro posts, las primeras cuatro
    los dejarían todos antes del mediodía y la tarde vacía. Se toman N
    posiciones repartidas a lo largo del día.
    """
    cuantos = posts_del_dia(pagina, desde, hoy)
    horas = sorted(pagina.horas)
    if not horas or cuantos <= 0:
        return []
    if cuantos >= len(horas):
        return horas
    elegidas = []
    for i in range(cuantos):
        lugar = min(len(horas) - 1, int(round(i * len(horas) / cuantos)))
        if horas[lugar] not in elegidas:
            elegidas.append(horas[lugar])
    return elegidas


def toca(pagina: Pagina, desde: Optional[date], ahora_dia: date, hora: int) -> bool:
    return hora in horas_del_dia(pagina, desde, ahora_dia)


def calendario(pagina: Pagina, desde: date, cuantas_frases: int, tope: int = 40) -> List[dict]:
    """Día por día hasta que se agota el banco.

    Sirve para ver la rampa entera antes de encenderla: cuántos salen cada
    día y qué día se termina el banco. Sin esto, que el banco se agote se
    descubre el día que el bot dice que no quedan frases.
    """
    filas, quedan = [], cuantas_frases
    for i in range(tope):
        dia = date.fromordinal(desde.toordinal() + i)
        salen = min(posts_del_dia(pagina, desde, dia), quedan)
        if salen <= 0:
            break
        quedan -= salen
        filas.append({"dia": dia, "numero": i + 1, "posts": salen,
                      "horas": horas_del_dia(pagina, desde, dia)[:salen], "quedan": quedan})
        if quedan <= 0:
            break
    return filas
