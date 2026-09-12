"""
Test script for Quiz WebSocket consumer.
Run: python test_quiz_ws.py
Requires: pip install channels[daphne] websockets
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

import django
django.setup()

from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from quiz.consumers import QuizArenaConsumer
from quiz.models import QuizRoom, QuizQuestion

User = get_user_model()


@database_sync_to_async
def create_test_users():
    u1, _ = User.objects.get_or_create(username='testuser1', defaults={'password': 'testpass123'})
    u2, _ = User.objects.get_or_create(username='testuser2', defaults={'password': 'testpass123'})
    return u1, u2


@database_sync_to_async
def create_test_room(creator, opponent=None):
    room = QuizRoom.objects.create(name="Test Room", creator=creator, opponent=opponent)
    # Add 3 questions
    questions_data = [
        ("2+2=?", "3", "4", "5", "6", "B"),
        ("O'zbekiston poytahti?", "Samarqand", "Toshkent", "Buxoro", "Xiva", "B"),
        ("Python da list mi?", "Ha", "Yo'q", "Bilmadim", "Qo'llanmagan", "A"),
    ]
    for i, (text, a, b, c, d, correct) in enumerate(questions_data):
        QuizQuestion.objects.create(
            room=room, text=text, option_a=a, option_b=b, option_c=c, option_d=d,
            correct_option=correct, order=i
        )
    return room


async def test_quiz_flow():
    print("=" * 60)
    print("QUIZ WEBSOCKET CONSUMER TEST")
    print("=" * 60)
    
    # Setup
    user1, user2 = await create_test_users()
    room = await create_test_room(user1)
    
    print(f"Created room: {room.id}")
    print(f"Creator: {user1.username}")
    print(f"Opponent: {user2.username}")
    
    # Test 1: Creator connects and joins
    print("\n[1] Creator connects...")
    comm1 = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), f"/ws/quiz/arena/")
    comm1.scope['user'] = user1
    connected, _ = await comm1.connect()
    assert connected, "Creator failed to connect"
    print("  ✓ Connected")
    
    # Join room
    await comm1.send_json_to({"type": "join", "room_id": str(room.id)})
    response = await comm1.receive_json_from()
    assert response['type'] == 'quiz.joined', f"Join failed: {response}"
    print(f"  ✓ Joined room: {response['room']['id']}")
    
    # Test 2: Opponent connects and joins
    print("\n[2] Opponent connects...")
    comm2 = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), f"/ws/quiz/arena/")
    comm2.scope['user'] = user2
    connected, _ = await comm2.connect()
    assert connected, "Opponent failed to connect"
    print("  ✓ Connected")
    
    await comm2.send_json_to({"type": "join", "room_id": str(room.id)})
    response = await comm2.receive_json_from()
    assert response['type'] == 'quiz.joined', f"Join failed: {response}"
    print(f"  ✓ Joined room: {response['room']['id']}")
    
    # Test 3: Creator starts quiz
    print("\n[3] Creator starts quiz...")
    await comm1.send_json_to({"type": "start"})
    response = await comm1.receive_json_from()
    assert response['type'] == 'quiz.question', f"Start failed: {response}"
    print(f"  ✓ First question received: Q{response['question_index']} - {response['text'][:30]}...")
    
    # Opponent should also receive question
    response2 = await comm2.receive_json_from()
    assert response2['type'] == 'quiz.question'
    print(f"  ✓ Opponent also received question")
    
    # Test 4: Both answer
    print("\n[4] Both users answer...")
    
    # Creator answers correctly (B for Q0)
    await comm1.send_json_to({"type": "answer", "question_index": 0, "answer": "B"})
    result1 = await comm1.receive_json_from()
    assert result1['type'] == 'quiz.answer_result'
    assert result1['is_correct'] == True
    print(f"  ✓ Creator answered: correct={result1['is_correct']}")
    
    # Opponent answers incorrectly (A for Q0)
    await comm2.send_json_to({"type": "answer", "question_index": 0, "answer": "A"})
    result2 = await comm2.receive_json_from()
    assert result2['type'] == 'quiz.answer_result'
    assert result2['is_correct'] == False
    print(f"  ✓ Opponent answered: correct={result2['is_correct']}")
    
    # Both should receive each other's results
    peer_result1 = await comm1.receive_json_from()
    peer_result2 = await comm2.receive_json_from()
    print(f"  ✓ Both received peer results")
    
    # Test 5: Next question auto-advances
    print("\n[5] Auto-advance to next question...")
    q2_1 = await comm1.receive_json_from()
    q2_2 = await comm2.receive_json_from()
    assert q2_1['type'] == 'quiz.question'
    assert q2_1['question_index'] == 1
    print(f"  ✓ Advanced to Q1: {q2_1['text'][:30]}...")
    
    # Answer Q1
    await comm1.send_json_to({"type": "answer", "question_index": 1, "answer": "B"})
    await comm2.send_json_to({"type": "answer", "question_index": 1, "answer": "B"})
    
    # Consume answer results (4 messages: 2 own + 2 peer)
    for _ in range(4):
        await comm1.receive_json_from()
        await comm2.receive_json_from()
    
    # Test 6: Final question and finish
    print("\n[6] Final question and finish...")
    q3_1 = await comm1.receive_json_from()
    assert q3_1['question_index'] == 2
    print(f"  ✓ Final Q2: {q3_1['text'][:30]}...")
    
    await comm1.send_json_to({"type": "answer", "question_index": 2, "answer": "A"})
    await comm2.send_json_to({"type": "answer", "question_index": 2, "answer": "A"})
    
    # Consume answer results
    for _ in range(4):
        await comm1.receive_json_from()
        await comm2.receive_json_from()
    
    # Final results
    final1 = await comm1.receive_json_from()
    final2 = await comm2.receive_json_from()
    assert final1['type'] == 'quiz.result'
    print(f"  ✓ Final results received:")
    for r in final1['results']:
        print(f"      {r['username']}: {r['score']}/{r['total']} ({r['percentage']}%)")
    
    # Cleanup
    await comm1.disconnect()
    await comm2.disconnect()
    
    print("\n" + "=" * 60)
    print("ALL QUIZ TESTS PASSED ✓")
    print("=" * 60)


async def test_edge_cases():
    print("\n" + "=" * 60)
    print("EDGE CASE TESTS")
    print("=" * 60)
    
    user1, user2 = await create_test_users()
    room = await create_test_room(user1)
    
    # Test: Duplicate answer rejected
    print("\n[1] Duplicate answer rejection...")
    comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/quiz/arena/")
    comm.scope['user'] = user1
    await comm.connect()
    await comm.send_json_to({"type": "join", "room_id": str(room.id)})
    await comm.receive_json_from()  # joined
    await comm.send_json_to({"type": "start"})
    await comm.receive_json_from()  # question
    
    # First answer
    await comm.send_json_to({"type": "answer", "question_index": 0, "answer": "B"})
    result1 = await comm.receive_json_from()
    assert result1['is_correct'] == True
    
    # Duplicate answer
    await comm.send_json_to({"type": "answer", "question_index": 0, "answer": "A"})
    error = await comm.receive_json_from()
    assert error['type'] == 'quiz.error'
    print(f"  ✓ Duplicate rejected: {error['message']}")
    
    await comm.disconnect()
    
    # Test: Wrong question index rejected
    print("\n[2] Wrong question index...")
    comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/quiz/arena/")
    comm.scope['user'] = user1
    await comm.connect()
    await comm.send_json_to({"type": "join", "room_id": str(room.id)})
    await comm.receive_json_from()
    await comm.send_json_to({"type": "start"})
    await comm.receive_json_from()  # Q0
    
    # Try to answer Q1 (not current)
    await comm.send_json_to({"type": "answer", "question_index": 1, "answer": "B"})
    error = await comm.receive_json_from()
    assert error['type'] == 'quiz.error'
    print(f"  ✓ Wrong index rejected: {error['message']}")
    
    await comm.disconnect()
    
    print("\n" + "=" * 60)
    print("EDGE CASE TESTS PASSED ✓")
    print("=" * 60)


async def main():
    await test_quiz_flow()
    await test_edge_cases()


if __name__ == "__main__":
    asyncio.run(main())