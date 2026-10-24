"""La memoria del reel del dia: que salio hoy y si hay una corrida en curso.

Vive en `src/` y no dentro del script porque lo preguntan DOS: el script que
arma y publica, y el boton del bot, que necesita saber si ya hay una corrida
andando antes de largar otra. Un `src` que importa un `script` seria al reves.

Las dos guardas son por lo mismo: armar un reel cuesta la voz de ElevenLabs y
las fotos, y tarda varios minutos.

- **Por dia**: el turno de las 18 se intenta dos veces -GitHub demora y saltea
  los horarios- y el segundo no puede armar un segundo reel.
- **Por corrida**: dos toques seguidos del boton del bot armarian dos, porque
  el primero todavia no termino y no anoto nada.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

SALIDOS = ROOT / "data" / "reels_publicados.json"
CANDADO = ROOT / "data" / "reel_del_dia.lock"

# A partir de cuanto un candado es basura y no una corrida. Un reel tarda unos
# minutos; media hora es que el proceso murio sin soltarlo -lo mato la maquina,
# se corto la luz- y dejarlo para siempre seria no poder armar nunca mas.
VIEJO = 30 * 60


def _leer(registro: Optional[Path] = None) -> dict:
    ruta = Path(registro or SALIDOS)
    if not ruta.is_file():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # Un registro roto no frena el turno: lo peor que pasa es un reel
        # repetido, y quedarse sin el reel del dia es peor.
        return {}
    return datos if isinstance(datos, dict) else {}


def ya_salio_hoy(dia: Optional[date] = None,
                 registro: Optional[Path] = None) -> dict:
    """Lo que salio hoy, o {} si todavia no salio nada.

    Es por DIA y no por hora a proposito: lo que se pidio es un reel diario,
    asi que si el de las 18 fallo y se dispara a mano a las 21, ese cuenta.
    """
    return _leer(registro).get((dia or date.today()).isoformat()) or {}


def anotar(ruta: Path, titulo: str, salidas: dict, dia: Optional[date] = None,
           registro: Optional[Path] = None) -> Path:
    """Anota el reel del dia. RELEE antes de escribir, como los demas.

    Dos corridas pueden solaparse -el boton y el turno- y el que guarde ultimo
    con una copia vieja en la mano le borraria al otro el dia que acaba de
    anotar, que es justo lo que evita armar dos.
    """
    ruta_r = Path(registro or SALIDOS)
    datos = _leer(ruta_r)
    datos[(dia or date.today()).isoformat()] = {
        "video": Path(ruta).name, "titulo": titulo, "salidas": salidas,
        "cuando": datetime.now().isoformat(timespec="seconds")}
    ruta_r.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta_r.with_suffix(".parcial")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(ruta_r)
    return ruta_r


def _vive(pid: int) -> bool:
    """Si ese proceso sigue vivo. La senal 0 no mata: solo pregunta."""
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    return True


def corriendo(candado: Optional[Path] = None) -> bool:
    """Si hay una corrida en curso de verdad.

    No alcanza con que el archivo exista: un proceso que murio sin soltarlo
    dejaria el boton muerto para siempre. Se mira que el proceso VIVA y que el
    candado no sea viejo.
    """
    ruta = Path(candado or CANDADO)
    if not ruta.is_file():
        return False
    try:
        pid = int((ruta.read_text(encoding="utf-8") or "0").split()[0])
        edad = datetime.now().timestamp() - ruta.stat().st_mtime
    except (ValueError, IndexError, OSError):
        return False
    return edad < VIEJO and _vive(pid)


def tomar(candado: Optional[Path] = None) -> bool:
    """Marca que arranca una corrida. False si ya habia otra andando."""
    ruta = Path(candado or CANDADO)
    if corriendo(ruta):
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Se pisa el viejo a proposito: si llegamos aca, o no habia o era basura.
    ruta.write_text("%d" % os.getpid(), encoding="utf-8")
    return True


def soltar(candado: Optional[Path] = None) -> None:
    """Suelta el candado. No revienta si ya no esta: lo importante es que no
    quede tomado, no quien lo saco."""
    try:
        Path(candado or CANDADO).unlink()
    except OSError:
        pass
