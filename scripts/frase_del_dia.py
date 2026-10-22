#!/usr/bin/env python3
"""La frase que toca: verla, dibujarla o publicarla.

    frase_del_dia.py                 muestra cuál toca y su caption, sin tocar nada
    frase_del_dia.py --dibujar       además deja el flyer en data/flyers/<id>.jpg
    frase_del_dia.py --publicar      dibuja, publica en la página y la anota como salida
    frase_del_dia.py --id ape-03     fuerza una frase en vez de la que toca

Cuál toca lo decide `frases.siguiente`: rota por tema y no repite hasta que
el banco entero haya salido. Publicar necesita PSI_FB_PAGE_ID y
PSI_FB_PAGE_TOKEN en el .env.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, diseno, frases  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="publicar esta frase en vez de la que toca")
    ap.add_argument("--dibujar", action="store_true", help="dejar el flyer en data/flyers")
    ap.add_argument("--publicar", action="store_true", help="publicar en Facebook y anotarla")
    ap.add_argument("--dia", help="fecha con la que se anota (YYYY-MM-DD), hoy si no")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    temas = frases.leer()
    problemas = frases.revisar(temas, pagina)
    if problemas:
        print("El banco tiene %d problemas; arréglalos antes de publicar (revisar_banco.py)." % len(problemas))
        for p in problemas[:10]:
            print("  -", p)
        return 2

    ya = frases.publicadas()
    if args.id:
        frase = frases.por_id(temas, args.id)
        if frase is None:
            print("No hay ninguna frase con id %s" % args.id)
            return 2
        if frase.id in ya:
            print("Ojo: %s ya salió el %s" % (frase.id, ya[frase.id]["dia"]))
    else:
        frase = frases.siguiente(temas, ya)
        if frase is None:
            print("El banco entero ya salió: %d frases. Toca escribir más." % len(frases.todas(temas)))
            return 1
    tema = frases.tema_de(temas, frase)
    texto = frases.caption(frase, tema, pagina)

    print("%s · capítulo %d, %s · quedan %d sin publicar"
          % (frase.id, tema.capitulo, tema.titulo, len(frases.todas(temas)) - len(ya)))
    print()
    print(texto)
    print()

    if not (args.dibujar or args.publicar):
        return 0
    ruta = diseno.dibujar(frase, tema, pagina)
    print("flyer:", ruta)
    if not args.publicar:
        return 0

    from src import facebook  # noqa: E402  (solo si hace falta: requests)
    dia = date.fromisoformat(args.dia) if args.dia else date.today()
    post_id = facebook.publicar(pagina, texto, ruta)
    frases.anotar_publicada(frase.id, dia, post_id, pagina.nombre)
    print("publicada: post %s, anotada para el %s" % (post_id, dia.isoformat()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
