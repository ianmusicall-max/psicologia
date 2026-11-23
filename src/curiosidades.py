"""Banco y selección de los datos curiosos de una página."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

TIPO = "curiosidad"


@dataclass
class Curiosidad:
    id: str
    lugar: str
    texto: str
    detalle: str
    fuente: str
    foto: Path
    credito: str
    foto_fuente: str
    licencia: str
    destacar: list[str] = field(default_factory=list)

    def caption(self) -> str:
        return f"{self.lugar}\n\n{self.texto}\n\n{self.detalle}"


def leer(ruta: Path) -> list[Curiosidad]:
    banco = []
    ids = set()
    for entrada in yaml.safe_load(ruta.read_text(encoding="utf-8")):
        dato = Curiosidad(**dict(entrada, foto=ruta.parent / entrada["foto"]))
        if not dato.id.startswith("mundo-") or dato.id in ids:
            raise ValueError(f"ID de curiosidad inválido o repetido: {dato.id}")
        if not dato.foto.is_file():
            raise ValueError(f"Falta la foto de {dato.id}: {dato.foto}")
        ids.add(dato.id)
        banco.append(dato)
    return banco


def toca_curiosidad(ya: dict) -> bool:
    ultima = max(
        ya.values(),
        key=lambda d: d.get("cuando") or f"{d.get('dia', '')}T{d.get('hora') or 0:02}",
        default={},
    )
    return ultima.get("tipo") != TIPO


def siguiente(banco: list[Curiosidad], ya: dict) -> Curiosidad | None:
    return next((dato for dato in banco if dato.id not in ya), None)
