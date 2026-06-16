from django.db import models
from django.conf import settings

class StudentProfile(models.Model):
    """Links the Django User (STUDENT role) to the school_admin Student record."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    # Reference to the school_admin Student model
    student = models.OneToOneField(
        'school_admin.Student',
        on_delete=models.CASCADE,
        related_name='profile',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"StudentProfile for {self.user.email}"

    @property
    def school_user(self):
        return self.student.school_user if self.student and self.student.school_user else None

    @property
    def institution(self):
        return self.student.branch.institution if self.student else None

    @property
    def branch(self):
        return self.student.branch if self.student else None
