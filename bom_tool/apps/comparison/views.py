from django.shortcuts import render

# Create your views here.
import json
import logging
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.core.mail import send_mail
from django.conf import settings

from .models import ComparisonSession, BOMFile, ComparisonResult
from .forms import ComparisonSessionForm
from .utils import read_bom_file, get_file_metadata, compare_bom

logger = logging.getLogger(__name__)

MASTER_EXTENSIONS = {'.xlsx'}
TARGET_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.docx', '.pdf', '.txt'}
EXT_TO_FORMAT = {
    '.csv': 'csv', '.xlsx': 'xlsx', '.xls': 'xls',
    '.docx': 'docx', '.pdf': 'pdf', '.txt': 'txt',
}


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def _validate_master(f):
    ext = _ext(f.name)
    if ext not in MASTER_EXTENSIONS:
        return False, f'Master BOM must be XLSX (received "{ext}").'
    if f.size > 25 * 1024 * 1024:
        return False, f'"{f.name}" exceeds the 25 MB limit.'
    return True, ''


def _validate_target(f):
    ext = _ext(f.name)
    if ext not in TARGET_EXTENSIONS:
        return False, f'"{f.name}": unsupported format. Use CSV, XLSX, XLS, DOCX, PDF or TXT.'
    if f.size > 25 * 1024 * 1024:
        return False, f'"{f.name}" exceeds the 25 MB limit.'
    return True, ''


def _send_completion_email(session):
    """Send email notification when a comparison session completes (if user opted in)."""
    try:
        user = session.user
        if not getattr(user, 'profile', None):
            return
        if not user.profile.email_notifications:
            return
        if not user.email:
            return

        result_url = f'/comparison/results/{session.id}/'
        files_info = '\n'.join(
            f'  • {r.optional_file.original_name}: {r.match_score:.1f}% match'
            for r in session.results.select_related('optional_file').all()
        )

        subject = f'BOMCompare — "{session.name}" completed'
        message = (
            f'Hi {user.first_name or user.username},\n\n'
            f'Your BOM comparison "{session.name}" has finished.\n\n'
            f'Results:\n{files_info}\n\n'
            f'Overall average score: {session.avg_match_score:.1f}%\n\n'
            f'View full results: {result_url}\n\n'
            f'— BOMCompare\n\n'
            f'To disable these notifications, go to Profile Settings.'
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'BOMCompare <noreply@bomcompare.local>'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info(f'Completion email sent to {user.email} for session {session.id}')
    except Exception as e:
        logger.warning(f'Failed to send completion email for session {session.id}: {e}')


@login_required
def upload_view(request):
    if request.method == 'POST':
        form = ComparisonSessionForm(request.POST, request.FILES)
        master_file    = request.FILES.get('master_file')
        optional_files = request.FILES.getlist('optional_files')
        errors = []

        if not master_file:
            errors.append('A master BOM file (XLSX) is required.')
        else:
            ok, msg = _validate_master(master_file)
            if not ok: errors.append(msg)

        if not optional_files:
            errors.append('At least one target BOM file is required.')
        elif len(optional_files) > 5:
            errors.append('Maximum 5 target files allowed.')
        else:
            for f in optional_files:
                ok, msg = _validate_target(f)
                if not ok: errors.append(msg)

        if errors or not form.is_valid():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                all_err = errors + [str(e) for fe in form.errors.values() for e in fe]
                return JsonResponse({'success': False, 'errors': all_err}, status=400)
            for e in errors: form.add_error(None, e)
            return render(request, 'comparison/upload.html', {'form': form})

        session = form.save(commit=False)
        session.user   = request.user
        session.status = 'processing'
        session.save()

        key_column_override = form.cleaned_data.get('key_column') or None

        try:
            master_bom = BOMFile.objects.create(
                session=session, file_role='master', file=master_file,
                original_name=master_file.name,
                file_format=EXT_TO_FORMAT.get(_ext(master_file.name), 'xlsx'),
                file_size=master_file.size,
            )
            master_df = read_bom_file(master_bom.file.path)
            meta = get_file_metadata(master_df)
            master_bom.row_count           = meta['row_count']
            master_bom.column_count        = meta['column_count']
            master_bom.columns_detected    = meta['columns']
            master_bom.key_column_detected = meta['key_column_detected']
            master_bom.save()

            for opt_file in optional_files:
                ext_o = _ext(opt_file.name)
                opt_bom = BOMFile.objects.create(
                    session=session, file_role='optional', file=opt_file,
                    original_name=opt_file.name,
                    file_format=EXT_TO_FORMAT.get(ext_o, 'csv'),
                    file_size=opt_file.size,
                )
                try:
                    opt_df = read_bom_file(opt_bom.file.path)
                    meta_o = get_file_metadata(opt_df)
                    opt_bom.row_count           = meta_o['row_count']
                    opt_bom.column_count        = meta_o['column_count']
                    opt_bom.columns_detected    = meta_o['columns']
                    opt_bom.key_column_detected = meta_o['key_column_detected']
                    opt_bom.save()

                    result_data = compare_bom(
                        master_df.copy(), opt_df.copy(),
                        key_column=key_column_override,
                        master_label=master_bom.original_name,
                        optional_label=opt_bom.original_name,
                    )
                    ComparisonResult.objects.create(
                        session=session,
                        master_file=master_bom, optional_file=opt_bom,
                        key_column_used=result_data['key_column_used'],
                        common_columns=result_data['common_columns'],
                        match_score=result_data['match_score'],
                        exact_match_count=result_data['summary']['exact_matches'],
                        partial_match_count=result_data['summary']['partial_matches'],
                        missing_count=result_data['summary']['missing_in_optional'],
                        extra_count=result_data['summary']['extra_in_optional'],
                        total_master_rows=result_data['summary']['total_master_rows'],
                        total_optional_rows=result_data['summary']['total_optional_rows'],
                        result_data=result_data,
                    )
                except Exception as e:
                    logger.error(f'Target file error ({opt_file.name}): {e}')
                    opt_bom.parse_error = str(e)
                    opt_bom.save()

            session.mark_completed()

            profile = request.user.profile
            profile.total_comparisons    += 1
            profile.total_files_uploaded += 1 + len(optional_files)
            profile.save()

            # Send email notification if enabled
            _send_completion_email(session)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'redirect_url': f'/comparison/results/{session.id}/'})
            return redirect('comparison_results', session_id=session.id)

        except Exception as e:
            logger.error(f'Session {session.id} failed: {e}')
            session.status = 'failed'
            session.error_message = str(e)
            session.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': [str(e)]}, status=500)
            form.add_error(None, str(e))
            return render(request, 'comparison/upload.html', {'form': form})
    else:
        form = ComparisonSessionForm()

    return render(request, 'comparison/upload.html', {'form': form})


