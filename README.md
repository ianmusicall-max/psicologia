# Frases de psicología · página de Facebook y borrador del libro

Un banco de frases de psicología que alimenta dos cosas a la vez: los posts
diarios de la página y el manuscrito del libro. **No son dos proyectos.** Cada
frase se escribe una vez, con el principio que la sostiene y la fuente al lado,
y de ahí salen el flyer, el caption y el capítulo. Si se escribieran por
separado, el libro terminaría contradiciendo a la página.

La página es de amor propio y vínculos: desarrollar el amor propio, recuperar
el amor de la pareja actual, qué hacer con una ex pareja, encontrar a alguien y
resolver problemas de comunicación. Son 14 temas y 113 frases, y están
repartidos en dos ejes.

## Cómo está armado

```
frases/        un archivo por tema = un capítulo del libro (14 temas, 113 frases)
src/frases.py  lee el banco, lo valida contra la línea editorial y dice cuál toca
src/diseno.py  el flyer: 1080x1350, papel cálido, la frase grande, una palabra en color
src/libro.py   arma libro/borrador.md con todas las frases y sus reflexiones
src/facebook.py  publica una foto con su caption. Es el único que habla con Meta
src/bot.py     el bot de Telegram: qué botones hay y qué hace cada uno
src/telegram.py  mandar y recoger de Telegram. Transporte y nada más
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
| `scripts/revisar_token.py` | si el token es de página o de usuario, de cuál, qué permisos y cuándo vence. Solo lee |
| `scripts/token_permanente.py` | convierte el token en uno de página que no vence y lo deja en el `.env` |
| `scripts/bot.py` | el bot de Telegram: muestra la frase que toca y la publica si aprietas el botón |
| `scripts/revisar_instagram.py` | si la página está en condiciones de publicar en Instagram. Solo lee |

Nada se publica solo: no hay timer ni cron. `--publicar` es el único camino
hacia Facebook y lo aprieta una persona. Si algún día se automatiza, la
aprobación tiene que seguir estando, como en el proyecto de salud.

## Los dos ejes

Cada tema declara `eje: nucleo` o `eje: apoyo`.

- **Núcleo**, los siete temas que la página promete: amor propio, límites,
  apego, comunicación, reconexión, ruptura y elegir pareja.
- **Apoyo**, los siete que sostienen a los otros sin ser el motivo por el que
  alguien sigue la página: emociones, ansiedad, hábitos, duelo, pensamientos,
  descanso y sentido. No se publican menos porque valgan menos: se publican
  menos porque no son lo que alguien vino a buscar.

**Dos de cada tres posts son del núcleo**, y la cuota se cumple turno a turno y
no contando al final, así que los temas se intercalan en vez de salir primero
un mes de pareja y después un mes de lo demás. Es una preferencia y no un
filtro: si un día no quedan frases del núcleo sin publicar, sale una de apoyo.
Perder un día de publicación sería mucho peor que romper la proporción.

## Cuál toca

Lo decide `frases.siguiente`: rota por tema dentro de su eje y dentro del tema
va en orden, así que no salen dos días seguidos del mismo tema ni se repite una
frase hasta que el banco entero haya salido. Es determinista, depende de
`data/publicadas.json` y no del reloj: mirarla dos veces el mismo día da la
misma frase. Con 113 frases y un post por día son casi cuatro meses sin
repetir.

## Agregar frases

Se edita el archivo del tema, se corre `revisar_banco.py` hasta que no diga
nada y después `armar_libro.py`. Una prueba exige que el borrador versionado
esté al día con el banco, así que olvidarse se ve en rojo y no en el libro.

Cada frase lleva:

El archivo del tema abre con `tema`, `capitulo`, `eje`, `titulo`, tres
`hashtags` (ninguno puede repetir uno de los fijos de la página) y la `tesis`
del capítulo. Después vienen las frases:

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

## El bot de Telegram

Para no abrir la Terminal. Le escribes cualquier cosa y aparece el menú:

- **Ver la que toca**, que manda el flyer y el texto que saldría, con dos
  botones: Publicar y Saltar.
- **Qué queda**, cuántas faltan por tema.
- **Ya salieron**, las últimas diez, marcando las que se saltearon.

```
.venv/bin/python scripts/bot.py            # escucha hasta que lo cortes
.venv/bin/python scripts/bot.py --una-vez  # atiende lo pendiente y sale
```

Hace falta `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID` en el `.env`. El token lo da
@BotFather; el chat id sale de escribirle al bot y abrir
`https://api.telegram.org/bot<TOKEN>/getUpdates`.

