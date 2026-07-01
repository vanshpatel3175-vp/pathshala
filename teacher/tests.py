from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import SchoolAdminProfile, Branch, Teacher
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
        # Create Django User (TEACHER role)
        self.teacher_user = User.objects.create_user(
            username="john.doe@testschool.com",
            email="john.doe@testschool.com",
            password="teacherpassword",
            first_name="John",
            last_name="Doe"
        )
        from super_admin.models import Role, SchoolRole
        role_obj, _ = Role.objects.get_or_create(role_name='TEACHER')
        school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=self.institution)
        # Create Teacher Record
        self.teacher_record = Teacher.objects.create(
            user=self.teacher_user,
            school_role=school_role,
            branch=self.branch,
            name="John Doe",
            email="john.doe@testschool.com",
            status="active"
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
        response = self.client.post(reverse('login'), {
            'email': 'john.doe@testschool.com',
            'password': 'teacherpassword'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_teacher_login_failure(self):
        response = self.client.post(reverse('login'), {
            'email': 'john.doe@testschool.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200) # Re-renders login page

    def test_teacher_dashboard_requires_login(self):
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

    def test_teacher_dashboard_denied_for_non_teachers(self):
        self.client.login(username='staff@testschool.com', password='staffpassword')
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'), target_status_code=302)

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

    def test_teacher_login_url_redirects_to_login(self):
        response = self.client.get(reverse('teacher_login'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
