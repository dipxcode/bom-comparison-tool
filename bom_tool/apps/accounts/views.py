from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from .forms import CustomLoginForm, RegisterForm


@require_POST
def ajax_login(request):
    form = CustomLoginForm(request, data=request.POST)
    if form.is_valid():
        user = form.get_user()
        login(request, user)
        return JsonResponse({
            'success': True,
            'redirect_url': '/dashboard/',
            'message': f'Welcome back, {user.first_name or user.username}!',
        })
    errors = {f: [str(e) for e in el] for f, el in form.errors.items()}
    return JsonResponse({'success': False, 'errors': errors}, status=400)


@require_POST
def ajax_register(request):
    form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return JsonResponse({
            'success': True,
            'redirect_url': '/dashboard/',
            'message': f'Welcome, {user.first_name}! Account created.',
        })
    errors = {f: [str(e) for e in el] for f, el in form.errors.items()}
    return JsonResponse({'success': False, 'errors': errors}, status=400)


def ajax_logout(request):
    logout(request)
    return redirect('landing')


@login_required
def profile_view(request):
    profile = request.user.profile

    if request.method == 'POST':
        user = request.user

        # Personal fields
        user.first_name = request.POST.get('first_name', user.first_name).strip()
        user.last_name  = request.POST.get('last_name',  user.last_name).strip()
        email = request.POST.get('email', user.email).strip()
        if email and email != user.email:
            user.email = email
        user.save()

        # Profile fields
        profile.company             = request.POST.get('company', '').strip()
        profile.job_title           = request.POST.get('job_title', '').strip()
        profile.phone               = request.POST.get('phone', '').strip()
        profile.bio                 = request.POST.get('bio', '').strip()
        profile.default_key_column  = request.POST.get('default_key_column', '').strip()
        # Checkbox: present in POST → True, absent → False
        profile.email_notifications = 'email_notifications' in request.POST
        profile.save()

        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')

    from apps.comparison.models import ComparisonSession
    recent_comparisons = ComparisonSession.objects.filter(user=request.user).order_by('-created_at')[:5]

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'recent_comparisons': recent_comparisons,
    })