from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.validators import validate_email

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User, UserFollowRel
from posts.views import get_user_info

import jwt
import datetime
import re


# Helper function to check password strength
def is_password_strong(password):
    """
    Checks if the password meets security criteria:
    - At least 8 characters
    - Contains at least one digit
    - Contains at least one special character
    """
    return len(password) >= 8 and re.search(r'\d', password) and re.search(r'[\W_]', password)


# Helper function to generate JWT token
def generate_jwt_token(user):
    """
    Generates a JWT token with user information and expiration time.
    Payload includes:
    - id: User's ID
    - email: User's email
    - display_name: User's display name
    - exp: Token expiration set to 8 hours from creation time
    """
    payload = {
        'id': user.id,
        'email': user.email,
        'display_name': user.display_name,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # Token expires in 8 hours
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


# Helper function to decode and validate JWT token
def decode_jwt_token(token):
    """
    Decodes a JWT token and handles potential errors.
    Raises:
    - ValueError if token is expired or invalid.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired')
    except jwt.InvalidTokenError:
        raise ValueError('Invalid token')


# Register API
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])  # Handle file uploads
def register_user(request):
    """
    Optimized API to register a new user.
    - Validates input fields.
    - Ensures confirmPassword matches password.
    - Checks for uniqueness of email and username.
    - Hashes the password and creates the user.
    """
    data = request.data
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirmPassword', '')
    username = data.get('username', '').strip()
    avatar = request.FILES.get('avatar')  # Get the uploaded file

    # Validate required fields
    if not email or not password or not confirm_password or not username:
        return Response({'error': 'All fields (email, username, password, confirmPassword) are required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Validate email format
    try:
        validate_email(email)
    except ValidationError:
        return Response({'error': 'Invalid email format.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check if passwords match
    if password != confirm_password:
        return Response({'error': 'Password and confirmPassword do not match.'}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure email uniqueness
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email is already registered.'}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure username uniqueness
    if User.objects.filter(display_name=username).exists():
        return Response({'error': 'Username is already taken.'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate password strength
    if len(password) < 8 or not re.search(r'\d', password) or not re.search(r'[\W_]', password):
        return Response({'error': 'Password must be at least 8 characters long, include a number, and a special character.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Save the uploaded avatar if provided
    avatar_url = 'user_avatars/default_avatar.png'
    if avatar:
        avatar_path = default_storage.save(f'user_avatars/{avatar.name}', avatar)
        avatar_url = avatar_path

    # Create and save the user
    user = User.objects.create(
        email=email,
        display_name=username,
        password=make_password(password),
        avatar_url=avatar_url
    )

    # Respond with success
    return Response({
        'message': 'User registered successfully.',
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.display_name,
            'avatar_url': user.avatar_url.url if user.avatar_url else None
        }
    }, status=status.HTTP_201_CREATED)



# Login API
@api_view(['POST'])
def login_user(request):
    """
    Authenticates a user and issues a JWT token upon successful login.
    - Verifies the provided email and password.
    - Generates and returns a JWT token with user information.
    """
    data = request.data
    email = data.get('email')
    password = data.get('password')

    # Validate email and password presence
    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Retrieve and authenticate user
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    # Check if password matches the stored hash
    if not check_password(password, user.password):
        return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    # Generate JWT token for the authenticated user
    token = generate_jwt_token(user)
    return Response({
        'token': token, 
        'user': {
            'id': user.id, 
            'email': user.email, 
            'display_name': user.display_name,
            'avatar_url': user.avatar_url.url if user.avatar_url else None
            }
    })


# Example of a protected route using JWT
@api_view(['GET'])
def protected_route(request):
    """
    Protected route example.
    - Extracts JWT token from Authorization header.
    - Decodes and validates the token.
    - Returns access granted message if token is valid, else returns an error.
    """
    token = request.headers.get('Authorization', '').split(' ')[-1]
    try:
        user_data = decode_jwt_token(token)
        return Response({'message': 'Access granted', 'user_data': user_data})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

# Get User Info by ID API
@api_view(['GET'])
def get_user_info_by_id(request, user_id):
    """
    Retrieves user information by user ID.
    - Requires JWT token for authentication.
    - Fetches user details for the given user_id, excluding sensitive fields.
    """
    # Check if JWT token is provided and valid
    token = request.headers.get('Authorization', '').split(' ')[-1]
    try:
        decode_jwt_token(token)  # Only validating if the token is valid, no data needed here
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    # Fetch user details by user_id
    try:
        user = User.objects.get(id=user_id)
        user_info = {
            'id': user.id,
            'email': user.email,
            'display_name': user.display_name,
            'bio': user.bio,  # Include other non-sensitive fields if available
            'avatar_url': user.avatar_url.url if user.avatar_url else None
        }
        return Response({'user': user_info})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def follow_user(request, user_id):
    """
    API to follow another user.
    - Authenticated user can follow a user by user_id.
    """
    try:
        user_info = get_user_info(request)  # Authenticate the request
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    follower = User.objects.get(id=user_info['id'])
    try:
        following = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if follower == following:
        return Response({'error': 'Users cannot follow themselves.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check if the relationship already exists
    if UserFollowRel.objects.filter(follower=follower, following=following).exists():
        return Response({'error': 'Already following this user.'}, status=status.HTTP_400_BAD_REQUEST)

    # Create the follow relationship
    UserFollowRel.objects.create(follower=follower, following=following)
    return Response({'message': f'{follower.display_name} is now following {following.display_name}.'}, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
def unfollow_user(request, user_id):
    """
    API to unfollow a user.
    - Authenticated user can unfollow a user by user_id.
    """
    try:
        user_info = get_user_info(request)  # Authenticate the request
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    follower = User.objects.get(id=user_info['id'])
    try:
        following = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Check if the relationship exists
    try:
        follow_relation = UserFollowRel.objects.get(follower=follower, following=following)
    except UserFollowRel.DoesNotExist:
        return Response({'error': 'Not following this user.'}, status=status.HTTP_400_BAD_REQUEST)

    # Delete the follow relationship
    follow_relation.delete()
    return Response({'message': f'{follower.display_name} has unfollowed {following.display_name}.'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def list_followers(request, user_id):
    """
    API to list all followers of a user.
    - Uses pagination for better performance.
    """
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('pageSize', 10)

    try:
        # Ensure the user exists
        User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Fetch followers
    followers = UserFollowRel.objects.filter(following_id=user_id).select_related('follower')

    # Paginate the results
    paginator = Paginator(followers, page_size)
    try:
        paginated_followers = paginator.page(page)
    except PageNotAnInteger:
        return Response({'error': 'Invalid page number.'}, status=status.HTTP_400_BAD_REQUEST)
    except EmptyPage:
        return Response({'error': 'Page out of range.'}, status=status.HTTP_404_NOT_FOUND)

    # Serialize followers
    results = [{'id': rel.follower.id, 'display_name': rel.follower.display_name, 'email': rel.follower.email, 'avatar_url': rel.follower.avatar_url.url if rel.follower.avatar_url else None}
               for rel in paginated_followers]

    return Response({
        'page': page,
        'pageSize': page_size,
        'totalItems': paginator.count,
        'totalPages': paginator.num_pages,
        'results': results
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
def list_following(request, user_id):
    """
    API to list all users a specific user is following.
    - Uses pagination for better performance.
    """
    page = request.query_params.get('page', 1)
    page_size = request.query_params.get('pageSize', 10)

    try:
        # Ensure the user exists
        User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Fetch following relationships
    following = UserFollowRel.objects.filter(follower_id=user_id).select_related('following')

    # Paginate the results
    paginator = Paginator(following, page_size)
    try:
        paginated_following = paginator.page(page)
    except PageNotAnInteger:
        return Response({'error': 'Invalid page number.'}, status=status.HTTP_400_BAD_REQUEST)
    except EmptyPage:
        return Response({'error': 'Page out of range.'}, status=status.HTTP_404_NOT_FOUND)

    # Serialize following users
    results = [{'id': rel.following.id, 'display_name': rel.following.display_name, 'email': rel.following.email, 'avatar_url': rel.following.avatar_url.url if rel.following.avatar_url else None}
               for rel in paginated_following]

    return Response({
        'page': page,
        'pageSize': page_size,
        'totalItems': paginator.count,
        'totalPages': paginator.num_pages,
        'results': results
    }, status=status.HTTP_200_OK)

@api_view(['PUT'])
@parser_classes([MultiPartParser, FormParser])
def update_profile(request):
    try:
        # Get user from token
        user_info = get_user_info(request)
        user = User.objects.get(id=user_info['id'])
        
        data = request.data
        
        # Update display name if provided
        if 'display_name' in data:
            display_name = data['display_name'].strip()
            if not display_name:
                return Response(
                    {'error': 'Username is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            if User.objects.exclude(id=user.id).filter(display_name=display_name).exists():
                return Response(
                    {'error': 'Display name already taken'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.display_name = display_name
            
        # Update email if provided
        if 'email' in data:
            email = data['email'].strip()
            try:
                validate_email(email)
                if not email.endswith('@bu.edu'):
                    return Response(
                        {'error': 'Only @bu.edu email addresses are allowed'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if User.objects.exclude(id=user.id).filter(email=email).exists():
                    return Response(
                        {'error': 'Email already registered'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                user.email = email
            except ValidationError:
                return Response(
                    {'error': 'Invalid email format'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        # Update bio if provided
        if 'bio' in data:
            user.bio = data['bio'].strip() if data['bio'] else None
            
        # Update avatar if provided
        if 'avatar_url' in request.FILES:
            avatar = request.FILES['avatar_url']
            if not avatar.content_type.startswith('image/'):
                return Response(
                    {'error': 'File must be an image'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete old avatar if exists
            if user.avatar_url:
                default_storage.delete(user.avatar_url.name)
                
            avatar_path = default_storage.save(
                f'user_avatars/{user.id}_{avatar.name}', 
                avatar
            )
            user.avatar_url = avatar_path
            
        user.save()
        
        return Response({
            'message': 'Profile updated successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'bio': user.bio or '',
                'avatar_url': user.avatar_url.url if user.avatar_url else None
            }
        })
        
    except ValueError as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_401_UNAUTHORIZED
        )
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['PUT'])
def change_password(request):
    try:
        user_info = get_user_info(request)
        user = User.objects.get(id=user_info['id'])
        
        data = request.data
        old_password = data.get('oldPassword')
        new_password = data.get('newPassword')
        confirm_password = data.get('confirmPassword')
        
        # Check if old password exists
        if not old_password:
            return Response({'error': 'Old password is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Verify old password
        if not user.check_password(old_password):
            return Response({'error': 'Current password is incorrect'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check password confirmation
        if new_password != confirm_password:
            return Response({'error': 'New passwords do not match'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if new password matches any previous passwords
        if hasattr(user, 'password_history'):
            for old_hash in user.password_history.split(','):
                if old_hash and check_password(new_password, old_hash):
                    return Response(
                        {'error': 'Already used the Password in the past. Please try a New Password.'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Validate new password
        try:
            validate_password(new_password, user)
            # Store the old password hash in history before updating
            if hasattr(user, 'password_history'):
                user.password_history = f"{user.password},{user.password_history}"
            else:
                user.password_history = user.password
            # Set new password
            user.set_password(new_password)
            user.save()
            
            return Response({'message': 'Password updated successfully'})
            
        except ValidationError as e:
            return Response({'error': e.messages}, 
                          status=status.HTTP_400_BAD_REQUEST)
            
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
