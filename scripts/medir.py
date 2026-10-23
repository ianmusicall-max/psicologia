#!/usr/bin/env python3
"""Que rindio cada cosa: por estilo, por tema, por eje y por hora.

    medir.py                 el informe
    medir.py --metrica comentarios

SOLO LEE. Pregunta los numeros a Facebook y a Instagram y los cruza con lo
que quedo guardado de cada post.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, frases, medir  # noqa: E402


def tabla(titulo: str, filas, campo: str, metrica: str, con_dias: bool = False) -> None:
    print()
    print(titulo)
    datos = medir.por(filas, campo, metrica)
    if not datos:
        print("  (todavia no hay posts con ese dato)")
        return
    dias = medir.dias_por(filas, campo) if con_dias else {}
    for valor, cuantos, mediana in datos:
        extra = "  %2d dias" % dias.get(valor, 0) if con_dias else ""
        aviso = "" if medir.alcanza(cuantos) else "   (pocos, no concluir)"
        print("  %-14s %3d posts%s   mediana %6.1f%s"
              % (valor, cuantos, extra, mediana, aviso))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrica", default="reacciones",
                    help="reacciones, comentarios, compartidos, me_gusta, comentarios_ig")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    ya = frases.publicadas()
    salidos = {k: v for k, v in ya.items() if v.get("post_id")}
    if not salidos:
        print("Todavia no salio ningun post.")
        return 1

    print("%d posts publicados. Midiendo por %s." % (len(salidos), args.metrica))
    filas = medir.juntar(pagina, salidos)
    medidos = [f for f in filas if args.metrica in f]
    if not medidos:
        print()
        print("No pude leer los numeros de ninguno. Revisa el token con "
              "scripts/revisar_token.py")
        return 1

    tabla("POR ESTILO", medidos, "estilo", args.metrica, con_dias=True)
    tabla("POR EJE (nucleo = los temas de la pagina)", medidos, "eje", args.metrica)
    tabla("POR TEMA", medidos, "tema", args.metrica)
    tabla("POR HORA", medidos, "hora", args.metrica)

    print()
    print("Mediana y no promedio: un post que se comparte de mas tira el promedio")
    print("de todo un grupo y hace parecer que gana algo que no gano.")
    pocos = [g for g in medir.por(medidos, "estilo", args.metrica) if not medir.alcanza(g[1])]
    if pocos:
        print("Con menos de %d posts por grupo todavia no hay nada que concluir."
              % medir.MINIMO)
    dias = medir.dias_por(medidos, "estilo")
    if dias and min(dias.values()) < 3:
        print()
        print("OJO CON LA COLUMNA DE DIAS: el estilo rota por dia, asi que los ocho")
        print("posts de una jornada comparten todo lo que paso ese dia. Un estilo con")
        print("dos dias tiene dos observaciones, no dieciseis. Para leer el estilo")
        print("hacen falta tres o cuatro dias de cada uno, o sea catorce dias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
