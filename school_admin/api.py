from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import SchoolAdminProfile

class SchoolLoginAPIView(APIView):
    def post(self, request):
       
        password = request.data.get('password')
        email = request.data.get('email')

        if not email and not password:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "Email or password is required."
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if email and not password:
            pass

        if not email:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "Email is required."
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not password:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": "Password is required."
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        user = None
        # Try finding user by email in profile
        profile = SchoolAdminProfile.objects.filter(user__email=email).first()
        if profile and profile.user:
            user = authenticate(username=profile.user.username, password=password)
            
        # Fallback if email is used as username or if it's an email actually
        if not user:
            user = authenticate(email=email, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            
            user_data = {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role if hasattr(user, 'role') else None,
            }
            
            if hasattr(user, 'school_profile'):
                profile = user.school_profile
                user_data["phone"] = profile.phone
                user_data["state"] = profile.state
                user_data["city"] = profile.city
                if profile.institution:
                    user_data["institution"] = profile.institution.name
                    user_data["institution_id"] = profile.institution.id

            return Response({
                "data": {
                    "success_key": 1,
                    "message": "Login successful.",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_data
                }
            }, status=status.HTTP_200_OK)
            
        return Response({
            "data": {
                "success_key": 0,
                "message": "Invalid email or password."
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
