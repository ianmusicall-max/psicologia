#!/usr/bin/env python3
"""Sube un reel ya armado a YouTube como Short.

    publicar_youtube.py                       sube data/reels/ultimo.mp4
    publicar_youtube.py data/reels/due-01.mp4
    publicar_youtube.py --ver                 dice que subiria, sin subir
    publicar_youtube.py --privado             sube sin que lo vea nadie

NO arma ningun reel y no gasta ni un centavo de API: sube el mp4 que ya esta
en disco. El titulo y la descripcion los arma `frases.para_youtube`, los
mismos que el comando del reel imprime.

De donde sale el texto: del id de la frase, que es el nombre del archivo
(`due-01.mp4` -> `due-01`). Con `--titulo` se le puede dar otro a mano.

**Lo que puede pasar y no es un error de esto**: hasta que Google audite el
proyecto, los videos que entran por la API quedan bloqueados en privado. La
subida sale bien igual, asi que el aviso lo dice explicitamente: un video que
no ve nadie se veria igual que uno publicado.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, frases, youtube  # noqa: E402

ULTIMO = ROOT / "data" / "reels" / "ultimo.mp4"


def texto_de(id_frase: str, capitulo: bool):
    """El titulo y la descripcion de esa frase, o None si no esta en el banco."""
    temas = frases.leer()
    frase = frases.por_id(temas, id_frase)
    if frase is None:
        return None
    tema = frases.tema_de(temas, frase)
    pagina = config.cargar()
    titulo, descripcion = frases.para_youtube(frase, tema, pagina,
                                              capitulo=capitulo)
    return titulo, descripcion, frases.hashtags(tema, pagina)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", nargs="?", default=str(ULTIMO))
    ap.add_argument("--id", help="id de la frase (por defecto, el nombre del archivo)")
    ap.add_argument("--capitulo", action="store_true",
                    help="el reel cubre el capitulo entero")
    ap.add_argument("--titulo")
    ap.add_argument("--descripcion")
    ap.add_argument("--privado", action="store_true",
                    help="lo sube sin que lo vea nadie")
    ap.add_argument("--ver", action="store_true", help="no sube nada")
    ap.add_argument("--otra-vez", action="store_true",
                    help="subirlo aunque ya este en YouTube")
    ap.add_argument("--agregar", metavar="VIDEO_ID",
                    help="solo meter en la lista un video que ya esta subido")
    ap.add_argument("--telegram", action="store_true", help="manda el enlace al chat")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")

    # Un video que ya esta arriba -los de antes de que la lista existiera-.
    if args.agregar:
        try:
            lista = youtube.agregar_a_playlist(args.agregar)
        except youtube.YoutubeError as e:
            print("No pude agregarlo: %s" % e)
            return 1
        print("Agregado a «%s»: %s" % (youtube.PLAYLIST,
                                       youtube.enlace_de_playlist(lista)))
        return 0

    ruta = Path(args.archivo)
    if not ruta.is_file():
        print("No existe %s" % ruta)
        print("Arma uno con: python3 scripts/reel.py --voz-eleven <voz>")
        return 1

    etiquetas = ()
    titulo, descripcion = args.titulo, args.descripcion
    if not (titulo and descripcion):
        # La ficha que dejo el comando del reel, si esta. Es la unica forma de
        # saber de que frase es `ultimo.mp4`, y ademas trae el texto tal como
        # se vio al armarlo.
        ficha = {} if args.id else youtube.ficha_guardada(ruta)
        if ficha:
            titulo = titulo or ficha["titulo"]
            descripcion = descripcion or ficha.get("descripcion") or ""
            etiquetas = ficha.get("etiquetas") or ()
        else:
            id_frase = args.id or ruta.stem
            armado = texto_de(id_frase, args.capitulo)
            if armado is None:
                print("No encuentro la frase %r en el banco ni una ficha al "
                      "lado del video." % id_frase)
                print("Pasale --id, o el titulo y la descripcion a mano con")
                print("--titulo y --descripcion.")
                return 2
            titulo = titulo or armado[0]
            descripcion = descripcion or armado[1]
            etiquetas = armado[2]

    privacidad = "private" if args.privado else "public"
    print("%s  (%.1f MB)" % (ruta, ruta.stat().st_size / 1048576.0))
    print()
    print("TITULO: %s" % titulo)
    print("DESCRIPCION:")
    for linea in descripcion.splitlines():
        print("   %s" % linea)
    print()
    print("Queda como: %s" % privacidad)

    if args.ver:
        print()
        print("Con --ver no subi nada.")
        return 0

    # YouTube no se da cuenta de que es el mismo video: dos corridas dejan dos
    # Shorts iguales en el canal, y cada subida gasta un sexto de la cuota del
    # dia. Paso el primer dia que esto se uso.
    if not args.otra_vez:
        antes = youtube.ya_subido(ruta)
        if antes:
            print()
            print("Este mismo video ya lo subiste el %s:" % (antes.get("cuando") or "?"))
            print("  %s" % youtube.enlace(antes.get("id", "")))
            print()
            print("No lo subo de nuevo. Si de verdad lo querés repetido,")
            print("agregale --otra-vez.")
            return 0

    falta = youtube.faltan()
    if falta:
        print()
        print("Falta %s en el .env." % ", ".join(falta))
        print("Corre: python3 scripts/youtube_token.py")
        return 1

    print()
    print("Subiendo...")
    try:
        r = youtube.publicar_short(ruta, titulo, descripcion, etiquetas,
                                   privacidad=privacidad)
    except youtube.YoutubeError as e:
        print("No pude subirlo: %s" % e)
        return 1

    if r.get("playlist"):
        print("En la lista «%s»: %s" % (youtube.PLAYLIST,
                                        youtube.enlace_de_playlist(r["playlist"])))
    elif r.get("playlist_error"):
        # El video SI salio: esto es un aviso, no un fallo.
        print("Subio, pero no pude meterlo en la lista: %s" % r["playlist_error"])

    enlace = youtube.enlace(r["id"])
    # Se anota ANTES de avisar: si el aviso falla, lo que no puede perderse es
    # la marca de que ya esta subido.
    youtube.anotar_subido(ruta, r["id"], titulo)
    print("Subido: %s" % enlace)
    print("Estado: %s" % youtube.como_quedo(r))

    aviso = ""
    if youtube.quedo_privado(r, privacidad):
        # Es la auditoria del proyecto, no la subida. Hay que decirlo con
        # todas las letras: la llamada salio bien y el video no lo ve nadie.
        aviso = ("Lo pedi publico y YouTube lo dejo PRIVADO. Es la auditoria "
                 "del proyecto que Google todavia no aprobo: el video esta "
                 "subido y no lo puede ver nadie mas que vos. Se arregla en "
                 "el panel de Google, no en el codigo.")
        print()
        print(aviso)

    if args.telegram:
        from src import telegram
        try:
            telegram.enviar("YouTube: %s\n%s%s"
                            % (titulo, enlace, "\n\n" + aviso if aviso else ""))
        except telegram.TelegramError as e:
            # Ya esta subido: que no se pueda avisar no lo deshace.
            print("No pude avisar al chat: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
