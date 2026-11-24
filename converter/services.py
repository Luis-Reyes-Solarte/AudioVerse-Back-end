"""Servicios de conversión de audio.

La conversión se apoya en el binario de ffmpeg que incluye ``imageio-ffmpeg``
(no requiere instalar ffmpeg en el sistema) y la lectura de metadatos del
archivo original se hace con ``mutagen`` (Python puro).
"""

import os
import subprocess
import tempfile

import imageio_ffmpeg
from mutagen import File as MutagenFile

# Añadir al inicio de services.py:
import mimetypes
from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# Añadir al final de services.py:
class TranscriptSegmentSchema(BaseModel):
    timestamp: str = Field(description='Marca de tiempo de inicio en formato MM:SS, por ejemplo "00:00" o "01:36".')
    text: str = Field(description='Párrafo transcrito correspondiente a este bloque de tiempo.')


class TranscriptOutputSchema(BaseModel):
    language: str = Field(description='Idioma principal detectado en inglés, por ejemplo "English" o "Spanish".')
    speakers_count: int = Field(description='Número estimado de hablantes distintos en el audio.')
    segments: list[TranscriptSegmentSchema] = Field(
        description='Lista cronológica de párrafos con marca de tiempo cada ~30-50 segundos o cambio de idea.'
    )
    full_text: str = Field(description='Transcripción completa limpia y bien puntuada en párrafos.')


