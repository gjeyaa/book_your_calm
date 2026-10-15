from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count, Avg, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
import datetime
import json

from .models import (
    MassageService, Therapist, Appointment, Review, UserProfile, Notification
)
from .forms import (
    RegisterForm, AppointmentForm, ReviewForm, UserProfileForm, AppointmentFilterForm
)


def is_admin(user):
    return user.is_staff


def get_or_create_profile(user):
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def create_notification(user, notif_type, title, message, appointment=None):
    Notification.objects.create(
        user=user,
        notification_type=notif_type,
        title=title,
        message=message,
        related_appointment=appointment
    )


# ──── Public Views ────────────────────────────────────────────────────────────

def home(request):
    services = MassageService.objects.filter(is_active=True)[:6]
    therapists = Therapist.objects.filter(is_available=True)[:4]
    reviews = Review.objects.select_related('client', 'therapist').order_by('-created_at')[:6]
    context = {'services': services, 'therapists': therapists, 'reviews': reviews}
    return render(request, 'appointments/home.html', context)


def services_list(request):
    category = request.GET.get('category', '')
    services = MassageService.objects.filter(is_active=True)
    if category:
        services = services.filter(category=category)
    return render(request, 'appointments/services.html', {'services': services, 'selected_category': category})


def service_detail(request, pk):
    service = get_object_or_404(MassageService, pk=pk, is_active=True)
    return render(request, 'appointments/service_detail.html', {'service': service})


def therapists_list(request):
    therapists = Therapist.objects.filter(is_available=True).prefetch_related('specializations')
    return render(request, 'appointments/therapists.html', {'therapists': therapists})


