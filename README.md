# AudioVerse — Back-end API

> \[!IMPORTANT\] > **Repositorio del Front-end:** Esta es la API REST del proyecto. Para ejecutar la interfaz gráfica completa creada en Angular 22, visita el repositorio del front-end aquí: [**🔗 Enlace al repositorio del Front-end**](https://github.com/Luis-Reyes-Solarte/AudioVerse-Front-end.git) _(reemplaza esta URL con tu enlace real)_.

## De qué trata

**AudioVerse Back-end** es una API REST desarrollada con **Django** y **Django REST Framework (DRF)** diseñada para procesar archivos de audio de forma efímera y segura (sin almacenamiento permanente en disco ni base de datos):

1. **Conversión de formatos de audio:** Recibe un archivo en cualquier formato, extrae sus metadatos técnicos originales y lo transcodifica al formato deseado (`MP3`, `WAV`, `FLAC`, `OGG`, `M4A`, `AAC`, `OPUS`, `WMA`, `AIFF`, `MP2`) devolviendo tanto los metadatos comparativos como el archivo listo para descarga.

2. **Transcripción inteligente con IA:** Analiza el audio mediante **Google Gemini API** (`gemini-2.5-flash` con respaldo automático a modelos ligeros ante picos de demanda) y devuelve una transcripción estructurada con detección de idioma, conteo estimado de hablantes y segmentos con marcas de tiempo (`MM:SS`).

## Tecnologías usadas

-   **Python** 3.11+

-   **Django** & **Django REST Framework (DRF)**

-   **imageio-ffmpeg** (binario integrado de `ffmpeg`, sin necesidad de instalación global en el sistema operativo)

-   **mutagen** (lectura de duración, bitrate, sample rate y canales)

-   **google-genai** & **Pydantic** (transcripción con salidas estructuradas en JSON Schema)

-   **python-dotenv** (gestión de variables de entorno)

## Requisitos previos

-   Python `3.11` o superior.

-   `pip` y `venv` instalados.

-   Una clave de API válida de **Google AI Studio (Gemini API)**.

## Instalación y Configuración

1. **Clonar el repositorio y entrar al directorio:**

```
git clone https://github.com/tu-usuario/audioverse-backend.git
cd audioverse-backend

```

2. **Crear y activar un entorno virtual:**

```
# En Windows
python -m venv venv
venv\Scripts\activate

# En Linux / macOS
python3 -m venv venv
source venv/bin/activate

```

3. **Instalar las dependencias:**

```
pip install django djangorestframework django-cors-headers imageio-ffmpeg mutagen google-genai pydantic python-dotenv

```

4. **Configurar las variables de entorno (`.env`):**

Crea un archivo `.env` en la raíz del proyecto (al mismo nivel que `manage.py`) con las siguientes variables:

```
GEMINI_API_KEY=tu_clave_de_google_ai_studio_aqui
GEMINI_TRANSCRIPTION_MODEL=gemini-2.5-flash

```

5. **Ejecutar migraciones e iniciar el servidor de desarrollo:**

```
python manage.py migrate
python manage.py runserver

```

La API quedará disponible por defecto en `http://127.0.0.1:8000/`.

## Endpoints de la API

| Método | Ruta                     | Descripción                                                                                                                                                                   |
| ------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/audio/formats/`    | Devuelve la lista de formatos de salida soportados (`value`, `label`, `mime`, `lossy`).                                                                                       |
| `POST` | `/api/audio/convert/`    | Recibe `file`, `format` (y opcionalmente `bitrate` y `filename`) vía `multipart/form-data`. Devuelve metadatos de `original` y `converted` junto con el `data_uri` en Base64. |
| `POST` | `/api/audio/transcribe/` | Recibe `file` vía `multipart/form-data`, optimiza el peso si supera los 18 MB y devuelve la transcripción estructurada en bloques con marcas de tiempo.                       |

## Arquitectura del Módulo Principal

```
├── serializers.py   # Validación de tamaño (máx. 50 MB), formatos de salida y patrón de bitrate.
├── services.py      # Lógica de transcodificación con ffmpeg, lectura con mutagen e integración con Gemini API.
├── views.py         # Controladores REST (AudioFormatListView, AudioConvertView, AudioTranscribeView).
└── urls.py          # Definición de rutas de la API.

```
