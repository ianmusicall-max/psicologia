#!/usr/bin/env python3
"""Genera la pista de piano del reel. Original, sin derechos de nadie.

    hacer_musica.py                 escribe assets/musica/piano.m4a
    hacer_musica.py --segundos 120
    hacer_musica.py --salida /tmp/prueba.m4a

Por que generada y no bajada: una pista con derechos le hace perder alcance a
TODA la cuenta, no solo al post donde se use. Lo que viene en el repo tiene
que ser propio.

Por que PIANO: se midio la musica del reel de referencia que mando el usuario
contra la que traia el repo, y la del repo no tenia nada arriba de 1 kHz -era
un colchon grave-. Un piano tiene armonicos hasta varios kHz, y eso es lo que
se oye como piano y no como zumbido.

Como suena un piano, que es lo que esto imita:

- cada nota es su fundamental mas sus armonicos, con los agudos MAS cortos que
  los graves: por eso un piano arranca brillante y se apaga calido;
- los armonicos no son multiplos exactos (`INARMONICO`): esa pequena
  desafinacion es gran parte de lo que distingue una cuerda de una sinusoide;
- el martillo de fieltro pega suave, asi que el ataque no es un clic.

SOLO ESCRIBE UN ARCHIVO DE AUDIO. No publica nada ni toca el banco.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import video  # noqa: E402

SR = 44100

# La Menor: triste sin ser lugubre, que es el registro de la pagina. Las notas
# van por su semitono respecto del La 440, y se tocan GRAVES -dos octavas
# abajo- para que no compitan con la voz, que vive entre 100 y 1000 Hz.
LA = 440.0
# La mano derecha, una octava abajo del La 440. MEDIDO: a dos octavas -donde
# estaba al principio- el piano salia tan oscuro como el colchon que venia a
# reemplazar, porque a 55 Hz los armonicos que dan el brillo caen fuera de
# donde se oyen. Con una, la firma del espectro queda a 4 dB de la referencia.
OCTAVA_ABAJO = -12
# La mano izquierda: la fundamental del acorde, dos octavas mas abajo todavia.
# No es adorno: sin ella faltan 38 dB en la banda de 60-120 Hz, que es el
# cuerpo que la referencia si tiene. Su nivel tambien esta medido.
OCTAVA_GRAVE = -36
FUERZA_GRAVE = 0.80

# i - VI - III - VII en La menor. Es la vuelta armonica mas comun de la musica
# melancolica y no resuelve nunca del todo, que es lo que se quiere debajo de
# alguien hablando: si resolviera, cada ocho compases el oido iria a la musica.
ACORDES = (
    (0, 3, 7, 12),        # Am
    (-4, 0, 5, 8),        # F
    (-9, -5, 0, 3),       # C
    (-2, 2, 7, 10),       # G
)
COMPAS = 6.0              # segundos por acorde: lento

# Las piezas que trae el repo. Lo pidio el usuario el 2026-10-25 -«varia la
# cancion»- porque hasta hoy TODOS los reels salian con la misma.
#
# **Las cuatro son la misma familia a proposito.** Lo que cambia es el tono,
# la vuelta armonica y cuanto dura cada acorde; lo que NO cambia es el piano,
# el registro grave -debajo de la voz- y que ninguna resuelve. Si una sonara
# de otro palo, el reel del martes se oiria de otra pagina, que es la misma
# leccion que la paleta de los flyers.
#
# `tono` son semitonos respecto de La. Hacia abajo y no hacia arriba: subir
# el tono mete la mano derecha en el rango de la voz (100-1000 Hz) y empieza
# a competir con lo que se dice.
PIEZAS = {
    # La que ya existia, y queda igual: es contra la que se midio todo.
    "piano": {
        "acordes": ACORDES, "compas": COMPAS, "tono": 0,
        "es": "La menor, i-VI-III-VII. La de siempre.",
    },
    # Mas grave y mas lenta: dos acordes nada mas, asi que casi no pasa nada.
    # Es la de los capitulos de quedarse quieto.
    "noche": {
        "acordes": ((0, 3, 7, 12), (-2, 2, 5, 10)),
        "compas": 7.5, "tono": -5,
        "es": "Mi menor, i-VII. Dos acordes, muy lenta.",
    },
    # La unica que empieza por el acorde mayor: no es alegre -sigue sin
    # resolver- pero abre en vez de cerrar.
    "ventana": {
        "acordes": ((-9, -5, 0, 3), (0, 3, 7, 12), (-2, 2, 7, 10), (-4, 0, 5, 8)),
        "compas": 5.5, "tono": -3,
        "es": "Fa# menor, III-i-VII-VI. Arranca por el mayor.",
    },
    # La mas oscura, y la mas lenta de todas. Va con duelo y con ruptura.
    "hondo": {
        "acordes": ((0, 3, 7, 10), (-5, -1, 2, 7), (-7, -4, 0, 5), (-2, 1, 5, 8)),
        "compas": 8.0, "tono": -7,
        "es": "Re menor, con septima. La mas oscura.",
    },
    # La del 2026-10-26, y la unica que NO comparte la voz de las otras cuatro.
    # El usuario pidio piano teniendo ya dos reels hechos con `piano.m4a`, asi
    # que el pedido no era otra cancion sino que la cancion se oyera como un
    # piano. Tres cosas la separan, y las tres estan medidas:
    #
    # - **las notas se oyen de a una**, y esto esta MEDIDO contando los golpes
    #   que sobresalen en la banda del martillo (2-5 kHz), no mirando la
    #   receta: `teclas` tiene **1,11 golpes por segundo que suben 10,4 dB**
    #   -el mayor, 17,1- contra los **0,39 que suben 3,8 dB** de `piano`. En
    #   las otras cuatro cae una nota cada 1,5 s y dura 4,5, asi que hay
    #   siempre tres superpuestas y lo que se oye es un acorde sostenido;
    # - **los armonicos altos se apagan rapido**, y ESTO es la causa, no el
    #   martillo. `por_armonico` 0,84 contra 0,92: el armonico 20 se apaga en
    #   0,07 s en vez de 1,1, asi que entre dos notas la banda del martillo se
    #   queda en silencio y el golpe que sigue sobresale. Aislado -misma
    #   pieza, solo ese numero- da **8,6 dB de golpe contra 4,3**;
    # - **y ENCIMA de eso el golpe del martillo** (`golpe`), que suma 1,8 dB
    #   mas: de 8,6 a 10,4. Se midio aparte porque la primera version de este
    #   comentario decia que el martillo era lo que hacia el piano, y es al
    #   reves: con `por_armonico` en 0,92 el martillo **no cambia nada**
    #   -4,3 dB con y sin el-, porque el brillo sostenido tapa el salto. El
    #   martillo no sirve si antes no se hizo silencio arriba;
    # - el brillo PROMEDIO baja con esto (2,3% contra 5,1%) y es lo correcto:
    #   un piano tiene el brillo en el ataque, no repartido. Buscar el
    #   promedio mas alto es lo que lleva de nuevo al colchon;
    # - **la mano izquierda sube una octava** (-24 y no -36) y pega mas suave.
    #   A 55 Hz esa sola nota se llevaba la mitad de la energia de la pieza, y
    #   en el telefono eso no se oye: se pierde.
    #
    # Sigue siendo de la familia: piano, debajo de la voz y sin resolver.
    "teclas": {
        "acordes": ((0, 3, 7, 12), (-7, -4, 0, 5), (-4, 0, 5, 8), (-5, -1, 2, 7)),
        "compas": 3.6, "tono": -2,
        "es": "Sol menor, i-iv-VI-v. Las notas se oyen de a una.",
        "voz": {"armonicos": 20, "potencia": 0.6, "por_armonico": 0.84,
                "caida": 2.2, "golpe": 0.100, "grave": -24,
                "fuerza_grave": 0.55, "techo": 11000,
                # Sala corta y floja. La de las otras cuatro devuelve ecos a
                # 60, 110 y 180 ms, que es exactamente el hueco donde tendria
                # que oirse el silencio entre dos notas: con esa sala el golpe
                # no sobresale -medido, 3,6 dB contra los 3,5 de `piano`-.
                "sala": "aecho=0.9:0.30:38|75:0.16|0.08",
                # Y `LRA=7` aplana lo que el golpe acaba de levantar. Con 12
                # la pieza sigue siendo una cama -no sube ni baja sola- pero
                # el ataque de cada nota llega entero.
                "lra": 12},
    },
}

# Cuanto se desafinan los armonicos. Un numero chico; con 0 suena a organo.
INARMONICO = 0.0004
ARMONICOS = 14

# Un martillo de fieltro no hace clic.
ATAQUE = 0.012
# Los agudos se apagan antes que los graves. Es lo que hace que la nota
# arranque brillante y termine calida.
CAIDA_GRAVE = 4.5
# 0.92 y no 0.55: con 0.55 cada armonico dura la mitad que el anterior y para
# el octavo ya no queda nada, asi que de la nota solo se oye la fundamental.
# Eso es un zumbido, no un piano.
CAIDA_POR_ARMONICO = 0.92
# Cuanto se reparte la fuerza entre los armonicos. Mas chico es mas brillante.
POTENCIA = 0.9


# EL MARTILLO. El 2026-10-26 el usuario pidio «otra musica, piano» teniendo
# ya dos reels hechos CON `piano.m4a`, asi que se midio el archivo en vez de
# releer la receta, y la receta mentia: el comentario de arriba dice que un
# piano se reconoce por sus armonicos de varios kHz, y de la energia de
# `piano.m4a` **el 1,9% esta arriba de 2 kHz y el 0,0% arriba de 5 kHz**.
#
# Lo que de verdad faltaba no es esto sino el SILENCIO entre dos notas, y
# conviene que quede escrito porque la primera version de este comentario lo
# tenia al reves. Un piano se reconoce por el salto al caer cada nota, y para
# que haya salto la banda de arriba tiene que vaciarse antes. En las cuatro
# piezas de siempre el armonico mas alto dura 1,5 s y cae una nota cada 1,5 s,
# o sea que no se vacia nunca: cada nota entra sobre la anterior y lo que se
# oye es un acorde sostenido -los 6,9 dB de cresta que se midieron-. Por eso
# `ATAQUE`, una rampa de 12 ms, no alcanzaba: una rampa sube el volumen de lo
# que ya estaba sonando.
#
# El martillo suma 1,8 dB ENCIMA de eso, y solo si eso ya se hizo: medido con
# `por_armonico` en 0,92, poner el martillo o no poner no cambia ni un dB. Es
# el adorno, no la causa. La cuenta completa esta en la ficha de `teclas`.
GOLPE_DESDE = 6           # el golpe son los armonicos altos, no la fundamental
GOLPE_HASTA = 46
GOLPE_CAIDA = 0.045       # se apaga en centesimas: es un golpe, no una nota
GOLPE_LARGO = 0.26        # mas alla de esto ya no queda nada que sumar
GOLPE_POTENCIA = 0.4      # casi plano: el golpe es ancho de banda

# La voz de cada pieza, que hasta hoy era una sola para todas y estaba suelta
# en constantes de modulo. Separarla es lo que deja agregar una pieza que
# suene distinto sin tocar ni un fotograma de las cuatro que ya salieron.
VOZ_DE_SIEMPRE = {
    "armonicos": ARMONICOS, "potencia": POTENCIA,
    "por_armonico": CAIDA_POR_ARMONICO, "caida": CAIDA_GRAVE,
    "golpe": 0.0, "grave": OCTAVA_GRAVE, "fuerza_grave": FUERZA_GRAVE,
    "techo": 8000,
    # Un poco de sala. Un piano en una habitacion seca suena a maqueta.
    "sala": "aecho=0.8:0.9:60|110|180:0.30|0.20|0.12",
    # Cuanto rango de volumen se le deja. Chico es una cama que no sube ni
    # baja, que es lo que se quiere debajo de alguien hablando.
    "lra": 7,
}


def _nota(frec: float, dura: float, fuerza: float, armonicos: int = ARMONICOS,
          potencia: float = POTENCIA, por_armonico: float = CAIDA_POR_ARMONICO,
          caida: float = CAIDA_GRAVE, golpe: float = 0.0):
    import array
    n = int(dura * SR)
    salida = array.array("d", [0.0]) * n
    if golpe:
        # El golpe del martillo: armonicos altos que se apagan en centesimas.
        # Va aparte y no estirando `armonicos` porque lo que lo hace un golpe
        # es que DURA poco, no que sea agudo. El bucle se corta en
        # `GOLPE_LARGO` -despues de eso la exponencial ya no suma nada- asi
        # que cuesta una fraccion de lo que cuesta la nota.
        hasta = min(n, int(GOLPE_LARGO * SR))
        for k in range(GOLPE_DESDE, GOLPE_HASTA + 1):
            f = frec * k * math.sqrt(1 + INARMONICO * k * k)
            if f > SR / 2.2:
                break
            amplitud = golpe * fuerza / (k ** GOLPE_POTENCIA)
            paso = 2 * math.pi * f / SR
            for i in range(hasta):
                t = i / SR
                env = math.exp(-t / GOLPE_CAIDA)
                if t < ATAQUE:
                    env *= t / ATAQUE
                salida[i] += amplitud * env * math.sin(paso * i)
    for k in range(1, armonicos + 1):
        # La desafinacion crece con el armonico, como en una cuerda real.
        f = frec * k * math.sqrt(1 + INARMONICO * k * k)
        if f > SR / 2.2:
            break
        amplitud = fuerza / (k ** potencia)
        apaga = caida * (por_armonico ** (k - 1))
        paso = 2 * math.pi * f / SR
        for i in range(n):
            t = i / SR
            env = math.exp(-t / apaga)
            if t < ATAQUE:
                env *= t / ATAQUE
            salida[i] += amplitud * env * math.sin(paso * i)
    return salida


def componer(segundos: float, pieza: str = "piano"):
    """La pista de una de las `PIEZAS`. Devuelve las muestras."""
    import array
    if pieza not in PIEZAS:
        raise SystemExit("No conozco la pieza %r. Hay: %s"
                         % (pieza, ", ".join(sorted(PIEZAS))))
    receta = PIEZAS[pieza]
    acordes = receta["acordes"]
    paso_compas = receta["compas"]
    tono = receta["tono"]
    voz = dict(VOZ_DE_SIEMPRE, **receta.get("voz", {}))
    total = int(segundos * SR)
    pista = array.array("d", [0.0]) * total
    notas = {}

    def frecuencia(semitono):
        return LA * (2 ** ((semitono + tono + OCTAVA_ABAJO) / 12.0))

    t = 0.0
    compas = 0
    while t < segundos:
        acorde = acordes[compas % len(acordes)]
        # Arpegio: las notas entran de a una y se superponen, que es lo que
        # deja el sonido continuo sin tener que sostener un acorde entero.
        for j, semitono in enumerate(acorde):
            cuando = t + j * (paso_compas / len(acorde))
            if cuando >= segundos:
                break
            f = frecuencia(semitono)
            # La primera del acorde se toca un poco mas fuerte: marca el
            # cambio sin que haga falta un golpe.
            fuerza = 0.30 if j == 0 else 0.20
            largo = min(voz["caida"] * 2.2, segundos - cuando)
            llave = (round(f, 2), round(largo, 2), fuerza)
            if llave not in notas:
                notas[llave] = _nota(f, largo, fuerza,
                                     armonicos=voz["armonicos"],
                                     potencia=voz["potencia"],
                                     por_armonico=voz["por_armonico"],
                                     caida=voz["caida"], golpe=voz["golpe"])
            nota = notas[llave]
            desde = int(cuando * SR)
            for i, v in enumerate(nota):
                if desde + i >= total:
                    break
                pista[desde + i] += v
        # La mano izquierda, al empezar el acorde. Sostiene mas que la
        # derecha, asi el cambio de acorde no deja un hueco.
        f = LA * (2 ** ((acorde[0] + tono + voz["grave"]) / 12.0))
        largo = min(voz["caida"] * 2.6, segundos - t)
        if largo > 0.2:
            llave = ("grave", round(f, 2), round(largo, 2))
            if llave not in notas:
                notas[llave] = _nota(f, largo, 0.30 * voz["fuerza_grave"],
                                     armonicos=6, potencia=1.4,
                                     por_armonico=0.75, caida=voz["caida"])
            desde = int(t * SR)
            for i, v in enumerate(notas[llave]):
                if desde + i >= total:
                    break
                pista[desde + i] += v
        t += paso_compas
        compas += 1
    return pista


def voz_de(pieza: str) -> dict:
    """Como se toca y como se graba una pieza. Vive aca y no en `guardar`
    porque es parte de como suena: a 8 kHz el golpe del martillo de `teclas`
    se va casi entero, y con `LRA=7` la normalizacion lo aplana igual. Las
    dos cosas son justo lo que se vino a arreglar."""
    return dict(VOZ_DE_SIEMPRE, **PIEZAS[pieza].get("voz", {}))


def guardar(pista, salida: Path, segundos: float, techo: int = 8000,
            sala: str = "aecho=0.8:0.9:60|110|180:0.30|0.20|0.12",
            lra: int = 7) -> Path:
    """A wav y de ahi a m4a. El fundido de entrada y de salida va aca y no al
    armar el reel: una pista que arranca de golpe se oye como un error."""
    pico = max((abs(x) for x in pista), default=1.0) or 1.0
    # Deja aire: la pista se vuelve a nivelar al mezclarla con la voz, y una
    # que llega al tope no deja margen para eso.
    escala = 0.55 / pico
    fundido = int(2.5 * SR)
    n = len(pista)
    crudo = salida.with_suffix(".wav")
    crudo.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(crudo), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        import array
        marco = array.array("h", [0]) * n
        for i, v in enumerate(pista):
            g = escala
            if i < fundido:
                g *= i / fundido
            elif i > n - fundido:
                g *= max(0.0, (n - i) / fundido)
            marco[i] = max(-32767, min(32767, int(v * g * 32767)))
        w.writeframes(marco.tobytes())
    video._correr([
        video.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(crudo),
        "-af", "%s,lowpass=f=%d,loudnorm=I=-18:TP=-3:LRA=%d"
                % (sala, techo, lra),
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        str(salida)], "pasar la musica a m4a", espera=600)
    crudo.unlink()
    return salida


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--segundos", type=float, default=95.0)
    ap.add_argument("--pieza", default="piano",
                    help="cual: %s" % ", ".join(sorted(PIEZAS)))
    ap.add_argument("--todas", action="store_true",
                    help="genera las que falten en assets/musica")
    ap.add_argument("--listar", action="store_true", help="dice cuales hay")
    ap.add_argument("--salida", default=None)
    args = ap.parse_args(argv)

    if args.listar:
        for nombre in sorted(PIEZAS):
            ruta = ROOT / "assets" / "musica" / ("%s.m4a" % nombre)
            print("%-10s %-46s %s" % (nombre, PIEZAS[nombre]["es"],
                                      "hecha" if ruta.exists() else "falta"))
        return 0

    cuales = sorted(PIEZAS) if args.todas else [args.pieza]
    for nombre in cuales:
        salida = Path(args.salida) if args.salida else (
            ROOT / "assets" / "musica" / ("%s.m4a" % nombre))
        # Con `--todas` no se rehace lo que ya esta: cada pieza tarda tanto
        # como dura, asi que repetirlas seria media hora para nada.
        if args.todas and salida.exists():
            print("%s ya estaba" % salida.name)
            continue
        print("Componiendo %.0f s de %s (%s)..."
              % (args.segundos, nombre, PIEZAS[nombre]["es"]))
        v = voz_de(nombre)
        guardar(componer(args.segundos, nombre), salida, args.segundos,
                v["techo"], v["sala"], v["lra"])
        print("%s  (%.1f MB)" % (salida, salida.stat().st_size / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
