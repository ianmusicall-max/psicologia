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
frases/        un archivo por tema = un capítulo del libro (19 temas, 153 frases)
src/frases.py  lee el banco, lo valida contra la línea editorial y dice cuál toca
src/diseno.py  el flyer: 1080x1350, papel cálido, la frase grande, una palabra en color
src/libro.py   arma libro/borrador.md con todas las frases y sus reflexiones
src/video.py   el reel vertical: el texto renglón a renglón, con o sin voz
src/facebook.py  publica una foto con su caption. Es el único que habla con Meta
src/bot.py     el bot de Telegram: la tabla de botones y qué contesta cada uno
src/telegram.py  mandar y recoger de Telegram. Transporte y nada más
config/pagina.yaml  el nombre, la paleta, los hashtags fijos y el pie sensible
LINEA_EDITORIAL.md  qué se puede decir y qué no, y por qué
libro/PLAN.md       cómo pasa el banco a ser un libro
```

## Empezar

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env     # y poner el id y el token de la página
.venv/bin/python scripts/revisar_banco.py     # 153 frases, 0 problemas
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
| `scripts/publicar_turno.py` | publica si a esta hora le toca. Pensado para correr cada hora |
| `scripts/parrilla.py` | el calendario de la rampa y hasta cuándo alcanza el banco. Solo lee |
| `scripts/reel.py` | el reel vertical de una frase. Deja el mp4 en `data/reels`, no publica |
| `scripts/fondos.py` | baja clips de naturaleza a `data/fondos`. Se corre una vez |
| `scripts/medir.py` | qué rindió cada modelo, tema, eje y hora. Solo lee. El mismo texto que contesta el bot |

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
    reflexion: >-               # el caption entero, y la semilla del capítulo
      ...
```

**El caption es la reflexión sola: la frase no se repite ahí.** Ya está en el
flyer, grande, que es lo primero que se ve; repetida se come los dos renglones
que Facebook muestra antes del «Ver más», que son el único lugar donde se puede
decir algo que la imagen todavía no dijo.

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

Para no abrir la Terminal. Le escribes cualquier cosa y aparece el menú, con
un botón por tarea:

| | |
|---|---|
| **Ver la que toca** | manda el flyer y el texto que saldría, con Publicar y Saltar |
| **Qué sale hoy** | la parrilla del día: cada hora, con qué modelo y si ya salió |
| **Qué queda** | cuántas faltan por tema |
| **Ya salieron** | las últimas diez, con su modelo, marcando las que se saltearon |
| **Cómo venimos** | el informe: qué rindió cada modelo, eje, tema y hora |
| **Revisar el banco** | si todo pasa la línea editorial, sin esperar a querer publicar |
| **¿Puedo publicar?** | si el token sirve y si Instagram está vinculado y con permisos |
| **Ver los 4 modelos** | la misma frase dibujada en los cuatro, para mirarlos |
| **Cómo va el libro** | capítulos, frases, palabras y si el borrador quedó viejo |

Los botones salen de **una sola tabla**, `TAREAS` en `src/bot.py`: la etiqueta,
cómo se nombra la tarea en una frase y qué contesta, todo en el mismo renglón.
Escritos aparte, un botón puede quedar sin tarea o una tarea sin botón, y las
dos cosas se descubren apretando; hay una prueba que exige que coincidan.
Escribir el nombre de una tarea en el chat (`hoy`, `/informe`) también la corre.

Cada tarea corre DENTRO del bot y no en su propia unidad de systemd, que es
como lo hace el bot de salud. Allá hace falta: vive en un servidor y lanza
tandas que tardan media hora y cuestan plata, así que tienen que sobrevivir a
que el lector se reinicie. Acá no hay ninguna API paga y la más lenta le
pregunta los números a Facebook post por post, que son segundos, con el bot
corriendo en la misma computadora de quien espera la respuesta. Las tres que
tardan avisan antes de empezar, que es lo que esa separación compraba.

**Ninguna tarea del menú publica.** Lo único que llega a Facebook es la frase
que apruebas con Publicar, y hay dos pruebas que lo exigen: una corre las nueve
tareas con la red tapada y otra lee el AST de `src/bot.py` y comprueba que el
único que nombra a `facebook.publicar` sea el camino del botón.

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

## El reel

El mismo texto en video vertical, con el renglón apareciendo a medida que se
dice. Sale de la frase **y de su reflexión**: una frase sola son seis segundos.

```
scripts/fondos.py                     baja clips de naturaleza (una sola vez)
scripts/reel.py --tema autoestima --fondo data/fondos --voz-ia --musica cama.mp3
scripts/reel.py --ver                 qué haría, sin armar nada
scripts/reel.py --id aut-01           una frase sola: unos 30 s
scripts/reel.py --voz mi-voz.m4a      tu voz leyendo el texto
scripts/reel.py                       sin fondo ni voz: sobre el papel, mudo
```

