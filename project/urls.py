"""
URL Configuration for essays and quiz apps.
Add to your project/urls.py
"""
from django.urls import path, include
from essays.views import EssaySubmitView

urlpatterns = [
    # Essay grading endpoint
    path('api/essays/submit/', EssaySubmitView.as_view(), name='essay-submit'),
    
    # Quiz REST endpoints (for room creation, history, etc.)
    path('api/quiz/', include('quiz.urls')),
    
    # Admin, auth, etc.
    # path('admin/', admin.site.urls),
]