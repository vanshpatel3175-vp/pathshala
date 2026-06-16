from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPER ADMIN', 'Super Admin'),
        ('SCHOOL STAFF', 'School Staff'),
    ]
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='SCHOOL STAFF')

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = 'SUPER ADMIN'
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'auth_user'

class SchoolApplication(models.Model):
    STATUS_CHOICES = [
        ('Awaiting Review', 'Awaiting Review'),
        ('Validated', 'Validated'),
        ('Declined', 'Declined'),
    ]
    name = models.CharField(max_length=255)
    trust_name = models.CharField(max_length=255)
    principal_name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20)
    board = models.CharField(max_length=255)
    medium = models.CharField(max_length=100)
    registration_code = models.CharField(max_length=100)
    date_applied = models.DateField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Awaiting Review')
    video_url = models.URLField(blank=True, null=True)
    accreditation_certificate = models.CharField(max_length=255, blank=True, null=True) # Stored path or mock info

    def __str__(self):
        return self.name

def default_features():
    return {
        "manage_branches": True,
        "add_new_branch": True,
        "manage_students": True,
        "manage_teachers": True,
        "manage_others": True,
        "manage_roles": True,
        "manage_mediums": True,
        "manage_classes": True,
        "attendance": False,
        "study_materials": True,
        "fees": False
    }

class Institution(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
        ('pending', 'Pending'),
    ]
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=100, default='SCHOOL')
    planned_type = models.CharField(max_length=100, blank=True)
    contact_no = models.CharField(max_length=50)
    email = models.EmailField()
    expired_date = models.DateTimeField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    school_code = models.CharField(max_length=50, blank=True, null=True)
    plan = models.CharField(max_length=100, default='Standard')
    activation_requested = models.BooleanField(default=False)
    features = models.JSONField(default=default_features, blank=True)

    def __str__(self):
        return self.name

    @property
    def school_name(self):
        return self.name

    @school_name.setter
    def school_name(self, value):
        self.name = value

    @property
    def total_students(self):
        from school_admin.models import Student
        return Student.objects.filter(branch__institution=self).count()

    @property
    def total_teachers(self):
        from school_admin.models import Teacher
        return Teacher.objects.filter(branch__institution=self).count()

    @property
    def total_staff(self):
        from school_admin.models import StaffMember
        return StaffMember.objects.filter(branch__institution=self).count()

class PlatformUser(models.Model):
    ROLE_CHOICES = [
        ('SCHOOL STAFF', 'School Staff'),
        ('SUPER ADMIN', 'Super Admin'),
    ]
    username = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    date_joined = models.DateTimeField()
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='SCHOOL STAFF')

    def __str__(self):
        return self.username

class Inquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Reject', 'Reject'),
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    school_name = models.CharField(max_length=100) # e.g. "RN", "VJ", "HD"
    contact_no = models.CharField(max_length=50)
    email = models.EmailField()
    state = models.CharField(max_length=100, default='Gujarat')
    city = models.CharField(max_length=100)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    last_active = models.DateTimeField()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name

class Meeting(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='meetings')
    meeting_no = models.IntegerField()
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    title = models.CharField(max_length=255)
    next_meeting_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Meeting {self.meeting_no} for {self.inquiry.full_name}"

class Subscription(models.Model):
    STATUS_CHOICES = [
        ('okay', 'Okay'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
    ]
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='subscriptions')
    sr_no = models.IntegerField()
    subscription_date = models.DateTimeField()
    expired_date = models.DateTimeField()
    type_of_planned = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='okay')

    def __str__(self):
        return f"Subscription {self.sr_no} for {self.inquiry.full_name}"
