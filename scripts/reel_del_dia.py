#!/usr/bin/env python3
"""Arma el reel del dia y lo publica en Facebook, Instagram y YouTube.

    reel_del_dia.py                  arma uno y lo publica en las tres
    reel_del_dia.py --ver            dice que haria, sin armar ni publicar
    reel_del_dia.py --video X.mp4    publica uno que ya esta armado
    reel_del_dia.py --sin-youtube    saltea una plataforma

Es UN solo camino con dos disparadores: el turno de las 18 y el boton del bot.
Si cada uno hiciera lo suyo, el dia que esto cambie se arregla uno y el otro
se queda con la forma vieja.

**Una plataforma que falla no se lleva a las demas.** Cada una va en su propio
intento y el aviso dice cual salio y cual no: un token vencido de Facebook no
puede dejar el reel sin subir a YouTube, donde el permiso esta bien.

El texto no se escribe aca: sale de la ficha que `reel.py` deja al lado del
mp4 (de que frase es) y de `frases`, igual que un post cualquiera. Para
Facebook e Instagram es el caption de siempre; para YouTube, el titulo y la
descripcion de `frases.para_youtube`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, diario, frases, video, youtube  # noqa: E402

# Como se arma el reel del dia. Son los mismos argumentos que se venian
# pasando a mano desde la pestania Actions, escritos una sola vez.
COMO = ["--voz-eleven", video.VOZ_ELEVEN, "--ingles", "--musica"]

# Los clips de fondo, si los hay. Sin ellos el reel sale sobre el papel de la
# marca, que no depende de nada: un fondo que falta no puede perder el turno.
FONDOS = ROOT / "data" / "fondos"
CLIPS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")

PLATAFORMAS = ("facebook", "instagram", "youtube")


def hay_clips(carpeta: Path = FONDOS) -> bool:
    """Si hay VIDEOS, no si hay archivos.

    Con «la carpeta no esta vacia» alcanzaba un LEEME.md para que `reel.py`
    abortara con «no hay ningun video»: el reel se perderia por un archivo de
    texto.
    """
    return any(x.is_file() and x.suffix.lower() in CLIPS
               for x in carpeta.iterdir()) if carpeta.is_dir() else False


def armar(tema: str = "", carpeta: Path = None) -> Path:
    """Arma el reel y devuelve donde quedo. Levanta si no se pudo."""
    from scripts import reel  # noqa: F401  (se importa tarde: tarda)
    argv = list(COMO) + ["--carpeta", str(carpeta or video.REELS)]
    if tema:
        argv += ["--tema", tema]
    if hay_clips():
        argv += ["--fondo", str(FONDOS)]
    reel.ULTIMO = None
    salida = reel.main(argv)
    if salida != 0 or not reel.ULTIMO:
        raise RuntimeError("no se pudo armar el reel (salida %s)" % salida)
    return Path(reel.ULTIMO)


def textos_de(ruta: Path):
    """El caption de Meta y el titulo y la descripcion de YouTube.

    Salen de la ficha que dejo `reel.py` -que dice de que frase es el video- y
    del banco. Si la ficha no esta, no se inventa nada: sin saber de que frase
    es, el caption seria de otra.
    """
    ficha = youtube.ficha_guardada(ruta)
    if not ficha:
        raise RuntimeError("no encuentro la ficha de %s: no se de que frase es"
                           % ruta.name)
    temas = frases.leer()
    frase = frases.por_id(temas, ficha.get("frase") or "")
    if frase is None:
        raise RuntimeError("la ficha dice %r y esa frase no esta en el banco"
                           % ficha.get("frase"))
    tema = frases.tema_de(temas, frase)
    pagina = config.cargar()
    return (frases.caption(frase, tema, pagina), ficha["titulo"],
            ficha.get("descripcion") or "", ficha.get("etiquetas") or [])


def publicar(ruta: Path, caption: str, titulo: str, descripcion: str,
             etiquetas, donde=PLATAFORMAS) -> dict:
    """Publica en cada una. Devuelve {plataforma: enlace o 'error: ...'}.

    Cada una en su propio intento, a proposito: un token vencido de Facebook
    no puede dejar el reel sin subir a YouTube.
    """
    pagina = config.cargar()
    salidas = {}

    if "facebook" in donde:
        from src import facebook
        try:
            ident = facebook.publicar_reel(pagina, ruta, caption)
            salidas["facebook"] = facebook.enlace_de_reel(ident)
        except Exception as e:                            # noqa: BLE001
            salidas["facebook"] = "error: %s" % e

    if "instagram" in donde:
        from src import instagram
        try:
            ident = instagram.publicar_reel(pagina, caption, ruta)
            salidas["instagram"] = "https://www.instagram.com/reel/%s" % ident
        except Exception as e:                            # noqa: BLE001
            salidas["instagram"] = "error: %s" % e

    if "youtube" in donde:
        try:
            antes = youtube.ya_subido(ruta)
            if antes:
                salidas["youtube"] = youtube.enlace(antes.get("id", ""))
            else:
                r = youtube.publicar_short(ruta, titulo, descripcion, etiquetas)
                youtube.anotar_subido(ruta, r["id"], titulo)
                enlace = youtube.enlace(r["id"])
                if youtube.quedo_privado(r):
                    enlace += "  (quedo PRIVADO: auditoria de Google)"
                if r.get("playlist_error"):
                    # El video salio igual: esto es un aviso, no un fallo.
                    enlace += "  (no entro en la lista: %s)" % r["playlist_error"]
                salidas["youtube"] = enlace
        except Exception as e:                            # noqa: BLE001
            salidas["youtube"] = "error: %s" % e
    return salidas


def probar(donde=PLATAFORMAS) -> dict:
    """Pregunta si las tres credenciales andan, sin publicar ni gastar nada.

    Existe porque el turno corre una vez por dia: sin esto, que falte un
    secreto se descubre a las 18, con el reel ya armado y pago. Las tres
    preguntas son de solo lectura y ninguna cuesta un centavo.
    """
    pagina = config.cargar()
    estado = {}
    if "facebook" in donde:
        from src import facebook
        r = facebook._leer("me", fields="id,name",
                           access_token=pagina.fb_token or "")
        estado["facebook"] = (r.get("name")
                              or facebook.sin_token(
                                  "error: %s" % ((r.get("error") or {}).get("message")
                                                 or "sin token")))
    if "instagram" in donde:
        from src import instagram
        c = instagram.cuenta_vinculada(pagina)
        from src import facebook as _fb
        estado["instagram"] = ("@%s" % c["usuario"] if c.get("usuario")
                               else _fb.sin_token("error: %s"
                                                  % (c.get("error") or "sin cuenta vinculada")))
    if "youtube" in donde:
        try:
            youtube.acceso()
            estado["youtube"] = "el permiso anda"
        except Exception as e:                            # noqa: BLE001
            estado["youtube"] = "error: %s" % e
    return estado


def aviso(ruta: Path, titulo: str, salidas: dict) -> str:
    lineas = ["Reel del dia: %s" % titulo, ""]
    for cual in PLATAFORMAS:
        if cual in salidas:
            lineas.append("%s: %s" % (cual.capitalize(), salidas[cual]))
    return "\n".join(lineas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", help="publicar uno ya armado en vez de armar")
    ap.add_argument("--tema", help="el capitulo entero en vez de la frase que toca")
    ap.add_argument("--ver", action="store_true", help="no arma ni publica")
    ap.add_argument("--probar", action="store_true",
                    help="comprobar las credenciales de las tres. No publica")
    ap.add_argument("--otra-vez", action="store_true",
                    help="armar otro aunque hoy ya haya salido uno")
    for cual in PLATAFORMAS:
        ap.add_argument("--sin-%s" % cual, action="store_true",
                        help="no publicar en %s" % cual)
    ap.add_argument("--carpeta", default=str(video.REELS))
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    donde = [c for c in PLATAFORMAS if not getattr(args, "sin_%s" % c)]
    if not donde:
        print("No queda ninguna plataforma donde publicar.")
        return 2

    if args.probar:
        estado = probar(donde)
        print("Las credenciales, una por una:")
        for cual in PLATAFORMAS:
            if cual in estado:
                print("  %-10s %s" % (cual, estado[cual]))
        mal = [c for c, v in estado.items() if v.startswith("error:")]
        print()
        print("Falta arreglar: %s" % ", ".join(mal) if mal
              else "Las tres estan en condiciones.")
        _avisar("Credenciales del reel:\n" +
                "\n".join("%s: %s" % (c, estado[c]) for c in PLATAFORMAS if c in estado))
        return 1 if mal else 0

    if args.ver:
        print("Armaria un reel con: %s" % " ".join(COMO))
        print("Fondo: %s" % ("los clips de data/fondos" if hay_clips()
                             else "el papel de la marca (no hay clips)"))
        print("Lo publicaria en: %s" % ", ".join(donde))
        print("Con --ver no hice nada.")
        return 0

    # El segundo intento del turno no vuelve a armar nada. Sin esto, cada
    # intento son unos centavos de voz y de fotos, y dos reels el mismo dia.
    if not args.otra_vez and not args.video:
        antes = diario.ya_salio_hoy()
        if antes:
            print("Hoy ya salio el reel: %s" % (antes.get("titulo") or "?"))
            for cual, donde in (antes.get("salidas") or {}).items():
                print("  %s: %s" % (cual, donde))
            print("No armo otro. Si de verdad queres uno mas, --otra-vez.")
            return 0

    # Una corrida a la vez. Dos toques seguidos del boton del bot armarian dos
    # reels: el primero todavia no termino, asi que la guarda del dia no sabe
    # nada todavia.
    if not diario.tomar():
        print("Ya hay una corrida armando el reel. No largo otra.")
        return 0
    try:
        return _trabajar(args, donde)
    finally:
        diario.soltar()


def _trabajar(args, donde) -> int:
    if args.video:
        ruta = Path(args.video)
        if not ruta.is_file():
            print("No existe %s" % ruta)
            return 1
    else:
        try:
            ruta = armar(args.tema or "", Path(args.carpeta))
        except Exception as e:                            # noqa: BLE001
            print("No pude armar el reel: %s" % e)
            _avisar("No pude armar el reel del dia: %s" % e)
            return 1

    try:
        caption, titulo, descripcion, etiquetas = textos_de(ruta)
    except Exception as e:                                # noqa: BLE001
        print("No pude armar el texto: %s" % e)
        _avisar("El reel se armo pero no pude armar su texto: %s" % e)
        return 1

    salidas = publicar(ruta, caption, titulo, descripcion, etiquetas, donde)
    # Se anota ANTES de avisar: si el aviso falla, lo que no puede perderse es
    # la marca de que hoy ya salio -o el proximo intento arma otro-.
    diario.anotar(ruta, titulo, salidas)
    texto = aviso(ruta, titulo, salidas)
    print()
    print(texto)
    _avisar(texto)
    # Que una plataforma falle no es un fallo del turno: las otras salieron.
    return 0 if any(not v.startswith("error:") for v in salidas.values()) else 1


def _avisar(texto: str) -> None:
    """Manda el aviso y se traga su propio error: el reel ya esta publicado."""
    try:
        from src import telegram
        telegram.enviar(texto)
    except Exception as e:                                # noqa: BLE001
        print("(no pude avisar al chat: %s)" % e)


if __name__ == "__main__":
    sys.exit(main())
