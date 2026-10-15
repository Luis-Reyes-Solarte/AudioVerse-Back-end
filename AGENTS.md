# AGENTS.md — AudioVerse (back-end)

Guía para agentes que trabajen en este repositorio. El repositorio **es** la
carpeta `back-end`; el front-end (Angular) vive en la carpeta hermana
`../front-end` y no forma parte de este repo.

## Descripción

API REST (Django + Django REST Framework) para convertir archivos de audio: el
usuario sube un audio de **cualquier formato**, elige un formato de salida y la
API responde con el archivo convertido más los metadatos del archivo original
(nombre, peso, formato) para que el front-end arme la descarga.

## Stack

- Python 3.13, Django 6.1, Django REST Framework 3.18.
- Base de datos: SQLite (`db.sqlite3`, en desarrollo).
- Conversión de audio: `imageio-ffmpeg` (incluye un binario de ffmpeg estático,
  **no requiere instalar ffmpeg en el sistema**).
- Lectura de metadatos: `mutagen` (Python puro).
- CORS habilitado para el front-end en `http://localhost:4200`.

## Comandos

El entorno virtual está en `.venv` (Windows). Usa siempre su Python:

```powershell
# Instalar dependencias dentro del .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Comprobar el proyecto
.\.venv\Scripts\python.exe manage.py check

# Levantar el servidor de desarrollo (http://localhost:8000)
.\.venv\Scripts\python.exe manage.py runserver
```

No hay modelos, así que normalmente no hacen falta `makemigrations`/`migrate`.

## Estructura

```
config/           # proyecto Django (settings, urls raíz)
converter/        # app de conversión de audio
  services.py     # lógica: formatos soportados, ffmpeg, mutagen
  serializers.py  # validación de entrada / forma de la respuesta
  views.py        # AudioConvertView, AudioFormatListView
  urls.py         # rutas de la app (montadas bajo /api/)
```

## API

- `GET /api/audio/formats/` — lista de formatos de salida soportados (para el
  selector del front-end).
- `POST /api/audio/convert/` — `multipart/form-data`:
  - `file` (obligatorio): audio de entrada, cualquier formato.
  - `format` (obligatorio): formato de salida (validado contra
    `SUPPORTED_FORMATS`).
  - `bitrate` (opcional): p. ej. `192k`; solo aplica a formatos con pérdida.
  - `filename` (opcional): nombre base deseado para el archivo de salida.

  Respuesta `200`:

  ```json
  {
    "original":  { "name": "cancion.wav", "size": 5242880, "size_human": "5.0 MB",
                   "format": "wav", "duration": 214.3, "bitrate": 705600,
                   "sample_rate": 44100, "channels": 2 },
    "converted": { "name": "cancion.mp3", "size": 1048576, "size_human": "1.0 MB",
                   "format": "mp3", "mime": "audio/mpeg", "duration": 214.3,
                   "data_uri": "data:audio/mpeg;base64,..." }
  }
  ```

  Errores: `400` con `{"detail": "..."}` (formato no soportado, archivo vacío,
  archivo que no es audio, o supera el límite).

## Decisiones de diseño (importantes)

- **Sin persistencia**: no se guardan modelos ni archivos en `/media`. Cada
  conversión se procesa en un directorio temporal (`tempfile`) que se borra
  automáticamente. No hay `MEDIA_ROOT`/`MEDIA_URL`.
- **Síncrono**: la conversión ocurre dentro de la petición HTTP. No hay
  Celery/Redis.
- **Entrega en JSON + base64**: el audio convertido viaja en
  `converted.data_uri`; el front-end lo convierte a `Blob` para ofrecer la
  descarga con el nombre que el usuario elija.
- **Formatos de salida**: se definen en `converter/services.py`
  (`SUPPORTED_FORMATS`). Para añadir uno, agrega su entrada con `label`, `mime`,
  `codec` (codificador de ffmpeg) y, si aplica, `lossy` + `default_bitrate`.
- **Límite de subida**: `MAX_AUDIO_UPLOAD_SIZE` en `config/settings.py`
  (50 MB). Se valida en `AudioConversionRequestSerializer`.

## Convenciones

- Mantener la lógica de audio en `converter/services.py`; las vistas solo
  orquestan y arman la respuesta.
- Errores de conversión controlados con `ConversionError` → respuesta `400`.
- Los textos de cara al usuario (mensajes de error, `help_text`) van en español.
- Código y comentarios: seguir el estilo existente.

## Verificación antes de terminar

```powershell
.\.venv\Scripts\python.exe manage.py check
```

Comprueba manualmente una conversión con la Browsable API de DRF
(`http://localhost:8000/api/audio/convert/`) o con `curl`:

```powershell
curl -F "file=@prueba.wav" -F "format=mp3" http://localhost:8000/api/audio/convert/
```
