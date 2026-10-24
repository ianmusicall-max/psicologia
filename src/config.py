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
    instagram: bool = False
    rotar_estilos: bool = False
    horas: List[int] = field(default_factory=list)
    arranque: List[Dict] = field(default_factory=list)
    posts_por_dia: int = 0
    hashtags_fijos: List[str] = field(default_factory=list)
    pie_sensible: str = ""
    instagram_horas: List[int] = field(default_factory=list)
    page_id_env: str = "PSI_FB_PAGE_ID"
    token_env: str = "PSI_FB_PAGE_TOKEN"

    @property
    def fb_page_id(self) -> Optional[str]:
        return os.environ.get(self.page_id_env) or None

    @property
    def fb_token(self) -> Optional[str]:
        return os.environ.get(self.token_env) or None

    def instagram_en(self, hora: int) -> bool:
        """Si a esa hora el flyer tambien va a Instagram.

        La lista vacia quiere decir TODAS, que es como funciono hasta que se
        bajo a dos por dia: una pagina que enciende Instagram y no declara
        horas no puede quedarse sin publicar ahi.
        """
        if not self.instagram:
            return False
        return not self.instagram_horas or hora in self.instagram_horas

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
        instagram=bool(datos.get("instagram", False)),
        instagram_horas=[int(h) for h in (datos.get("instagram_horas") or [])],
        rotar_estilos=bool(datos.get("rotar_estilos", False)),
        horas=[int(h) for h in (datos.get("horas") or [])],
        arranque=[dict(x) for x in (datos.get("arranque") or [])],
        posts_por_dia=int(datos.get("posts_por_dia") or 0),
        hashtags_fijos=list(datos.get("hashtags_fijos") or []),
        pie_sensible=(datos.get("pie_sensible") or "").strip(),
        page_id_env=fb.get("page_id_env", "PSI_FB_PAGE_ID"),
        token_env=fb.get("token_env", "PSI_FB_PAGE_TOKEN"),
    )
