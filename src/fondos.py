"""Que clip de fondo acompaña a cada capitulo.

El banco de clips crece: el usuario sube los que le gustan, con el nombre que
les da Pexels. `data/fondos/catalogo.yaml` dice que se ve en cada uno, y este
modulo dice que BUSCA cada capitulo.

**Son dos listas separadas a proposito.** Las etiquetas describen lo que se ve
-lluvia, mar, niebla- y no el capitulo: un mismo clip sirve para varios, y
atarlo a uno solo desperdicia la mitad del archivo. Y al reves: un capitulo
nuevo no obliga a volver a mirar los clips.

**Nada de esto es obligatorio.** Un clip sin catalogar se usa igual, y un tema
sin etiquetas usa todos. Es una PREFERENCIA, no un filtro: quedarse sin fondo
por no encontrar la etiqueta exacta seria mucho peor que usar uno cualquiera,
que al fin y al cabo son todos paisajes de la misma familia.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOGO = ROOT / "data" / "fondos" / "catalogo.yaml"

# Que busca cada capitulo. Las etiquetas van en orden de preferencia, asi que
# la primera es la que mas lo representa.
#
# No estan los veintinueve: los que faltan toman cualquiera. Escribir una
# linea para cada uno solo para que diga «cualquiera» es ruido, y ademas
# invita a inventar una correspondencia que no se siente al mirar el reel.
QUE_BUSCA: Dict[str, List[str]] = {
    # Los de perder y de estar solo: lluvia y gris.
    "duelo":        ["lluvia", "gris", "quietud", "melancolia"],
    "ruptura":      ["lluvia", "gris", "soledad", "ventana"],
    "soledad":      ["soledad", "encierro", "ciudad", "lluvia"],
    "tristeza":     ["lluvia", "gris", "melancolia"],

    # Los de mirar hacia adentro: interior, quietud.
    "emociones":    ["interior", "quietud", "ventana"],
    "ansiedad":     ["encierro", "ciudad", "lluvia"],
    "pensamientos": ["niebla", "interior", "quietud"],
    "culpa":        ["gris", "encierro", "interior"],
    "autoestima":   ["interior", "quietud", "ventana"],
    "descanso":     ["quietud", "niebla", "interior"],

    # Los de vinculos: distancia y cercania.
    "apego":        ["distancia", "ventana", "interior"],
    "intimidad":    ["interior", "quietud"],
    "reconexion":   ["horizonte", "distancia", "mar"],
    "familia":      ["interior", "ventana"],
    "amistad":      ["horizonte", "viaje"],
    "confianza":    ["horizonte", "quietud"],
    "celos":        ["encierro", "gris", "ciudad"],
    "discutir":     ["gris", "ciudad"],
    "limites":      ["ventana", "distancia"],
    "comunicacion": ["ventana", "distancia"],
    "perdon":       ["horizonte", "quietud", "mar"],

    # Los de seguir: mar, viaje, horizonte.
    "cambio":       ["viaje", "partida", "mar", "horizonte"],
    "miedo":        ["niebla", "distancia", "mar"],
    "elegir":       ["horizonte", "viaje", "partida"],
    "sentido":      ["horizonte", "mar", "bosque"],
    "habitos":      ["quietud", "ciudad"],
    "expectativas": ["horizonte", "distancia"],

    # Los de afuera.
    "redes":        ["ciudad", "encierro"],
    "dinero":       ["ciudad", "gris"],
    "hogar":        ["interior", "ventana"],
}


def catalogo(ruta: Optional[Path] = None) -> Dict[str, dict]:
    """Lo que dice `catalogo.yaml`. Vacio si no esta o no se puede leer.

    No revienta: el catalogo es una ayuda para elegir mejor, no un requisito
    para armar el reel. Si falta, se usan todos los clips por igual.
    """
    ruta = Path(ruta or CATALOGO)
    if not ruta.is_file():
        return {}
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return datos if isinstance(datos, dict) else {}


def etiquetas_de(nombre: str, cat: Optional[Dict[str, dict]] = None) -> List[str]:
    cat = catalogo() if cat is None else cat
    ficha = cat.get(nombre) or {}
    etiquetas = ficha.get("etiquetas") or []
    return [str(x) for x in etiquetas]


def puntaje(nombre: str, busca: List[str], cat: Optional[Dict[str, dict]] = None) -> float:
    """Cuanto le sirve ese clip a ese capitulo.

    Las etiquetas que busca el capitulo valen MAS las primeras: son las que
    mejor lo representan. Un clip apaisado pierde un poco, porque el reel es
    vertical y de el se usa una franja del centro.
    """
    cat = catalogo() if cat is None else cat
    tiene = set(etiquetas_de(nombre, cat))
    if not busca:
        return 0.0
    total = 0.0
    for i, etiqueta in enumerate(busca):
        if etiqueta in tiene:
            total += len(busca) - i
    if (cat.get(nombre) or {}).get("apaisado"):
        total -= 0.5
    return total


def ordenar(clips: List[Path], tema: Optional[str], semilla: str,
            cat: Optional[Dict[str, dict]] = None) -> List[Path]:
    """Los clips, los que mejor le van al capitulo primero.

    El desempate sale de una semilla y no del azar: volver a armar el mismo
    reel tiene que dar el mismo video. Es la misma razon por la que el orden
    ya se barajaba con el id de la frase.

    Los que no puntuan NO se descartan: van detras. Quedarse sin fondo por no
    encontrar la etiqueta exacta seria peor que usar un paisaje cualquiera.
    """
    cat = catalogo() if cat is None else cat
    busca = QUE_BUSCA.get((tema or "").strip().lower(), [])
    mezclados = list(clips)
    random.Random(semilla).shuffle(mezclados)
    if not busca:
        return mezclados
    return sorted(mezclados, key=lambda c: -puntaje(c.name, busca, cat))
