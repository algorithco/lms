"""
WebSocket URL routing for Quiz Arena.
"""
from django.urls import re_path
from quiz.consumers import QuizArenaConsumer

websocket_urlpatterns = [
    re_path(r'ws/quiz/arena/$', QuizArenaConsumer.as_asgi()),
]