# ──── Auth Views ──────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()
            profile = UserProfile.objects.create(user=user, phone=form.cleaned_data.get('phone', ''))
            login(request, user)
            create_notification(user, 'general', 'Welcome to Book Your Calm!',
                                f'Hi {user.first_name}! Your account has been created. Start booking your relaxation session today.')
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'appointments/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'dashboard'))
    else:
        form = AuthenticationForm()
    return render(request, 'appointments/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


# ──── Client Views ────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = get_or_create_profile(request.user)
    appointments = Appointment.objects.filter(client=request.user).select_related('service', 'therapist')
    upcoming = appointments.filter(
        status__in=['pending', 'confirmed'],
        appointment_date__gte=datetime.date.today()
    ).order_by('appointment_date', 'appointment_time')[:5]
    past = appointments.filter(
        Q(status='completed') | Q(appointment_date__lt=datetime.date.today())
    ).order_by('-appointment_date')[:3]
    unread_notifs = request.user.notifications.filter(is_read=False).count()
    context = {
        'profile': profile,
        'upcoming': upcoming,
        'past': past,
        'total_appointments': appointments.count(),
        'unread_notifs': unread_notifs,
    }
    return render(request, 'appointments/dashboard.html', context)


@login_required
def book_appointment(request):
    service_id = request.GET.get('service')
    initial = {}
    if service_id:
        initial['service'] = service_id

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.client = request.user
            appointment.total_price = appointment.service.price

            # Auto-assign therapist if not selected
            if not appointment.therapist:
                available = Therapist.objects.filter(
                    is_available=True,
                    specializations=appointment.service
                ).first()
                if not available:
                    available = Therapist.objects.filter(is_available=True).first()
                appointment.therapist = available

            appointment.save()
            create_notification(
                request.user, 'appointment_confirmed',
                'Appointment Booked!',
                f'Your {appointment.service.name} appointment on {appointment.appointment_date} at {appointment.appointment_time.strftime("%I:%M %p")} has been received.',
                appointment
            )
            messages.success(request, 'Your appointment has been booked successfully!')
            return redirect('my_appointments')
    else:
        form = AppointmentForm(initial=initial)
    services = MassageService.objects.filter(is_active=True)
    return render(request, 'appointments/book_appointment.html', {'form': form, 'services': services})


@login_required
def my_appointments(request):
    filter_form = AppointmentFilterForm(request.GET)
    appointments = Appointment.objects.filter(client=request.user).select_related('service', 'therapist')

    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            appointments = appointments.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('date_from'):
            appointments = appointments.filter(appointment_date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            appointments = appointments.filter(appointment_date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('search'):
            q = filter_form.cleaned_data['search']
            appointments = appointments.filter(service__name__icontains=q)

    paginator = Paginator(appointments, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    reviewed_ids = set(Review.objects.filter(client=request.user).values_list('appointment_id', flat=True))
    return render(request, 'appointments/my_appointments.html', {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'reviewed_ids': reviewed_ids,
    })


@login_required
def cancel_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, client=request.user)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if appointment.status in ['pending', 'confirmed']:
            appointment.status = 'cancelled'
            appointment.cancelled_reason = reason
            appointment.save()
            create_notification(
                request.user, 'appointment_cancelled',
                'Appointment Cancelled',
                f'Your {appointment.service.name} appointment on {appointment.appointment_date} has been cancelled.',
                appointment
            )
            messages.success(request, 'Appointment cancelled successfully.')
        else:
            messages.error(request, 'This appointment cannot be cancelled.')
    return redirect('my_appointments')


@login_required
def submit_review(request, appointment_pk):
    appointment = get_object_or_404(Appointment, pk=appointment_pk, client=request.user, status='completed')
    if hasattr(appointment, 'review'):
        messages.warning(request, 'You have already reviewed this appointment.')
        return redirect('my_appointments')
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.appointment = appointment
            review.client = request.user
            review.therapist = appointment.therapist
            review.save()
            # Update therapist rating
            if appointment.therapist:
                avg = Review.objects.filter(therapist=appointment.therapist).aggregate(Avg('rating'))['rating__avg']
                appointment.therapist.rating = round(avg, 2)
                appointment.therapist.save()
            messages.success(request, 'Thank you for your review!')
            return redirect('my_appointments')
    else:
        form = ReviewForm()
    return render(request, 'appointments/review_form.html', {'form': form, 'appointment': appointment})


@login_required
def profile_view(request):
    profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            request.user.first_name = form.cleaned_data.get('first_name', request.user.first_name)
            request.user.last_name = form.cleaned_data.get('last_name', request.user.last_name)
            request.user.email = form.cleaned_data.get('email', request.user.email)
            request.user.save()
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        initial = {'first_name': request.user.first_name, 'last_name': request.user.last_name, 'email': request.user.email}
        form = UserProfileForm(instance=profile, initial=initial)
    return render(request, 'appointments/profile.html', {'form': form, 'profile': profile})


@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'appointments/notifications.html', {'notifications': notifications})


# ──── Admin Views ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    today = datetime.date.today()
    total_appointments = Appointment.objects.count()
    today_appointments = Appointment.objects.filter(appointment_date=today).count()
    total_revenue = Appointment.objects.filter(
        status='completed', payment_status='paid'
    ).aggregate(Sum('total_price'))['total_price__sum'] or 0
    pending_count = Appointment.objects.filter(status='pending').count()

    recent_appointments = Appointment.objects.select_related(
        'client', 'service', 'therapist'
    ).order_by('-created_at')[:10]

    monthly_data = []
    for i in range(6):
        month_start = (today.replace(day=1) - datetime.timedelta(days=30*i))
        count = Appointment.objects.filter(
            appointment_date__year=month_start.year,
            appointment_date__month=month_start.month
        ).count()
        monthly_data.append({'month': month_start.strftime('%b'), 'count': count})
    monthly_data.reverse()

    context = {
        'total_appointments': total_appointments,
        'today_appointments': today_appointments,
        'total_revenue': total_revenue,
        'pending_count': pending_count,
        'recent_appointments': recent_appointments,
        'monthly_data': json.dumps(monthly_data),
        'total_clients': User.objects.filter(is_staff=False).count(),
    }
    return render(request, 'appointments/admin/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def admin_appointments(request):
    filter_form = AppointmentFilterForm(request.GET)
    appointments = Appointment.objects.select_related('client', 'service', 'therapist').all()

    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            appointments = appointments.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('date_from'):
            appointments = appointments.filter(appointment_date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            appointments = appointments.filter(appointment_date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('search'):
            q = filter_form.cleaned_data['search']
            appointments = appointments.filter(
                Q(service__name__icontains=q) |
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q)
            )

    paginator = Paginator(appointments, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'appointments/admin/appointments.html', {
        'page_obj': page_obj, 'filter_form': filter_form
    })


@login_required
@user_passes_test(is_admin)
def admin_update_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        new_payment = request.POST.get('payment_status')
        if new_status:
            appointment.status = new_status
        if new_payment:
            appointment.payment_status = new_payment
        appointment.save()

        if new_status == 'confirmed':
            create_notification(
                appointment.client, 'appointment_confirmed',
                'Appointment Confirmed!',
                f'Your {appointment.service.name} appointment on {appointment.appointment_date} has been confirmed.',
                appointment
            )
        elif new_status == 'completed':
            create_notification(
                appointment.client, 'review_request',
                'How was your session?',
                f'We hope you enjoyed your {appointment.service.name}! Please leave a review.',
                appointment
            )
        messages.success(request, 'Appointment updated successfully.')
        # Redirect back to the referring page (preserves filters/pagination)
        return redirect(request.META.get('HTTP_REFERER', 'admin_appointments'))
    
    # If someone tries to GET this URL, just redirect
    return redirect('admin_appointments')


@login_required
@user_passes_test(is_admin)
def admin_services(request):
    services = MassageService.objects.all()
    return render(request, 'appointments/admin/services.html', {'services': services})


@login_required
@user_passes_test(is_admin)
def admin_service_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        desc = request.POST.get('description')
        duration = request.POST.get('duration_minutes')
        price = request.POST.get('price')
        category = request.POST.get('category')
        MassageService.objects.create(name=name, description=desc, duration_minutes=duration, price=price, category=category)
        messages.success(request, 'Service created successfully.')
        return redirect('admin_services')
    return render(request, 'appointments/admin/service_form.html', {'action': 'Create'})


@login_required
@user_passes_test(is_admin)
def admin_service_edit(request, pk):
    service = get_object_or_404(MassageService, pk=pk)
    if request.method == 'POST':
        service.name = request.POST.get('name')
        service.description = request.POST.get('description')
        service.duration_minutes = request.POST.get('duration_minutes')
        service.price = request.POST.get('price')
        service.category = request.POST.get('category')
        service.is_active = request.POST.get('is_active') == 'on'
        service.save()
        messages.success(request, 'Service updated.')
        return redirect('admin_services')
    return render(request, 'appointments/admin/service_form.html', {'action': 'Edit', 'service': service})


@login_required
@user_passes_test(is_admin)
def admin_service_delete(request, pk):
    service = get_object_or_404(MassageService, pk=pk)
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'Service deleted.')
    return redirect('admin_services')


@login_required
@user_passes_test(is_admin)
def admin_clients(request):
    clients = User.objects.filter(is_staff=False).select_related('userprofile').order_by('-date_joined').annotate(
        appt_count=Count('appointments')
    )
    search = request.GET.get('search', '')
    if search:
        clients = clients.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search))
    paginator = Paginator(clients, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'appointments/admin/clients.html', {'page_obj': page_obj, 'search': search})


@login_required
@user_passes_test(is_admin)
def admin_reports(request):
    today = datetime.date.today()
    # Service popularity
    service_stats = MassageService.objects.annotate(
        booking_count=Count('appointment'),
        revenue=Sum('appointment__total_price')
    ).order_by('-booking_count')

    # Therapist performance
    therapist_stats = Therapist.objects.annotate(
        session_count=Count('appointment'),
        avg_rating=Avg('review__rating')
    ).order_by('-session_count')

    context = {
        'service_stats': service_stats,
        'therapist_stats': therapist_stats,
        'total_revenue': Appointment.objects.filter(status='completed', payment_status='paid').aggregate(Sum('total_price'))['total_price__sum'] or 0,
    }
    return render(request, 'appointments/admin/reports.html', context)


# ──── API Endpoints ───────────────────────────────────────────────────────────

def get_service_price(request, pk):
    service = get_object_or_404(MassageService, pk=pk)
    return JsonResponse({'price': str(service.price), 'duration': service.duration_minutes})
