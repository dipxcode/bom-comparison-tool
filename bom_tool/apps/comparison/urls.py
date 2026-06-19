from django.urls import path
from . import views

urlpatterns = [
    path('new/', views.upload_view, name='comparison_upload'),
    path('results/<int:session_id>/', views.results_view, name='comparison_results'),
    path('history/', views.history_view, name='comparison_history'),
    path('download/<int:result_id>/', views.download_result_json, name='download_result'),
    path('delete/<int:session_id>/', views.delete_session, name='delete_session'),
]