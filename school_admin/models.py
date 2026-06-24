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

class UserRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='User_id', related_name='user_roles')
    role = models.ForeignKey('super_admin.Role', on_delete=models.CASCADE, db_column='role_id', related_name='user_roles')
    institution = models.ForeignKey('super_admin.Institution', on_delete=models.CASCADE, db_column='institute_id', related_name='user_roles')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, db_column='branch_id', null=True, blank=True, related_name='user_roles')

    class Meta:
        db_table = 'userRole'

    def __str__(self):
        return f"{self.user.email} - {self.role.role_name} - {self.institution.name}"


class RoleProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id', related_name='role_profiles')
    role = models.ForeignKey('super_admin.Role', on_delete=models.CASCADE, db_column='role_id', related_name='role_profiles')
    role_name = models.CharField(max_length=100)
    email_id = models.EmailField()
    mobile_no = models.CharField(max_length=15, blank=True, null=True)
    institution = models.ForeignKey('super_admin.Institution', on_delete=models.CASCADE, db_column='institution_id', related_name='role_profiles')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, db_column='branch_id', null=True, blank=True, related_name='role_profiles')
    address_record = models.ForeignKey('super_admin.Address', on_delete=models.SET_NULL, null=True, blank=True, db_column='address_id', related_name='role_profiles')
    permissions = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('user', 'role', 'institution')
        db_table = 'role_profile'

    def __str__(self):
        return f"{self.name} ({self.role_name})"

    def save(self, *args, **kwargs):
        # Auto-create/resolve user by email if not set
        if not hasattr(self, 'user') or self.user is None:
            email_to_use = getattr(self, 'email_id', None) or getattr(self, 'email', None)
            if email_to_use:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                name_str = getattr(self, '_name_to_set', None) or getattr(self, 'name', '')
                first_name = name_str.split(' ')[0] if name_str else ''
                last_name = ' '.join(name_str.split(' ')[1:]) if name_str else ''
                user_obj, created = User.objects.get_or_create(
                    email=email_to_use,
                    defaults={
                        'username': email_to_use,
                        'first_name': first_name,
                        'last_name': last_name,
                        'mobile_no': self.mobile_no
                    }
                )
                if created:
                    # Newly auto-created placeholder: no login allowed until
                    # the real registration flow sets a proper password.
                    user_obj.set_unusable_password()
                    user_obj.save()
                self.user = user_obj

        if self.user:
            if not self.email_id:
                self.email_id = self.user.email
            if self.mobile_no and not self.user.mobile_no:
                self.user.mobile_no = self.mobile_no
                self.user.save()
            elif not self.mobile_no and self.user.mobile_no:
                self.mobile_no = self.user.mobile_no
        if self.role and not self.role_name:
            self.role_name = self.role.role_name
        if self.branch and not self.institution_id:
            self.institution = self.branch.institution

        super().save(*args, **kwargs)

        if hasattr(self, '_temp_date_of_birth'):
            from student.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=self.user)
            profile.date_of_birth = self._temp_date_of_birth
            profile.save()
            del self._temp_date_of_birth

        # Sync to UserRole
        UserRole.objects.get_or_create(
            user=self.user,
            role=self.role,
            institution=self.institution,
            branch=self.branch
        )

    @property
    def user_profile(self):
        if self.user:
            try:
                return self.user.user_profile
            except Exception:
                pass
        return None

    def _get_or_create_user_profile(self):
        from student.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        return profile

    @property
    def student(self):
        return self

    @property
    def teacher(self):
        return self

    @property
    def student_profile_rel(self):
        try:
            return self.user_profile
        except Exception:
            return None

    @property
    def teacher_profile_rel(self):
        try:
            return self.user_profile
        except Exception:
            return None

    @property
    def school_user(self):
        return self

    @property
    def full_name(self):
        return self.name

    @property
    def school_role(self):
        from super_admin.models import SchoolRole
        school_role, _ = SchoolRole.objects.get_or_create(role=self.role, school=self.institution)
        return school_role

    @school_role.setter
    def school_role(self, value):
        if value:
            self.role = value.role
            self.institution = value.school

    @property
    def school_role_id(self):
        return self.school_role.id if self.school_role else None

    @property
    def name(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return ""

    @name.setter
    def name(self, value):
        if self.user and value:
            parts = value.split(' ', 1)
            self.user.first_name = parts[0]
            if len(parts) > 1:
                self.user.last_name = parts[1]
            self.user.save()

    @property
    def first_name(self):
        return self.user.first_name if self.user else ""

    @first_name.setter
    def first_name(self, value):
        if self.user:
            self.user.first_name = value
            self.user.save()

    @property
    def last_name(self):
        return self.user.last_name if self.user else ""

    @last_name.setter
    def last_name(self, value):
        if self.user:
            self.user.last_name = value
            self.user.save()

    @property
    def middle_name(self):
        return self.user.middle_name if self.user else ""

    @middle_name.setter
    def middle_name(self, value):
        if self.user:
            self.user.middle_name = value
            self.user.save()

    @property
    def email(self):
        return self.email_id

    @email.setter
    def email(self, value):
        self.email_id = value

    @property
    def password(self):
        return self.user.password if self.user else ""

    @password.setter
    def password(self, value):
        if self.user:
            self.user.password = value
            self.user.save()

    @property
    def status(self):
        return "active" if (self.user and self.user.is_active) else "disabled"

    @status.setter
    def status(self, value):
        if self.user:
            self.user.is_active = (value == "active")
            self.user.save()

    # Address properties
    @property
    def address(self):
        if self.address_record:
            lines = []
            if self.address_record.addressline1:
                lines.append(self.address_record.addressline1)
            if self.address_record.addressline2:
                lines.append(self.address_record.addressline2)
            return "\n".join(lines)
        return ""

    @address.setter
    def address(self, value):
        from super_admin.models import Address
        if value:
            if not self.address_record:
                self.address_record = Address.objects.create(
                    addressline1=value,
                    city="",
                    state="Gujarat",
                    pincode=""
                )
            else:
                self.address_record.addressline1 = value
                self.address_record.save()

    @property
    def city(self):
        return self.address_record.city if self.address_record else ""

    @city.setter
    def city(self, value):
        from super_admin.models import Address
        if not self.address_record:
            self.address_record = Address.objects.create(
                city=value or "",
                state="Gujarat",
                addressline1="",
                pincode=""
            )
        else:
            self.address_record.city = value or ""
            self.address_record.save()

    @property
    def state(self):
        return self.address_record.state if self.address_record else "Gujarat"

    @state.setter
    def state(self, value):
        from super_admin.models import Address
        if not self.address_record:
            self.address_record = Address.objects.create(
                state=value or "Gujarat",
                city="",
                addressline1="",
                pincode=""
            )
        else:
            self.address_record.state = value or "Gujarat"
            self.address_record.save()

    @property
    def pincode(self):
        return self.address_record.pincode if self.address_record else ""

    @pincode.setter
    def pincode(self, value):
        from super_admin.models import Address
        if not self.address_record:
            self.address_record = Address.objects.create(
                pincode=value or "",
                city="",
                state="Gujarat",
                addressline1=""
            )
        else:
            self.address_record.pincode = value or ""
            self.address_record.save()

    # Student specific properties
    @property
    def school_class(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.school_class
        return None

    @school_class.setter
    def school_class(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.school_class = value
            profile.save()

    @property
    def school_class_id(self):
        return self.school_class.id if self.school_class else None

    @property
    def roll_no(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.roll_no
        return ""

    @roll_no.setter
    def roll_no(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.roll_no = value
            profile.save()

    @property
    def roll_number(self):
        return self.roll_no

    @roll_number.setter
    def roll_number(self, value):
        self.roll_no = value

    @property
    def uid_no(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.uid_no
        return ""

    @uid_no.setter
    def uid_no(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.uid_no = value
            profile.save()

    @property
    def grno(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.grno
        return ""

    @grno.setter
    def grno(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.grno = value
            profile.save()

    @property
    def parent_full_name(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.parent_full_name
        return ""

    @parent_full_name.setter
    def parent_full_name(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.parent_full_name = value
            profile.save()

    @property
    def parent_mobile_no(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.parent_mobile_no
        return ""

    @parent_mobile_no.setter
    def parent_mobile_no(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.parent_mobile_no = value
            profile.save()

    @property
    def gardian_name(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.gardian_name
        return ""

    @gardian_name.setter
    def gardian_name(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.gardian_name = value
            profile.save()

    @property
    def gardian_mobile_no(self):
        if self.role_name == 'STUDENT' and hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.gardian_mobile_no
        return ""

    @gardian_mobile_no.setter
    def gardian_mobile_no(self, value):
        if self.role_name == 'STUDENT':
            profile = self._get_or_create_user_profile()
            profile.gardian_mobile_no = value
            profile.save()

    @property
    def date_of_birth(self):
        if hasattr(self, '_temp_date_of_birth'):
            return self._temp_date_of_birth
        if self.user:
            return self.user.date_of_birth
        if hasattr(self, 'user_profile') and self.user_profile:
            return self.user_profile.date_of_birth
        return None

    @date_of_birth.setter
    def date_of_birth(self, value):
        if not self.pk:
            self._temp_date_of_birth = value
        else:
            if self.user:
                self.user.date_of_birth = value
            else:
                profile = self._get_or_create_user_profile()
                profile.date_of_birth = value
                profile.save()

    @property
    def dob(self):
        return self.date_of_birth

    @property
    def mobile_number(self):
        return self.mobile_no


class StudentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(role__role_name='STUDENT')

class Student(RoleProfile):
    objects = StudentManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        if not self.school_role_id:
            from super_admin.models import Role, SchoolRole
            role_obj, _ = Role.objects.get_or_create(role_name='STUDENT')
            school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=self.branch.institution)
            self.school_role = school_role
        super().save(*args, **kwargs)

    @property
    def profile(self):
        try:
            return self.student_profile_rel
        except Exception:
            return None

class TeacherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(role__role_name='TEACHER')

class Teacher(RoleProfile):
    objects = TeacherManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        if not self.school_role_id:
            from super_admin.models import Role, SchoolRole
            role_obj, _ = Role.objects.get_or_create(role_name='TEACHER')
            school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=self.branch.institution)
            self.school_role = school_role
        super().save(*args, **kwargs)

    @property
    def profile(self):
        try:
            return self.teacher_profile_rel
        except Exception:
            return None

class StaffMemberManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(role__role_name__in=['STUDENT', 'TEACHER', 'USER'])

class StaffMember(RoleProfile):
    objects = StaffMemberManager()

    class Meta:
        proxy = True

    @property
    def role(self):
        return self.school_role.role.role_name if self.school_role else ""

    @role.setter
    def role(self, value):
        if value:
            self._role_to_set = value

    def __init__(self, *args, **kwargs):
        role_val = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)
        if role_val:
            self._role_to_set = role_val

    def save(self, *args, **kwargs):
        if not self.school_role_id and getattr(self, '_role_to_set', None):
            from super_admin.models import Role, SchoolRole
            role_obj, _ = Role.objects.get_or_create(role_name=self._role_to_set)
            school_role, _ = SchoolRole.objects.get_or_create(role=role_obj, school=self.branch.institution)
            self.school_role = school_role
        super().save(*args, **kwargs)

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

