#!/usr/bin/env python3
"""Publica la frase que toca, si a esta hora le toca. Pensado para correr cada hora.

    publicar_turno.py          publica si corresponde
    publicar_turno.py --ver    dice que haria, sin publicar

Las horas estan en `config/pagina.yaml`. Fuera de esas horas sale sin hacer
nada, asi que se puede correr cada hora sin pensar.

ES IDEMPOTENTE: si en esta hora ya salio un post, no publica otro. Sin eso,
dos corridas de la misma hora -un reintento, el reloj que se atrasa, dos
programadores encendidos- publicarian dos frases.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, diseno, frases  # noqa: E402


def ya_salio_en_esta_hora(ya: dict, ahora: datetime) -> bool:
    hoy = ahora.date().isoformat()
    return any(d.get("dia") == hoy and d.get("hora") == ahora.hour for d in ya.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", action="store_true", help="decir que haria, sin publicar")
    ap.add_argument("--ahora", help="fingir esta fecha y hora (YYYY-MM-DDTHH), para probar")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    ahora = datetime.fromisoformat(args.ahora) if args.ahora else datetime.now()

    if pagina.horas and ahora.hour not in pagina.horas:
        print("A las %02d no toca. Las horas son %s."
              % (ahora.hour, ", ".join("%02d" % h for h in pagina.horas)))
        return 0

    temas = frases.leer()
    problemas = frases.revisar(temas, pagina)
    if problemas:
        print("El banco tiene %d problemas; no publico. El primero: %s"
              % (len(problemas), problemas[0]))
        return 2

    ya = frases.publicadas()
    if ya_salio_en_esta_hora(ya, ahora):
        print("A las %02d de hoy ya salio un post. No publico otro." % ahora.hour)
        return 0

    frase = frases.siguiente(temas, ya)
    if frase is None:
        print("Ya salieron las %d frases del banco. Toca escribir mas."
              % len(frases.todas(temas)))
        return 1
    tema = frases.tema_de(temas, frase)
    estilo = (diseno.estilo_del_turno(ahora.date(), ahora.hour, pagina.horas)
              if pagina.rotar_estilos else None)
    texto = frases.caption(frase, tema, pagina)

    print("%s · %s · estilo %s · %02d h" % (frase.id, tema.tema, estilo or pagina.estilo, ahora.hour))
    if args.ver:
        return 0

    ruta = diseno.dibujar(frase, tema, pagina, estilo=estilo)
    if pagina.instagram:
        from src import instagram  # noqa: E402
        salida = instagram.publicar_las_dos(pagina, texto, ruta)
    else:
        from src import facebook  # noqa: E402
        salida = {"post_id": facebook.publicar(pagina, texto, ruta),
                  "instagram": "", "error_instagram": ""}

    frases.anotar_publicada(frase.id, ahora.date(), salida["post_id"], pagina.nombre, extra={
        "hora": ahora.hour, "tema": tema.tema, "eje": tema.eje,
        "estilo": estilo or pagina.estilo, "instagram": salida.get("instagram") or "",
    })
    print("publicada: %s" % salida["post_id"])
    if salida.get("error_instagram"):
        print("Instagram NO salio: %s" % salida["error_instagram"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
