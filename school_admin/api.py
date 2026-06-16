from rest_framework.views import APIView
from rest_framework import status
from .serializer import SchoolSignupSerializer,UserResponseSerializer,schoolloginSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model,authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import SchoolAdminProfile

User = get_user_model()

@api_view(['POST'])
def school_signup_api(request):
    serializer = SchoolSignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        # Remove password from the response data
        user_data = dict(serializer.validated_data)
        user_data.pop('password', None)
        
        return Response({
            
            'user': user_data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=201)
    return Response(serializer.errors, status=400)

@api_view(['POST'])
def school_login_api(request):
    serializer = schoolloginSerializer(data=request.data)
    email=request.data.get('email')
    password=request.data.get('password')
    if not email or not password:
            return Response({
                "data": {
                    "success_key": 0,
                    "message": " Valid Email Id and password is required."
                }
            },status=400)
    user = authenticate(request, username=email, password=password)
    if user is not None:
        refresh = RefreshToken.for_user(user)
        return Response({
            "data": {
                "success_key": 1,
                "message": "Login successful.",
                "user": UserResponseSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=200)
    else:
        return Response({
            "data": {
                "success_key": 0,
                "message": "Invalid email or password."
            }
        }, status=401)

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
            user = authenticate(username=email, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                "data": {
                    "success_key": 1,
                    "message": "Login successful.",
                    "token": str(refresh.access_token),
                    "refresh_token": str(refresh)
                }
            }, status=status.HTTP_200_OK)
            
        return Response({
            "data": {
                "success_key": 0,
                "message": "Invalid email or password."
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
