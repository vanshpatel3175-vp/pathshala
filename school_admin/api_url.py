from django.urls import path
from .api import SchoolLoginAPIView

urlpatterns = [
    path('login/', SchoolLoginAPIView.as_view(), name='api_school_login'),
]
