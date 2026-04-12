"""Custom DRF permissions for the blog application."""

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import Comment, Post


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Allow write access only to the author of a :class:`Post` or :class:`Comment`.

    Safe HTTP methods (GET, HEAD, OPTIONS) are always permitted so that
    unauthenticated visitors can browse content.
    """

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: object,
    ) -> bool:
        """Return ``True`` when the request is read-only, or the user is the author.

        Args:
            request: The current HTTP request.
            view: The view that triggered the permission check.
            obj: The model instance being accessed.

        Returns:
            ``True`` if access should be granted, ``False`` otherwise.
        """
        # Read-only methods are safe for everyone.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write methods require the requester to be the object's author.
        if isinstance(obj, Post | Comment):
            return obj.author == request.user

        return False
