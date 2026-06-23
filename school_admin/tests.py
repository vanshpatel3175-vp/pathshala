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
        self.assertEqual(student.uid_no, 'UID12345')
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
        self.assertEqual(student_profile.uid_no, 'UID12345')
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
        user = User.objects.filter(email='jane@testschool.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, 'Student Jane Updated')
        self.assertEqual(user.last_name, 'Doe')

    def test_register_dual_role_user(self):
        # Pre-register user in directory
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

        # 2. Register as student (cross-promotion)
        resp2 = self.client.post(reverse('school_students'), {
            'school_user_id': school_user.id,
            'password': 'newdualpassword',
            'branch_id': self.branch.id
        })
        self.assertEqual(resp2.status_code, 302)

        # Verify both Teacher and Student records exist linked to same user
        teacher = Teacher.objects.filter(email_id='dual@testschool.com').first()
        student = Student.objects.filter(email_id='dual@testschool.com').first()
        self.assertIsNotNone(teacher)
        self.assertIsNotNone(student)

        # Verify a single User record exists
        user_count = User.objects.filter(email='dual@testschool.com').count()
        self.assertEqual(user_count, 1)

        # Verify both profiles are linked to the same auth User
        user = User.objects.get(email='dual@testschool.com')
        self.assertEqual(user.teacher_profile.teacher, teacher)
        self.assertEqual(user.student_profile.student, student)


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



