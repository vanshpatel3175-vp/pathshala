from . import api 
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('school_signup/', api.school_signup_api, name='api_school_signup'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('school_login/', api.school_login_api, name='api_school_login'),
    path('school_logout/', api.SchoolLogoutAPIView.as_view(), name='api_school_logout'),
]