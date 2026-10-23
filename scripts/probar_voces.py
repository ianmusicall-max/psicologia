#!/usr/bin/env python3
"""Lee la MISMA frase con varias voces y te las manda al chat para elegir.

    probar_voces.py                      las cinco candidatas
    probar_voces.py --voces onyx,ash
    probar_voces.py --texto "Otra frase"
    probar_voces.py --ver                dice que haria, sin pedir ni gastar

Existe porque "que se parezca a la voz de la referencia" no lo puede decidir
quien escribe el codigo: hay que oirlas. Antes la unica forma de comparar era
armar el reel entero con cada una -tres minutos y el capitulo completo de
voz cada vez-; aca son unos 180 caracteres por voz.

La frase es la MISMA para todas a proposito: si cada una leyera algo distinto,
lo que se compara es el texto y no la voz.

SOLO PIDE AUDIO Y LO MANDA AL CHAT. No publica nada ni toca el banco.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import video  # noqa: E402

# Las de OpenAI que son de hombre y graves, que es lo que mide la referencia.
# `onyx` es la que esta puesta hoy. No estan todas las del modelo: una voz
# aguda no se parece a la referencia y escucharla es perder el tiempo.
CANDIDATAS = ("onyx", "ash", "ballad", "verse", "echo")

# Corta y con un punto en el medio, para que se oiga como marca las pausas,
# que es la mitad de lo que distingue una voz de otra en este formato.
TEXTO = ("El valor de una persona no se gana ni se pierde: se reconoce. "
         "Y lo que te dices cuando fallas, casi siempre alguien te lo dijo "
         "primero.")


def probar_colores(args, voz: str) -> int:
    """La MISMA voz con varios procesados, para elegir el timbre.

    Separado de probar voces porque es otra pregunta: alla se compara QUIEN
    lee, aca COMO suena. Y porque el audio se pide UNA sola vez y se procesa
    cuatro: las versiones no cuestan nada, solo la primera.

    Se nivelan todas con `loudnorm`. Sin eso gana la mas fuerte y no la que
    mejor suena, que es el error clasico al comparar procesados de audio.
    """
    colores = [c.strip() for c in args.colores.split(",") if c.strip()]
    # Se comprueban TODOS antes de pedir nada: un nombre mal escrito al final
    # de la lista no puede descubrirse despues de haber pagado la voz.
    for c in colores:
        try:
            video.filtro_de_color(c)
        except video.VideoError as e:
            print(e)
            return 2
    carpeta = Path(args.carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    print("La voz %s con %d procesados: %s" % (voz, len(colores), ", ".join(colores)))
    print("La frase: %s" % args.texto)
    print("Se pide UNA vez; los procesados no cuestan nada.")
    if args.ver:
        print()
        print("Con --ver no pedi ni mande nada.")
        return 0

    try:
        crudo = video.decir_con_ia(args.texto, carpeta / ("color-%s.mp3" % voz), voz)
    except video.VideoError as e:
        print("No pude pedir la voz: %s" % e)
        return 1

    from src import telegram
    mandadas = 0
    for c in colores:
        salida = carpeta / ("color-%s-%s.m4a" % (voz, c))
        filtro = video.filtro_de_color(c)
        # `loudnorm` SIEMPRE, incluso en «nada»: si solo lo llevaran los
        # procesados, la comparacion mediria el nivelado y no el color.
        cadena = "%s,loudnorm=%s" % (filtro, video.SONORIDAD) if filtro \
            else "loudnorm=%s" % video.SONORIDAD
        try:
            video._correr([video.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                           "-i", str(crudo), "-af", cadena, str(salida)],
                          "colorear la voz")
        except video.VideoError as e:
            print("  %-8s no pude: %s" % (c, e))
            continue
        print("  %-8s %s" % (c, salida))
        if not telegram.configurado():
            continue
        try:
            telegram.enviar_audio(salida, "voz %s · procesado: %s" % (voz, c))
            mandadas += 1
        except telegram.TelegramError as e:
            print("  no pude mandarla al chat: %s" % e)
    if telegram.configurado() and mandadas:
        print()
        print("Mande %d al chat." % mandadas)
        telegram.enviar(
            "Es la MISMA voz (%s) con cuatro procesados distintos, todas al "
            "mismo volumen para que compares el timbre y no el nivel. "
            "Decime cual se acerca mas a la del reel de referencia." % voz)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voces", default=",".join(CANDIDATAS),
                    help="cuales probar, separadas por coma")
    ap.add_argument("--colores", default=None, metavar="LISTA",
                    help="en vez de varias voces, UNA voz con varios procesados "
                         "(ej: nada,calida,cine,honda)")
    ap.add_argument("--texto", default=TEXTO, help="que lean")
    ap.add_argument("--ver", action="store_true", help="no pide nada ni gasta")
    ap.add_argument("--carpeta", default="data/voces_prueba")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    voces = [v.strip() for v in args.voces.split(",") if v.strip()]
    if not voces:
        print("No me dijiste ninguna voz.")
        return 2

    if args.colores:
        return probar_colores(args, voces[0])

    carpeta = Path(args.carpeta)
    print("%d voces x %d caracteres = %d caracteres en total."
          % (len(voces), len(args.texto), len(voces) * len(args.texto)))
    print("La frase: %s" % args.texto)
    print()
    for v in voces:
        esta = video.en_cache(args.texto, v)
        print("  %-8s %s" % (v, "ya esta en la cache" if esta else "hay que pedirla"))
    if args.ver:
        print()
        print("Con --ver no pedi ni mande nada.")
        return 0

    carpeta.mkdir(parents=True, exist_ok=True)
    from src import telegram
    mandadas = 0
    for v in voces:
        print()
        print("Pidiendo %s..." % v)
        try:
            ruta = video.decir_con_ia(args.texto, carpeta / ("prueba-%s.mp3" % v), v)
        except video.VideoError as e:
            # Una voz que no existe no puede llevarse las demas: el valor de
            # esto es comparar, y con cuatro de cinco todavia se compara.
            print("  no pude: %s" % e)
            continue
        print("  %s" % ruta)
        if not telegram.configurado():
            continue
        try:
            telegram.enviar_audio(ruta, "voz %s" % v)
            mandadas += 1
        except telegram.TelegramError as e:
            print("  no pude mandarla al chat: %s" % e)
    if telegram.configurado():
        print()
        print("Mande %d al chat." % mandadas)
        if mandadas:
            telegram.enviar(
                "Esas son las voces. Decime cual se parece mas a la del reel "
                "de referencia y la dejo puesta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
