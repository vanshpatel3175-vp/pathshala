from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.teacher_login_view, name='teacher_login'),
    path('logout/', views.teacher_logout_view, name='teacher_logout'),
    path('dashboard/', views.teacher_dashboard_view, name='teacher_dashboard'),
    path('profile/', views.teacher_profile_view, name='teacher_profile'),
]
