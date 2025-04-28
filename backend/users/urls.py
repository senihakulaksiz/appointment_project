from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),  # ➔ bizim yazdığımız login_view kullanılacak
    path('logout/', views.logout_view, name='logout'),  # ➔ logout işlemi için ayrıca bir view yazacağız (aşağıda göstereceğim)
    path('redirect/', views.role_based_redirect, name='role_redirect'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/profile/', views.teacher_profile, name='teacher_profile'),
    path('teacher/appointments/', views.teacher_appointments, name='teacher_appointments'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/profile/', views.student_profile, name='student_profile'),
    path('teacher/announcement/new/', views.create_announcement, name='create_announcement'),
    path('student/join-announcement/<int:announcement_id>/', views.join_announcement, name='join_announcement'),
    path("ask-llm/", views.ask_llm, name="ask_llm"),
    path('chatbot/', views.chatbot_page, name='chatbot_page'),
    path('redirect/', views.role_redirect, name='role_redirect'),
    path('student/my-lessons/', views.my_lessons, name='my_lessons'),


]
