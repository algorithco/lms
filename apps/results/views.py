"""
Results views — student results and analytics.

Endpoints:
    GET /api/results/my-results/      — O'quvchining barcha natijalari
    GET /api/results/{id}/detail/     — Natija tafsilotlari
    GET /api/results/stats/           — Umumiy statistika
"""
from django.db.models import Avg, Count, Q, Sum
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudent

from .models import Result
from .access import result_queryset_for_user
from .serializers import (
    ResultDetailSerializer,
    ResultListSerializer,
    ResultStatsSerializer,
)


# ---------------------------------------------------------------------------
# My Results (Student)
# ---------------------------------------------------------------------------

class MyResultsView(generics.ListAPIView):
    """
    GET /api/results/my-results/

    O'quvchining barcha natijalari — kamdan-kamga tartiblangan.
    Agar o'quvchi bo'lmasa, o'z natijalarini ko'radi.
    Agar o'qituvchi bo'lsa, o'z kurslaridagi natijalarni ko'radi.
    Agar admin bo'lsa, barcha natijalarni ko'radi.
    """

    serializer_class = ResultListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return result_queryset_for_user(self.request.user).select_related(
            "test", "course", "student",
        )


# ---------------------------------------------------------------------------
# Result Detail
# ---------------------------------------------------------------------------

class ResultDetailView(generics.RetrieveAPIView):
    """
    GET /api/results/{id}/detail/

    Natija tafsilotlari — qaysi savollarda xato qilganini ko'rsatadi.
    Student faqat o'z natijasini ko'radi.
    """

    serializer_class = ResultDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return result_queryset_for_user(self.request.user)

    def retrieve(self, request: Request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Result Stats
# ---------------------------------------------------------------------------

class ResultStatsView(APIView):
    """
    GET /api/results/stats/

    O'quvchining umumiy statistikasi:
        - Jami testlar soni
        - O'tganlar / o'tmaganlar
        - O'rtacha foiz
        - Eng yuqori foiz
        - Jami sarflangan vaqt
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args, **kwargs) -> Response:
        """Statistika hisoblash."""
        qs = result_queryset_for_user(request.user)

        stats = qs.aggregate(
            total_tests_taken=Count("id"),
            total_passed=Count("id", filter=Q(is_passed=True)),
            total_failed=Count("id", filter=Q(is_passed=False)),
            average_percentage=Avg("percentage"),
            best_percentage=Avg("percentage"),  # will use Max below
            total_time_spent_seconds=Sum("time_taken_seconds"),
        )

        # Best percentage (Max)
        from django.db.models import Max
        best = qs.aggregate(best=Max("percentage"))["best"]
        stats["best_percentage"] = float(best) if best else 0.0
        stats["average_percentage"] = (
            round(float(stats["average_percentage"] or 0), 2)
        )
        stats["total_time_spent_seconds"] = (
            stats["total_time_spent_seconds"] or 0
        )

        serializer = ResultStatsSerializer(data=stats)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
