from django.urls import path
from . import views

urlpatterns = [
    # School Admin
    path('admin/', views.admin_study_materials_view, name='admin_study_materials'),
    path('admin/delete/<int:material_id>/', views.admin_delete_material_view, name='admin_delete_material'),

    # Teacher
    path('teacher/', views.teacher_study_materials_view, name='teacher_study_materials'),
    path('teacher/delete/<int:material_id>/', views.teacher_delete_material_view, name='teacher_delete_material'),

    # Student
    path('student/', views.student_study_materials_view, name='student_study_materials'),
]
