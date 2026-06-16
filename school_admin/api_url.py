from django.urls import path
from .api import SchoolLoginAPIView

urlpatterns = [
    path('school_login/', SchoolLoginAPIView.as_view(), name='api_school_login'),
]
