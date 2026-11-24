# serializers.py
import re
from django.conf import settings
from rest_framework import serializers
from .services import SUPPORTED_FORMATS, human_size

BITRATE_RE = re.compile(r'^\d{1,4}k$')


def validate_audio_file_size(value):
    if value.size == 0:
        raise serializers.ValidationError('El archivo está vacío.')

    max_size = getattr(settings, 'MAX_AUDIO_UPLOAD_SIZE', 50 * 1024 * 1024)
    if value.size > max_size:
        raise serializers.ValidationError(
            f'El archivo supera el límite de {human_size(max_size)}.'
        )
    return value


class AudioConversionRequestSerializer(serializers.Serializer):
    """Valida la petición de conversión."""

    file = serializers.FileField(help_text='Archivo de audio de entrada, en cualquier formato.')
    format = serializers.ChoiceField(
        choices=sorted(SUPPORTED_FORMATS.keys()),
        help_text='Formato de audio de salida.',
    )
    bitrate = serializers.CharField(required=False, allow_blank=True, max_length=16)
    filename = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_file(self, value):
        return validate_audio_file_size(value)

    def validate_bitrate(self, value):
        if not value:
            return ''
        value = value.strip().lower()
        if not BITRATE_RE.match(value):
            raise serializers.ValidationError('Bitrate inválido, usa un valor como "192k".')
        return value


class AudioTranscriptionRequestSerializer(serializers.Serializer):
    """Valida la petición de transcripción con IA."""

    file = serializers.FileField(help_text='Archivo de audio a transcribir.')

    def validate_file(self, value):
        return validate_audio_file_size(value)
