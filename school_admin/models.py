from django.db import models
from django.conf import settings
from super_admin.models import Institution


class SchoolAdminProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='school_profile')
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, blank=True, related_name='admins')
    phone = models.CharField(max_length=20)
    state = models.CharField(max_length=100, default='Gujarat')
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"Profile for {self.user.email} ({self.institution.name if self.institution else 'Pending Approval'})"

class Branch(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
    ]
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    branch_code = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.institution.name}"

    @property
    def school_id(self):
        return self.institution_id

    @property
    def branch_name(self):
        return self.name

    @branch_name.setter
    def branch_name(self, value):
        self.name = value

class Student(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='students')
    school_class = models.ForeignKey('SchoolClass', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    school_user = models.OneToOneField('SchoolUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_role')
    roll_number = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    password = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} ({self.branch.name})"


class SchoolUser(models.Model):
    """Pre-registered users that can later be assigned roles like Teacher."""
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='school_users')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    dob = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, default='Gujarat')
    address = models.TextField(blank=True)
    mobile_number = models.CharField(max_length=15, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Teacher(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='teachers')
    school_user = models.OneToOneField(SchoolUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='teacher_role')
    name = models.CharField(max_length=255)
    email = models.EmailField()
    password = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

class StaffMember(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='staff_members')
    name = models.CharField(max_length=255)
    email = models.EmailField()
    role = models.CharField(max_length=100) # e.g. "Student", "Principal", "Teacher"
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} - {self.role} ({self.branch.name})"

class BranchRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='branch_requests')
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_branch_requests')
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Request for {self.institution.name} ({self.status})"

    @property
    def school_id(self):
        return self.institution_id

class SchoolClass(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='classes')
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=50, blank=True, null=True)
    teacher = models.ForeignKey(
        'Teacher',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_classes'
    )

    def __str__(self):
        return f"{self.name} ({self.branch.name})"


class CustomRole(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='custom_roles')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.institution.name})"

class Medium(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='mediums')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.institution.name})"




class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendances_taken')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('school_class', 'student', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student.name} — {self.school_class.name} — {self.date} — {self.status}"


class Holiday(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='holidays')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name='holidays')
    # null branch means the holiday applies to ALL branches of the institution
    holiday_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        branch_str = self.branch.name if self.branch else "All Branches"
        return f"{self.holiday_name} ({branch_str}) [{self.start_date} – {self.end_date}]"

    @property
    def is_single_day(self):
        return self.start_date == self.end_date


class Event(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='events')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name='events')
    # null branch means the event applies to ALL branches of the institution
    event_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        branch_str = self.branch.name if self.branch else "All Branches"
        return f"{self.event_name} ({branch_str}) [{self.start_date} – {self.end_date}]"

    @property
    def is_single_day(self):
        return self.start_date == self.end_date

