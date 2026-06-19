from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.comparison.models import ComparisonSession, BOMFile, ComparisonResult


def landing_page(request):
    if request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('dashboard')
    return render(request, 'landing.html')


@login_required
def dashboard_view(request):
    user = request.user
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    all_sessions = ComparisonSession.objects.filter(user=user)
    session_stats = all_sessions.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        failed=Count('id', filter=Q(status='failed')),
        avg_score=Avg('avg_match_score'),
    )

    recent_sessions = all_sessions.prefetch_related('files', 'results').order_by('-created_at')[:8]
    total_files = BOMFile.objects.filter(session__user=user).count()
    last_30 = all_sessions.filter(created_at__gte=thirty_days_ago).extra(select={'day': "date(created_at)"}).values('day').annotate(count=Count('id')).order_by('day')

    activity_data = {str(row['day']): row['count'] for row in last_30}
    top_results = ComparisonResult.objects.filter(session__user=user, session__status='completed', ).select_related('session', 'optional_file').order_by('-match_score')[:5]

    all_results = ComparisonResult.objects.filter(session__user=user)
    score_buckets = {
        'Excellent (90–100%)': all_results.filter(match_score__gte=90).count(),
        'Good (70–89%)':       all_results.filter(match_score__gte=70, match_score__lt=90).count(),
        'Fair (50–69%)':       all_results.filter(match_score__gte=50, match_score__lt=70).count(),
        'Poor (<50%)':         all_results.filter(match_score__lt=50).count(),
    }

    context = {
        'session_stats': session_stats,
        'recent_sessions': recent_sessions,
        'total_files': total_files,
        'activity_data': activity_data,
        'top_results': top_results,
        'score_buckets': score_buckets,
        'chart_labels': list(score_buckets.keys()),
        'chart_data': list(score_buckets.values()),
        'page_title': 'Dashboard',
    }
    return render(request, 'dashboard/index.html', context)


import json as _json

def _chart_data(score_buckets):
    return (
        _json.dumps(list(score_buckets.keys())),
        _json.dumps(list(score_buckets.values()))
    )