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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voces", default=",".join(CANDIDATAS),
                    help="cuales probar, separadas por coma")
    ap.add_argument("--texto", default=TEXTO, help="que lean")
    ap.add_argument("--ver", action="store_true", help="no pide nada ni gasta")
    ap.add_argument("--carpeta", default="data/voces_prueba")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    voces = [v.strip() for v in args.voces.split(",") if v.strip()]
    if not voces:
        print("No me dijiste ninguna voz.")
        return 2

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
