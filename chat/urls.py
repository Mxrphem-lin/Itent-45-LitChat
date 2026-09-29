from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path, reverse_lazy
from django.views.decorators.cache import never_cache

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path(
        "accounts/login/",
        views.LitChatLoginView.as_view(),
        name="login",
    ),
    path("accounts/logout/", never_cache(auth_views.LogoutView.as_view()), name="logout"),
    path("accounts/signup/", views.signup, name="signup"),
    path(
        "accounts/password/change/",
        never_cache(login_required(
            auth_views.PasswordChangeView.as_view(
                template_name="registration/password_change_form.html",
                success_url=reverse_lazy("password_change_done"),
            )
        )),
        name="password_change",
    ),
    path(
        "accounts/password/change/done/",
        never_cache(login_required(
            auth_views.PasswordChangeDoneView.as_view(
                template_name="registration/password_change_done.html"
            )
        )),
        name="password_change_done",
    ),
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
