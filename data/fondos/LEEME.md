# Los videos de fondo del reel

**Los archivos de video van en esta misma carpeta** (`data/fondos/`), sueltos,
sin subcarpetas.

    data/fondos/
      LEEME.md      <- este archivo
      clip-01.mp4   <- tus videos, aca
      clip-02.mp4
      ...

## Lo importante: no alcanza con tenerlos en la Mac

El reel **no se arma en tu computadora, se arma en los servidores de GitHub**,
y esa maquina es nueva cada vez: solo tiene lo que esta subido al repositorio.
Un video que esta en tu Mac y no se subio, para el reel no existe.

Asi que: copiarlos a esta carpeta, y despues subirlos.

    git add data/fondos
    git commit -m "Clips de fondo para los reels"
    git push

Esta carpeta es la unica de `data/` que se versiona a proposito (ver el
`.gitignore`). Son unos megas cada uno, no cambian nunca, y es lo unico que
hace que el reel salga sobre paisajes y no sobre el papel de la marca.

## Los clips estan recortados a seis segundos

El reel usa los **primeros cuatro segundos** de cada clip y nada mas. No es
que corte por tramos: cada tramo del reel es una entrada propia de ffmpeg con
`trim=duration` y sin `-ss`, asi que si un clip sale dos veces en el mismo
reel se ven los mismos cuatro segundos las dos veces. Del segundo seis en
adelante no se ve nada nunca; los dos de margen son para el dia que
`video.ESCENA` suba de cuatro.

El 2026-10-26 se recortaron los 54 que habia y **la carpeta paso de 584 MB a
263 MB**. El recorte fue sin recomprimir, asi que los cuatro segundos que se
usan son bit por bit los del original.

Un clip nuevo se recorta al entrar:

    ffmpeg -i tuyo.mp4 -t 6 -c copy data/fondos/nombre-descriptivo.mp4

`-c copy` es la parte importante: copia los cuadros tal cual, sin volver a
comprimir, asi que no se pierde nada de imagen y tarda un segundo. Hay una
prueba que falla si algun clip de la carpeta pasa de seis segundos, para que
la carpeta no vuelva a crecer sin que nadie se entere.

Si alguna vez hace falta bajarla mas, `scripts/achicar_fondos.py` los deja
ademas en 1080x1920 y sin audio -eso si recomprime- y guarda los originales
en `data/fondos/originales/`, que no se sube.

## Como se elige cual va en cada reel

Los clips se eligen por lo que SE VE en ellos. `catalogo.yaml` dice que hay en
cada uno -lluvia, mar, niebla- y `src/fondos.py` dice que busca cada capitulo:
uno de duelo arranca con la lluvia, uno de cambio con el mar.

Importa que los primeros sean los que mejor van, porque el reel cambia de clip
cada cuatro segundos y los primeros son los que mas se ven.

**Un clip sin catalogar se usa igual**, solo que sin preferencia. Asi se puede
subir uno nuevo sin tener que tocar el catalogo el mismo dia. Cuando lo
agregues, avisame y lo miro: necesito VER el clip para saber que etiquetas
ponerle.

El nombre del archivo es descriptivo a proposito -`lluvia-arbol-gris` y no
`7681527`- porque es lo primero que se lee al mirar la carpeta y al leer el
log de una corrida.

## Que clips sirven

- **Verticales.** El reel es 1080x1920. Uno horizontal entra igual pero se
  recorta por los costados y se pierde medio encuadre.
- **De 900 px de ancho para arriba.** Mas chico se ve pixelado al agrandarlo.
- **mp4, mov, m4v, webm o mkv.**
- **El largo no importa: mandalos como vengan.** Al entrar se recortan a seis
  segundos (ver abajo). Lo que NO pasa es que un clip largo se use por tramos:
  el reel toma siempre los primeros cuatro segundos, aunque el mismo clip
  salga dos veces en el mismo reel.
- **Sin texto, sin logos y sin gente hablando a camara**: encima va el texto
  del reel y compiten.
- **Movimiento lento.** Una rama con viento, agua, nubes. Un dron sobre una
  cascada le gana la atencion a la frase, que es justo al reves de lo que se
  busca.

Con **ocho o diez** ya no se repiten de un reel a otro.

El video se oscurece y se dessatura al armarlo, asi que uno muy claro o muy
saturado queda mejor de lo que parece al mirarlo suelto.

## La otra forma: que se bajen solos

Si no queres juntarlos a mano, `scripts/fondos.py` los baja de Pexels. Necesita
una clave gratuita (https://www.pexels.com/api/) cargada como secreto del
repositorio con el nombre `PEXELS_API_KEY`, y a partir de ahi el flujo del reel
los baja solo la primera vez y los reusa.

Las dos formas conviven: lo que haya en esta carpeta se usa, y lo que se baje
se suma.