def _format_duration(seconds):
    if not seconds or seconds <= 0:
        return None
    total = int(round(seconds))
    mins, secs = divmod(total, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f'{hours:02d}:{mins:02d}:{secs:02d}'
    return f'{mins:02d}:{secs:02d}'


def transcribe_audio_with_gemini(uploaded_file):
    """Transcribe un archivo de audio usando Gemini API y devuelve metadatos + segmentos."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ConversionError('Falta configurar GEMINI_API_KEY en el archivo .env del servidor.')

    model_name = getattr(settings, 'GEMINI_TRANSCRIPTION_MODEL', 'gemini-2.5-flash')
    _, src_ext = os.path.splitext(uploaded_file.name or '')
    src_ext = src_ext.lower() or '.mp3'

    # Leemos metadatos originales con mutagen
    with tempfile.TemporaryDirectory(prefix='audioverse-meta-') as tmp_dir:
        tmp_path = os.path.join(tmp_dir, f'source{src_ext}')
        with open(tmp_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)
        original_info = _read_audio_info(tmp_path)

    uploaded_file.seek(0)

    # Si supera 18 MB (ej. WAV sin comprimir), optimizamos a MP3 64k antes de enviarlo
    if uploaded_file.size > 18 * 1024 * 1024:
        compressed = convert_audio(uploaded_file, output_format='mp3', bitrate='64k')
        audio_bytes = compressed['data']
        mime_type = 'audio/mpeg'
    else:
        audio_bytes = uploaded_file.read()
        guessed_mime, _ = mimetypes.guess_type(uploaded_file.name or '')
        mime_type = uploaded_file.content_type or guessed_mime or 'audio/mpeg'
        if mime_type == 'application/octet-stream':
            mime_type = 'audio/mpeg'

    client = genai.Client(api_key=api_key)

    prompt = (
        'Transcribe el siguiente archivo de audio con alta precisión, manteniendo el idioma original '
        'en el que se habla, puntuación natural y división en párrafos coherentes con marcas de tiempo (MM:SS).'
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=TranscriptOutputSchema,
                temperature=0.1,
            ),
        )
    except Exception as exc:
        raise ConversionError(f'Error al comunicarse con Gemini API: {exc}')

    if not response.text:
        raise ConversionError('Gemini no devolvió contenido para este audio.')

    parsed = TranscriptOutputSchema.model_validate_json(response.text)

    return {
        'original': {
            'name': uploaded_file.name,
            'size': uploaded_file.size,
            'size_human': human_size(uploaded_file.size),
            'format': src_ext.lstrip('.').lower() or None,
            'duration_formatted': _format_duration(original_info.get('duration')),
            **original_info,
        },
        'transcript': parsed.model_dump(),
    }

#: Bitrate por defecto cuando el usuario no envía uno y el formato tiene pérdida.
DEFAULT_BITRATE = '192k'

#: Formatos de salida soportados. El ``codec`` es el codificador de ffmpeg.
SUPPORTED_FORMATS = {
    'mp3': {
        'label': 'MP3', 'mime': 'audio/mpeg', 'codec': 'libmp3lame',
        'lossy': True, 'default_bitrate': '192k',
    },
    'wav': {
        'label': 'WAV', 'mime': 'audio/wav', 'codec': 'pcm_s16le',
        'lossy': False,
    },
    'flac': {
        'label': 'FLAC', 'mime': 'audio/flac', 'codec': 'flac',
        'lossy': False,
    },
    'ogg': {
        'label': 'OGG', 'mime': 'audio/ogg', 'codec': 'libvorbis',
        'lossy': True, 'default_bitrate': '192k',
    },
    'm4a': {
        'label': 'M4A', 'mime': 'audio/mp4', 'codec': 'aac',
        'lossy': True, 'default_bitrate': '192k',
    },
    'aac': {
        'label': 'AAC', 'mime': 'audio/aac', 'codec': 'aac',
        'lossy': True, 'default_bitrate': '192k',
    },
    'opus': {
        'label': 'OPUS', 'mime': 'audio/opus', 'codec': 'libopus',
        'lossy': True, 'default_bitrate': '128k',
    },
    'wma': {
        'label': 'WMA', 'mime': 'audio/x-ms-wma', 'codec': 'wmav2',
        'lossy': True, 'default_bitrate': '192k',
    },
    'aiff': {
        'label': 'AIFF', 'mime': 'audio/aiff', 'codec': 'pcm_s16be',
        'lossy': False,
    },
    'mp2': {
        'label': 'MP2', 'mime': 'audio/mpeg', 'codec': 'mp2',
        'lossy': True, 'default_bitrate': '192k',
    },
}


class ConversionError(Exception):
    """Error controlado durante la conversión de audio."""


def human_size(num_bytes):
    """Devuelve un tamaño legible, por ejemplo ``4.2 MB``."""
    size = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            if unit == 'B':
                return f'{size:.0f} {unit}'
            return f'{size:.1f} {unit}'
        size /= 1024


def supported_formats():
    """Lista de formatos de salida para poblar el selector del front-end."""
    return [
        {
            'value': key,
            'label': value['label'],
            'mime': value['mime'],
            'lossy': value['lossy'],
        }
        for key, value in SUPPORTED_FORMATS.items()
    ]


def _read_audio_info(path):
    """Lee duración, bitrate, sample rate y canales con mutagen.

    Devuelve un dict vacío si mutagen no reconoce el formato; nunca lanza.
    """
    try:
        audio = MutagenFile(path)
    except Exception:
        return {}

    info = getattr(audio, 'info', None)
    if audio is None or info is None:
        return {}

    data = {}
    length = getattr(info, 'length', None)
    if length:
        data['duration'] = round(float(length), 2)
    bitrate = getattr(info, 'bitrate', None)
    if bitrate:
        data['bitrate'] = int(bitrate)
    sample_rate = getattr(info, 'sample_rate', None)
    if sample_rate:
        data['sample_rate'] = int(sample_rate)
    channels = getattr(info, 'channels', None)
    if channels:
        data['channels'] = int(channels)
    return data


def convert_audio(uploaded_file, output_format, bitrate=None):
    """Convierte ``uploaded_file`` al formato indicado.

    Devuelve un dict con:
      * ``data``: bytes del archivo convertido.
      * ``original``: metadatos del archivo de entrada.
      * ``converted``: metadatos del archivo de salida.
    """
    if output_format not in SUPPORTED_FORMATS:
        raise ConversionError(f'Formato no soportado: {output_format}')

    fmt = SUPPORTED_FORMATS[output_format]
    _, src_ext = os.path.splitext(uploaded_file.name or '')
    src_ext = src_ext.lower() or '.bin'

    with tempfile.TemporaryDirectory(prefix='audioverse-') as tmp_dir:
        input_path = os.path.join(tmp_dir, f'input{src_ext}')
        output_path = os.path.join(tmp_dir, f'output.{output_format}')

        with open(input_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        original_info = _read_audio_info(input_path)

        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-y', '-hide_banner', '-loglevel', 'error',
            '-i', input_path,
            '-vn',
            '-c:a', fmt['codec'],
        ]
        if fmt['lossy']:
            command += ['-b:a', bitrate or fmt.get('default_bitrate', DEFAULT_BITRATE)]
        command.append(output_path)

        process = subprocess.run(command, capture_output=True)
        if process.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            stderr = (process.stderr or b'').decode('utf-8', 'ignore').strip()
            last_line = stderr.splitlines()[-1] if stderr else 'No se pudo procesar el archivo.'
            raise ConversionError(f'No se pudo convertir el archivo: {last_line}')

        with open(output_path, 'rb') as converted_file:
            converted_bytes = converted_file.read()

        converted_info = _read_audio_info(output_path)

    return {
        'data': converted_bytes,
        'original': original_info,
        'converted': converted_info,
    }
