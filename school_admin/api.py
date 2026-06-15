from .serializer import SchoolSignupSerializer,UserResponseSerializer,schoolloginSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model,authenticate
from rest_framework_simplejwt.tokens import RefreshToken

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