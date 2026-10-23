"""La configuración de la página: config/pagina.yaml más las credenciales del .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "pagina.yaml"


@dataclass
class Pagina:
    nombre: str
    firma: str = ""
    paleta: Dict[str, str] = field(default_factory=dict)
    estilo: str = "regla"
    hashtags_fijos: List[str] = field(default_factory=list)
    pie_sensible: str = ""
    page_id_env: str = "PSI_FB_PAGE_ID"
    token_env: str = "PSI_FB_PAGE_TOKEN"

    @property
    def fb_page_id(self) -> Optional[str]:
        return os.environ.get(self.page_id_env) or None

    @property
    def fb_token(self) -> Optional[str]:
        return os.environ.get(self.token_env) or None

    def color(self, campo: str, defecto: str) -> str:
        return self.paleta.get(campo) or defecto


def cargar(ruta: Path = CONFIG) -> Pagina:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))["pagina"]
    fb = datos.get("facebook") or {}
    return Pagina(
        nombre=datos["nombre"],
        firma=datos.get("firma") or "",
        paleta=dict(datos.get("paleta") or {}),
        estilo=str(datos.get("estilo") or "regla"),
        hashtags_fijos=list(datos.get("hashtags_fijos") or []),
        pie_sensible=(datos.get("pie_sensible") or "").strip(),
        page_id_env=fb.get("page_id_env", "PSI_FB_PAGE_ID"),
        token_env=fb.get("token_env", "PSI_FB_PAGE_TOKEN"),
    )
