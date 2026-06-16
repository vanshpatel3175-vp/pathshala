from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import Branch, Teacher, Student, SchoolUser
from teacher.models import TeacherProfile
from student.models import StudentProfile

User = get_user_model()

class StudentPortalTests(TestCase):
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
        # Create SchoolUser for Student
        self.su_student = SchoolUser.objects.create(
            institution=self.institution,
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@testschool.com"
        )
        # Create Student Directory Record
        self.student_record = Student.objects.create(
            branch=self.branch,
            school_user=self.su_student,
            name=self.su_student.full_name,
            email=self.su_student.email,
            status="active"
        )
        # Create auth User for Student
        self.student_user = User.objects.create_user(
            username=self.su_student.email,
            email=self.su_student.email,
            password="studentpassword",
            first_name=self.su_student.first_name,
            last_name=self.su_student.last_name,
            role="STUDENT"
        )
        # Create StudentProfile
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            student=self.student_record
        )

        # Create a non-student user (School Staff)
        self.staff_user = User.objects.create_user(
            username="staff@testschool.com",
            email="staff@testschool.com",
            password="staffpassword",
            role="SCHOOL STAFF"
        )

        self.client = Client()

    def test_student_login_success(self):
        response = self.client.post(reverse('login'), {
            'email': 'jane.doe@testschool.com',
            'password': 'studentpassword'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('student_dashboard'))

    def test_student_dashboard_requires_login(self):
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

    def test_student_dashboard_denied_for_non_students(self):
        self.client.login(username='staff@testschool.com', password='staffpassword')
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'), target_status_code=302)

    def test_student_dashboard_accessible_for_students(self):
        self.client.login(username='jane.doe@testschool.com', password='studentpassword')
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jane Doe")

    def test_student_profile_view(self):
        self.client.login(username='jane.doe@testschool.com', password='studentpassword')
        response = self.client.get(reverse('student_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "jane.doe@testschool.com")
        self.assertContains(response, "Main Branch")


class DualRolePortalTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(
            name="Test School",
            email="admin@testschool.com",
            status="active",
            expired_date="2027-01-01T00:00:00Z"
        )
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        self.su_dual = SchoolUser.objects.create(
            institution=self.institution,
            first_name="Dual",
            last_name="User",
            email="dual@testschool.com"
        )
        # Create auth User
        self.user = User.objects.create_user(
            username=self.su_dual.email,
            email=self.su_dual.email,
            password="dualpassword",
            first_name=self.su_dual.first_name,
            last_name=self.su_dual.last_name,
            role="TEACHER" # Primary field doesn't restrict dual-profiles
        )
        # Create Teacher Record and Profile
        self.teacher_record = Teacher.objects.create(
            branch=self.branch,
            school_user=self.su_dual,
            name=self.su_dual.full_name,
            email=self.su_dual.email,
            status="active"
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.user,
            teacher=self.teacher_record
        )
        # Create Student Record and Profile
        self.student_record = Student.objects.create(
            branch=self.branch,
            school_user=self.su_dual,
            name=self.su_dual.full_name,
            email=self.su_dual.email,
            status="active"
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.user,
            student=self.student_record
        )

        self.client = Client()

    def test_dual_login_redirects_to_select_profile(self):
        # Hitting login should redirect to /select-profile/
        response = self.client.post(reverse('login'), {
            'email': 'dual@testschool.com',
            'password': 'dualpassword'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('select_profile'))

    def test_profile_selector_renders(self):
        self.client.login(username='dual@testschool.com', password='dualpassword')
        response = self.client.get(reverse('select_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teacher Portal")
        self.assertContains(response, "Student Portal")

    def test_select_teacher_redirects_to_teacher_dashboard(self):
        self.client.login(username='dual@testschool.com', password='dualpassword')
        response = self.client.post(reverse('select_profile'), {
            'role': 'TEACHER'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('teacher_dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'TEACHER')

    def test_select_student_redirects_to_student_dashboard(self):
        self.client.login(username='dual@testschool.com', password='dualpassword')
        response = self.client.post(reverse('select_profile'), {
            'role': 'STUDENT'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('student_dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'STUDENT')

    def test_decorator_blocks_mismatched_active_role(self):
        self.client.login(username='dual@testschool.com', password='dualpassword')
        
        # 1. Set active role to Student
        self.client.post(reverse('select_profile'), {
            'role': 'STUDENT'
        })
        
        # Accessing teacher dashboard should redirect to select-profile
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('select_profile'))
