from django.db import models
from school_admin.models import Branch, SchoolClass, Teacher


class StudyMaterial(models.Model):
    CATEGORY_CHOICES = [
        ('notes', 'Notes'),
        ('assignment', 'Assignment'),
        ('worksheet', 'Worksheet'),
        ('syllabus', 'Syllabus'),
        ('question_paper', 'Question Paper'),
        ('other', 'Other'),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='new_study_materials')
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name='new_study_materials',
        null=True, blank=True
    )
    # Who uploaded it — null means school admin uploaded
    uploaded_by_teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_materials'
    )
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='notes')
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='study_materials/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} — {self.branch.name}"

    @property
    def uploaded_by_label(self):
        if self.uploaded_by_teacher:
            return f"Teacher: {self.uploaded_by_teacher.name}"
        return "School Admin"

    @property
    def file_extension(self):
        name = self.file.name
        if '.' in name:
            return name.rsplit('.', 1)[-1].lower()
        return ''
