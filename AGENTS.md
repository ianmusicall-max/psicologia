# AGENTS.md

Instrucciones para agentes de código (OpenAI Codex y similares) en este
repositorio. Equivalente de `CLAUDE.md` para Claude Code: léelo antes de
tocar nada.

## El proyecto, en una línea

Un banco de frases de psicología (amor propio y vínculos) que alimenta a
la vez los posts diarios de una página de Facebook y el manuscrito de un
libro: cada frase se escribe una sola vez y de ahí salen el flyer, el
caption y el capítulo.

## Dónde está cada cosa

- `README.md` — cómo está armado el banco de frases y el pipeline.
- `LINEA_EDITORIAL.md` — el tono y las reglas editoriales: léelo antes de
  escribir o tocar una frase.
- `frases/`, `frases_mayores/`, `textos/` — el contenido.
- `libro/` — el manuscrito.
- `src/`, `scripts/` — el código que genera flyers, posts y capítulos.

## Por completar

Este repositorio no tenía `CLAUDE.md`. Lo que falta, y conviene agregar la
próxima vez que se trabaje aquí:

- Cómo correr las pruebas de `tests/`.
- Qué pide cada `requirements*.txt` (parecen ser tres instalaciones
  distintas: libro, video, y el resto).
- Qué revisa el workflow en `.github/workflows/` y qué tiene que seguir
  pasando en verde.
