from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from django.contrib.auth import logout
from .models import CustomUser, Student, Teacher, Lesson, AvailableSlot, LessonAnnouncement
from .forms import TeacherProfileForm, LessonAnnouncementForm
from django.contrib.auth.forms import AuthenticationForm


User = get_user_model()


# --- LOGIN VIEW ---
def login_view(request):
    form = AuthenticationForm()  # 👈 Formu oluşturduk

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('role_redirect')
            else:
                messages.error(request, "Kullanıcı adı veya şifre yanlış.")
        else:
            messages.error(request, "Hatalı giriş yaptınız.")

    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect('login')

# --- REGISTER VIEW ---
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


# --- ROLE-BASED REDIRECT VIEW ---
@login_required
def role_based_redirect(request):
    user = request.user
    if user.is_teacher:
        return redirect('teacher_dashboard')
    elif user.is_student:
        return redirect('student_dashboard')
    else:
        return redirect('login')


# --- TEACHER DASHBOARD VIEW ---
@login_required
def teacher_dashboard(request):
    if request.user.is_teacher:
        announcements = LessonAnnouncement.objects.filter(teacher=request.user.teacher).order_by('-created_at')
        return render(request, 'users/teacher_dashboard.html', {'announcements': announcements})
    else:
        return redirect('student_dashboard')




# --- STUDENT DASHBOARD VIEW ---
@login_required
def student_dashboard(request):
    return render(request, 'users/student_dashboard.html')


# --- TEACHER PROFILE VIEW ---
@login_required
def teacher_profile(request):
    teacher = request.user.teacher
    slots = AvailableSlot.objects.filter(teacher=teacher)

    if request.method == 'POST':
        form = TeacherProfileForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, "Profiliniz başarıyla güncellendi.")
            return redirect('teacher_profile')
    else:
        form = TeacherProfileForm(instance=teacher)

    context = {
        'teacher': teacher,
        'slots': slots,
        'form': form
    }
    return render(request, 'users/teacher_profile.html', context)


# --- TEACHER APPOINTMENTS VIEW ---
@login_required
def teacher_appointments(request):
    teacher = request.user.teacher
    appointments = Appointment.objects.filter(slot__teacher=teacher)
    return render(request, 'users/teacher_appointments.html', {'appointments': appointments})


# --- LLM İSTEĞİ ATMA (Ollama İÇİN) ---
@csrf_exempt
def ask_llm(request):
    user_prompt = request.POST.get("prompt", "Merhaba, nasıl yardımcı olabilirim?")
    prompt = f"Bu soruya sadece Türkçe olarak cevap ver: {user_prompt}"

    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3",  # veya hangi model yüklüyse
                "prompt": prompt,
                "stream": False
            }
        )
        result = response.json()
        return JsonResponse({"response": result.get("response", "Cevap alınamadı.")})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def create_announcement(request):
    if not request.user.is_teacher:
        return redirect('student_dashboard')  # Öğrenci ilan veremesin

    teacher = request.user.teacher

    if request.method == 'POST':
        form = LessonAnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)  # Kaydetmeden önce öğretmen atıyoruz
            announcement.teacher = teacher
            announcement.save()
            messages.success(request, "Ders ilanı başarıyla oluşturuldu.")
            return redirect('teacher_dashboard')
    else:
        form = LessonAnnouncementForm()

    return render(request, 'users/create_announcement.html', {'form': form})
@login_required
def join_announcement(request, announcement_id):
    if not request.user.is_student:
        return redirect('teacher_dashboard')  # Öğretmen katılamaz!

    try:
        announcement = LessonAnnouncement.objects.get(id=announcement_id, student__isnull=True)
    except LessonAnnouncement.DoesNotExist:
        messages.error(request, "Bu ilana katılım mümkün değil.")
        return redirect('student_dashboard')

    student = request.user.student
    announcement.student = student
    announcement.save()

    messages.success(request, "Başarıyla derse katıldınız!")
    return redirect('student_dashboard')

@login_required
def chatbot_page(request):
    return render(request, 'users/chatbot.html')
