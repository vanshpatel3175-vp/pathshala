from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import SchoolAdminProfile, Branch, Teacher, SchoolUser
from teacher.models import TeacherProfile

User = get_user_model()

class TeacherAppTests(TestCase):
    def setUp(self):
        # Create Institution
        self.institution = Institution.objects.create(
            name="Test School",
            email="admin@testschool.com",
            status="active",
            expired_date="2027-01-01T00:00:00Z"
        )
        # Create Branch
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        # Create SchoolUser
        self.school_user = SchoolUser.objects.create(
            institution=self.institution,
            first_name="John",
            last_name="Doe",
            email="john.doe@testschool.com"
        )
        # Create Teacher Record
        self.teacher_record = Teacher.objects.create(
            branch=self.branch,
            school_user=self.school_user,
            name=self.school_user.full_name,
            email=self.school_user.email,
            status="active"
        )
        # Create Django User (TEACHER role)
        self.teacher_user = User.objects.create_user(
            username=self.school_user.email,
            email=self.school_user.email,
            password="teacherpassword",
            first_name=self.school_user.first_name,
            last_name=self.school_user.last_name,
            role="TEACHER"
        )
        # Create TeacherProfile
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            teacher=self.teacher_record
        )

        # Create a standard non-teacher user for permission test
        self.staff_user = User.objects.create_user(
            username="staff@testschool.com",
            email="staff@testschool.com",
            password="staffpassword",
            role="SCHOOL STAFF"
        )

        self.client = Client()

    def test_teacher_login_success(self):
        response = self.client.post(reverse('teacher_login'), {
            'email': 'john.doe@testschool.com',
            'password': 'teacherpassword'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_teacher_login_failure(self):
        response = self.client.post(reverse('teacher_login'), {
            'email': 'john.doe@testschool.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200) # Re-renders login page

    def test_teacher_dashboard_requires_login(self):
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('teacher_login'))

    def test_teacher_dashboard_denied_for_non_teachers(self):
        self.client.login(username='staff@testschool.com', password='staffpassword')
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('teacher_login'))

    def test_teacher_dashboard_accessible_for_teachers(self):
        self.client.login(username='john.doe@testschool.com', password='teacherpassword')
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_teacher_profile_view(self):
        self.client.login(username='john.doe@testschool.com', password='teacherpassword')
        response = self.client.get(reverse('teacher_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "john.doe@testschool.com")
        self.assertContains(response, "Main Branch")
