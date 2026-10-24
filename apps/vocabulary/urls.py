from django.urls import path
from .views import (
    generate_vocabulary_view,
    vocabulary_packs_list_view,
    assign_vocabulary_homework_view,
    spaced_repetition_quiz_view,
    spaced_repetition_submit_view,
)

app_name = "vocabulary"

urlpatterns = [
    path("generate/", generate_vocabulary_view, name="generate"),
    path("packs/", vocabulary_packs_list_view, name="packs_list"),
    path("assign-homework/", assign_vocabulary_homework_view, name="assign_homework"),
    path("spaced-repetition/quiz/", spaced_repetition_quiz_view, name="spaced_quiz"),
    path("spaced-repetition/submit/", spaced_repetition_submit_view, name="spaced_submit"),
]
