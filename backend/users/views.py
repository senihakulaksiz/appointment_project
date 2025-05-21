from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
from django.contrib.auth import logout
from .models import CustomUser, Student, Teacher, Lesson, AvailableSlot, LessonAnnouncement, Message
from .forms import TeacherProfileForm, LessonAnnouncementForm, MessageForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import ApplyToAnnouncementForm


User = get_user_model()


# --- LOGIN VIEW ---
def login_view(request):
    form = AuthenticationForm()

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


@login_required
def role_redirect(request):
    if request.user.is_teacher:
        return redirect('teacher_dashboard')
    elif request.user.is_student:
        return redirect('student_dashboard')
    else:
        return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('login')

# --- REGISTER VIEW ---
@csrf_exempt  # Şu anda deneme amaçlı sorun değil
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        user_type = request.POST.get("user_type")
        subject = request.POST.get("subject")  # sadece öğretmene lazım

        if not all([username, email, password, user_type]):
            messages.error(request, "Lütfen tüm alanları doldurun.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password)

        if user_type == "student":
            user.is_student = True
            user.save()
            Student.objects.create(user=user)

        elif user_type == "teacher":
            user.is_teacher = True
            user.save()
            try:
                lesson = Lesson.objects.get(name=subject)
                Teacher.objects.create(user=user, lesson=lesson)
            except Lesson.DoesNotExist:
                messages.error(request, "Seçilen branş bulunamadı.")
                user.delete()  # yanlış veri oluşmasın
                return redirect("register")

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
        announcements = LessonAnnouncement.objects.all().order_by('-created_at')
        return render(request, 'users/teacher_dashboard.html', {'announcements': announcements})
    else:
        return redirect('student_dashboard')




# --- STUDENT DASHBOARD VIEW ---
@login_required
def student_dashboard(request):
    announcements = LessonAnnouncement.objects.all()
    lessons = Lesson.objects.all()

    # Filtre veya arama varsa
    branch = request.GET.get('branch')
    teacher_name = request.GET.get('teacher_name')

    if branch:
        announcements = announcements.filter(lesson__name=branch)

    if teacher_name:
        announcements = announcements.filter(teacher__user__username__icontains=teacher_name)

    return render(request, 'users/student_dashboard.html', {'announcements': announcements, 'lessons': lessons})


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

@login_required
def student_profile(request):
    user = request.user

    # Öğrenci modeli üzerinden randevu aldığı öğretmenleri bul
    try:
        student = user.student
    except:
        student = None

    if student:
        joined_teachers = Teacher.objects.filter(
            availableslot__appointment__student=student
        ).distinct()
    else:
        joined_teachers = []

    context = {
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined,
        'joined_teachers': joined_teachers
    }

    return render(request, 'users/student_profile.html', context)

    return render(request, 'users/student_profile.html', context)
@login_required
def student_change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Şifre değişince login kalmaya devam etsin
            messages.success(request, 'Şifreniz başarıyla güncellendi!')
            return redirect('student_profile')
        else:
            messages.error(request, 'Lütfen hataları düzeltin.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/change_password.html', {'form': form})


# --- TEACHER APPOINTMENTS VIEW ---
@login_required
def teacher_appointments(request):
    teacher = request.user.teacher
    appointments = Appointment.objects.filter(slot__teacher=teacher)
    return render(request, 'users/teacher_appointments.html', {'appointments': appointments})


# --- LLM İSTEĞİ ATMA (Ollama İÇİN) ---
@csrf_exempt
@login_required
def ask_llm(request):
    user_prompt = request.POST.get("prompt", "").strip()

    # Hazır sorular
    predefined_questions = {
        "ilk_soru": "Şu an başvurabileceğim ders var mı?",
        "ikinci_soru": "Katıldığım dersler neler?"
    }

    # Eğer gelen prompt boşsa veya belirli bir keyword ise hazır soruyu kullan
    if not user_prompt:
        user_prompt = predefined_questions["ilk_soru"]
    elif user_prompt.lower() in ["ilk soru", "soru 1"]:
        user_prompt = predefined_questions["ilk_soru"]
    elif user_prompt.lower() in ["ikinci soru", "soru 2"]:
        user_prompt = predefined_questions["ikinci_soru"]

    katildigi_dersler = "Yok"
    basvurabilecegi_dersler = "Yok"
    onaybekleyen_basvurular = "Yok"
    yayinladigi_dersler = "Yok"
    basvuran_ogrenciler = "Yok"
    yayinladigi_branslar = "Yok"

    try:
        if request.user.is_student:
            student = request.user.student
            lessons_joined = LessonAnnouncement.objects.filter(student=student, is_approved=True)
            if lessons_joined.exists():
                katildigi_dersler = ", ".join([f"{l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in lessons_joined])

            available_lessons = LessonAnnouncement.objects.filter(student__isnull=True)
            if available_lessons.exists():
                basvurabilecegi_dersler = ", ".join([f"{l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in available_lessons])

            pending_lessons = LessonAnnouncement.objects.filter(student=student, is_approved=False)
            if pending_lessons.exists():
                onaybekleyen_basvurular = ", ".join([f"{l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in pending_lessons])

        elif request.user.is_teacher:
            teacher = request.user.teacher
            teacher_announcements = LessonAnnouncement.objects.filter(teacher=teacher)
            if teacher_announcements.exists():
                yayinladigi_dersler = ", ".join([
                    f"{l.lesson.name} (Öğrenci: {l.student.user.username if l.student else 'Henüz başvuru yok'})"
                    for l in teacher_announcements
                ])

            applications_pending = LessonAnnouncement.objects.filter(teacher=teacher, student__isnull=False, is_approved=False)
            if applications_pending.exists():
                basvuran_ogrenciler = ", ".join([f"{l.lesson.name} (Başvuran: {l.student.user.username})" for l in applications_pending])

            lesson = getattr(teacher, 'lesson', None)
            if lesson:
                yayinladigi_branslar = lesson.name

        prompt = (
            f"You are a smart assistant for a private tutoring platform. "
            f"Help users with their lessons, applications, announcements, and teacher profiles.\n\n"
            f"User current data:\n"
            f"- Joined lessons: {katildigi_dersler}\n"
            f"- Available lessons: {basvurabilecegi_dersler}\n"
            f"- Pending applications: {onaybekleyen_basvurular}\n"
            f"- Published lessons: {yayinladigi_dersler}\n"
            f"- Applicants: {basvuran_ogrenciler}\n"
            f"- Published branches: {yayinladigi_branslar}\n\n"
            f"Example Q&A:\n"
            f"Q: Do I have any joined lessons?\n"
            f"A: Yes, you are registered for the following lessons: Math (Teacher: Ahmet Hoca).\n\n"
            f"Q: Are there any applicants for my published lesson?\n"
            f"A: Yes, Ayşe has applied for the Turkish lesson.\n\n"
            f"User question:\n\"{user_prompt}\"\n\n"
            f"Please answer clearly, politely, and only based on the provided information. "
            f"Do not guess or make up information. "
            f"Keep your answer short and in Turkish."
        )

        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 300
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
            announcement.lesson = teacher.lesson
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

@login_required
def my_lessons(request):
    student = request.user.student
    approved_lessons = LessonAnnouncement.objects.filter(student=student, is_approved=True).order_by('student_requested_date', 'student_requested_time')
    pending_lessons = LessonAnnouncement.objects.filter(student=student, is_approved=False)
    return render(request, 'users/my_lessons.html', {
        'approved_lessons': approved_lessons,
        'pending_lessons': pending_lessons
    })

@login_required
def apply_to_announcement(request, announcement_id):
    if not request.user.is_student:
        return redirect('teacher_dashboard')  # Güvenlik: Öğretmen başvuramasın

    try:
        announcement = LessonAnnouncement.objects.get(id=announcement_id, student__isnull=True)
    except LessonAnnouncement.DoesNotExist:
        messages.error(request, "Bu ilana başvuramazsınız.")
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = ApplyToAnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.student = request.user.student
            announcement.save()
            messages.success(request, "Başvurunuz başarıyla alındı!")
            return redirect('student_dashboard')
    else:
        form = ApplyToAnnouncementForm()

    return render(request, 'users/apply_to_announcement.html', {'form': form, 'announcement': announcement})

@login_required
def delete_announcement(request, announcement_id):
    teacher = request.user.teacher
    try:
        announcement = LessonAnnouncement.objects.get(id=announcement_id, teacher=teacher)
        announcement.delete()
        messages.success(request, "İlan başarıyla silindi.")
    except LessonAnnouncement.DoesNotExist:
        messages.error(request, "Silinecek ilan bulunamadı.")

    return redirect('my_announcements')



@login_required
def approve_application(request, announcement_id):
    if not request.user.is_teacher:
        return redirect('student_dashboard')  # Güvenlik: Sadece öğretmen onaylayabilir

    try:
        announcement = LessonAnnouncement.objects.get(id=announcement_id, teacher=request.user.teacher, student__isnull=False)
    except LessonAnnouncement.DoesNotExist:
        messages.error(request, "Onaylanacak uygun başvuru bulunamadı.")
        return redirect('teacher_dashboard')

    announcement.is_approved = True
    announcement.save()

    messages.success(request, "Başvuru başarıyla onaylandı!")
    return redirect('teacher_dashboard')

@login_required
def view_teacher_profile(request, teacher_id):
    try:
        teacher = Teacher.objects.get(id=teacher_id)
    except Teacher.DoesNotExist:
        messages.error(request, "Öğretmen bulunamadı.")
        return redirect('student_dashboard')

    return render(request, 'users/view_teacher_profile.html', {'teacher': teacher})

@login_required
def my_announcements(request):
    teacher = request.user.teacher

    # 1. Kendi oluşturduğu ilanlar
    created_announcements = LessonAnnouncement.objects.filter(teacher=teacher).order_by('-created_at')

    # 2. Başvurusunu onayladığı ilanlar
    approved_announcements = LessonAnnouncement.objects.filter(teacher=teacher, is_approved=True).order_by('-created_at')
    pending_announcements = LessonAnnouncement.objects.filter(teacher=teacher, is_approved=False, student__isnull=False).order_by('-created_at')

    context = {
        'created_announcements': created_announcements,
        'approved_announcements': approved_announcements,
        'pending_announcements': pending_announcements,
    }
    return render(request, 'users/my_announcements.html', context)

@login_required
def chat_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    messages = Message.objects.filter(
        sender__in=[request.user, other_user],
        receiver__in=[request.user, other_user]
    )

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            new_msg = form.save(commit=False)
            new_msg.sender = request.user
            new_msg.receiver = other_user
            new_msg.save()
            return redirect('chat_with_user', user_id=other_user.id)
    else:
        form = MessageForm()

    users = User.objects.exclude(id=request.user.id)  # Mesajlaşılabilecek diğer kullanıcılar
    return render(request, 'chat.html', {
        'active_user': other_user,
        'users': users,
        'messages': messages,
        'form': form
    })

@login_required
def chat_with_user_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    # 🔄 Sadece ilgili kişiler listelensin
    if request.user.is_student:
        student = request.user.student
        # Katıldığı ilanların öğretmenleri
        related_announcements = LessonAnnouncement.objects.filter(student=student, is_approved=True)
        allowed_users = [ann.teacher.user for ann in related_announcements]
    elif request.user.is_teacher:
        teacher = request.user.teacher
        # Öğretmenin ilanlarına başvuran öğrenciler
        related_announcements = LessonAnnouncement.objects.filter(teacher=teacher, student__isnull=False)
        allowed_users = [ann.student.user for ann in related_announcements]
    else:
        allowed_users = []

    # Sidebar kullanıcıları (listede gözüken kişiler)
    users = allowed_users

    # Eğer seçilen kullanıcı listede yoksa, hata gösterme
    if other_user not in allowed_users:
        messages.error(request, "Bu kullanıcıyla mesajlaşamazsınız.")
        return redirect('chat')

    # Ortak mesajlar
    messages_qs = Message.objects.filter(
        sender=request.user, receiver=other_user
    ) | Message.objects.filter(
        sender=other_user, receiver=request.user
    )
    messages_qs = messages_qs.order_by('timestamp')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.receiver = other_user
            msg.save()
            return redirect('chat_with_user', user_id=other_user.id)
    else:
        form = MessageForm()

    return render(request, 'users/chat.html', {
        'messages': messages_qs,
        'form': form,
        'users': users,
        'active_user': other_user,
    })
@login_required
def chat_home(request):
    if request.user.is_student:
        student = request.user.student
        related_announcements = LessonAnnouncement.objects.filter(student=student, is_approved=True)
        allowed_users = [ann.teacher.user for ann in related_announcements]
    elif request.user.is_teacher:
        teacher = request.user.teacher
        related_announcements = LessonAnnouncement.objects.filter(teacher=teacher, student__isnull=False)
        allowed_users = [ann.student.user for ann in related_announcements]
    else:
        allowed_users = []

    return render(request, 'users/chat.html', {
        'active_user': None,
        'users': allowed_users,
        'messages': [],
        'form': None
    })
