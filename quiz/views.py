"""
Quiz REST Views - Room management, history (async, SQLite-safe).
"""
import json
import uuid
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from .models import QuizRoom, QuizQuestion, QuizResult


@method_decorator(csrf_exempt, name='dispatch')
class CreateRoomView(LoginRequiredMixin, View):
    """POST /api/quiz/rooms/create/ - Create new quiz room."""
    
    async def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name', '').strip() or f"Quiz {uuid.uuid4().hex[:6]}"
        question_ids = data.get('question_ids', [])  # Optional: pre-selected questions

        room = await self._create_room(request.user, name, question_ids)
        return JsonResponse({
            'id': str(room.id),
            'name': room.name,
            'creator': {'id': room.creator_id, 'username': room.creator.username},
            'websocket_url': f'/ws/quiz/arena/?room_id={room.id}',
        })

    @staticmethod
    @transaction.atomic
    def _create_room(user, name, question_ids):
        room = QuizRoom.objects.create(name=name, creator=user)
        
        if question_ids:
            # Add predefined questions (simplified)
            questions = QuizQuestion.objects.filter(id__in=question_ids).order_by('id')
            for idx, q in enumerate(questions):
                QuizQuestion.objects.create(
                    room=room,
                    text=q.text,
                    option_a=q.option_a,
                    option_b=q.option_b,
                    option_c=q.option_c,
                    option_d=q.option_d,
                    correct_option=q.correct_option,
                    order=idx,
                )
        return room


class RoomDetailView(LoginRequiredMixin, View):
    """GET /api/quiz/rooms/<uuid>/ - Get room details."""
    
    async def get(self, request, room_id):
        room = await self._get_room_with_access(room_id, request.user)
        if not room:
            return JsonResponse({'error': 'Room not found'}, status=404)
        
        return JsonResponse(await self._room_to_dict(room))

    @staticmethod
    def _get_room_with_access(room_id, user):
        try:
            return QuizRoom.objects.select_related('creator', 'opponent').get(
                id=room_id, creator=user
            ) or QuizRoom.objects.select_related('creator', 'opponent').get(
                id=room_id, opponent=user
            )
        except QuizRoom.DoesNotExist:
            return None

    @staticmethod
    async def _room_to_dict(room):
        return {
            'id': str(room.id),
            'name': room.name,
            'creator': {'id': room.creator_id, 'username': room.creator.username},
            'opponent': {'id': room.opponent_id, 'username': room.opponent.username} if room.opponent else None,
            'is_active': room.is_active,
            'current_question_index': room.current_question_index,
            'questions_count': await room.questions.acount(),
            'created_at': room.created_at.isoformat(),
        }


@method_decorator(csrf_exempt, name='dispatch')
class JoinRoomView(LoginRequiredMixin, View):
    """POST /api/quiz/rooms/<uuid>/join/ - Join as opponent."""
    
    async def post(self, request, room_id):
        room = await self._get_joinable_room(room_id, request.user)
        if not room:
            return JsonResponse({'error': 'Room not found or already full'}, status=404)
        
        room.opponent = request.user
        await room.asave(update_fields=['opponent'])
        
        return JsonResponse({
            'id': str(room.id),
            'websocket_url': f'/ws/quiz/arena/?room_id={room.id}',
        })

    @staticmethod
    def _get_joinable_room(room_id, user):
        try:
            room = QuizRoom.objects.select_related('creator', 'opponent').get(id=room_id)
            if room.opponent is None and room.creator_id != user.id:
                return room
            if room.opponent_id == user.id or room.creator_id == user.id:
                return room
            return None
        except QuizRoom.DoesNotExist:
            return None


class RoomQuestionsView(LoginRequiredMixin, View):
    """GET /api/quiz/rooms/<uuid>/questions/ - List questions (for debugging)."""
    
    async def get(self, request, room_id):
        room = await self._get_room_with_access(room_id, request.user)
        if not room:
            return JsonResponse({'error': 'Room not found'}, status=404)
        
        questions = []
        async for q in room.questions.order_by('order').all():
            questions.append({
                'id': q.id,
                'order': q.order,
                'text': q.text,
                'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
                'correct': q.correct_option,
            })
        return JsonResponse({'questions': questions})


class UserQuizHistoryView(LoginRequiredMixin, View):
    """GET /api/quiz/history/ - User's quiz history."""
    
    async def get(self, request):
        results = []
        async for result in QuizResult.objects.select_related('room').filter(user=request.user).order_by('-completed_at')[:50]:
            results.append({
                'room_id': str(result.room_id),
                'room_name': result.room.name,
                'score': result.score,
                'total': result.total_questions,
                'percentage': round((result.score / result.total_questions * 100) if result.total_questions else 0, 1),
                'completed_at': result.completed_at.isoformat(),
            })
        return JsonResponse({'history': results})


class RoomResultsView(LoginRequiredMixin, View):
    """GET /api/quiz/results/<uuid>/ - Final results for a room."""
    
    async def get(self, request, room_id):
        room = await self._get_room_with_access(room_id, request.user)
        if not room:
            return JsonResponse({'error': 'Room not found'}, status=404)
        
        results = []
        async for result in QuizResult.objects.select_related('user').filter(room=room):
            results.append({
                'user_id': result.user_id,
                'username': result.user.username,
                'score': result.score,
                'total': result.total_questions,
                'percentage': round((result.score / result.total_questions * 100) if result.total_questions else 0, 1),
            })
        return JsonResponse({'results': results})