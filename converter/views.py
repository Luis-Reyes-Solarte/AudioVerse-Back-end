"""Vistas de la API de conversión de audio."""

import base64
import os

from django.utils.text import get_valid_filename
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AudioConversionRequestSerializer
from .services import (
    SUPPORTED_FORMATS,
    ConversionError,
    convert_audio,
    human_size,
    supported_formats,
)


class AudioFormatListView(APIView):
    """Devuelve los formatos de salida soportados."""

    def get(self, request):
        return Response(supported_formats())


class AudioConvertView(APIView):
    """Convierte un audio subido a cualquier formato soportado.

    Responde con los metadatos del archivo original y del convertido, además
    del audio resultante codificado en base64 (``data_uri``) para que el
    front-end arme la descarga.
    """

    def post(self, request):
        serializer = AudioConversionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        input_file = data['file']
        output_format = data['format']
        fmt = SUPPORTED_FORMATS[output_format]

        try:
            result = convert_audio(
                uploaded_file=input_file,
                output_format=output_format,
                bitrate=data.get('bitrate') or None,
            )
        except ConversionError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_name = data.get('filename') or os.path.splitext(input_file.name or '')[0]
        base_name = get_valid_filename(base_name).strip() or 'audio'
        output_name = f'{base_name}.{output_format}'
        converted_bytes = result['data']

        encoded = base64.b64encode(converted_bytes).decode('ascii')

        return Response({
            'original': {
                'name': input_file.name,
                'size': input_file.size,
                'size_human': human_size(input_file.size),
                'format': os.path.splitext(input_file.name or '')[1].lstrip('.').lower() or None,
                **result['original'],
            },
            'converted': {
                'name': output_name,
                'size': len(converted_bytes),
                'size_human': human_size(len(converted_bytes)),
                'format': output_format,
                'mime': fmt['mime'],
                'data_uri': f'data:{fmt["mime"]};base64,{encoded}',
                **result['converted'],
            },
        })
