from django.contrib import admin
from .models import MassageService, Therapist, Appointment, Review, UserProfile, Notification

@admin.register(MassageService)
class MassageServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'duration_minutes', 'price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

@admin.register(Therapist)
class TherapistAdmin(admin.ModelAdmin):
    list_display = ['name', 'years_experience', 'rating', 'is_available']
    list_filter = ['is_available']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['client', 'service', 'therapist', 'appointment_date', 'appointment_time', 'status', 'payment_status']
    list_filter = ['status', 'payment_status', 'appointment_date']
    search_fields = ['client__username', 'client__first_name', 'service__name']
    date_hierarchy = 'appointment_date'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['client', 'therapist', 'rating', 'created_at']
    list_filter = ['rating']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'created_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
