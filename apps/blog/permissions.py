from rest_framework import permissions
from .models import Post, Comment

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission: only authors can edit/delete their posts/comments.
    """
    
    def has_object_permission(self, request, view, obj) -> bool:
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the author
        if isinstance(obj, (Post, Comment)):
            return obj.author == request.user
        
        return False