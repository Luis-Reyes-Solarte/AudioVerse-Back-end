"""Rutas de la app de conversión de audio."""

from django.urls import path

from .views import AudioConvertView, AudioFormatListView

urlpatterns = [
    path('audio/convert/', AudioConvertView.as_view(), name='audio-convert'),
    path('audio/formats/', AudioFormatListView.as_view(), name='audio-formats'),
]
