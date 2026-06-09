from django.core.management.base import BaseCommand
from datetime import datetime, date, time, timezone
from django.contrib.auth.models import User
from dashboard.models import SchoolApplication, Institution, PlatformUser, Inquiry, Meeting, Subscription
from school_admin.models import SchoolAdminProfile, Branch, Student, Teacher, StaffMember, SchoolClass

class Command(BaseCommand):
    help = 'Seeds mock data from the Balsamiq mockups project into the SQLite database.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting existing data...")
        SchoolApplication.objects.all().delete()
        Institution.objects.all().delete()
        PlatformUser.objects.all().delete()
        Meeting.objects.all().delete()
        Subscription.objects.all().delete()
        Inquiry.objects.all().delete()
        SchoolAdminProfile.objects.all().delete()
        Branch.objects.all().delete()
        Student.objects.all().delete()
        Teacher.objects.all().delete()
        StaffMember.objects.all().delete()
        SchoolClass.objects.all().delete()
        
        # Ensure a default admin user exists
        if not User.objects.filter(username="admin").exists():
            self.stdout.write("Creating superuser admin/admin...")
            User.objects.create_superuser("admin", "admin@superadmin.com", "admin")
        
        self.stdout.write("Creating mock data...")

        # 1. School Applications
        app1 = SchoolApplication.objects.create(
            name="AB Eng (CBSC)",
            trust_name="AB Education Trust",
            principal_name="Rohan Patel",
            email="ab@gmail.com",
            contact_number="1010121212",
            board="Central Board of Secondary Education",
            medium="English Medium",
            registration_code="03",
            date_applied=date(2026, 6, 1),
            status="Awaiting Review",
            video_url="https://www.w3schools.com/html/mov_bbb.mp4",
            accreditation_certificate="accreditation_cert_ab_eng.pdf"
        )
        
        app2 = SchoolApplication.objects.create(
            name="VJ Secondary School",
            trust_name="VJ Char Trust",
            principal_name="Vijay Patel",
            email="vijay@vj.com",
            contact_number="2020232323",
            board="Gujarat Secondary Board",
            medium="Gujarati Medium",
            registration_code="05",
            date_applied=date(2026, 5, 25),
            status="Validated",
            video_url="",
            accreditation_certificate="vj_cert.pdf"
        )
        
        app3 = SchoolApplication.objects.create(
            name="HD Primary Unit",
            trust_name="HD Trust",
            principal_name="Harshad Patel",
            email="harshad@hd.com",
            contact_number="3030343434",
            board="ICSE",
            medium="English Medium",
            registration_code="12",
            date_applied=date(2026, 5, 28),
            status="Declined",
            video_url="",
            accreditation_certificate="hd_cert.pdf"
        )

        # 2. Registered Institutions
        inst_rn = Institution.objects.create(
            name="RN",
            type="SCHOOL",
            planned_type="SCHOOL",
            contact_no="965656666",
            email="rn@gmail.com",
            expired_date=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc),
            status="active"
        )
        
        inst_hd = Institution.objects.create(
            name="HD",
            type="SCHOOL",
            planned_type="SCHOOL",
            contact_no="965656666",
            email="hd@gmail.com",
            expired_date=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc),
            status="disabled"
        )

        inst_vj = Institution.objects.create(
            name="VJ",
            type="SCHOOL",
            planned_type="SCHOOL",
            contact_no="565655666",
            email="vj@gmail.com",
            expired_date=datetime(2026, 8, 30, 3, 58, 0, tzinfo=timezone.utc),
            status="active"
        )

        # 3. Platform Users
        PlatformUser.objects.create(
            username="Vansh Patel",
            email="admin@ab.com",
            phone="1010101012",
            date_joined=datetime(2026, 6, 1, 12, 6, 0, tzinfo=timezone.utc),
            role="SCHOOL STAFF"
        )
        
        PlatformUser.objects.create(
            username="kris Patel",
            email="admin@mv.com",
            phone="1212121212",
            date_joined=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc),
            role="SCHOOL STAFF"
        )

        # 4. Inquiries
        inq1 = Inquiry.objects.create(
            first_name="kris",
            last_name="patel",
            school_name="RN",
            contact_no="9173641088",
            email="kris@gmail.com",
            state="Gujarat",
            city="Amalsad",
            status="Approved",
            last_active=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc)
        )
        
        inq2 = Inquiry.objects.create(
            first_name="veer",
            last_name="patel",
            school_name="VJ",
            contact_no="565655666",
            email="veer@gmail.com",
            state="Gujarat",
            city="Navsari",
            status="Pending",
            last_active=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc)
        )

        inq3 = Inquiry.objects.create(
            first_name="vansh",
            last_name="patel",
            school_name="HD",
            contact_no="565655666",
            email="vansh@gmail.com",
            state="Gujarat",
            city="Navsari",
            status="Reject",
            last_active=datetime(2026, 6, 1, 3, 58, 0, tzinfo=timezone.utc)
        )

        # 5. Meetings for Inquiries
        Meeting.objects.create(
            inquiry=inq1,
            meeting_no=1,
            date=date(2026, 6, 1),
            start_time=time(10, 0, 0),
            end_time=time(10, 45, 0),
            title="Overview & Platform Introduction",
            next_meeting_date=date(2026, 6, 5)
        )
        
        Meeting.objects.create(
            inquiry=inq1,
            meeting_no=2,
            date=date(2026, 6, 5),
            start_time=time(15, 30, 0),
            end_time=time(16, 15, 0),
            title="Subscription and Terms Review",
            next_meeting_date=None
        )

        Meeting.objects.create(
            inquiry=inq2,
            meeting_no=1,
            date=date(2026, 6, 2),
            start_time=time(11, 0, 0),
            end_time=time(12, 0, 0),
            title="First Inquiry Call",
            next_meeting_date=None
        )

        # 6. Subscriptions
        for sr in range(2, 7):
            Subscription.objects.create(
                inquiry=inq1,
                sr_no=sr,
                subscription_date=datetime(2026, 2, 1, 3, 58, 0, tzinfo=timezone.utc) if sr==2 else datetime(2026, 8, 30, 3, 58, 0, tzinfo=timezone.utc),
                expired_date=datetime(2026, 7, 30, 4, 0, 0, tzinfo=timezone.utc) if sr==2 else datetime(2027, 8, 30, 3, 58, 0, tzinfo=timezone.utc),
                type_of_planned="Primary School Pack" if sr==2 else "Institution Premium Combo",
                status="okay"
            )

        # 7. School Admin user, branches, students, teachers and staff
        self.stdout.write("Creating school admin mock data...")
        if not User.objects.filter(username="school_admin@rn.com").exists():
            school_user = User.objects.create_user(
                username="school_admin@rn.com",
                email="school_admin@rn.com",
                password="admin",
                first_name="Rohan",
                last_name="Patel",
                is_active=True
            )
            # Link profile to inst_rn (RN)
            SchoolAdminProfile.objects.create(
                user=school_user,
                institution=inst_rn,
                phone="965656666",
                state="Gujarat",
                city="Amalsad"
            )

        # Create branches for RN
        br1 = Branch.objects.create(institution=inst_rn, name="Primary Section", city="Amalsad", status="active")
        br2 = Branch.objects.create(institution=inst_rn, name="Secondary Section", city="Navsari", status="active")

        # Create students
        Student.objects.create(branch=br1, name="Vansh Patel", email="vansh@gmail.com", status="active")
        Student.objects.create(branch=br1, name="Bunty Patel", email="bunty@gmail.com", status="active")

        # Create teachers
        Teacher.objects.create(branch=br2, name="Vansh Patel", email="vansh@gmail.com", status="active")
        Teacher.objects.create(branch=br2, name="Bunty Patel", email="bunty@gmail.com", status="active")

        # Create other staff members
        StaffMember.objects.create(branch=br1, name="Vansh Patel", email="vansh@gmail.com", role="Clark", status="active")
        StaffMember.objects.create(branch=br1, name="Bunty Patel", email="bunty@gmail.com", role="Trusti", status="active")

        # Create school classes
        SchoolClass.objects.create(branch=br1, name="Grade 1", section="A")
        SchoolClass.objects.create(branch=br1, name="Grade 2", section="B")
        SchoolClass.objects.create(branch=br2, name="Grade 10", section="A")
        SchoolClass.objects.create(branch=br2, name="Grade 11", section="B")

        self.stdout.write(self.style.SUCCESS("Successfully seeded database with mock data."))
