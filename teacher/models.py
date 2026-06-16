from django.db import models
from django.conf import settings


class TeacherProfile(models.Model):
    """Links the Django User (TEACHER role) to the school_admin Teacher record."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    # Reference to the school_admin Teacher model
    teacher = models.OneToOneField(
        'school_admin.Teacher',
        on_delete=models.CASCADE,
        related_name='profile',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"TeacherProfile for {self.user.email}"

    @property
    def school_user(self):
        return self.teacher.school_user if self.teacher and self.teacher.school_user else None

    @property
    def institution(self):
        return self.teacher.branch.institution if self.teacher else None

    @property
    def branch(self):
        return self.teacher.branch if self.teacher else None
