"""Cuánto rindió cada post, y agrupado por lo que lo distingue.

Lee los números de Facebook e Instagram y los cruza con lo que `publicadas.json`
guardó de cada post: el estilo, el tema, el eje y la hora. Esa unión es todo el
asunto; sin ella, los números de Facebook no se pueden atribuir a nada.

**Se usa la mediana y no el promedio.** Un post que se comparte de más tira el
promedio de todo un grupo y hace parecer que un estilo gana cuando lo que pasó
fue un solo post. La mediana no se mueve por un caso.
"""
from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional

from . import facebook
from .config import Pagina

# Por debajo de esto no se saca conclusión: se lista el número y se avisa.
MINIMO = 7


def numeros_de_facebook(pagina: Pagina, post_id: str) -> Dict[str, int]:
    """Reacciones, comentarios y veces compartido de un post de la página."""
    datos = facebook._leer(
        post_id, access_token=pagina.fb_token or "",
        fields="reactions.summary(total_count),comments.summary(total_count),shares")
    if "error" in datos:
        return {}
    def total(campo):
        return int(((datos.get(campo) or {}).get("summary") or {}).get("total_count") or 0)
    return {"reacciones": total("reactions"), "comentarios": total("comments"),
            "compartidos": int((datos.get("shares") or {}).get("count") or 0)}


def numeros_de_instagram(pagina: Pagina, media_id: str) -> Dict[str, int]:
    """Me gusta y comentarios de una publicación de Instagram.

    Se piden `like_count` y `comments_count`, que alcanzan con
    `instagram_basic`. Las estadísticas de alcance necesitan
    `instagram_manage_insights`, que el token no tiene y que no hace falta
    para comparar un estilo contra otro.
    """
    datos = facebook._leer(media_id, access_token=pagina.fb_token or "",
                           fields="like_count,comments_count")
    if "error" in datos:
        return {}
    return {"me_gusta": int(datos.get("like_count") or 0),
            "comentarios_ig": int(datos.get("comments_count") or 0)}


def juntar(pagina: Pagina, publicadas: Dict[str, dict],
           pedir_fb=None, pedir_ig=None) -> List[dict]:
    """Un renglón por post, con lo guardado y lo medido."""
    pedir_fb = pedir_fb or numeros_de_facebook
    pedir_ig = pedir_ig or numeros_de_instagram
    filas = []
    for fid, d in sorted(publicadas.items(), key=lambda kv: kv[1].get("dia") or ""):
        if not d.get("post_id"):
            continue                      # salteada: no salió, no se mide
        fila = {"id": fid, "dia": d.get("dia"), "hora": d.get("hora"),
                "tema": d.get("tema") or "", "eje": d.get("eje") or "",
                "estilo": d.get("estilo") or ""}
        fila.update(pedir_fb(pagina, d["post_id"]) or {})
        if d.get("instagram"):
            fila.update(pedir_ig(pagina, d["instagram"]) or {})
        filas.append(fila)
    return filas


def _mediana(valores: List[int]) -> float:
    return median(valores) if valores else 0.0


def por(filas: List[dict], campo: str, metrica: str = "reacciones") -> List[tuple]:
    """(valor, cuántos, mediana) ordenado de mejor a peor.

    Devuelve también cuántos posts tiene cada grupo, porque una mediana de
    dos posts no es una conclusión y el número es lo único que lo dice.
    """
    grupos: Dict[str, List[int]] = {}
    for f in filas:
        if f.get(campo) in (None, ""):
            continue
        grupos.setdefault(str(f[campo]), []).append(int(f.get(metrica) or 0))
    salida = [(k, len(v), _mediana(v)) for k, v in grupos.items()]
    salida.sort(key=lambda x: (-x[2], x[0]))
    return salida


def alcanza(cuantos: int) -> bool:
    return cuantos >= MINIMO


def dias_por(filas: List[dict], campo: str) -> Dict[str, int]:
    """Cuántos DÍAS distintos tiene cada grupo, no cuántos posts.

    Con el estilo rotando por día, los ocho posts de una jornada comparten
    todo lo que pasó ese día: la hora en que el algoritmo mostró la página,
    quién estaba conectado, si hubo un post que se compartió. Ocho posts de
    dos días no son dieciséis observaciones independientes: son dos.

    Por eso el informe cuenta los dos números. El que manda para concluir
    sobre el estilo es este.
    """
    dias: Dict[str, set] = {}
    for f in filas:
        if f.get(campo) in (None, ""):
            continue
        dias.setdefault(str(f[campo]), set()).add(f.get("dia"))
    return {k: len(v) for k, v in dias.items()}
