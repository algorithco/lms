"""
Quiz REST API URLs - for room management, history, etc.
"""
from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    # Room management
    path('rooms/create/', views.CreateRoomView.as_view(), name='create-room'),
    path('rooms/<uuid:room_id>/', views.RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<uuid:room_id>/join/', views.JoinRoomView.as_view(), name='join-room'),
    path('rooms/<uuid:room_id>/questions/', views.RoomQuestionsView.as_view(), name='room-questions'),
    
    # History & results
    path('history/', views.UserQuizHistoryView.as_view(), name='quiz-history'),
    path('results/<uuid:room_id>/', views.RoomResultsView.as_view(), name='room-results'),
]