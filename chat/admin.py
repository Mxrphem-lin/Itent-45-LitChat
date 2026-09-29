from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied


User = get_user_model()


class LitChatUserAdmin(UserAdmin):
    delete_confirmation_template = "admin/auth/user/delete_confirmation.html"
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2"),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Status", {"fields": ("is_active",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    list_display = ("username", "email", "is_active", "is_superuser")
    list_filter = ("is_active", "is_superuser")
    search_fields = ("username", "email")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.is_superuser:
            return ("is_active",)
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_staff = False
            obj.is_superuser = False
        else:
            original = User.objects.get(pk=obj.pk)
            if original.is_superuser:
                obj.is_staff = True
                obj.is_superuser = True
                obj.is_active = original.is_active
            else:
                obj.is_staff = False
                obj.is_superuser = False
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        if obj.is_superuser:
            raise PermissionDenied("The LitChat superuser cannot be deleted in Admin.")
        super().delete_model(request, obj)


admin.site.unregister(User)
admin.site.register(User, LitChatUserAdmin)
