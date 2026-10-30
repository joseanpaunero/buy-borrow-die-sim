# Prompter Discreto (Android)

Teleprompter para Pixel pensado para que **no se note que lees**: el guion flota en un
recuadro pequeño pegado a la cámara frontal, encima de la propia app de cámara del móvil.
Así grabas con la cámara de siempre y la mirada apenas se separa del objetivo.

## Cómo funciona

1. Abre la app, pega tu guion y ajusta tamaño, velocidad, ancho y líneas visibles.
2. Pulsa **Activar flotante sobre la cámara**. La primera vez Android pedirá el permiso
   «Mostrar sobre otras aplicaciones»; actívalo y vuelve a pulsar.
3. Se abre la cámara en modo vídeo y el recuadro aparece arriba, centrado bajo el agujero
   de la cámara frontal. Arrástralo con el icono ⋮⋮ hasta pegarlo al objetivo.
4. Toca el texto para empezar (hay cuenta atrás de 3 s), vuelve a tocar para pausar y
   arrástralo para moverte por el guion. Los botones del recuadro: volver al inicio,
   reproducir/pausar, más lento, más rápido y cerrar.
5. También puedes pausar o cerrar desde la notificación.

Hay además un **modo pantalla completa** para usar el móvil como teleprompter junto a
otra cámara (con opción de espejo para cristales de teleprompter).

## Consejos para que no se note

- Cuanto más estrecho el recuadro y menos líneas (2 o 3), menos se mueve la mirada.
- Letra pequeña y velocidad constante: los ojos casi no se desplazan.
- Aléjate un poco del móvil; a más distancia, menos se nota el ángulo.
- El texto está centrado y la línea de lectura es la de arriba, la más cercana a la cámara.

## Instalar el APK

El APK se compila automáticamente en GitHub Actions (workflow *Build teleprompter APK*).
Entra en la pestaña **Actions** del repositorio, abre la última ejecución y descarga el
artefacto `prompter-discreto-debug`. Copia el `app-debug.apk` al Pixel y ábrelo
(permite «Instalar apps desconocidas» si lo pide).

Para compilarlo en local necesitas Android Studio o el SDK de Android (API 35):

```bash
cd teleprompter-android
./gradlew assembleDebug
# resultado: app/build/outputs/apk/debug/app-debug.apk
```

## Estructura

- `PrompterView.kt`: vista del teleprompter (desplazamiento, desvanecido, espejo, gestos, cuenta atrás).
- `OverlayService.kt`: servicio en primer plano que mantiene el recuadro flotante sobre la cámara.
- `MainActivity.kt`: editor del guion y ajustes.
- `PrompterActivity.kt`: modo pantalla completa.
- `Prefs.kt`: guion y ajustes guardados.

Requisitos: Android 8.0 (API 26) o superior. Probado pensando en Pixel con cámara frontal centrada.