**Nada se publica sin el botón**, y hay una prueba que le manda al bot el texto
«publica todo ya» y exige que no publique nada. Tampoco le hace caso a otro
chat: el nombre de un bot se puede encontrar, y sin ese filtro cualquiera
publicaría en la página.

**Saltar no es posponer**: la frase queda anotada y no vuelve a tocar. Se anota
en el mismo archivo que las publicadas, con el post vacío, porque dos listas
separadas serían dos cosas que consultar y `siguiente` miraría una sola.

## Los estilos del flyer

Cuatro repartos del mismo flyer, todos sobre el crema de la marca. Se eligen
con `estilo:` en `config/pagina.yaml` y `scripts/probar_estilos.py` los dibuja
todos con la misma frase para comparar mirando.

| | |
|---|---|
| `regla` | una raya de acento y el texto a la izquierda |
| `marco` | como la página de un libro: un filete alrededor, centrado |
| `ficha` | papel rayado limpio, con el margen del cuaderno |
| `marcador` | la palabra marcada con resaltador en vez de en color |

Llegaron a ser once. El usuario eligió estos cuatro y los otros siete se
borraron en vez de dejarlos apagados: un renderer sin camino envejece sin que
nadie lo note y después nadie sabe si se puede tocar.

Ninguno lleva fondo oscuro, y eso es una prueba y no una intención: dibuja
cada estilo y mira el fondo de verdad.

## El token

Un token de página **no vence** cuando se deriva de un token de usuario largo,
y ese es el único camino:

```
token corto de usuario
  -> /oauth/access_token (fb_exchange_token)   = token largo de usuario
  -> /me/accounts                              = un token por página, sin vencimiento
```

`scripts/token_permanente.py` hace los dos pasos y con `--guardar` escribe el
resultado en el `.env`. Necesita `FB_APP_ID` y `FB_APP_SECRET`, porque el
intercambio lo firma la app. Si lo que tienes es el token de la página y no el
del usuario, el script lo dice y no inventa nada: hay que volver al Explorador
de Meta y pedir el del usuario.

Un id de app y un id de página son dos números de dieciséis dígitos y se ven
iguales. Usar uno por el otro hace que publicar falle con un error que no dice
cuál de los dos está mal, así que `revisar_token.py` los separa antes.

## Instagram

**Todavía no se publica en Instagram**, y no es solo cuestión de permisos.
`scripts/revisar_instagram.py` dice qué falta, en orden:

1. Una cuenta de Instagram **profesional vinculada a la página**. Eso se hace
   en la configuración de la página en Facebook, no desde acá.
2. El token con `instagram_basic` e `instagram_content_publish`, que no hacen
   falta para Facebook.
3. Una **dirección pública** de donde bajar el flyer. Instagram no acepta que
   le subas el archivo: lo baja de internet. Hoy los flyers viven en el disco
   de la máquina que publica, así que no hay de dónde bajarlos.

El tercero es el que decide: o el proyecto corre en un servidor que sirva las
imágenes, o Instagram se hace a mano.

## Lo que falta

- Poner el `.env` en la máquina desde la que se publica. El `page_id` y el
  token son de PÁGINA, con `pages_manage_posts` y `pages_read_engagement`.
- El nombre en `config/pagina.yaml` es provisional. El flyer lo lee de ahí, así
  que cambiarlo es una línea y no tocar el dibujo.
- Las historias, los comentarios y la medición no están. En el proyecto de
  salud existen y se pueden portar; aquí todavía no hacen falta.