@login_required
def results_view(request, session_id):
    session = get_object_or_404(ComparisonSession, id=session_id, user=request.user)
    results = session.results.select_related('master_file', 'optional_file').all()

    results_data = {}
    for r in results:
        details = {}
        if r.result_data and isinstance(r.result_data, dict):
            raw = r.result_data.get('details', {})
            details = raw

        results_data[str(r.id)] = {
            'key_col':     r.key_column_used or 'Row #',
            'common_cols': list(r.common_columns) if r.common_columns else [],
            'details':     details,
            'score':       float(r.match_score),
        }

    context = {
        'session':      session,
        'results':      results,
        'master_file':  session.get_master_file(),
        'results_data': results_data,
    }
    return render(request, 'comparison/results.html', context)


@login_required
def history_view(request):
    sessions = ComparisonSession.objects.filter(user=request.user) \
                .prefetch_related('files', 'results').order_by('-created_at')
    stats = sessions.aggregate(
        total=Count('id'),
        avg_score=Avg('avg_match_score'),
        completed=Count('id', filter=Q(status='completed')),
    )
    return render(request, 'comparison/history.html', {'sessions': sessions, 'stats': stats})


@login_required
def download_result_json(request, result_id):
    result = get_object_or_404(ComparisonResult, id=result_id, session__user=request.user)
    payload = {
        'metadata': {
            'session_name':  result.session.name,
            'master_file':   result.master_file.original_name,
            'optional_file': result.optional_file.original_name,
            'key_column':    result.key_column_used,
            'generated_at':  timezone.now().isoformat(),
        },
        'summary': {
            'match_score':         result.match_score,
            'exact_matches':       result.exact_match_count,
            'partial_matches':     result.partial_match_count,
            'missing_in_optional': result.missing_count,
            'extra_in_optional':   result.extra_count,
            'total_master_rows':   result.total_master_rows,
            'total_optional_rows': result.total_optional_rows,
        },
        'details': result.result_data.get('details', {}) if result.result_data else {},
    }
    name_m = result.master_file.original_name.rsplit('.', 1)[0]
    name_o = result.optional_file.original_name.rsplit('.', 1)[0]
    filename = f"bom_compare_{name_m}_vs_{name_o}.json"
    resp = HttpResponse(json.dumps(payload, indent=2, default=str), content_type='application/json')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def delete_session(request, session_id):
    session = get_object_or_404(ComparisonSession, id=session_id, user=request.user)
    if request.method == 'POST':
        session.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)