**Un reel de un minuto es un CAPÍTULO, no una frase larga.** Una frase con su
reflexión son 344 caracteres, unos 30 segundos hablados, y no hay nada que
estirar: el texto es el que es. `--tema` arma el reel con la tesis del
capítulo y las frases que entren —texto ya escrito, ya validado y ya ordenado,
que es lo mismo que hace el libro con ese material—. Da entre 71 y 79 segundos
según el capítulo. Nunca corta una frase por la mitad: entra entera o no entra.

**La música va 17 dB bajo la voz**, que es `volume=0.14`. No es un gusto: está
medido sobre la referencia que mandó el usuario, donde la cama está exactamente
a esa distancia. Sin voz sube al frente. `amix` lleva `normalize=0` porque si
no divide por la cantidad de entradas, la voz sale a la mitad y hay que
compensarla subiéndola, que es como se llega a un reel que satura en el
teléfono. Al final todo pasa por `loudnorm` al volumen de las plataformas, así
que un reel grabado con tu voz y otro hecho con `say` suenan parejo.

**La voz que elige `--voz-mac`** sale de `VOCES`, que arranca por las
masculinas: el audio de la referencia mide 122 Hz de mediana, que es voz de
hombre. Entre dos variantes del mismo nombre gana la mejorada. Si ninguna de la
lista está instalada toma la que haya, porque perder la voz sería peor que no
tener la que se quería.

### La voz de IA

`--voz-ia` usa `gpt-4o-mini-tts` de OpenAI. **Es la única llamada paga de todo
el repo**, y hay una prueba que lo verifica leyendo los archivos: si algún día
aparece otra, tiene que venir a cambiar esa lista y a explicar por qué.

Lo que la hace sonar reflexiva y no a locutor de noticias no es el modelo sino
`INSTRUCCIONES`, que le describe el tono. La voz por defecto es `onyx`, grave y
de hombre, que es lo que mide la referencia.

**No hay un precio escrito en el código, a propósito.** Las fuentes de terceros
no coinciden entre sí y OpenAI no publica una tarifa por carácter para este
modelo. Se anotan los caracteres y los segundos en `data/voz.jsonl` y el costo
se mira en el panel de OpenAI. Es la misma decisión que se tomó en la página de
salud con este mismo modelo: un precio inventado haría que el registro dijera
que gastaste lo que no gastaste.

**Lo que ya se pagó no se vuelve a pagar.** Cada renglón se guarda en
`data/voz_cache` con la pedida entera como llave —modelo, voz, instrucciones y
texto—, así que rehacer un reel, cambiarle el fondo o cambiarle la música no
cuesta nada. Un cambio de una coma sí es otro audio, porque lo único grave
sería devolver el audio de otro texto. La cache se mira ANTES de pedir la
clave: el día que la clave falte o esté vencida es justo cuando más conviene
poder seguir.

`--ver` dice cuántos renglones habría que pedir y cuántos ya están pagados,
antes de gastar nada.

Deja el mp4 en `data/reels`. **No publica**: subirlo es una decisión.

**El fondo son varios clips que se van turnando**, uno cada siete segundos, no
un video de fondo: es lo que hace la referencia y buena parte de por qué no se
hace larga. Los clips salen de `data/fondos`, en un orden que depende del id de
la frase y no del azar, así que volver a armar el mismo reel da el mismo video.

Sobre video **no van el logo ni el pie**, como en la referencia: es el texto
sobre la imagen y nada más. Sobre el papel sí van, porque si no es una hoja en
blanco. El texto también cambia solo: amarillo con contorno sobre un clip —lo
único que se lee pase lo que pase debajo—, tinta sobre el crema de la marca.

`scripts/fondos.py` baja los clips de Pexels, que son de uso libre y no piden
atribución. Necesita una clave gratuita (https://www.pexels.com/api/, un
correo) en `PEXELS_API_KEY`. El camino a mano da lo mismo: buscar en inglés en
https://www.pexels.com/videos/, filtrar Vertical y dejarlos en `data/fondos`.

**Qué cuesta cada parte**, que es lo que decide cómo está hecho:

- El armado es gratis: ffmpeg. No hay ninguna API.
- El fondo puede ser gratis: por defecto no usa ningún video, dibuja el papel
  de la marca con una deriva lenta y le pone el nombre de la página arriba y
  el capítulo abajo. Un clip de naturaleza es una mejora, no un requisito.
- La voz es lo único que se decide. La tuya grabada es gratis y la que mejor
  suena; `say` es gratis y suena sintético; una voz de IA sería la primera API
  paga del repo. Sin voz sale mudo y se lee igual.

**Los dos caminos de voz no se diferencian por el timbre sino por el
sincronismo.** `--voz-mac` lee renglón por renglón, mide cada uno y el
subtítulo cae exacto donde se lo dice. Con un audio entero el tiempo se
reparte proporcional al largo de cada renglón, que es lo más cerca que se
puede estar sin tener los tiempos palabra por palabra.

