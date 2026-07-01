from django.db import models
from django.conf import settings

class UserProfileQuerySet(models.QuerySet):
    def _translate_query_kwargs(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k == 'student' or k == 'student_id':
                if k == 'student_id':
                    new_kwargs['user__role_profiles__id'] = v
                else:
                    new_kwargs['user__role_profiles'] = v
                new_kwargs['user__role_profiles__role__role_name'] = 'STUDENT'
            elif k == 'teacher' or k == 'teacher_id':
                if k == 'teacher_id':
                    new_kwargs['user__role_profiles__id'] = v
                else:
                    new_kwargs['user__role_profiles'] = v
                new_kwargs['user__role_profiles__role__role_name'] = 'TEACHER'
            elif k.startswith('student__') or k.startswith('student_id__'):
                suffix = k[7:] if k.startswith('student__') else k[10:]
                new_kwargs['user__role_profiles' + suffix] = v
                new_kwargs['user__role_profiles__role__role_name'] = 'STUDENT'
            elif k.startswith('teacher__') or k.startswith('teacher_id__'):
                suffix = k[7:] if k.startswith('teacher__') else k[10:]
                new_kwargs['user__role_profiles' + suffix] = v
                new_kwargs['user__role_profiles__role__role_name'] = 'TEACHER'
            else:
                new_kwargs[k] = v
        return new_kwargs

    def _clean_write_kwargs(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k in ['student', 'student_id', 'teacher', 'teacher_id']:
                if 'user' not in kwargs and 'user_id' not in kwargs:
                    if hasattr(v, 'user'):
                        new_kwargs['user'] = v.user
            else:
                new_kwargs[k] = v
        return new_kwargs

    def filter(self, *args, **kwargs):
        return super().filter(*args, **self._translate_query_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **self._translate_query_kwargs(kwargs))

    def create(self, **kwargs):
        cleaned = self._clean_write_kwargs(kwargs)
        user = cleaned.get('user')
        if user:
            try:
                profile = self.get(user=user)
                updated = False
                for k, v in cleaned.items():
                    if k != 'user' and v is not None and getattr(profile, k) != v:
                        setattr(profile, k, v)
                        updated = True
                if updated:
                    profile.save()
                return profile
            except self.model.DoesNotExist:
                pass
        return super().create(**cleaned)

    def update_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        cleaned_defaults = self._clean_write_kwargs(defaults)
        cleaned_kwargs = self._clean_write_kwargs(kwargs)
        # Strip None values so existing non-None fields (e.g. date_of_birth) are not overwritten
        cleaned_defaults = {k: v for k, v in cleaned_defaults.items() if v is not None}
        return super().update_or_create(defaults=cleaned_defaults, **cleaned_kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        defaults = defaults or {}
        cleaned_defaults = self._clean_write_kwargs(defaults)
        cleaned_kwargs = self._clean_write_kwargs(kwargs)
        return super().get_or_create(defaults=cleaned_defaults, **cleaned_kwargs)

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
        from school_admin.models import RoleProfile
        student_user_ids = RoleProfile.objects.filter(role__role_name='STUDENT').values_list('user_id', flat=True)
        return super().get_queryset().filter(user_id__in=student_user_ids)

class UserProfile(models.Model):
    """Links the Django User to their role profiles and details."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_profile'
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
    date_of_birth = models.DateField(null=True, blank=True)

    objects = UserProfileManager()

    class Meta:
        db_table = 'userProfile'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def student(self):
        return self.user.role_profiles.filter(role__role_name='STUDENT').first()

    @student.setter
    def student(self, value):
        pass

    @property
    def teacher(self):
        return self.user.role_profiles.filter(role__role_name='TEACHER').first()

    @teacher.setter
    def teacher(self, value):
        pass

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
        return self.user.role_profiles.filter(role__role_name='USER').first()

    @property
    def institution(self):
        rp = self.user.role_profiles.first()
        return rp.institution if rp else None

    @property
    def branch(self):
        rp = self.user.role_profiles.filter(role__role_name='STUDENT').first()
        if not rp:
            rp = self.user.role_profiles.filter(role__role_name='TEACHER').first()
        if not rp:
            rp = self.user.role_profiles.first()
        return rp.branch if rp else None


class StudentProfile(UserProfile):
    objects = StudentProfileManager()

    class Meta:
        proxy = True
