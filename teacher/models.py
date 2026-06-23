from django.db import models
from student.models import UserProfile, UserProfileManager

class TeacherProfileManager(UserProfileManager):
    def get_queryset(self):
        return super().get_queryset().filter(role_profile__role__role_name='TEACHER')

class TeacherProfile(UserProfile):
    objects = TeacherProfileManager()

    class Meta:
        proxy = True
