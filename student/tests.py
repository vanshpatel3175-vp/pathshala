from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import Branch, Teacher, Student
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
        # Create auth User for Student
        self.student_user = User.objects.create_user(
            username="jane.doe@testschool.com",
            email="jane.doe@testschool.com",
            password="studentpassword",
            first_name="Jane",
            last_name="Doe"
        )
        from super_admin.models import Role, SchoolRole
        role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
        school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=self.institution)
        # Create Student Directory Record
        self.student_record = Student.objects.create(
            user=self.student_user,
            school_role=school_role,
            branch=self.branch,
            name="Jane Doe",
            email="jane.doe@testschool.com",
            status="active"
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
        # Create auth User
        self.user = User.objects.create_user(
            username="dual@testschool.com",
            email="dual@testschool.com",
            password="dualpassword",
            first_name="Dual",
            last_name="User"
        )
        from super_admin.models import Role, SchoolRole
        teacher_role_obj, _ = Role.objects.get_or_create(role_name='TEACHER')
        teacher_school_role, _ = SchoolRole.objects.get_or_create(role=teacher_role_obj, school=self.institution)
        student_role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
        student_school_role, _ = SchoolRole.objects.get_or_create(role=student_role_obj, school=self.institution)
        # Create Teacher Record and Profile
        self.teacher_record = Teacher.objects.create(
            user=self.user,
            school_role=teacher_school_role,
            branch=self.branch,
            name="Dual User",
            email="dual@testschool.com",
            status="active"
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.user,
            teacher=self.teacher_record
        )
        # Create Student Record and Profile
        self.student_record = Student.objects.create(
            user=self.user,
            school_role=student_school_role,
            branch=self.branch,
            name="Dual User",
            email="dual@testschool.com",
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
