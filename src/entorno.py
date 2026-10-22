"""Escribir claves en el .env sin pisar lo que ya está."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"


def guardar(valores: Dict[str, str], ruta: Optional[Path] = None) -> Path:
    """Pone o reemplaza esas claves y deja el resto del archivo como estaba.

    Escribe aparte y renombra: si algo se corta en el medio, el .env no queda
    a medias. Y lo deja en 600, porque son credenciales.
    """
    ruta = Path(ruta or ENV)
    lineas = ruta.read_text(encoding="utf-8").split("\n") if ruta.exists() else []
    for clave, valor in valores.items():
        puesto = False
        for i, l in enumerate(lineas):
            if l.split("=", 1)[0].strip() == clave:
                lineas[i] = "%s=%s" % (clave, valor)
                puesto = True
                break
        if not puesto:
            lineas.append("%s=%s" % (clave, valor))
    tmp = ruta.with_suffix(".parcial")
    tmp.write_text("\n".join(lineas), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(ruta)
    return ruta
