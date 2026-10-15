from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('services/', views.services_list, name='services'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('therapists/', views.therapists_list, name='therapists'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Client
    path('dashboard/', views.dashboard, name='dashboard'),
    path('book/', views.book_appointment, name='book_appointment'),
    path('my-appointments/', views.my_appointments, name='my_appointments'),
    path('appointments/<int:pk>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    path('appointments/<int:appointment_pk>/review/', views.submit_review, name='submit_review'),
    path('profile/', views.profile_view, name='profile'),
    path('notifications/', views.notifications_view, name='notifications'),

    # Admin
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/appointments/', views.admin_appointments, name='admin_appointments'),
    path('admin-panel/appointments/<int:pk>/update/', views.admin_update_appointment, name='admin_update_appointment'),
    path('admin-panel/services/', views.admin_services, name='admin_services'),
    path('admin-panel/services/create/', views.admin_service_create, name='admin_service_create'),
    path('admin-panel/services/<int:pk>/edit/', views.admin_service_edit, name='admin_service_edit'),
    path('admin-panel/services/<int:pk>/delete/', views.admin_service_delete, name='admin_service_delete'),
    path('admin-panel/clients/', views.admin_clients, name='admin_clients'),
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),

    # API
    path('api/service/<int:pk>/price/', views.get_service_price, name='service_price_api'),
]
