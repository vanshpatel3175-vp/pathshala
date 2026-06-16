from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import SchoolAdminProfile, Branch, Teacher, SchoolUser

User = get_user_model()

class TeacherRegistrationAndLoginTest(TestCase):
    def setUp(self):
        # Create an institution
        self.institution = Institution.objects.create(
            name="Test School",
            email="admin@testschool.com",
            status="active",
            expired_date="2027-01-01T00:00:00Z"
        )
        # Create branch
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        # Create a school admin user and profile so we can perform actions
        self.admin_user = User.objects.create_user(
            username="admin@testschool.com",
            email="admin@testschool.com",
            password="password123",
            role="SCHOOL STAFF"
        )
        self.admin_profile = SchoolAdminProfile.objects.create(
            user=self.admin_user,
            institution=self.institution,
            city="Navsari"
        )
        self.client = Client()
        self.client.login(username="admin@testschool.com", password="password123")

    def test_register_teacher_creates_user_and_profile(self):
        # Pre-register the user first in the Users Directory
        school_user = SchoolUser.objects.create(
            institution=self.institution,
            first_name='Teacher',
            last_name='John',
            email='john@testschool.com',
            dob='1990-01-01',
            city='Navsari'
        )

        # Register that user as a teacher
        response = self.client.post(reverse('school_teachers'), {
            'school_user_id': school_user.id,
            'password': 'teacherpassword',
            'branch_id': self.branch.id,
            'medium_id': ''
        })
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify Teacher model record exists
        teacher = Teacher.objects.filter(email='john@testschool.com').first()
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher.name, 'Teacher John')
        self.assertEqual(teacher.branch, self.branch)
        self.assertTrue(teacher.password is not None and len(teacher.password) > 0)
        
        # Verify User model record exists
        user = User.objects.filter(email='john@testschool.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Teacher')
        self.assertEqual(user.last_name, 'John')
        self.assertEqual(user.role, 'TEACHER')
        
        # Verify the teacher can log in
        login_client = Client()
        login_success = login_client.login(username='john@testschool.com', password='teacherpassword')
        self.assertTrue(login_success)

    def test_edit_school_user_syncs_with_teacher_and_user(self):
        # Pre-register the user
        school_user = SchoolUser.objects.create(
            institution=self.institution,
            first_name='Teacher',
            last_name='John',
            email='john@testschool.com',
            dob='1990-01-01',
            city='Navsari'
        )

        # Register that user as a teacher
        self.client.post(reverse('school_teachers'), {
            'school_user_id': school_user.id,
            'password': 'teacherpassword',
            'branch_id': self.branch.id,
            'medium_id': ''
        })
        
        teacher = Teacher.objects.get(email='john@testschool.com')
        
        # Edit user details via Users Directory
        response = self.client.post(reverse('school_users'), {
            'action': 'edit',
            'user_id': school_user.id,
            'first_name': 'Teacher John Updated',
            'last_name': 'Smith',
            'dob': '1990-01-01',
            'city': 'Navsari',
            'state': 'Gujarat',
            'address': 'Some Address',
            'pincode': '123456'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify Teacher is updated
        teacher.refresh_from_db()
        self.assertEqual(teacher.name, 'Teacher John Updated Smith')
        
        # Verify Django auth User is synchronized
        user = User.objects.filter(email='john@testschool.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Teacher John Updated')
        self.assertEqual(user.last_name, 'Smith')

