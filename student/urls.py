from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.student_login_view, name='student_login'),
    path('logout/', views.student_logout_view, name='student_logout'),
    path('dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('profile/', views.student_profile_view, name='student_profile'),
]
