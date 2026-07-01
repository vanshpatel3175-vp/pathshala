from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from super_admin.models import Institution
from school_admin.models import SchoolAdminProfile, Branch, Teacher, Student, Holiday, Event, RoleProfile

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
        user = User.objects.create_user(
            username='john@testschool.com',
            email='john@testschool.com',
            password='password123',
            first_name='Teacher',
            last_name='John'
        )
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        school_role_obj, _ = SchoolRole.objects.get_or_create(role=user_role_obj, school=self.institution)
        school_user = RoleProfile.objects.create(
            user=user,
            school_role=school_role_obj,
            name='Teacher John',
            email='john@testschool.com',
            date_of_birth='1990-01-01',
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
        teacher = Teacher.objects.filter(email_id='john@testschool.com').first()
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
        user = User.objects.create_user(
            username='john@testschool.com',
            email='john@testschool.com',
            password='password123',
            first_name='Teacher',
            last_name='John'
        )
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        school_role_obj, _ = SchoolRole.objects.get_or_create(role=user_role_obj, school=self.institution)
        school_user = RoleProfile.objects.create(
            user=user,
            school_role=school_role_obj,
            name='Teacher John',
            email='john@testschool.com',
            date_of_birth='1990-01-01',
            city='Navsari'
        )

        # Register that user as a teacher
        self.client.post(reverse('school_teachers'), {
            'school_user_id': school_user.id,
            'password': 'teacherpassword',
            'branch_id': self.branch.id,
            'medium_id': ''
        })
        
        teacher = Teacher.objects.get(email_id='john@testschool.com')
        
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

    def test_register_student_creates_user_and_profile(self):
        # Pre-register the user first in the Users Directory
        user = User.objects.create_user(
            username='jane@testschool.com',
            email='jane@testschool.com',
            password='password123',
            first_name='Student',
            last_name='Jane'
        )
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        school_role_obj, _ = SchoolRole.objects.get_or_create(role=user_role_obj, school=self.institution)
        school_user = RoleProfile.objects.create(
            user=user,
            school_role=school_role_obj,
            name='Student Jane',
            email='jane@testschool.com',
            date_of_birth='2005-05-05',
            city='Navsari'
        )

        from school_admin.models import SchoolClass
        school_class = SchoolClass.objects.create(
            branch=self.branch,
            name="10th",
            section="A"
        )

        # Register that user as a student
        response = self.client.post(reverse('school_students'), {
            'school_user_id': school_user.id,
            'password': 'studentpassword',
            'branch_id': self.branch.id,
            'school_class_id': school_class.id,
            'parent_full_name': 'Jane Parent',
            'parent_mobile_no': '9876543210',
            'gardian_name': 'Jane Guardian',
            'gardian_mobile_no': '9876543211',
            'uid_no': 'UID12345',
            'roll_no': 'R10',
            'grno': 'GR999'
        })
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify Student model record exists
        student = Student.objects.filter(email_id='jane@testschool.com').first()
        self.assertIsNotNone(student)
        self.assertEqual(student.name, 'Student Jane')
        self.assertEqual(student.branch, self.branch)
        self.assertEqual(student.roll_no, 'R10')
        self.assertEqual(student.roll_number, 'R10')
        self.assertEqual(student.grno, 'GR999')
        
        # Verify User model record exists
        user = User.objects.filter(email='jane@testschool.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'STUDENT')
        
        # Verify StudentProfile model record exists with the form data
        from student.models import StudentProfile
        student_profile = StudentProfile.objects.filter(user=user).first()
        self.assertIsNotNone(student_profile)
        self.assertEqual(student_profile.school_class, school_class)
        self.assertEqual(student_profile.parent_full_name, 'Jane Parent')
        self.assertEqual(student_profile.parent_mobile_no, '9876543210')
        self.assertEqual(student_profile.gardian_name, 'Jane Guardian')
        self.assertEqual(student_profile.gardian_mobile_no, '9876543211')
        self.assertEqual(student_profile.roll_no, 'R10')
        self.assertEqual(student_profile.grno, 'GR999')
        
        # Verify the student can log in
        login_client = Client()
        login_success = login_client.login(username='jane@testschool.com', password='studentpassword')
        self.assertTrue(login_success)

    def test_edit_school_user_syncs_with_student_and_user(self):
        # Pre-register the user
        user = User.objects.create_user(
            username='jane@testschool.com',
            email='jane@testschool.com',
            password='password123',
            first_name='Student',
            last_name='Jane'
        )
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        school_role_obj, _ = SchoolRole.objects.get_or_create(role=user_role_obj, school=self.institution)
        school_user = RoleProfile.objects.create(
            user=user,
            school_role=school_role_obj,
            name='Student Jane',
            email='jane@testschool.com'
        )

        # Register that user as a student
        self.client.post(reverse('school_students'), {
            'school_user_id': school_user.id,
            'password': 'studentpassword',
            'branch_id': self.branch.id
        })
        
        student = Student.objects.get(email_id='jane@testschool.com')
        
        # Edit user details via Users Directory
        self.client.post(reverse('school_users'), {
            'action': 'edit',
            'user_id': school_user.id,
            'first_name': 'Student Jane Updated',
            'last_name': 'Doe',
            'city': 'Navsari',
            'state': 'Gujarat'
        })
        
        # Verify Student is updated
        student.refresh_from_db()
        self.assertEqual(student.name, 'Student Jane Updated Doe')
        
        # Verify Django auth User is synchronized
        user.refresh_from_db()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Student Jane Updated')
        self.assertEqual(user.last_name, 'Doe')

    def test_register_dual_role_user_prevented(self):
        # Pre-register the user
        user = User.objects.create_user(
            username='dual@testschool.com',
            email='dual@testschool.com',
            password='password123',
            first_name='Dual',
            last_name='User'
        )
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        school_role_obj, _ = SchoolRole.objects.get_or_create(role=user_role_obj, school=self.institution)
        school_user = RoleProfile.objects.create(
            user=user,
            school_role=school_role_obj,
            name='Dual User',
            email='dual@testschool.com'
        )

        # 1. Register as teacher
        resp1 = self.client.post(reverse('school_teachers'), {
            'school_user_id': school_user.id,
            'password': 'dualpassword',
            'branch_id': self.branch.id,
            'medium_id': ''
        })
        self.assertEqual(resp1.status_code, 302)

        # 2. Register as student (should be prevented)
        resp2 = self.client.post(reverse('school_students'), {
            'school_user_id': school_user.id,
            'password': 'newdualpassword',
            'branch_id': self.branch.id
        })
        self.assertEqual(resp2.status_code, 302)

        # Verify Teacher record exists but Student does NOT
        teacher = Teacher.objects.filter(email_id='dual@testschool.com').first()
        student = Student.objects.filter(email_id='dual@testschool.com').first()
        self.assertIsNotNone(teacher)
        self.assertIsNone(student)

        # Verify a single User record exists
        user_count = User.objects.filter(email='dual@testschool.com').count()
        self.assertEqual(user_count, 1)


# ─── Holiday Tests ──────────────────────────────────────────────────────────

from datetime import date, timedelta
from school_admin.models import Holiday

class HolidayTests(TestCase):
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
        self.branch2 = Branch.objects.create(
            institution=self.institution,
            name="Second Branch",
            city="Surat",
            status="active"
        )
        # Create a school admin user and profile
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

    def test_holiday_list_view_get(self):
        # Access the holidays management page
        response = self.client.get(reverse('school_holidays'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'school_admin/holidays.html')

    def test_add_holiday_for_specific_branch(self):
        # Create holiday for a specific branch
        start_date = date.today() + timedelta(days=5)
        end_date = date.today() + timedelta(days=6)
        response = self.client.post(reverse('school_holidays'), {
            'action': 'add',
            'holiday_name': 'Diwali Specific',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'branch_name': self.branch.id,
        })
        self.assertRedirects(response, reverse('school_holidays'))
        
        # Verify Holiday created
        holiday = Holiday.objects.filter(holiday_name='Diwali Specific').first()
        self.assertIsNotNone(holiday)
        self.assertEqual(holiday.branch, self.branch)
        self.assertEqual(holiday.start_date, start_date)
        self.assertEqual(holiday.end_date, end_date)

    def test_add_holiday_for_all_branches(self):
        # Create holiday for all branches
        start_date = date.today() + timedelta(days=5)
        end_date = date.today() + timedelta(days=6)
        response = self.client.post(reverse('school_holidays'), {
            'action': 'add',
            'holiday_name': 'Diwali Global',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'add_branch': 'on',
            'branch_name': '',
        })
        self.assertRedirects(response, reverse('school_holidays'))
        
        # Verify Holiday created with branch=None
        holiday = Holiday.objects.filter(holiday_name='Diwali Global').first()
        self.assertIsNotNone(holiday)
        self.assertIsNone(holiday.branch)

    def test_add_holiday_validation_today_vs_yesterday(self):
        # Start date today, end date yesterday
        start_date = date.today()
        end_date = date.today() - timedelta(days=1)
        response = self.client.post(reverse('school_holidays'), {
            'action': 'add',
            'holiday_name': 'Invalid Holiday',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'branch_name': self.branch.id,
        })
        self.assertRedirects(response, reverse('school_holidays'))
        
        # Verify no Holiday was created
        holiday_count = Holiday.objects.filter(holiday_name='Invalid Holiday').count()
        self.assertEqual(holiday_count, 0)

    def test_delete_holiday(self):
        holiday = Holiday.objects.create(
            institution=self.institution,
            branch=self.branch,
            holiday_name='ToDelete',
            start_date=date.today(),
            end_date=date.today()
        )
        response = self.client.post(reverse('school_holidays'), {
            'action': 'delete',
            'holiday_id': holiday.id
        })
        self.assertRedirects(response, reverse('school_holidays'))
        
        # Verify deleted
        self.assertEqual(Holiday.objects.filter(id=holiday.id).count(), 0)


# ─── Event Tests ────────────────────────────────────────────────────────────

from school_admin.models import Event

class EventTests(TestCase):
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
        self.branch2 = Branch.objects.create(
            institution=self.institution,
            name="Second Branch",
            city="Surat",
            status="active"
        )
        # Create a school admin user and profile
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

    def test_event_list_view_get(self):
        # Access the events management page
        response = self.client.get(reverse('school_events'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'school_admin/events.html')

    def test_add_event_for_specific_branch(self):
        # Create event for a specific branch
        start_date = date.today() + timedelta(days=5)
        end_date = date.today() + timedelta(days=6)
        response = self.client.post(reverse('school_events'), {
            'action': 'add',
            'event_name': 'Diwali Specific Event',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'branch_name': self.branch.id,
        })
        self.assertRedirects(response, reverse('school_events'))
        
        # Verify Event created
        event = Event.objects.filter(event_name='Diwali Specific Event').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.branch, self.branch)
        self.assertEqual(event.start_date, start_date)
        self.assertEqual(event.end_date, end_date)

    def test_add_event_for_all_branches(self):
        # Create event for all branches
        start_date = date.today() + timedelta(days=5)
        end_date = date.today() + timedelta(days=6)
        response = self.client.post(reverse('school_events'), {
            'action': 'add',
            'event_name': 'Diwali Global Event',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'add_branch': 'on',
            'branch_name': '',
        })
        self.assertRedirects(response, reverse('school_events'))
        
        # Verify Event created with branch=None
        event = Event.objects.filter(event_name='Diwali Global Event').first()
        self.assertIsNotNone(event)
        self.assertIsNone(event.branch)

    def test_add_event_validation_today_vs_yesterday(self):
        # Start date today, end date yesterday
        start_date = date.today()
        end_date = date.today() - timedelta(days=1)
        response = self.client.post(reverse('school_events'), {
            'action': 'add',
            'event_name': 'Invalid Event',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'branch_name': self.branch.id,
        })
        self.assertRedirects(response, reverse('school_events'))
        
        # Verify no Event was created
        event_count = Event.objects.filter(event_name='Invalid Event').count()
        self.assertEqual(event_count, 0)

    def test_delete_event(self):
        event = Event.objects.create(
            institution=self.institution,
            branch=self.branch,
            event_name='ToDeleteEvent',
            start_date=date.today(),
            end_date=date.today()
        )
        response = self.client.post(reverse('school_events'), {
            'action': 'delete',
            'event_id': event.id
        })
        self.assertRedirects(response, reverse('school_events'))
        
        # Verify deleted
        self.assertEqual(Event.objects.filter(id=event.id).count(), 0)


class UserProfileDateOfBirthSyncTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from super_admin.models import Institution, Role, SchoolRole
        from school_admin.models import Branch
        from datetime import datetime, timedelta
        
        self.User = get_user_model()
        self.institution = Institution.objects.create(
            name="Sync Test School",
            contact_no="1234567890",
            email="sync@school.com",
            expired_date=datetime.now() + timedelta(days=365)
        )
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        self.user = self.User.objects.create_user(
            username="dualrole@test.com",
            email="dualrole@test.com",
            password="password123"
        )
        
        self.student_role, _ = Role.objects.get_or_create(role_name='STUDENT')
        self.student_school_role, _ = SchoolRole.objects.get_or_create(role=self.student_role, school=self.institution)
        
        self.teacher_role, _ = Role.objects.get_or_create(role_name='TEACHER')
        self.teacher_school_role, _ = SchoolRole.objects.get_or_create(role=self.teacher_role, school=self.institution)

    def test_date_of_birth_syncs_across_profiles(self):
        from school_admin.models import Student, Teacher
        from student.models import StudentProfile
        from teacher.models import TeacherProfile
        
        # Create student profile
        student = Student.objects.create(
            user=self.user,
            role=self.student_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Dual Role User",
            email=self.user.email
        )
        student_profile = StudentProfile.objects.create(
            user=self.user,
            student=student,
            date_of_birth="2005-05-15"
        )
        
        self.assertEqual(str(student_profile.date_of_birth), "2005-05-15")
        
        # Create teacher profile for the same user
        teacher = Teacher.objects.create(
            user=self.user,
            role=self.teacher_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Dual Role User",
            email=self.user.email
        )
        teacher_profile = TeacherProfile.objects.create(
            user=self.user,
            teacher=teacher
        )
        
        # The teacher profile should automatically inherit the user's DOB
        self.assertEqual(str(teacher_profile.date_of_birth), "2005-05-15")
        
        # Update DOB on teacher profile
        teacher_profile.date_of_birth = "2005-05-20"
        teacher_profile.save()
        
        # Verify student profile DOB updated as well
        student_profile.refresh_from_db()
        self.assertEqual(str(student_profile.date_of_birth), "2005-05-20")


class RoleWisePermissionTests(TestCase):
    def setUp(self):
        from super_admin.models import Institution, Role, SchoolRole
        from school_admin.models import Branch
        from datetime import datetime, timedelta
        
        self.User = get_user_model()
        self.institution = Institution.objects.create(
            name="Permission Test School",
            contact_no="1234567890",
            email="perm@school.com",
            expired_date=datetime.now() + timedelta(days=365)
        )
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        
        # Student role setup
        self.student_role, _ = Role.objects.get_or_create(role_name='STUDENT')
        self.student_school_role, _ = SchoolRole.objects.get_or_create(role=self.student_role, school=self.institution)
        
        # Teacher role setup
        self.teacher_role, _ = Role.objects.get_or_create(role_name='TEACHER')
        self.teacher_school_role, _ = SchoolRole.objects.get_or_create(role=self.teacher_role, school=self.institution)
        
        # Admin role setup
        self.admin_role, _ = Role.objects.get_or_create(role_name='SCHOOL_ADMIN')
        self.admin_school_role, _ = SchoolRole.objects.get_or_create(role=self.admin_role, school=self.institution)

    def test_dual_role_login_excludes_admin(self):
        from school_admin.models import Student, RoleProfile
        from student.models import StudentProfile
        
        # Create dual-role user (Student + School Admin)
        user = self.User.objects.create_user(
            username="dualadmin@test.com",
            email="dualadmin@test.com",
            password="password123"
        )
        
        # 1. Add STUDENT role profile
        student = Student.objects.create(
            user=user,
            role=self.student_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Dual Admin",
            email=user.email
        )
        student_profile = StudentProfile.objects.create(
            user=user,
            student=student,
            date_of_birth="2005-05-15"
        )
        
        # 2. Add SCHOOL_ADMIN role profile
        RoleProfile.objects.create(
            user=user,
            role=self.admin_school_role.role,
            institution=self.institution,
            role_name='SCHOOL_ADMIN',
            email_id=user.email,
            status='active'
        )
        
        # Login via API
        client = Client()
        response = client.post(reverse('api_login'), {
            'email': 'dualadmin@test.com',
            'password': 'password123'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        roles = data.get('all_roles', [])
        # Should include STUDENT, but NOT SCHOOL_ADMIN
        self.assertIn('STUDENT', roles)
        self.assertNotIn('SCHOOL_ADMIN', roles)

    def test_pure_admin_login_includes_admin(self):
        from school_admin.models import RoleProfile
        
        user = self.User.objects.create_user(
            username="pureadmin@test.com",
            email="pureadmin@test.com",
            password="password123"
        )
        
        RoleProfile.objects.create(
            user=user,
            role=self.admin_school_role.role,
            institution=self.institution,
            role_name='SCHOOL_ADMIN',
            email_id=user.email,
            status='active'
        )
        # Create school admin profile model representation
        SchoolAdminProfile.objects.create(
            user=user,
            institution=self.institution,
            city="Navsari"
        )
        
        client = Client()
        response = client.post(reverse('api_login'), {
            'email': 'pureadmin@test.com',
            'password': 'password123'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        roles = data.get('all_roles', [])
        self.assertIn('SCHOOL_ADMIN', roles)

    def test_verify_api_excludes_pure_admin(self):
        from school_admin.models import RoleProfile
        
        user = self.User.objects.create_user(
            username="pureadmin@test.com",
            email="pureadmin@test.com",
            password="password123"
        )
        RoleProfile.objects.create(
            user=user,
            role=self.admin_school_role.role,
            institution=self.institution,
            role_name='SCHOOL_ADMIN',
            email_id=user.email,
            status='active'
        )
        SchoolAdminProfile.objects.create(
            user=user,
            institution=self.institution,
            city="Navsari"
        )
        
        client = Client()
        # Login to get token
        login_res = client.post(reverse('api_login'), {
            'email': 'pureadmin@test.com',
            'password': 'password123'
        }, content_type='application/json')
        access_token = login_res.json().get('access_token')
        
        # Access verify endpoint
        verify_res = client.post(reverse('api_verify_profile'), {
            'access': access_token
        }, content_type='application/json')
        
        # Access should be denied (403)
        self.assertEqual(verify_res.status_code, 403)

    def test_dual_role_web_login_redirects_correctly(self):
        from school_admin.models import Student, RoleProfile
        from student.models import StudentProfile
        
        user = self.User.objects.create_user(
            username="dualadmin@test.com",
            email="dualadmin@test.com",
            password="password123"
        )
        
        student = Student.objects.create(
            user=user,
            role=self.student_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Dual Admin",
            email=user.email
        )
        StudentProfile.objects.create(
            user=user,
            student=student,
            date_of_birth="2005-05-15"
        )
        
        RoleProfile.objects.create(
            user=user,
            role=self.admin_school_role.role,
            institution=self.institution,
            role_name='SCHOOL_ADMIN',
            email_id=user.email,
            status='active'
        )
        SchoolAdminProfile.objects.create(
            user=user,
            institution=self.institution,
            city="Navsari"
        )
        
        client = Client()
        # Logging in should redirect to student_dashboard (since they have a student role, and admin roles are blocked)
        # instead of school_overview
        response = client.post(reverse('login'), {
            'email': 'dualadmin@test.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('student_dashboard'))

    def test_school_admin_required_blocks_dual_role_user(self):
        from school_admin.models import Student, RoleProfile
        from student.models import StudentProfile
        
        user = self.User.objects.create_user(
            username="dualadmin@test.com",
            email="dualadmin@test.com",
            password="password123"
        )
        
        student = Student.objects.create(
            user=user,
            role=self.student_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Dual Admin",
            email=user.email
        )
        StudentProfile.objects.create(
            user=user,
            student=student,
            date_of_birth="2005-05-15"
        )
        
        RoleProfile.objects.create(
            user=user,
            role=self.admin_school_role.role,
            institution=self.institution,
            role_name='SCHOOL_ADMIN',
            email_id=user.email,
            status='active'
        )
        SchoolAdminProfile.objects.create(
            user=user,
            institution=self.institution,
            city="Navsari"
        )
        
        client = Client()
        client.login(username='dualadmin@test.com', password='password123')
        
        # Try accessing school overview
        response = client.get(reverse('school_overview'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

    def test_teacher_attendance_history_view_resolves_name_field(self):
        from school_admin.models import Teacher, Student, SchoolClass, Attendance
        from teacher.models import TeacherProfile
        from student.models import StudentProfile
        from datetime import date
        
        # Create a teacher user
        teacher_user = self.User.objects.create_user(
            username="teacher@test.com",
            email="teacher@test.com",
            password="password123"
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            role=self.teacher_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Teacher User",
            email=teacher_user.email
        )
        TeacherProfile.objects.create(
            user=teacher_user,
            teacher=teacher
        )
        
        # Create student user
        student_user = self.User.objects.create_user(
            username="student@test.com",
            email="student@test.com",
            password="password123"
        )
        student = Student.objects.create(
            user=student_user,
            role=self.student_school_role.role,
            institution=self.institution,
            branch=self.branch,
            name="Student User",
            email=student_user.email
        )
        StudentProfile.objects.create(
            user=student_user,
            student=student
        )
        
        # Create SchoolClass
        school_class = SchoolClass.objects.create(
            branch=self.branch,
            name="Class 10",
            section="A",
            teacher=teacher
        )
        
        # Create Attendance record
        Attendance.objects.create(
            school_class=school_class,
            student=student,
            teacher=teacher,
            date=date.today(),
            status="present"
        )
        
        # Log in teacher and access attendance history view
        client = Client()
        client.login(username="teacher@test.com", password="password123")
        
        # Set active_role session variable so teacher_required decorator allows access
        session = client.session
        session['active_role'] = 'TEACHER'
        session.save()
        
        response = client.get(reverse('teacher_attendance_history'), {
            'class_id': school_class.id,
            'date': str(date.today())
        })
        
        self.assertEqual(response.status_code, 200)

    def test_add_existing_user_to_another_school_preserves_data(self):
        from super_admin.models import Institution, Role, SchoolRole
        from school_admin.models import RoleProfile
        from datetime import datetime, timedelta
        
        # 1. Create another institution
        school2 = Institution.objects.create(
            name="Second School",
            email="school2@test.com",
            status="active",
            expired_date=datetime.now() + timedelta(days=365)
        )
        
        # Create user with initial details
        user = self.User.objects.create_user(
            username="existing@test.com",
            email="existing@test.com",
            password="original_password",
            first_name="OriginalName",
            last_name="LastName"
        )
        
        # Log in admin for Second School
        admin2 = self.User.objects.create_user(
            username="admin2@test.com",
            email="admin2@test.com",
            password="adminpassword",
            role="SCHOOL STAFF"
        )
        SchoolAdminProfile.objects.create(
            user=admin2,
            institution=school2,
            city="Navsari"
        )
        
        # Let's hit school_users_view POST (add action) to register the same email in School 2
        client = Client()
        client.login(username="admin2@test.com", password="adminpassword")
        
        response = client.post(reverse('school_users'), {
            'action': 'add',
            'first_name': 'NewName',
            'last_name': 'NewLastName',
            'email': 'existing@test.com',
            'password': 'new_password',
            'mobile_no': '9999999999'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify that User model was NOT modified
        user.refresh_from_db()
        self.assertEqual(user.first_name, "OriginalName")
        self.assertEqual(user.last_name, "LastName")
        # Assert password check still passes with the original password, not the new one
        self.assertTrue(user.check_password("original_password"))
        self.assertFalse(user.check_password("new_password"))
        
        # But a new RoleProfile should exist for this user in School 2
        self.assertTrue(RoleProfile.objects.filter(user=user, institution=school2).exists())

    def test_register_shared_student_preserves_central_user_details(self):
        from super_admin.models import Institution, Role, SchoolRole
        from school_admin.models import Student, RoleProfile
        from student.models import StudentProfile
        from datetime import datetime, timedelta
        
        # School 1 (self.institution) already has a USER RoleProfile for this user:
        user = self.User.objects.create_user(
            username="shared_student@test.com",
            email="shared_student@test.com",
            password="original_password",
            first_name="OriginalName",
            last_name="LastName"
        )
        
        # Create a RoleProfile in another institution to make the user 'shared'
        other_inst = Institution.objects.create(
            name="Other Institution",
            email="other@inst.com",
            status="active",
            expired_date=datetime.now() + timedelta(days=365)
        )
        RoleProfile.objects.create(
            user=user,
            role=self.student_school_role.role, # just any role
            institution=other_inst,
            role_name="STUDENT",
            email_id=user.email,
            status="active"
        )
        
        # Also create lookup USER RoleProfile in the current school
        user_role, _ = Role.objects.get_or_create(role_name='USER')
        user_school_role, _ = SchoolRole.objects.get_or_create(role=user_role, school=self.institution)
        su = RoleProfile.objects.create(
            user=user,
            role=user_school_role.role,
            institution=self.institution,
            role_name="USER",
            email_id=user.email,
            status="active"
        )
        
        # Create an admin user and profile for the current school
        admin_user = self.User.objects.create_user(
            username="admin@testschool.com",
            email="admin@testschool.com",
            password="password123",
            role="SCHOOL STAFF"
        )
        SchoolAdminProfile.objects.create(
            user=admin_user,
            institution=self.institution,
            city="Navsari"
        )
        
        # Log in current school admin and try to register them as a student
        client = Client()
        client.login(username="admin@testschool.com", password="password123")
        
        response = client.post(reverse('school_students'), {
            'school_user_id': su.id,
            'password': 'new_student_password',
            'first_name': 'OverwrittenName',
            'last_name': 'OverwrittenLast',
            'branch_id': self.branch.id,
            'mobile_no': '8888888888'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify that User model details are NOT modified
        user.refresh_from_db()
        self.assertEqual(user.first_name, "OriginalName")
        self.assertEqual(user.last_name, "LastName")
        self.assertTrue(user.check_password("original_password"))
        self.assertFalse(user.check_password("new_student_password"))
        
        # But they are successfully registered as a Student in the current school/branch
        self.assertTrue(Student.objects.filter(user=user, branch=self.branch).exists())


class VerifyProfileAPITokenRefreshTest(TestCase):
    def setUp(self):
        # Create user
        self.user = get_user_model().objects.create_user(
            username="student@test.com",
            email="student@test.com",
            password="studentpassword123",
            role="STUDENT"
        )
        # Create institution, branch and profile
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
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
        self.student = Student.objects.create(
            user=self.user,
            role=user_role_obj,
            name='Test Student',
            email_id='student@test.com',
            role_name='STUDENT',
            institution=self.institution,
            branch=self.branch
        )
        self.client = Client()

    def test_verify_profile_with_expired_access_and_valid_refresh(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        # Generate initial tokens
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Create an expired or invalid access token (by adding junk to it, or using an old token)
        invalid_access_token = access_token + "invalidjunk"

        # Make the request to verify endpoint
        response = self.client.post(
            reverse('api_verify_profile'),
            data={
                'access': invalid_access_token,
                'refresh': refresh_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['success_key'], 1)
        self.assertEqual(data['email'], self.user.email)
        # Verify that a new valid access token has been generated and returned
        self.assertNotEqual(data['access_token'], invalid_access_token)
        self.assertNotEqual(data['refresh_token'], refresh_token)
        self.assertTrue(len(data['profiles']) > 0)


class RegisterStaffMemberTest(TestCase):
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
        # School admin user
        self.admin_user = get_user_model().objects.create_user(
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
        # Target user (with USER role profile)
        self.target_user = get_user_model().objects.create_user(
            username="staffmember@test.com",
            email="staffmember@test.com",
            password="staffpassword123"
        )
        # Create USER role
        from super_admin.models import Role, SchoolRole
        user_role_obj, _ = Role.objects.get_or_create(role_name='USER')
        self.profile = RoleProfile.objects.create(
            user=self.target_user,
            role=user_role_obj,
            name='Test Staff User',
            email_id='staffmember@test.com',
            role_name='USER',
            institution=self.institution,
            branch=self.branch
        )
        self.client = Client()
        self.client.login(username="admin@testschool.com", password="password123")

    def test_register_staff_member_success(self):
        # Register them as Trustee
        response = self.client.post(
            reverse('school_others'),
            data={
                'school_user_id': self.profile.id,
                'password': 'newpassword123',
                'role': 'Trustee',
                'branch_id': self.branch.id,
            }
        )
        self.assertEqual(response.status_code, 302)
        from school_admin.models import StaffMember
        self.assertTrue(StaffMember.objects.filter(email_id='staffmember@test.com').exists())


from django.core.files.uploadedfile import SimpleUploadedFile
from super_admin.models import AcademicYear
from school_admin.models import SchoolClass, Medium, Student
from student.models import UserProfile

class StudentImportServiceTest(TestCase):
    def setUp(self):
        # Create Institution
        self.institution = Institution.objects.create(
            name="Import Test School",
            email="admin@importschool.com",
            status="active",
            expired_date="2030-01-01T00:00:00Z"
        )
        # Create Branch
        self.branch = Branch.objects.create(
            institution=self.institution,
            name="Main Branch",
            city="Navsari",
            status="active"
        )
        # Create Academic Year
        self.academic_year = AcademicYear.objects.create(
            name="2024-2025",
            is_active=True
        )
        # Create Medium
        self.medium = Medium.objects.create(
            institution=self.institution,
            name="English"
        )
        # Create Class
        self.school_class = SchoolClass.objects.create(
            branch=self.branch,
            name="Class 1",
            section="A",
            medium=self.medium
        )
        # Create School Admin User and log in
        self.admin_user = User.objects.create_user(
            username="admin@importschool.com",
            email="admin@importschool.com",
            password="password123",
            role="SCHOOL STAFF"
        )
        self.admin_profile = SchoolAdminProfile.objects.create(
            user=self.admin_user,
            institution=self.institution,
            city="Navsari"
        )
        self.client = Client()
        self.client.login(username="admin@importschool.com", password="password123")

    def test_import_valid_csv(self):
        csv_data = (
            "First Name,Middle Name,Last Name,Gender,Date of Birth,Mobile Number,Alternate Mobile,Email,Blood Group,"
            "Admission Number,Roll Number,Admission Date,Academic Year,Class,Section,Medium,Aadhaar Number,UDISE Number,"
            "Category (General/OBC/SC/ST),Religion,Caste,Nationality,City,State,Address Line 1,Address Line 2,Pincode,"
            "Father Name,Father Mobile,Father Occupation,Mother Name,Mother Mobile,Guardian Name,Guardian Mobile,Guardian Relation\n"
            "Rahul,,Patel,Male,15/08/2012,9876543210,,rahul.patel@import.com,B+,ADM-001,1,01/06/2024,2024-2025,Class 1,A,English,123456789012,,General,Hindu,Patel,Indian,Surat,Gujarat,123 Main Street,,395001,Suresh Patel,9876543211,Engineer,Meena Patel,9876543212,,,\n"
        )
        uploaded_file = SimpleUploadedFile("students.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        from school_admin.services.student_import import StudentImportService
        importer = StudentImportService()
        result = importer.run(uploaded_file, self.institution, self.branch)
        
        self.assertEqual(result.success, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.total, 1)
        
        # Verify student created in database
        student = Student.objects.filter(email_id="rahul.patel@import.com").first()
        self.assertIsNotNone(student)
        self.assertEqual(student.name, "Rahul Patel")
        self.assertEqual(student.school_class, self.school_class)
        self.assertEqual(student.academic_year, self.academic_year)
        self.assertEqual(student.gr_number, "ADM-001")
        self.assertEqual(student.roll_number, "1")
        
        # Verify UserProfile personal info
        profile = UserProfile.objects.get(user=student.user)
        self.assertEqual(profile.gender, "Male")
        self.assertEqual(profile.blood_group, "B+")
        self.assertEqual(profile.father_name, "Suresh Patel")

    def test_import_missing_required_field(self):
        # Missing "Last Name"
        csv_data = (
            "First Name,Middle Name,Last Name,Gender,Date of Birth,Mobile Number,Alternate Mobile,Email,Blood Group,"
            "Admission Number,Roll Number,Admission Date,Academic Year,Class,Section,Medium,Aadhaar Number,UDISE Number,"
            "Category (General/OBC/SC/ST),Religion,Caste,Nationality,City,State,Address Line 1,Address Line 2,Pincode,"
            "Father Name,Father Mobile,Father Occupation,Mother Name,Mother Mobile,Guardian Name,Guardian Mobile,Guardian Relation\n"
            "Rahul,, ,Male,15/08/2012,9876543210,,rahul.patel@import.com,B+,ADM-001,1,01/06/2024,2024-2025,Class 1,A,English,123456789012,,General,Hindu,Patel,Indian,Surat,Gujarat,123 Main Street,,395001,Suresh Patel,9876543211,Engineer,Meena Patel,9876543212,,,\n"
        )
        uploaded_file = SimpleUploadedFile("students.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        from school_admin.services.student_import import StudentImportService
        importer = StudentImportService()
        result = importer.run(uploaded_file, self.institution, self.branch)
        
        self.assertEqual(result.success, 0)
        self.assertEqual(result.failed, 1)
        self.assertTrue(any("Last Name" in e.column for e in result.errors))

    def test_import_invalid_academic_year_or_class(self):
        # Academic year "2025-2026" does not exist in DB setup
        csv_data = (
            "First Name,Middle Name,Last Name,Gender,Date of Birth,Mobile Number,Alternate Mobile,Email,Blood Group,"
            "Admission Number,Roll Number,Admission Date,Academic Year,Class,Section,Medium,Aadhaar Number,UDISE Number,"
            "Category (General/OBC/SC/ST),Religion,Caste,Nationality,City,State,Address Line 1,Address Line 2,Pincode,"
            "Father Name,Father Mobile,Father Occupation,Mother Name,Mother Mobile,Guardian Name,Guardian Mobile,Guardian Relation\n"
            "Rahul,,Patel,Male,15/08/2012,9876543210,,rahul.patel@import.com,B+,ADM-001,1,01/06/2024,2025-2026,Class 1,A,English,123456789012,,General,Hindu,Patel,Indian,Surat,Gujarat,123 Main Street,,395001,Suresh Patel,9876543211,Engineer,Meena Patel,9876543212,,,\n"
        )
        uploaded_file = SimpleUploadedFile("students.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        from school_admin.services.student_import import StudentImportService
        importer = StudentImportService()
        result = importer.run(uploaded_file, self.institution, self.branch)
        
        self.assertEqual(result.success, 0)
        self.assertEqual(result.failed, 1)
        self.assertTrue(any("Academic Year" in e.column for e in result.errors))

    def test_import_auto_email_generation(self):
        # Email field is blank -> should auto-generate
        csv_data = (
            "First Name,Middle Name,Last Name,Gender,Date of Birth,Mobile Number,Alternate Mobile,Email,Blood Group,"
            "Admission Number,Roll Number,Admission Date,Academic Year,Class,Section,Medium,Aadhaar Number,UDISE Number,"
            "Category (General/OBC/SC/ST),Religion,Caste,Nationality,City,State,Address Line 1,Address Line 2,Pincode,"
            "Father Name,Father Mobile,Father Occupation,Mother Name,Mother Mobile,Guardian Name,Guardian Mobile,Guardian Relation\n"
            "Rahul,,Patel,Male,15/08/2012,9876543210,,,B+,ADM-999,1,01/06/2024,2024-2025,Class 1,A,English,123456789012,,General,Hindu,Patel,Indian,Surat,Gujarat,123 Main Street,,395001,Suresh Patel,9876543211,Engineer,Meena Patel,9876543212,,,\n"
        )
        uploaded_file = SimpleUploadedFile("students.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        from school_admin.services.student_import import StudentImportService
        importer = StudentImportService()
        result = importer.run(uploaded_file, self.institution, self.branch)
        
        self.assertEqual(result.success, 1)
        
        student = Student.objects.filter(gr_number="ADM-999").first()
        self.assertIsNotNone(student)
        self.assertTrue(student.email_id.startswith("rahul.patel.adm-999"))
        self.assertTrue(student.email_id.endswith("@student.local"))

    def test_import_api_endpoint(self):
        # Post directly to the URL to check view layer integration
        csv_data = (
            "First Name,Middle Name,Last Name,Gender,Date of Birth,Mobile Number,Alternate Mobile,Email,Blood Group,"
            "Admission Number,Roll Number,Admission Date,Academic Year,Class,Section,Medium,Aadhaar Number,UDISE Number,"
            "Category (General/OBC/SC/ST),Religion,Caste,Nationality,City,State,Address Line 1,Address Line 2,Pincode,"
            "Father Name,Father Mobile,Father Occupation,Mother Name,Mother Mobile,Guardian Name,Guardian Mobile,Guardian Relation\n"
            "Rahul,,Patel,Male,15/08/2012,9876543210,,rahul.api@import.com,B+,ADM-888,1,01/06/2024,2024-2025,Class 1,A,English,123456789012,,General,Hindu,Patel,Indian,Surat,Gujarat,123 Main Street,,395001,Suresh Patel,9876543211,Engineer,Meena Patel,9876543212,,,\n"
        )
        uploaded_file = SimpleUploadedFile("students.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(
            reverse('student_import'),
            {'file': uploaded_file, 'branch_id': self.branch.id}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['success'], 1)
        self.assertEqual(data['failed'], 0)
        self.assertEqual(data['total'], 1)







