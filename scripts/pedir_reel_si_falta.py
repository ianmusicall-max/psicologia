#!/usr/bin/env python3
"""Pide el reel del dia cuando el turno de GitHub no lo disparo.

**Por que existe.** El reel tiene su cron a las 14 de Lima, y GitHub no lo
corre. Medido el 2026-10-27 sobre este repositorio:

    frases   declara 96 corridas por dia  ->  llegaron 5
    reel     declara 2 corridas por dia   ->  llegaron 0 (y 1 por dia antes,
                                              siempre dos o tres horas tarde)

No es un error del repositorio ni algo que se arregle con otro horario: el
`schedule` de GitHub es «lo antes posible despues de», y con carga se demora o
se saltea. El turno de las frases ya lo sabia -por eso declara cuatro intentos
por hora desde el 2026-10-23- y el del reel no tenia nada parecido.

Asi que este script es el camino de atras: lo corre el turno de las frases,
que es el que mas corridas recibe, y si el reel de hoy falta lo PIDE. No arma
nada: dispara `reel-diario.yml`, que es el mismo camino de siempre -el del
cron y el del boton del bot-. Si cada uno armara el reel a su manera, el dia
que esto cambie se arregla uno y el otro se queda con la forma vieja.

**No publica nada y no se saltea tu aprobacion**: el reel que sale de aca pasa
por el bot igual que cualquier otro. Lo unico que cambia es quien aprieta el
boton.

Las tres puertas que decide `diario.falta_pedir_el_reel` estan explicadas ahi;
la que acota el gasto es la tercera, que no pide un segundo reel el dia que
una corrida se cayo a mitad de camino.

    python scripts/pedir_reel_si_falta.py        # pide si falta
    python scripts/pedir_reel_si_falta.py --ver  # solo dice que haria
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import diario  # noqa: E402

FLUJO = "reel-diario.yml"
API = "https://api.github.com"


def _pedir(camino: str, token: str, datos: dict = None) -> dict:
    pedido = urllib.request.Request(
        API + camino,
        data=json.dumps(datos).encode("utf-8") if datos is not None else None,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + token,
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(pedido, timeout=30) as r:
        cuerpo = r.read()
    return json.loads(cuerpo) if cuerpo else {}


def corridas_de_hoy(repo: str, token: str, hoy: date) -> int:
    """Cuantas corridas del reel se crearon hoy, en dias de Lima.

    En dias de Lima y no de UTC porque es la unica cuenta que coincide con la
    del registro: una corrida de las 19:12 UTC que GitHub entrega seis horas
    tarde cae el dia siguiente en UTC y el mismo dia en Lima, que es el dia
    del que estamos hablando.
    """
    r = _pedir("/repos/%s/actions/workflows/%s/runs?per_page=20"
               % (repo, FLUJO), token)
    cuantas = 0
    for corrida in r.get("workflow_runs") or []:
        cuando = datetime.strptime(corrida["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        if (cuando + timedelta(hours=diario.UTC_A_LIMA)).date() == hoy:
            cuantas += 1
    return cuantas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ver", action="store_true",
                    help="Decir que haria, sin pedir nada")
    args = ap.parse_args(argv)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    rama = os.environ.get("GITHUB_REF_NAME", "")
    if not (repo and token and rama):
        # Fuera de Actions no hay nada que pedir, y no es un error: este script
        # es un paso de un flujo, no una herramienta de la Mac.
        print("Sin GITHUB_REPOSITORY, GITHUB_TOKEN y GITHUB_REF_NAME no pido "
              "nada.")
        return 0

    ahora = datetime.now()
    try:
        cuantas = corridas_de_hoy(repo, token, ahora.date())
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        # Que esto falle no puede tumbar el turno de las frases, que ya
        # publico. Es una red, y una red que se rompe deja las cosas como
        # estaban.
        print("No pude preguntar por las corridas del reel: %s" % e)
        return 0

    motivo = diario.falta_pedir_el_reel(ahora, diario.ya_salio_hoy(), cuantas)
    if not motivo:
        print("El reel de hoy no necesita que lo pida (corridas de hoy: %d)."
              % cuantas)
        return 0

    print("Pido el reel del dia: %s." % motivo)
    if args.ver:
        print("Con --ver no pedi nada.")
        return 0
    try:
        _pedir("/repos/%s/actions/workflows/%s/dispatches" % (repo, FLUJO),
               token, {"ref": rama})
    except (urllib.error.URLError, OSError) as e:
        print("No pude pedirlo: %s" % e)
        return 0
    print("Pedido. El reel llega al bot para que lo apruebes, como siempre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
