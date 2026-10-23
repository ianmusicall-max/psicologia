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


# ---------------------------------------------------------------------------
# El informe, como texto.
#
# Vive acá y no en `scripts/medir.py` porque el botón del bot necesita el
# MISMO texto: el usuario no tiene terminal a mano -corre las cosas desde el
# teléfono- y el informe era la respuesta a «veamos cuál funciona mejor».
# Armarlo dos veces es como se descubre tarde que una de las dos copias quedó
# vieja; pasó en el repo de salud con los permisos y con la carpeta de turnos.
# ---------------------------------------------------------------------------

METRICAS = ("reacciones", "comentarios", "compartidos", "me_gusta", "comentarios_ig")


def _tabla(titulo: str, filas: List[dict], campo: str, metrica: str,
           con_dias: bool = False) -> List[str]:
    out = ["", titulo]
    datos = por(filas, campo, metrica)
    if not datos:
        return out + ["  (todavía no hay posts con ese dato)"]
    dias = dias_por(filas, campo) if con_dias else {}
    for valor, cuantos, med in datos:
        extra = "  %2d días" % dias.get(valor, 0) if con_dias else ""
        aviso = "" if alcanza(cuantos) else "   (pocos, no concluir)"
        out.append("  %-14s %3d posts%s   mediana %6.1f%s"
                   % (valor, cuantos, extra, med, aviso))
    return out


def informe(pagina: Pagina, salidos: Dict[str, dict], metrica: str = "reacciones",
            pedir_fb=None, pedir_ig=None) -> str:
    """Qué rindió cada modelo, eje, tema y hora. SOLO LEE.

    `salidos` son las publicadas que de verdad tienen post_id: una frase
    salteada no se mide porque no salió.
    """
    if not salidos:
        return ("Todavía no salió ningún post, así que no hay nada que medir.\n\n"
                "El informe compara por modelo, por eje, por tema y por hora, y "
                "con menos de %d posts por grupo avisa que no se puede concluir."
                % MINIMO)
    filas = juntar(pagina, salidos, pedir_fb=pedir_fb, pedir_ig=pedir_ig)
    medidos = [f for f in filas if metrica in f]
    if not medidos:
        return ("Hay %d posts publicados pero no pude leer los números de "
                "ninguno.\n\nCasi siempre es el token: tocame «¿Puedo "
                "publicar?» y mirá qué dice." % len(salidos))

    out = ["%d posts publicados. Medidos por %s." % (len(medidos), metrica)]
    out += _tabla("POR MODELO", medidos, "estilo", metrica, con_dias=True)
    out += _tabla("POR EJE (núcleo = los temas de la página)", medidos, "eje", metrica)
    out += _tabla("POR TEMA", medidos, "tema", metrica)
    out += _tabla("POR HORA", medidos, "hora", metrica)
    out += ["", "Mediana y no promedio: un post que se comparte de más tira el "
            "promedio de todo un grupo y hace parecer que ganó algo que no ganó."]
    if any(not alcanza(c) for _, c, _ in por(medidos, "estilo", metrica)):
        out.append("Con menos de %d posts por grupo todavía no hay nada que "
                   "concluir." % MINIMO)
    dias = dias_por(medidos, "estilo")
    if dias and min(dias.values()) < 3:
        out += ["", "La columna de días dice si un modelo vio días buenos y malos "
                "o se concentró en pocos. Con menos de tres días, lo que se está "
                "midiendo es todavía el día y no el modelo."]
    sin_datos = len(filas) - len(medidos)
    if sin_datos:
        out.append("")
        out.append("De %d posts no pude leer los números y quedaron afuera."
                   % sin_datos)
    return "\n".join(out)
