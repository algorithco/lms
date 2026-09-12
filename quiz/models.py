"""
Quiz Arena Models - Minimal models for 1v1 quiz.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User


class QuizRoom(models.Model):
    """1v1 Quiz room."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    opponent = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='joined_rooms')
    is_active = models.BooleanField(default=True)
    current_question_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quiz_rooms'
        indexes = [
            models.Index(fields=['is_active', 'opponent']),
        ]


class QuizQuestion(models.Model):
    """Question belonging to a room (or global pool)."""
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    option_d = models.CharField(max_length=200)
    correct_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'quiz_questions'
        ordering = ['order']


class QuizAnswer(models.Model):
    """User's answer to a question in a room."""
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='answers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quiz_answers'
        unique_together = ['room', 'user', 'question']  # One answer per user per question
        indexes = [
            models.Index(fields=['room', 'question']),
        ]


class QuizResult(models.Model):
    """Final result for a user in a room."""
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE, related_name='results')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_results')
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quiz_results'
        unique_together = ['room', 'user']