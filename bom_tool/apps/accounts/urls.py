from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.ajax_login, name='ajax_login'),
    path('register/', views.ajax_register, name='ajax_register'),
    path('logout/', views.ajax_logout, name='logout'),
    path('profile/', views.profile_view, name='profile'),
]