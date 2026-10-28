#!/usr/bin/env python3
"""Publica la frase que toca, o la que se perdio hoy. Pensado para correr seguido.

    publicar_turno.py          publica si corresponde
    publicar_turno.py --ver    dice que haria, sin publicar

Las horas estan en `config/pagina.yaml`. Fuera de esas horas no publicaba
nada, y eso fue el problema del 2026-10-26/28: la pagina estuvo dos dias
enteros sin un solo flyer.

LA CAUSA NO ERA EL CODIGO SINO EL RELOJ DE GITHUB. El flujo declara 96
corridas por dia (cada quince minutos) y GitHub honra unas cinco, a horas
que elige el. Medido el 2026-10-27, las cinco cayeron a la 01, las 07, las
13, las 18 y las 22 de Lima. La parrilla son horas PARES, asi que de las
cinco corridas, CERO cayeron en una hora de la parrilla y ese dia no salio
nada. En cinco dias salieron 7 posts de los 25 que tocaban.

Por eso este script ya no pregunta «es esta hora de la parrilla» sino «que
turno de hoy ya paso y todavia no salio». Si son las 19:18 y el turno de las
18 no salio, sale ahora.

Tres cosas acotan eso, porque una pagina que publica cuatro flyers seguidos
es peor que una que publica tres:

- **Se toma el turno pendiente MAS NUEVO**, no el mas viejo. A las 19 sale el
  de las 18 y no el de las 08: un flyer once horas tarde se anota con una hora
  que no es y le roba el lugar al que si podia salir cerca de su horario.
- **Uno por corrida.** Los turnos que quedaron atras se pierden, y esta bien
  que se pierdan: publicar los seis de una vez es lo unico peor que no
  publicar.
- **Una espera minima entre dos posts** (`ESPERA_ENTRE_POSTS`), que solo se le
  pide a los atrasados. Dos corridas de GitHub en la misma hora -pasa- sacarian
  dos flyers con media hora de diferencia.

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

from src import config, diseno, frases, parrilla  # noqa: E402


# Cuanto tiene que haber pasado desde el ultimo post para publicar uno
# ATRASADO. Al turno que sale a su hora no se le pide nada: dos horas de la
# parrilla estan a dos horas de distancia por definicion.
#
# Hora y media y no media hora: el valor que importa es el que se ve en la
# pagina, y dos flyers con veinte minutos de diferencia se leen como un error
# del sistema aunque cada uno sea correcto.
ESPERA_ENTRE_POSTS = 90 * 60


def ya_salio_en_esta_hora(ya: dict, ahora: datetime) -> bool:
    hoy = ahora.date().isoformat()
    return any(d.get("dia") == hoy and d.get("hora") == ahora.hour for d in ya.values())


def pendientes(horas_hoy, ya: dict, ahora: datetime) -> list:
    """Los turnos de hoy que ya pasaron y todavia no salieron, de viejo a nuevo."""
    hoy = ahora.date().isoformat()
    salieron = {d.get("hora") for d in ya.values() if d.get("dia") == hoy}
    return [h for h in horas_hoy if h <= ahora.hour and h not in salieron]


def hora_a_publicar(horas_hoy, ya: dict, ahora: datetime):
    """Que turno sale en esta corrida, o None si no hay ninguno.

    El MAS NUEVO de los pendientes. Ver la cabecera del archivo: el mas viejo
    se anotaria con una hora que ya no es y dejaria afuera al que todavia
    puede salir a tiempo.
    """
    faltan = pendientes(horas_hoy, ya, ahora)
    return max(faltan) if faltan else None


def hace_muy_poco(ya: dict, ahora: datetime, espera: int = ESPERA_ENTRE_POSTS) -> bool:
    """Si hace menos de `espera` que salio un post de hoy.

    Mira `cuando`, que es la hora REAL en que se publico, y no `hora`, que es
    el turno al que pertenece. Son distintas justamente en los atrasados, que
    es el unico caso donde esto se usa.

    Un registro sin `cuando` -los de antes del 2026-10-28- no frena nada: no
    se puede saber, y frenar por las dudas dejaria la pagina sin publicar, que
    es el problema que esto viene a arreglar.
    """
    hoy = ahora.date().isoformat()
    for d in ya.values():
        if d.get("dia") != hoy:
            continue
        try:
            cuando = datetime.fromisoformat(d.get("cuando") or "")
        except (TypeError, ValueError):
            continue
        if 0 <= (ahora - cuando).total_seconds() < espera:
            return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", action="store_true", help="decir que haria, sin publicar")
    ap.add_argument("--ahora", help="fingir esta fecha y hora (YYYY-MM-DDTHH), para probar")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    ahora = datetime.fromisoformat(args.ahora) if args.ahora else datetime.now()

    temas = frases.leer()
    problemas = frases.revisar(temas, pagina)
    if problemas:
        print("El banco tiene %d problemas; no publico. El primero: %s"
              % (len(problemas), problemas[0]))
        return 2

    ya = frases.publicadas()
    desde = frases.primer_dia(ya) or ahora.date()
    horas_hoy = parrilla.horas_del_dia(pagina, desde, ahora.date())
    hoy = "Hoy (dia %d) salen %d: %s." % (
        parrilla.dia_de_la_prueba(desde, ahora.date()), len(horas_hoy),
        ", ".join("%02d" % h for h in horas_hoy))

    if ya_salio_en_esta_hora(ya, ahora):
        print("A las %02d de hoy ya salio un post. No publico otro." % ahora.hour)
        return 0

    hora = hora_a_publicar(horas_hoy, ya, ahora) if horas_hoy else ahora.hour
    if hora is None:
        print("A las %02d no hay ningun turno pendiente. %s" % (ahora.hour, hoy))
        return 0

    # Al turno atrasado se le pide espacio; al que sale a su hora, no. Ver la
    # cabecera: esto es lo unico que separa recuperar un turno perdido de
    # vaciar la cola del dia en media hora.
    if hora != ahora.hour and hace_muy_poco(ya, ahora):
        print("El turno de las %02d esta pendiente, pero hace menos de %d minutos "
              "que salio un post. Lo dejo para la proxima corrida."
              % (hora, ESPERA_ENTRE_POSTS // 60))
        return 0

    if hora != ahora.hour:
        print("Son las %02d y el turno de las %02d no salio. Lo publico ahora."
              % (ahora.hour, hora))

    frase = frases.siguiente(temas, ya)
    if frase is None:
        print("Ya salieron las %d frases del banco. Toca escribir mas."
              % len(frases.todas(temas)))
        return 1
    tema = frases.tema_de(temas, frase)
    # Las horas de HOY, no la parrilla entera: es lo que hace que en un dia
    # de cuatro posts salgan cuatro estilos y no dos. La cuenta vive en
    # `diseno.estilo_de`, que es la misma que usa el boton del bot: copiada,
    # el bot mostraria un flyer y este publicaria otro.
    estilo = diseno.estilo_de(pagina, ahora.date(), hora, horas_hoy)
    texto = frases.caption(frase, tema, pagina)

    print("%s · %s · estilo %s · %02d h" % (frase.id, tema.tema, estilo, hora))
    if args.ver:
        return 0

    ruta = diseno.dibujar(frase, tema, pagina, estilo=estilo)
    # Por HORA y no solo por el interruptor: desde el 2026-10-24 a Instagram
    # van dos de los ocho posts del dia.
    if pagina.instagram_en(hora):
        from src import instagram  # noqa: E402
        salida = instagram.publicar_las_dos(pagina, texto, ruta)
    else:
        from src import facebook  # noqa: E402
        salida = {"post_id": facebook.publicar(pagina, texto, ruta),
                  "instagram": "", "error_instagram": ""}

    # La historia del flyer, DESPUES de que el post salio. Va aca y no dentro
    # de `facebook.publicar` porque Instagram usa esa misma funcion para su
    # camino y una historia de Facebook no tiene nada que hacer ahi.
    #
    # No se mira si salio: `del_flyer` no levanta error nunca. Lo que ya se
    # publico esta publicado, y la historia es el extra.
    from src import historias  # noqa: E402
    historias.del_flyer(pagina, ruta)

    frases.anotar_publicada(frase.id, ahora.date(), salida["post_id"], pagina.nombre, extra={
        "hora": hora, "tema": tema.tema, "eje": tema.eje,
        "estilo": estilo, "instagram": salida.get("instagram") or "",
        # La hora REAL, que en un turno atrasado no es `hora`. Es lo que lee
        # `hace_muy_poco` para no sacar dos flyers pegados.
        "cuando": ahora.isoformat(timespec="seconds"),
    })
    print("publicada: %s" % salida["post_id"])
    if salida.get("error_instagram"):
        print("Instagram NO salio: %s" % salida["error_instagram"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
