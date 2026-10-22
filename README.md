# Frases de psicología · página de Facebook y borrador del libro

Un banco de frases de psicología que alimenta dos cosas a la vez: los posts
diarios de la página y el manuscrito del libro. **No son dos proyectos.** Cada
frase se escribe una vez, con el principio que la sostiene y la fuente al lado,
y de ahí salen el flyer, el caption y el capítulo. Si se escribieran por
separado, el libro terminaría contradiciendo a la página.

## Cómo está armado

```
frases/        un archivo por tema = un capítulo del libro (10 temas, 81 frases)
src/frases.py  lee el banco, lo valida contra la línea editorial y dice cuál toca
src/diseno.py  el flyer: 1080x1350, papel cálido, la frase grande, una palabra en color
src/libro.py   arma libro/borrador.md con todas las frases y sus reflexiones
src/facebook.py  publica una foto con su caption. Es el único que habla con Meta
config/pagina.yaml  el nombre, la paleta, los hashtags fijos y el pie sensible
LINEA_EDITORIAL.md  qué se puede decir y qué no, y por qué
libro/PLAN.md       cómo pasa el banco a ser un libro
```

## Empezar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env     # y poner el id y el token de la página
.venv/bin/python scripts/revisar_banco.py     # 81 frases, 0 problemas
.venv/bin/python scripts/frase_del_dia.py --dibujar
```

## Los cuatro comandos

| | |
|---|---|
| `scripts/revisar_banco.py` | cuántas frases hay, cuántas salieron y qué rompe la línea editorial. Solo lee |
| `scripts/frase_del_dia.py` | la que toca, con su caption. `--dibujar` deja el flyer, `--publicar` la sube |
| `scripts/dibujar_todas.py` | el banco entero en `data/flyers`, para mirarlo antes de que salga |
| `scripts/armar_libro.py` | vuelve a escribir `libro/borrador.md` desde el banco |

Nada se publica solo: no hay timer ni cron. `--publicar` es el único camino
hacia Facebook y lo aprieta una persona. Si algún día se automatiza, la
aprobación tiene que seguir estando, como en el proyecto de salud.

## Cuál toca

Lo decide `frases.siguiente`: rota por tema y dentro del tema va en orden, así
que no salen dos días seguidos del mismo tema ni se repite una frase hasta que
el banco entero haya salido. Es determinista, depende de `data/publicadas.json`
y no del reloj: mirarla dos veces el mismo día da la misma frase. Con 81 frases
y un post por día son casi tres meses sin repetir.

## Agregar frases

Se edita el archivo del tema, se corre `revisar_banco.py` hasta que no diga
nada y después `armar_libro.py`. Una prueba exige que el borrador versionado
esté al día con el banco, así que olvidarse se ve en rojo y no en el libro.

Cada frase lleva:

```yaml
  - id: emo-10                  # tres letras del tema y dos dígitos, en orden
    texto: "..."                # lo que va en el flyer: 25 a 180 caracteres
    destacar: [aviso]           # la palabra que va en color. Siempre al menos una
    principio: "..."            # qué sostiene la frase, en una línea
    fuente: "..."               # autor, año y dónde. Sin esto no se publica
    reflexion: >-               # el caption, y la semilla del capítulo
      ...
```

El `principio` y la `fuente` no se publican en el flyer. Están porque el libro
los necesita y porque obligan a saber de dónde sale cada frase antes de
escribirla: es lo que separa una página de psicología de una de frases bonitas.

## Las fuentes

Están verificadas una por una contra la literatura, y donde hubo duda se
recortó la afirmación en vez de redondearla. Dos ejemplos que conviene conocer
porque marcan el criterio: la frase de que preocuparse se paga dos veces cita
el 91% de LaFreniere y Newman, que es lo que el estudio midió, y no añade el
«y salió mejor de lo esperado» que circula pegado a ese dato y que no se pudo
comprobar; la de moverse nombra caminar, yoga y fuerza, que es lo que la
revisión de Noetel sostiene, y no bailar, que no está entre sus resultados.

## Lo que falta

- La página no existe todavía: hay que crearla, sacar el token y llenar el
  `.env`. El `page_id` y el token son de PÁGINA, con `pages_manage_posts`.
- El nombre en `config/pagina.yaml` es provisional. El flyer lo lee de ahí, así
  que cambiarlo es una línea y no tocar el dibujo.
- Las historias, los comentarios y la medición no están. En el proyecto de
  salud existen y se pueden portar; aquí todavía no hacen falta.