**Dónde se corta el texto es el problema de verdad**, no el video. Un corte en
mitad de un sintagma —«exigirse con / dureza se vuelve»— se lee mal aunque
entre en pantalla. Se corta primero por las comas y después por el mejor
lugar: nunca después de una palabra que pide la siguiente (`del`, `con`,
`está`) y de preferencia antes de un conector (`que`, `porque`, `si`). Dos
pruebas lo cuidan sobre el banco entero, y una tercera exige que no se pierda
ni una palabra al partir, que es el peor error posible acá: el reel sale, se
ve bien y le falta media idea.

El cuerpo de la letra se mide antes de dibujar, como en el flyer: el más
grande con el que todas las unidades entran en dos renglones. Medido sobre las
153 frases, sale entre 80 y 104 px.

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

## La prueba: una rampa hasta ocho por día

El ritmo sube por etapas: **4 posts los primeros 3 días, 5 los 4 siguientes, 6
los 5 siguientes, y 8 de ahí en adelante**. Está en `arranque` y
`posts_por_dia` en `config/pagina.yaml`.

La rampa se cuenta **desde el primer post publicado**, no desde una fecha
escrita a mano: empieza sola y no hay nada que acordarse de cambiar.

`scripts/parrilla.py` imprime el calendario entero: qué día sale cuánto, a qué
hora y con qué diseño, y hasta cuándo alcanza el banco. Con 113 frases, hasta
el día 19.

Las horas de cada día **se reparten a lo largo del día**, no son las primeras
N de la parrilla: con cuatro posts, las primeras cuatro los dejarían todos
antes del mediodía.

**Cada post del día sale con un estilo distinto**, y el reparto se corre un
lugar cada día. El lugar se cuenta sobre las horas de **ese día** y no sobre
la parrilla completa: contándolo sobre las ocho, un día de cuatro posts caía
en posiciones pares y salían solo dos estilos. Ese corrimiento no es decoración: sin él, las 8 llevarían
siempre el mismo estilo y no habría forma de separar el estilo de la hora. Con
él, en una semana cada estilo sale 14 veces y pasa por las ocho horas.

Sale de la fecha y la hora, no de la cuenta de publicados, para que un día
salteado no corra la rueda y volver a dibujar el mismo post dé el mismo
estilo.

`scripts/publicar_turno.py` corre **cada hora** y sale sin hacer nada si no le
toca, así que se programa una sola vez. Es idempotente: si en esa hora ya
salió un post, no publica otro.

**Es el único camino que publica sin aprobación**, y entró para esto: ocho
aprobaciones diarias en el teléfono no son un sistema que alguien use. El
botón del bot sigue existiendo para publicar a mano.

En la Mac, para que corra cada hora:

```
crontab -e
# y agregar esta línea:
0 * * * * cd ~/psicologia && .venv/bin/python scripts/publicar_turno.py >> data/turnos.log 2>&1
```

### Qué se puede concluir y qué no

Con la rampa, el banco de 113 frases dura **19 días**. A ocho fijos habría
durado 14. Igual es una prueba con fecha de vencimiento: el día 19 hay que
tener frases nuevas escritas.

Con la rampa, la primera semana son 32 posts y no 56: ocho por estilo. Es una
lectura temprana, no una conclusión. El informe muestra la columna de días
porque dice si un estilo vio días buenos y malos o se concentró en pocos.

**No alcanza para comparar temas** en ningún caso: son 14 temas y les tocan 4
posts a cada uno. `scripts/medir.py` marca con «pocos, no concluir» todo grupo
con menos de 7.

Y se usa la **mediana y no el promedio**: un post que se comparte de más tira
el promedio de todo un grupo y hace parecer que gana algo que no ganó.

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

Se publica en las dos con `instagram: true` en `config/pagina.yaml`. El flyer
**no se sube dos veces**: Instagram no acepta que le subas el archivo, pero sí
baja la imagen de una dirección pública, y la foto que Facebook acaba de
publicar ya es una. Así que el orden es: Facebook primero, y la dirección de
esa misma foto va al contenedor de Instagram. **No hace falta ningún
servidor.**

Hacen falta dos cosas que no dependen del código:

1. Una cuenta de Instagram **profesional vinculada a la página**, desde la
   configuración de la página en Facebook.
2. El token con `instagram_basic` e `instagram_content_publish`, que no hacen
   falta para Facebook.

`scripts/revisar_instagram.py` dice si están y, si no, qué hacer. En esta
página las dos estaban: la cuenta es `@jos.delcarpio` y el token trae los dos
permisos, comprobado contra Meta el 2026-10-23. Por eso `instagram: true`.

**Si Instagram falla, el post de Facebook ya salió.** Por eso la frase se
anota como publicada igual y el fallo se avisa aparte. Si se tratara como
turno fallido, la frase quedaría sin anotar y mañana se ofrecería de nuevo, ya
publicada.

## Lo que falta

- Poner el `.env` en la máquina desde la que se publica. El `page_id` y el
  token son de PÁGINA, con `pages_manage_posts` y `pages_read_engagement`.
- El nombre en `config/pagina.yaml` es provisional. El flyer lo lee de ahí, así
  que cambiarlo es una línea y no tocar el dibujo.
- Las historias, los comentarios y la medición no están. En el proyecto de
  salud existen y se pueden portar; aquí todavía no hacen falta.
