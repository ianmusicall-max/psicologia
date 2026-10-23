#!/usr/bin/env python3
"""El reel: vertical, el texto renglon a renglon sobre un fondo.

    reel.py                      la frase que toca, sin voz, sobre el papel
    reel.py --id aut-01          esa frase
    reel.py --tema autoestima    el CAPITULO entero: un reel de un minuto
    reel.py --fondo data/fondos  un clip de naturaleza (o una carpeta con varios)
    reel.py --voz mi-voz.m4a     tu voz grabada leyendo el texto
    reel.py --voz-mac            la voz de la Mac (`say`), renglon por renglon
    reel.py --voz-ia             la voz de IA de OpenAI: es la UNICA llamada paga
    reel.py --musica             la cama que trae el repo, bien abajo si hay voz
    reel.py --musica otra.mp3    la tuya
    reel.py --telegram           ademas te lo manda al chat
    reel.py --ver                dice que haria, sin armar nada

UNA FRASE SON UNOS 30 SEGUNDOS HABLADOS y no llega al minuto por mas que se
alargue. Para un minuto va `--tema`: la tesis del capitulo y las frases que
entren, que es texto ya escrito y ya validado, y ademas ordenado -la tesis
presenta el asunto y cada frase lo desarrolla-.

NO PUBLICA NADA. Deja el mp4 en data/reels y lo subis vos, o lo mandas por
Telegram para mirarlo en el telefono.

La voz es lo unico que hay que decidir: tu voz grabada es gratis y es la que
mejor suena; `say` es gratis y suena sintetico; sin voz el reel sale mudo y se
lee igual. `--voz-mac` lee RENGLON POR RENGLON, asi que el subtitulo cae
exacto donde se lo dice; con un audio entero el tiempo se reparte proporcional
al largo de cada renglon, que es lo mas cerca que se puede estar sin tener los
tiempos palabra por palabra.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, frases, traducir, video  # noqa: E402

CLIPS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def elegir_fondo(donde: str, semilla: str) -> list:
    """Los clips del fondo, en el orden en que se van a turnar.

    Varios y no uno: la referencia que mando el usuario va cortando entre
    clips cada pocos segundos, y es buena parte de por que no se hace larga.

    El orden sale de una semilla que es el id de la frase y no del azar: asi
    volver a armar el mismo reel da el mismo video -el que aprobaste es el que
    sale- y dos frases seguidas no arrancan con el mismo clip.
    """
    ruta = Path(donde)
    if ruta.is_file():
        return [ruta]
    if not ruta.is_dir():
        raise SystemExit("No encuentro %s" % ruta)
    clips = sorted(x for x in ruta.iterdir() if x.suffix.lower() in CLIPS)
    if not clips:
        raise SystemExit("En %s no hay ningun video (%s)" % (ruta, ", ".join(CLIPS)))
    random.Random(semilla).shuffle(clips)
    return clips


def buscar_musica(cual: str) -> Path:
    """Un archivo, o el nombre de una de las que trae el repo.

    Las del repo estan generadas con ffmpeg y son originales. Una pista con
    derechos le hace perder alcance a TODA la cuenta, no solo a ese post, asi
    que lo que viene incluido no puede ser de nadie mas.
    """
    ruta = Path(cual)
    if ruta.is_file():
        return ruta
    propia = Path(video.MUSICA).parent / ("%s.m4a" % cual)
    if propia.is_file():
        return propia
    hay = sorted(x.stem for x in Path(video.MUSICA).parent.glob("*.m4a"))
    raise SystemExit("No encuentro la musica %r. Las que trae el repo: %s"
                     % (cual, ", ".join(hay) or "ninguna"))


def buscar_tema(temas, cual: str):
    """Por nombre («autoestima») o por numero de capitulo («3»)."""
    cual = (cual or "").strip().lower()
    for t in temas:
        if t.tema.lower() == cual or str(t.capitulo) == cual:
            return t
    return None


def contar_lo_que_tardo(unidades, duraciones) -> float:
    """Cuanto tardo la voz de verdad contra lo que se habia calculado.

    Es la unica forma de corregir `video.VOZ_MAS_LENTA` con datos en vez de
    con una corazonada: ese numero sale de UNA medicion, y de el depende que
    un capitulo entre o no en el tope de Facebook. Sin esto, el unico aviso
    de que se quedo corto es un reel que no se puede publicar DESPUES de
    haber pagado la voz.
    """
    leido = video.duracion_del_guion(unidades)
    real = sum(duraciones) + video.COLA
    # El factor se despeja de la MISMA cuenta que hace el codigo
    # -`duracion_del_guion` por el factor-, asi que el numero que sale es el
    # que habria acertado. Dividir solo por el cuerpo y dejar la cola arriba
    # lo infla.
    factor = real / leido if leido else 0.0
    print()
    print("Calculado %.0f s, la voz tardo %.0f. El factor real es %.2f "
          "(en el codigo, %.2f)." % (leido * video.VOZ_MAS_LENTA, real,
                                     factor, video.VOZ_MAS_LENTA))
    if factor > video.VOZ_MAS_LENTA:
        # No es un detalle: con el factor corto, el calculo dice que entra y
        # la voz se pasa. Hay que subir la constante, no el margen.
        print("OJO: la voz tardo MAS de lo calculado. Subi "
              "video.VOZ_MAS_LENTA a %.2f o mas." % (factor + 0.03))
    return factor


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="que frase")
    ap.add_argument("--tema", help="el capitulo entero, por nombre o por numero")
    ap.add_argument("--objetivo", type=float, default=video.OBJETIVO,
                    metavar="SEG",
                    help="con --tema, el minimo que se busca (leido, no hablado); "
                         "el maximo lo pone el tope de Facebook")
    ap.add_argument("--desde", type=int, default=0,
                    help="con --tema, desde que frase del capitulo empezar")
    ap.add_argument("--color", default=None, metavar="CUAL",
                    help="como suena la voz: nada, calida, cine, honda")
    ap.add_argument("--ingles", action="store_true",
                    help="la VOZ en ingles y los SUBTITULOS en espanol")
    ap.add_argument("--musica", nargs="?", const="calma", default=None,
                    metavar="ARCHIVO",
                    help="musica de fondo; sin nombre usa la que trae el repo")
    ap.add_argument("--voz-ia", nargs="?", const=video.VOZ_IA, default=None,
                    metavar="VOZ", help="voz de OpenAI (onyx, ash, sage...). CUESTA")
    ap.add_argument("--fondo", help="un clip o una carpeta con clips")
    ap.add_argument("--voz", help="un audio tuyo leyendo el texto")
    ap.add_argument("--voz-mac", nargs="?", const="", default=None, metavar="VOZ",
                    help="usar `say`; sin nombre elige la mejor en espanol que tengas")
    ap.add_argument("--voz-eleven", nargs="?", const=video.VOZ_ELEVEN, default=None,
                    metavar="ID", help="voz de ElevenLabs (el id, o vacio para la "
                                       "elegida por defecto). CUESTA")
    ap.add_argument("--ver", action="store_true", help="decir que haria, sin armar")
    ap.add_argument("--carpeta", default=str(video.REELS))
    ap.add_argument("--telegram", action="store_true",
                    help="mandar el reel al chat cuando este listo")
    args = ap.parse_args(argv)

    # Sin esto, OPENAI_API_KEY del .env no se lee nunca y `--voz-ia` dice que
    # falta la clave aunque esté puesta.
    load_dotenv(ROOT / ".env")
    if args.color is not None:
        try:
            video.filtro_de_color(args.color)
        except video.VideoError as e:
            print(e)
            return 2
    pagina = config.cargar()
    temas = frases.leer()
    ya = frases.publicadas()
    carpeta = Path(args.carpeta)

    if args.tema:
        tema = buscar_tema(temas, args.tema)
        if tema is None:
            print("No encuentro el tema %r. Hay: %s"
                  % (args.tema, ", ".join(t.tema for t in temas)))
            return 2
        if args.desde >= len(tema.frases):
            print("%s tiene %d frases." % (tema.tema, len(tema.frases)))
            return 2
        frase = tema.frases[args.desde]
        unidades = video.guion_de_tema(tema, args.objetivo, args.desde)
    else:
        frase = frases.por_id(temas, args.id) if args.id else frases.siguiente(temas, ya)
        if frase is None:
            print("No encuentro esa frase." if args.id else "Ya salieron todas.")
            return 2
        tema = frases.tema_de(temas, frase)
        unidades = video.guion(frase)
    fondo = elegir_fondo(args.fondo, frase.id) if args.fondo else None
    cuerpo, _ = video.reparto(unidades)

    print("%s · capitulo %d, %s%s" % (frase.id, tema.capitulo, tema.titulo,
                                      "  (el capitulo entero)" if args.tema else ""))
    if args.musica:
        print("musica: %s" % buscar_musica(args.musica).name)
    print("%d renglones, cuerpo %d, fondo %s"
          % (len(unidades), cuerpo,
             ", ".join(x.name for x in fondo[:3]) if fondo else "papel de la marca"))
    for u in unidades:
        print("   %s" % u)

    # Las CUATRO, no tres: con dos banderas puestas se armaba la voz dos veces
    # -la segunda pisando a la primera- y se pagaban las dos.
    cuantas = sum(1 for x in (args.voz, args.voz_mac is not None,
                              args.voz_ia, args.voz_eleven is not None) if x)
    if cuantas > 1:
        print()
        print("Elegi una voz sola: --voz es tu grabacion, --voz-mac la del Mac,")
        print("--voz-ia la de OpenAI y --voz-eleven la de ElevenLabs.")
        return 2

    if args.ver:
        leido = video.duracion_del_guion(unidades)
        print()
        # El tope que se muestra es el que el codigo respeta, que es el de
        # Facebook MENOS el margen: si dijera 90, un reel de 88 pareceria
        # tener aire y en realidad ya no se habria armado asi.
        print("Duraria %.0f s leido, o sea unos %.0f hablados (tope %.0f, "
              "que son los %d de Facebook con margen)."
              % (leido, leido * video.VOZ_MAS_LENTA, video.TOPE_CON_MARGEN,
                 video.TOPE_SEGUNDOS))
        letras = sum(len(u) for u in unidades)
        nuevas = [u for u in unidades if not video.en_cache(u, args.voz_ia or video.VOZ_IA)]
        print("Con --voz-ia serian %d caracteres, %d renglones, y %d habria que "
              "pedirlos (el resto ya esta en la cache)."
              % (letras, len(unidades), len(nuevas)))
        return 0

    marcas = None
    voz = Path(args.voz) if args.voz else None

    # Con --ingles lo que se LEE no es lo que se MUESTRA. El subtitulo sigue
    # siendo el espanol del banco y la voz dice su traduccion, oracion por
    # oracion, que es la unidad mas chica donde los dos coinciden.
    grupos, a_leer = None, unidades
    if args.ingles:
        grupos = video.agrupar_en_oraciones(unidades)
        en_espanol = [" ".join(g) for g in grupos]
        print()
        print("Traduciendo %d oraciones al ingles..." % len(en_espanol))
        try:
            a_leer = traducir.a_ingles(en_espanol)
        except traducir.TraducirError as e:
            print(e)
            return 1
        for es, en in zip(en_espanol, a_leer):
            print("   ES  %s" % es)
            print("   EN  %s" % en)
        # El tope se comprueba ANTES de pedir la voz. El guion se eligio
        # midiendo el ESPANOL, y el ingles no dura lo mismo: sin esto, un
        # capitulo que se pasa se descubre despues de haber pagado el audio
        # entero, que es exactamente lo que ya paso una vez.
        sobran = []
        while len(a_leer) > 1:
            dicho = video.duracion_del_guion(a_leer) * video.VOZ_MAS_LENTA
            if dicho <= video.TOPE_CON_MARGEN:
                break
            sobran.append(a_leer.pop())
            grupos = grupos[:-1]
        if sobran:
            # Se sacan oraciones ENTERAS y desde el final, nunca media: media
            # oracion termina en el aire y el reel se lee como un error.
            print()
            print("El ingles da mas largo que el espanol: saco %d oracion(es) "
                  "del final para entrar en el tope." % len(sobran))
            unidades = [u for g in grupos for u in g]
    if args.voz_ia:
        letras = sum(len(u) for u in a_leer)
        print()
        print("Leyendo %d %s (%d caracteres) con la voz %s de OpenAI..."
              % (len(a_leer), "oraciones" if args.ingles else "renglones",
                 letras, args.voz_ia))
        try:
            voz, duraciones = video.voz_por_unidades(
                a_leer, carpeta / ("%s-voz" % frase.id), args.voz_ia,
                decir_fn=video.decir_con_ia, color=args.color)
        except video.VideoError as e:
            print(e)
            return 1
        marcas = (video.marcas_por_oracion(grupos, duraciones) if args.ingles
                  else video.tiempos_exactos(duraciones))
        print("Listo. Lo pedido queda anotado en data/voz.jsonl; el costo se")
        print("mira en el panel de OpenAI, que es donde esta el precio de verdad.")
        contar_lo_que_tardo(a_leer, duraciones)
    if args.voz_eleven is not None:
        letras = sum(len(u) for u in a_leer)
        print()
        print("Leyendo %d %s (%d caracteres) con ElevenLabs..."
              % (len(a_leer), "oraciones" if args.ingles else "renglones", letras))
        try:
            voz, duraciones = video.voz_por_unidades(
                a_leer, carpeta / ("%s-voz" % frase.id), args.voz_eleven,
                decir_fn=video.decir_con_eleven, color=args.color)
        except video.VideoError as e:
            print(e)
            return 1
        marcas = (video.marcas_por_oracion(grupos, duraciones) if args.ingles
                  else video.tiempos_exactos(duraciones))
        print("Listo. Lo pedido queda anotado en data/voz.jsonl; los creditos")
        print("se miran en el panel de ElevenLabs.")
        contar_lo_que_tardo(a_leer, duraciones)
    if args.voz_mac is not None:
        quien = args.voz_mac or video.voz_preferida()
        print()
        print("Leyendo renglon por renglon con la voz %s..." % quien)
        try:
            voz, duraciones = video.voz_por_unidades(
                unidades, carpeta / ("%s-voz" % frase.id), quien, color=args.color)
        except video.VideoError as e:
            print(e)
            hay = video.voces_en_espanol()
            if hay:
                print("Voces en espanol instaladas: %s" % ", ".join(hay))
                print("Si la que pediste no esta: Ajustes del sistema -> "
                      "Accesibilidad -> Contenido hablado -> Voz del sistema.")
            else:
                print("`say` solo existe en Mac. Sin voz el reel sale igual, mudo.")
            return 1
        marcas = video.tiempos_exactos(duraciones)
        contar_lo_que_tardo(a_leer, duraciones)

    try:
        ruta = video.armar(frase, pagina, titulo=tema.titulo, fondo=fondo, voz=voz,
                           carpeta=carpeta, marcas=marcas, unidades=unidades,
                           musica=buscar_musica(args.musica) if args.musica else None)
    except video.VideoError as e:
        print(e)
        return 1
    print()
    print(ruta)
    if args.telegram:
        from src import telegram
        pie = "%s · %s%s" % (frase.id, tema.titulo,
                             "  (capitulo entero)" if args.tema else "")
        try:
            telegram.enviar_video(ruta, pie)
            print("Mandado al chat.")
        except telegram.TelegramError as e:
            # El reel ya esta armado: que no se pueda mandar no lo pierde.
            print("No pude mandarlo al chat: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
