from . import api 
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('school_signup/', api.SchoolSignupAPIView.as_view(), name='api_school_signup'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', api.SchoolLoginAPIView.as_view(), name='api_school_login'),
    path('logout/', api.SchoolLogoutAPIView.as_view(), name='api_school_logout'),
]