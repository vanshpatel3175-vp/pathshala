from django.db import models
from django.conf import settings

class UserProfileQuerySet(models.QuerySet):
    def _translate_kwargs(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k == 'student' or k == 'student_id':
                new_kwargs['role_profile'] = v
            elif k == 'teacher' or k == 'teacher_id':
                new_kwargs['role_profile'] = v
            elif k.startswith('student__') or k.startswith('student_id__'):
                new_kwargs['role_profile' + k[7:]] = v
            elif k.startswith('teacher__') or k.startswith('teacher_id__'):
                new_kwargs['role_profile' + k[7:]] = v
            else:
                new_kwargs[k] = v
        return new_kwargs

    def filter(self, *args, **kwargs):
        return super().filter(*args, **self._translate_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **self._translate_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**self._translate_kwargs(kwargs))

    def update_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        translated_defaults = self._translate_kwargs(defaults)
        translated_kwargs = self._translate_kwargs(kwargs)
        return super().update_or_create(defaults=translated_defaults, **translated_kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        translated_defaults = self._translate_kwargs(defaults)
        translated_kwargs = self._translate_kwargs(kwargs)
        return super().get_or_create(defaults=translated_defaults, **translated_kwargs)

class UserProfileManager(models.Manager):
    def get_queryset(self):
        return UserProfileQuerySet(self.model, using=self._db)

    def create(self, **kwargs):
        return self.get_queryset().create(**kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        return self.get_queryset().update_or_create(defaults=defaults, **kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        return self.get_queryset().get_or_create(defaults=defaults, **kwargs)

class StudentProfileManager(UserProfileManager):
    def get_queryset(self):
        return super().get_queryset().filter(role_profile__role__role_name='STUDENT')

class UserProfile(models.Model):
    """Links the Django User to their role profiles and details."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_profiles'
    )
    role_profile = models.OneToOneField(
        'school_admin.RoleProfile',
        on_delete=models.CASCADE,
        related_name='user_profile',
        null=True,
        blank=True
    )
    school_class = models.ForeignKey(
        'school_admin.SchoolClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profiles'
    )
    roll_no = models.CharField(max_length=50, blank=True, null=True)
    uid_no = models.CharField(max_length=100, blank=True, null=True)
    grno = models.CharField(max_length=100, blank=True, null=True)
    parent_full_name = models.CharField(max_length=255, blank=True, null=True)
    parent_mobile_no = models.CharField(max_length=15, blank=True, null=True)
    gardian_name = models.CharField(max_length=255, blank=True, null=True)
    gardian_mobile_no = models.CharField(max_length=15, blank=True, null=True)

    objects = UserProfileManager()

    class Meta:
        db_table = 'userProfile'

    @property
    def student(self):
        return self.role_profile

    @student.setter
    def student(self, value):
        self.role_profile = value

    @property
    def teacher(self):
        return self.role_profile

    @teacher.setter
    def teacher(self, value):
        self.role_profile = value

    @property
    def roll_number(self):
        return self.roll_no

    @roll_number.setter
    def roll_number(self, value):
        self.roll_no = value

    def __str__(self):
        return f"UserProfile for {self.user.email}"

    @property
    def school_user(self):
        return self.role_profile.school_user if self.role_profile and hasattr(self.role_profile, 'school_user') else None

    @property
    def institution(self):
        return self.role_profile.institution if self.role_profile else None

    @property
    def branch(self):
        return self.role_profile.branch if self.role_profile else None


class StudentProfile(UserProfile):
    objects = StudentProfileManager()

    class Meta:
        proxy = True
