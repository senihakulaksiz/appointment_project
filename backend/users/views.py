from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CustomUser, Student, Teacher, Lesson
from .models import AvailableSlot
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt



User = get_user_model()  # doğru yerde tanımladık
@csrf_exempt
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        user_type = request.POST.get("user_type")
        subject = request.POST.get("subject")

        if not all([username, email, password, user_type]):
            messages.error(request, "Tüm alanları doldurun.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password)

        if user_type == "student":
            user.is_student = True
            user.save()
            Student.objects.create(user=user)

        elif user_type == "teacher":
            user.is_teacher = True
            user.save()
            lesson = Lesson.objects.get(name=subject)
            Teacher.objects.create(user=user, lesson=lesson)

        login(request, user)
        return redirect('role_redirect')

    lessons = Lesson.objects.all()
    return render(request, "users/register.html", {"lessons": lessons})



@login_required
def teacher_profile(request):
    teacher = request.user.teacher
    slots = AvailableSlot.objects.filter(teacher=teacher)
    return render(request, 'users/teacher_profile.html', {'teacher': teacher, 'slots': slots})

@login_required
def teacher_appointments(request):
    teacher = request.user.teacher
    appointments = Appointment.objects.filter(slot__teacher=teacher)
    return render(request, 'users/teacher_appointments.html', {'appointments': appointments})

@login_required
def role_based_redirect(request):
    user = request.user
    if user.is_teacher:
        return redirect('teacher_dashboard')
    elif user.is_student:
        return redirect('student_dashboard')
    else:
        return redirect('login')  # veya başka bir sayfa

@login_required
def student_dashboard(request):
    return render(request, 'users/student_dashboard.html')


@csrf_exempt
def ask_llm(request):
    prompt = request.GET.get("prompt", "Merhaba, nasıl yardımcı olabilirim?")

    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3",  # Kendi modelin buysa
                "prompt": prompt,
                "stream": False
            }
        )
        result = response.json()
        return JsonResponse({"response": result.get("response", "Yanıt alınamadı.")})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
