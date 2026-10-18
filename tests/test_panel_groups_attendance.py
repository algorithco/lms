"""Tests for Admin Panel Groups, Teachers, Attendance Monitoring, and Telegram Linking."""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.courses.models import StudentGroup
from apps.attendance.models import AttendanceSession, AttendanceRecord


class PanelGroupsAndAttendanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="admin_panel_test@grandec.uz",
            password="TestPassword123!",
            role="admin",
            first_name="Admin",
            last_name="Test",
        )
        self.teacher = User.objects.create_user(
            email="teacher_panel_test@grandec.uz",
            password="TestPassword123!",
            role="teacher",
            first_name="Teacher",
            last_name="Test",
        )
        self.student = User.objects.create_user(
            email="student_panel_test@grandec.uz",
            password="TestPassword123!",
            role="student",
            first_name="Student",
            last_name="Test",
        )

    def test_panel_groups_list_and_create(self):
        self.client.force_authenticate(user=self.admin)
        # Create group
        payload = {
            "name": "IELTS Academic Band 8.0",
            "subject": "english",
            "teacher_id": self.teacher.id,
            "monthly_fee": 600000,
        }
        res = self.client.post("/api/v1/panel/groups/", payload, format="json", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["name"], "IELTS Academic Band 8.0")
        self.assertEqual(res.data["subject"], "english")
        self.assertEqual(res.data["teacher_id"], self.teacher.id)
        self.assertEqual(res.data["monthly_fee"], 600000)
        self.assertTrue(res.data["invite_code"].startswith("GR-"))

        # List groups
        res_list = self.client.get("/api/v1/panel/groups/", HTTP_HOST="localhost")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data["results"]), 1)
        self.assertEqual(res_list.data["results"][0]["name"], "IELTS Academic Band 8.0")

    def test_panel_teachers_list(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/v1/panel/teachers/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        teacher_emails = [t["email"] for t in res.data["results"]]
        self.assertIn("teacher_panel_test@grandec.uz", teacher_emails)
        self.assertIn("admin_panel_test@grandec.uz", teacher_emails)

    def test_panel_attendance_overview_and_export(self):
        group = StudentGroup.objects.create(
            name="Ona tili Attestatsiya 2026",
            subject="uzbek",
            teacher=self.teacher,
            monthly_fee=450000,
        )
        group.students.add(self.student)

        import datetime
        session = AttendanceSession.objects.create(
            group=group,
            teacher=self.teacher,
            lesson_date=datetime.date.today(),
            status=AttendanceSession.Status.FINALIZED,
        )
        AttendanceRecord.objects.create(
            session=session,
            student=self.student,
            status=AttendanceRecord.Status.PRESENT,
        )

        self.client.force_authenticate(user=self.admin)

        # Overview
        res = self.client.get("/api/v1/panel/attendance/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["results"]), 1)
        item = res.data["results"][0]
        self.assertEqual(item["group_id"], group.id)
        self.assertEqual(item["student_count"], 1)
        self.assertEqual(item["total_sessions"], 1)
        self.assertEqual(item["present_count"], 1)
        self.assertEqual(item["attendance_rate"], 100.0)

        # Export Excel
        res_export = self.client.get("/api/v1/panel/attendance/export/", HTTP_HOST="localhost")
        self.assertEqual(res_export.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res_export["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertGreater(len(res_export.content), 1000)

    def test_direct_telegram_link(self):
        self.client.force_authenticate(user=self.admin)
        payload = {"telegram_chat_id": 5582178765}
        res = self.client.post("/api/v1/accounts/link-telegram/", payload, format="json", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["ok"], True)
        self.assertEqual(res.data["telegram_chat_id"], 5582178765)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.telegram_chat_id, 5582178765)
        self.assertIsNotNone(self.admin.telegram_identity_verified_at)

    def test_student_forbidden_from_panel_groups(self):
        self.client.force_authenticate(user=self.student)
        res = self.client.get("/api/v1/panel/groups/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
