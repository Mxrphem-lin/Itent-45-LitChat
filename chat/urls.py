from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("api/conversations/", views.conversation_collection, name="conversation-collection"),
    path(
        "api/conversations/<uuid:conversation_id>/",
        views.conversation_detail,
        name="conversation-detail",
    ),
    path(
        "api/conversations/<uuid:conversation_id>/messages/",
        views.conversation_messages,
        name="conversation-messages",
    ),
]
