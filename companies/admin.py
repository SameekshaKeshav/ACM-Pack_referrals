from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry_tag")
    search_fields = ("name",)
from django.contrib import admin

from .models import Company, InterviewExperience


@admin.register(InterviewExperience)
class InterviewExperienceAdmin(admin.ModelAdmin):
    list_display = ("company", "role_title", "outcome", "difficulty", "is_hidden")
    list_filter = ("outcome", "difficulty", "is_hidden")
    search_fields = ("company__name", "role_title", "process_text")
