import json
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ComparisonSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comparison_sessions')
    name = models.CharField(max_length=200, help_text='Friendly name for this comparison')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_comparisons = models.PositiveIntegerField(default=0)
    avg_match_score = models.FloatField(default=0.0)

    class Meta:
        verbose_name = 'Comparison Session'
        verbose_name_plural = 'Comparison Sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.user.username})'

    def get_master_file(self):
        return self.files.filter(file_role='master').first()

    def get_optional_files(self):
        return self.files.filter(file_role='optional').order_by('uploaded_at')

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        results = self.results.all()
        if results.exists():
            self.total_comparisons = results.count()
            self.avg_match_score = sum(r.match_score for r in results) / results.count()
        self.save()


class BOMFile(models.Model):
    ROLE_CHOICES = [
        ('master', 'Master BOM'),
        ('optional', 'Optional BOM'),
    ]

    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel (XLSX)'),
        ('xls', 'Excel (XLS)'),
        ('json', 'JSON'),
    ]

    session = models.ForeignKey(ComparisonSession, on_delete=models.CASCADE, related_name='files')
    file_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    file = models.FileField(upload_to='bom_files/%Y/%m/')
    original_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    file_size = models.PositiveBigIntegerField(default=0)  # bytes
    row_count = models.PositiveIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)
    columns_detected = models.JSONField(default=list)
    key_column_detected = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    parse_error = models.TextField(blank=True)

    class Meta:
        verbose_name = 'BOM File'
        verbose_name_plural = 'BOM Files'
        ordering = ['file_role', 'uploaded_at']

    def __str__(self):
        return f'{self.original_name} ({self.file_role})'

    def get_file_size_display(self):
        size = self.file_size
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        else:
            return f'{size / (1024 * 1024):.1f} MB'


class ComparisonResult(models.Model):
    session = models.ForeignKey(ComparisonSession, on_delete=models.CASCADE, related_name='results')
    master_file = models.ForeignKey(BOMFile, on_delete=models.CASCADE, related_name='as_master')
    optional_file = models.ForeignKey(BOMFile, on_delete=models.CASCADE, related_name='as_optional')
    key_column_used = models.CharField(max_length=100, blank=True)
    common_columns = models.JSONField(default=list)
    match_score = models.FloatField(default=0.0)
    exact_match_count = models.PositiveIntegerField(default=0)
    partial_match_count = models.PositiveIntegerField(default=0)
    missing_count = models.PositiveIntegerField(default=0)
    extra_count = models.PositiveIntegerField(default=0)
    total_master_rows = models.PositiveIntegerField(default=0)
    total_optional_rows = models.PositiveIntegerField(default=0)
    result_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comparison Result'
        verbose_name_plural = 'Comparison Results'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.master_file.original_name} vs {self.optional_file.original_name} — {self.match_score:.1f}%'

    def get_score_badge_class(self):
        if self.match_score >= 90:
            return 'score-excellent'
        elif self.match_score >= 70:
            return 'score-good'
        elif self.match_score >= 50:
            return 'score-fair'
        else:
            return 'score-poor'

    def get_result_json(self):
        return json.dumps(self.result_data, indent=2, default=str)