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


def _nota(frec: float, dura: float, fuerza: float, armonicos: int = ARMONICOS,
          potencia: float = POTENCIA, por_armonico: float = CAIDA_POR_ARMONICO):
    import array
    n = int(dura * SR)
    salida = array.array("d", [0.0]) * n
    for k in range(1, armonicos + 1):
        # La desafinacion crece con el armonico, como en una cuerda real.
        f = frec * k * math.sqrt(1 + INARMONICO * k * k)
        if f > SR / 2.2:
            break
        amplitud = fuerza / (k ** potencia)
        caida = CAIDA_GRAVE * (por_armonico ** (k - 1))
        paso = 2 * math.pi * f / SR
        for i in range(n):
            t = i / SR
            env = math.exp(-t / caida)
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
            largo = min(CAIDA_GRAVE * 2.2, segundos - cuando)
            llave = (round(f, 2), round(largo, 2), fuerza)
            if llave not in notas:
                notas[llave] = _nota(f, largo, fuerza)
            nota = notas[llave]
            desde = int(cuando * SR)
            for i, v in enumerate(nota):
                if desde + i >= total:
                    break
                pista[desde + i] += v
        # La mano izquierda, al empezar el acorde. Sostiene mas que la
        # derecha, asi el cambio de acorde no deja un hueco.
        f = LA * (2 ** ((acorde[0] + tono + OCTAVA_GRAVE) / 12.0))
        largo = min(CAIDA_GRAVE * 2.6, segundos - t)
        if largo > 0.2:
            llave = ("grave", round(f, 2), round(largo, 2))
            if llave not in notas:
                notas[llave] = _nota(f, largo, 0.30 * FUERZA_GRAVE,
                                     armonicos=6, potencia=1.4,
                                     por_armonico=0.75)
            desde = int(t * SR)
            for i, v in enumerate(notas[llave]):
                if desde + i >= total:
                    break
                pista[desde + i] += v
        t += paso_compas
        compas += 1
    return pista


def guardar(pista, salida: Path, segundos: float) -> Path:
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
        # Un poco de sala. Un piano en una habitacion seca suena a maqueta.
        "-af", "aecho=0.8:0.9:60|110|180:0.30|0.20|0.12,"
               "lowpass=f=8000,"      # fieltro: sin los agudos mas duros
               "loudnorm=I=-18:TP=-3:LRA=7",
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
        guardar(componer(args.segundos, nombre), salida, args.segundos)
        print("%s  (%.1f MB)" % (salida, salida.stat().st_size / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
