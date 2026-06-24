from django.db import models
from student.models import UserProfile, UserProfileManager

class TeacherProfileManager(UserProfileManager):
    def get_queryset(self):
        from school_admin.models import RoleProfile
        teacher_user_ids = RoleProfile.objects.filter(role__role_name='TEACHER').values_list('user_id', flat=True)
        return super().get_queryset().filter(user_id__in=teacher_user_ids)

class TeacherProfile(UserProfile):
    objects = TeacherProfileManager()

    class Meta:
        proxy = True
