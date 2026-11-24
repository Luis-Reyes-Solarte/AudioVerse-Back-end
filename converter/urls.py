# urls.py
from django.urls import path
from .views import AudioConvertView, AudioFormatListView, AudioTranscribeView

urlpatterns = [
    path('audio/convert/', AudioConvertView.as_view(), name='audio-convert'),
    path('audio/formats/', AudioFormatListView.as_view(), name='audio-formats'),
    path('audio/transcribe/', AudioTranscribeView.as_view(), name='audio-transcribe'),
]
