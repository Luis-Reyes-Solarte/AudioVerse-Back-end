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
