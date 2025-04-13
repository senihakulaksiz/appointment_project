from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('redirect/', views.role_based_redirect, name='role_redirect'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('teacher/profile/', views.teacher_profile, name='teacher_dashboard'),
    path('student/profile/', views.student_dashboard, name='student_dashboard'),
    path('teacher/appointments/', views.teacher_appointments, name='teacher_appointments'),


]
