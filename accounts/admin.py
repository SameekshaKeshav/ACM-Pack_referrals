from django.contrib import admin

from .models import PastRole, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "major", "grad_year", "open_to_connect", "account_status")


@admin.register(PastRole)
class PastRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role_title", "start_date", "end_date")
