# Next Steps

El MVP actual ya cubre el flujo base del bot y los triggers principales de `wake-up`.

## Ideas Para La Siguiente Etapa

### 1. i18n

Permitir mensajes en más de un idioma para que el bot no dependa solo de textos en español.

Posibles líneas de trabajo:

- definir idioma preferido por usuario
- mover templates de `bot_settings` a una estructura por locale
- traducir onboarding, reminders y briefings

### 2. Briefings Después De Cada Sesión

Extender `post_race_briefing` para que no aplique solo a `Race`.

Posibles líneas de trabajo:

- soportar `Practice`, `Qualifying`, `Sprint` y `Race`
- adaptar placeholders según el tipo de sesión
- decidir qué resumen mostrar cuando no existe podio clásico

### 3. Grilla De Salida En `session_reminder`

Agregar contexto extra antes de la sesión mostrando la grilla o posiciones de salida.

Posibles líneas de trabajo:

- consultar la fuente correcta para la grilla
- decidir cuántas posiciones mostrar
- definir formato compacto para Telegram

## Estado Del Proyecto

En este checkpoint, el MVP ya incluye:

- registro con `/start`
- activación y desactivación de alertas
- selección de timezone con `/set_country`
- `weekly_digest`
- `session_reminder`
- `post_race_briefing`
