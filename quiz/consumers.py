"""
Quiz Arena WebSocket Consumer - SQLite-safe, race-condition free.
"""
import json
import logging
from typing import Dict, Any, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db import transaction

from quiz.models import QuizRoom, QuizQuestion, QuizAnswer, QuizResult

logger = logging.getLogger(__name__)


class QuizArenaConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for 1v1 Quiz Arena.
    
    Groups: quiz_<room_id>
    Events: quiz.join, quiz.start, quiz.question, quiz.answer, quiz.result, quiz.error
    """

    # Message type handlers
    MESSAGE_HANDLERS = {
        'join': 'handle_join',
        'start': 'handle_start',
        'answer': 'handle_answer',
        'leave': 'handle_leave',
    }

    async def connect(self):
        """Accept connection, user auth checked in join handler."""
        self.room_id: Optional[str] = None
        self.room_group_name: Optional[str] = None
        self.user = self.scope.get('user', AnonymousUser())
        await self.accept()
        logger.info(f"WS connected: {self.user}")

    async def disconnect(self, close_code):
        """Leave room group on disconnect."""
        if self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            logger.info(f"WS disconnected from {self.room_group_name}: {self.user}")

    async def receive(self, text_data: str):
        """Route incoming messages to handlers."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Noto'g'ri JSON format")
            return

        msg_type = data.get('type')
        handler_name = self.MESSAGE_HANDLERS.get(msg_type)
        if not handler_name:
            await self.send_error(f"Noma'lum xabar turi: {msg_type}")
            return

        handler = getattr(self, handler_name)
        try:
            await handler(data)
        except Exception as e:
            logger.exception(f"Error handling {msg_type}")
            await self.send_error(f"Server xatosi: {str(e)[:100]}")

    # --- Handlers ---

    async def handle_join(self, data: Dict[str, Any]):
        """Join a quiz room: quiz_<room_id> group."""
        room_id = data.get('room_id')
        if not room_id:
            await self.send_error("room_id majburiy")
            return

        # Verify room exists and user has access
        room = await self._get_room_with_access(room_id)
        if not room:
            await self.send_error("Xona topilmadi yoki kirish huquqi yo'q")
            return

        self.room_id = str(room.id)
        self.room_group_name = f"quiz_{self.room_id}"

        # Join group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Send current room state
        room_data = await self._get_room_state(room)
        await self.send_json({
            'type': 'quiz.joined',
            'room': room_data,
            'user_id': self.user.id,
        })
        logger.info(f"User {self.user.id} joined quiz room {self.room_id}")

    async def handle_start(self, data: Dict[str, Any]):
        """Creator starts the quiz."""
        if not self.room_id:
            await self.send_error("Avval xonaga qo'shiling")
            return

        room = await self._get_room(self.room_id)
        if not room or room.creator_id != self.user.id:
            await self.send_error("Faqat xona egasi boshlashi mumkin")
            return

        if not room.is_active:
            await self.send_error("Xona allaqachon tugagan")
            return

        # Initialize game state
        await self._initialize_game(room)
        
        # Send first question
        question = await self._get_current_question(room)
        if question:
            await self._broadcast_question(room, question)
        else:
            await self._finish_quiz(room)

    async def handle_answer(self, data: Dict[str, Any]):
        """Submit answer for current question."""
        if not self.room_id:
            await self.send_error("Avval xonaga qo'shiling")
            return

        room = await self._get_room(self.room_id)
        if not room or not room.is_active:
            await self.send_error("Xona faol emas")
            return

        question_index = data.get('question_index')
        selected_option = data.get('answer')  # 'A', 'B', 'C', 'D'

        if question_index is None or selected_option not in ('A', 'B', 'C', 'D'):
            await self.send_error("Noto'g'ri javob formati")
            return

        # Verify this is the current question
        if question_index != room.current_question_index:
            await self.send_error("Bu savol allaqachon o'tib ketgan")
            return

        # Save answer atomically
        result = await self._save_answer(room, question_index, selected_option)
        if not result:
            await self.send_error("Javob saqlanmadi (allaqachon javob berilgan)")
            return

        is_correct, correct_option = result

        # Broadcast answer result to room
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'quiz.answer_result',
            'user_id': self.user.id,
            'username': self.user.username,
            'question_index': question_index,
            'selected_option': selected_option,
            'correct_option': correct_option,
            'is_correct': is_correct,
        })

        # Check if both users answered -> move to next question
        await self._check_and_advance(room)

    async def handle_leave(self, data: Dict[str, Any]):
        """Leave room voluntarily."""
        if self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            self.room_id = None
            self.room_group_name = None
        await self.send_json({'type': 'quiz.left'})

    # --- Group event handlers (called by channel_layer.group_send) ---

    async def quiz_answer_result(self, event: Dict[str, Any]):
        """Broadcast answer result to all in room."""
        await self.send_json({
            'type': 'quiz.answer_result',
            **event
        })

    async def quiz_question(self, event: Dict[str, Any]):
        """Broadcast new question to all in room."""
        await self.send_json({
            'type': 'quiz.question',
            **event
        })

    async def quiz_result(self, event: Dict[str, Any]):
        """Broadcast final results."""
        await self.send_json({
            'type': 'quiz.result',
            **event
        })

    async def quiz_error(self, event: Dict[str, Any]):
        """Broadcast error."""
        await self.send_json({
            'type': 'quiz.error',
            'message': event.get('message', 'Noma\'lum xatolik')
        })

    # --- Database operations (all sync_to_async) ---

    @database_sync_to_async
    def _get_room(self, room_id: str) -> Optional[QuizRoom]:
        try:
            return QuizRoom.objects.select_related('creator', 'opponent').get(id=room_id)
        except QuizRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_room_with_access(self, room_id: str) -> Optional[QuizRoom]:
        """Get room if user is creator or opponent."""
        try:
            room = QuizRoom.objects.select_related('creator', 'opponent').get(id=room_id)
            if room.creator_id == self.user.id or room.opponent_id == self.user.id:
                return room
            # Auto-join as opponent if slot empty
            if room.opponent is None and room.creator_id != self.user.id:
                room.opponent = self.user
                room.save(update_fields=['opponent'])
                return room
            return None
        except QuizRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_room_state(self, room: QuizRoom) -> Dict[str, Any]:
        return {
            'id': str(room.id),
            'name': room.name,
            'creator': {'id': room.creator_id, 'username': room.creator.username},
            'opponent': {'id': room.opponent_id, 'username': room.opponent.username} if room.opponent else None,
            'is_active': room.is_active,
            'current_question_index': room.current_question_index,
            'questions_count': room.questions.count(),
        }

    @database_sync_to_async
    def _initialize_game(self, room: QuizRoom):
        """Reset room state for new game."""
        with transaction.atomic():
            room.current_question_index = 0
            room.is_active = True
            room.save(update_fields=['current_question_index', 'is_active', 'updated_at'])
            # Clear previous answers
            QuizAnswer.objects.filter(room=room).delete()
            QuizResult.objects.filter(room=room).delete()

    @database_sync_to_async
    def _get_current_question(self, room: QuizRoom) -> Optional[QuizQuestion]:
        try:
            return room.questions.order_by('order')[room.current_question_index]
        except IndexError:
            return None

    @database_sync_to_async
    def _save_answer(self, room: QuizRoom, question_index: int, selected_option: str) -> Optional[tuple]:
        """
        Atomically save answer. Returns (is_correct, correct_option) or None if duplicate.
        Uses select_for_update to prevent race conditions.
        """
        try:
            with transaction.atomic():
                question = room.questions.select_for_update().get(order=question_index)
                
                # Check if already answered
                if QuizAnswer.objects.filter(room=room, user=self.user, question=question).exists():
                    return None
                
                is_correct = (selected_option == question.correct_option)
                
                QuizAnswer.objects.create(
                    room=room,
                    user=self.user,
                    question=question,
                    selected_option=selected_option,
                    is_correct=is_correct,
                )
                return is_correct, question.correct_option
        except QuizQuestion.DoesNotExist:
            return None

    @database_sync_to_async
    def _check_and_advance(self, room: QuizRoom):
        """Check if both players answered, advance or finish."""
        # Refresh room
        room.refresh_from_db()
        
        current_q = room.questions.filter(order=room.current_question_index).first()
        if not current_q:
            return  # No current question
        
        # Count answers for this question
        answer_count = QuizAnswer.objects.filter(room=room, question=current_q).count()
        participants = 2 if room.opponent_id else 1
        
        if answer_count >= participants:
            # Both answered -> advance
            self._advance_question(room)

    def _advance_question(self, room: QuizRoom):
        """Move to next question or finish quiz."""
        next_index = room.current_question_index + 1
        next_question = room.questions.filter(order=next_index).first()
        
        if next_question:
            room.current_question_index = next_index
            room.save(update_fields=['current_question_index', 'updated_at'])
            # Broadcast next question (async)
            asyncio.create_task(self._broadcast_question(room, next_question))
        else:
            # Quiz finished
            asyncio.create_task(self._finish_quiz(room))

    async def _broadcast_question(self, room: QuizRoom, question: QuizQuestion):
        """Send question to room group."""
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'quiz.question',
            'question_index': question.order,
            'text': question.text,
            'options': {
                'A': question.option_a,
                'B': question.option_b,
                'C': question.option_c,
                'D': question.option_d,
            },
            'time_limit': 30,  # seconds
        })

    async def _finish_quiz(self, room: QuizRoom):
        """Calculate and broadcast final results."""
        room.is_active = False
        await sync_to_async(room.save)(update_fields=['is_active', 'updated_at'])

        # Calculate scores
        results = await self._calculate_results(room)
        
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'quiz.result',
            'results': results,
        })

    @database_sync_to_async
    def _calculate_results(self, room: QuizRoom) -> list:
        """Calculate final scores for both players."""
        participants = [room.creator]
        if room.opponent:
            participants.append(room.opponent)
        
        results = []
        for user in participants:
            answers = QuizAnswer.objects.filter(room=room, user=user)
            score = sum(1 for a in answers if a.is_correct)
            total = answers.count()
            
            QuizResult.objects.update_or_create(
                room=room, user=user,
                defaults={'score': score, 'total_questions': total}
            )
            
            results.append({
                'user_id': user.id,
                'username': user.username,
                'score': score,
                'total': total,
                'percentage': round((score / total * 100) if total else 0, 1),
            })
        return results

    # --- Helpers ---

    async def send_json(self, data: Dict[str, Any]):
        await self.send(text_data=json.dumps(data, ensure_ascii=False))

    async def send_error(self, message: str):
        await self.send_json({'type': 'quiz.error', 'message': message})