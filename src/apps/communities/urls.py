from django.urls import path

from .views import (
    CommunityDetailView,
    CommunityInvitationAcceptView,
    CommunityInvitationCreateView,
    CommunityJoinRequestCreateView,
    CommunityJoinRequestReviewView,
    CommunityListView,
)

app_name = "communities"

urlpatterns = [
    path("", CommunityListView.as_view(), name="list"),
    path(
        "invitations/<uuid:invite_code>/accept/",
        CommunityInvitationAcceptView.as_view(),
        name="accept_invitation",
    ),
    path("<slug:slug>/", CommunityDetailView.as_view(), name="detail"),
    path("<slug:slug>/join/", CommunityJoinRequestCreateView.as_view(), name="join"),
    path(
        "<slug:slug>/invitations/create/",
        CommunityInvitationCreateView.as_view(),
        name="create_invitation",
    ),
    path(
        "<slug:slug>/join-requests/<int:join_request_id>/review/",
        CommunityJoinRequestReviewView.as_view(),
        name="review",
    ),
]
