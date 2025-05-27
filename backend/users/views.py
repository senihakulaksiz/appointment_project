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
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import ApplyToAnnouncementForm
from .models import ChatRequest, Message
from .forms import MessageForm, ChatRequestForm
from django.db.models import Q
from .models import Notification

from users.tasks import notify_admin_teacher_registered

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


@login_required
def role_redirect(request):
    if hasattr(request.user, 'teacher'):
        return redirect('teacher_dashboard')
    elif hasattr(request.user, 'student'):
        return redirect('student_dashboard')
    else:
        return redirect('login')

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

                #  Admin'e e-posta bildirimi gönder (CELERY)
                from users.tasks import notify_admin_teacher_registered
                notify_admin_teacher_registered.delay(user.username, user.email)

            except Lesson.DoesNotExist:
                messages.error(request, "Seçilen branş bulunamadı.")
                user.delete()
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
    context = {
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined,
    }
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
    user_prompt = request.POST.get("prompt", "Merhaba, nasıl yardımcı olabilirim?")

    # 🔒 Tüm veri alanlarını varsayılan olarak boş ayarla (hata riskini sıfırla)
    katildigi_dersler = "Yok"
    basvurabilecegi_dersler = "Yok"
    onay_bekleyen_basvurular = "Yok"
    yayinladigi_dersler = "Yok"
    basvuran_ogrenciler = "Yok"
    yayinladigi_branşlar = "Yok"

    # 👩‍🎓 Öğrenci ise
    if hasattr(request.user, 'student'):
        # Katıldığı onaylanmış dersler
        lessons_joined = LessonAnnouncement.objects.filter(student=request.user.student, is_approved=True)
        if lessons_joined.exists():
            katildigi_dersler = "\n".join([
                f"- {l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in lessons_joined
            ])

        # Başvurabileceği boş dersler
        available_lessons = LessonAnnouncement.objects.filter(student__isnull=True)
        if available_lessons.exists():
            basvurabilecegi_dersler = "\n".join([
                f"- {l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in available_lessons
            ])

        # Onay bekleyen başvurular
        pending_lessons = LessonAnnouncement.objects.filter(student=request.user.student, is_approved=False)
        if pending_lessons.exists():
            onay_bekleyen_basvurular = "\n".join([
                f"- {l.lesson.name} (Öğretmen: {l.teacher.user.username})" for l in pending_lessons
            ])

    # 👨‍🏫 Öğretmen ise
    elif hasattr(request.user, 'teacher'):
        # Yayınladığı ders ilanları
        teacher_announcements = LessonAnnouncement.objects.filter(teacher=request.user.teacher)
        if teacher_announcements.exists():
            yayinladigi_dersler = "\n".join([
                f"- {l.lesson.name} (Öğrenci: {l.student.user.username if l.student else 'Henüz başvuru yok'})" for l in teacher_announcements
            ])

        # Başvuru almış ama onaylanmamış olanlar
        applications_pending = LessonAnnouncement.objects.filter(
            teacher=request.user.teacher, student__isnull=False, is_approved=False
        )
        if applications_pending.exists():
            basvuran_ogrenciler = "\n".join([
                f"- {l.lesson.name} (Başvuran: {l.student.user.username})" for l in applications_pending
            ])

        # Yayınladığı branşlar
        lesson = getattr(request.user.teacher, 'lesson', None)
        if lesson:
            yayinladigi_branşlar = f"- {lesson.name}"

    # 🧠 LLM'e gönderilecek prompt
    prompt = (
        f"Sen bir özel ders platformunun akıllı sohbet asistanısın. Kullanıcılara ders katılımı, başvurular, "
        f"ilan durumu ve öğretmen profilleri hakkında yardımcı olursun.\n\n"
        f"Kullanıcının mevcut durumu:\n"
        f"- Katıldığı Dersler:\n{katildigi_dersler}\n"
        f"- Başvurabileceği Dersler:\n{basvurabilecegi_dersler}\n"
        f"- Onay Bekleyen Başvurular:\n{onay_bekleyen_basvurular}\n"
        f"- Yayınladığı Dersler:\n{yayinladigi_dersler}\n"
        f"- Başvuran Öğrenciler:\n{basvuran_ogrenciler}\n"
        f"- Yayınladığı Branşlar:\n{yayinladigi_branşlar}\n\n"

        f"📌 Örnek Soru-Cevaplar (Kullanıcıya yardımcı olacak hazır sorular):\n"
        f"👩‍🎓 Öğrenci:\n"
        f"Soru: Katıldığım ders var mı?\n"
        f"Cevap: {katildigi_dersler if katildigi_dersler != 'Yok' else 'İlgili bilgi bulunamadı.'}\n\n"
        f"Soru: Başvurabileceğim ders var mı?\n"
        f"Cevap: {basvurabilecegi_dersler if basvurabilecegi_dersler != 'Yok' else 'Şu anda başvurabileceğiniz bir ders bulunmamaktadır.'}\n\n"
        f"👨‍🏫 Öğretmen:\n"
        f"Soru: Derslerime kimler katılmış?\n"
        f"Cevap: {yayinladigi_dersler if yayinladigi_dersler != 'Yok' else 'Henüz öğrencisi olan dersiniz bulunmamaktadır.'}\n\n"

        f"🗣 Kullanıcının gerçek sorusu:\n\"{user_prompt}\"\n\n"

        f"📌 Kurallar:\n"
        f"- Sadece yukarıdaki bilgilere göre cevap ver\n"
        f"- Açık, kısa ve kullanıcı dostu bir Türkçe kullan\n"
        f"- Bilgi yoksa 'ilgili bilgi bulunamadı' de\n"
        f"- Uydurma bilgi verme, tahmin yapma\n"
        f"- Aynı şeyi tekrar etme veya gereksiz cümle kurma\n"
    )

    # 🔁 LLM ile iletişim
    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3",
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
def send_chat_request(request, teacher_id):
    receiver = CustomUser.objects.get(id=teacher_id)
    return redirect('chat_with_user', user_id=receiver.id)


@login_required
def chat_requests(request):
    pending_requests = ChatRequest.objects.filter(receiver=request.user, is_accepted=False)
    return render(request, 'users/message_requests.html', {'pending_requests': pending_requests})


@login_required
def accept_chat_request(request, request_id):
    try:
        chat_request = ChatRequest.objects.get(id=request_id, receiver=request.user)
        chat_request.is_accepted = True
        chat_request.save()
        messages.success(request, "Mesaj isteği kabul edildi.")
    except ChatRequest.DoesNotExist:
        messages.error(request, "İstek bulunamadı.")
    return redirect('chat_requests')


@login_required
def chat_with_user(request, user_id):
    other_user = CustomUser.objects.get(id=user_id)

    # Sohbet geçmişi
    messages_qs = Message.objects.filter(
        sender__in=[request.user, other_user],
        receiver__in=[request.user, other_user]
    ).order_by('timestamp')

    # ChatRequest kontrolü
    try:
        chat_request = ChatRequest.objects.get(
            sender__in=[request.user, other_user],
            receiver__in=[request.user, other_user]
        )
        is_accepted = chat_request.is_accepted
    except ChatRequest.DoesNotExist:
        chat_request = None
        is_accepted = False

    is_sender_student = request.user.is_student and (chat_request is None or chat_request.sender == request.user)
    student_sent_message = messages_qs.filter(sender=request.user).exists()

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            # Eğer öğrenci ilk mesajı atıyorsa, ChatRequest yarat
            if not chat_request and request.user.is_student:
                chat_request = ChatRequest.objects.create(
                    sender=request.user,
                    receiver=other_user,
                    is_accepted=False
                )
                is_accepted = False
                is_sender_student = True

                # 🟡 Mesaj isteği bildirimi
                Notification.objects.create(
                    user=other_user,
                    message=f"{request.user.username} adlı öğrenci size mesaj atmak istiyor.",
                    link=f"/users/chat/{request.user.id}/"
                )

            # Öğretmen istek onaylamadan yazamaz
            if request.user.is_teacher and not is_accepted:
                messages.error(request, "Öğrenci isteğini kabul etmeden mesaj gönderemezsiniz.")
            else:
                message = form.save(commit=False)
                message.sender = request.user
                message.receiver = other_user
                message.save()

                # 🟢 Normal mesaj bildirimi
                Notification.objects.create(
                    user=other_user,
                    message=f"{request.user.username} size bir mesaj gönderdi.",
                    link=f"/users/chat/{request.user.id}/"
                )

                # 💡 Bildirim oluştur (sadece öğrenciden gelen ilk mesaj için)
                if request.user.is_student and chat_request and not is_accepted and not Notification.objects.filter(user=other_user, message__icontains="size bir mesaj isteği gönderdi").exists():
                    Notification.objects.create(
                        user=other_user,
                        message=f"{request.user.username} size bir mesaj isteği gönderdi.",
                        is_read=False
                    )

                return redirect('chat_with_user', user_id=other_user.id)
    else:
        form = MessageForm()

    return render(request, 'users/chat.html', {
        'messages': messages_qs,
        'form': form,
        'active_user': other_user,
        'users': get_chat_partners(request.user),
        'is_accepted': is_accepted,
        'awaiting_approval': not is_accepted and is_sender_student and student_sent_message
    })


def get_chat_partners(user):
    accepted = ChatRequest.objects.filter(
        (Q(sender=user) | Q(receiver=user)),
        is_accepted=True
    )
    partner_ids = set()
    for r in accepted:
        partner_ids.add(r.sender.id)
        partner_ids.add(r.receiver.id)
    partner_ids.discard(user.id)
    return CustomUser.objects.filter(id__in=partner_ids)

@login_required
def chat_list(request):
    users = get_chat_partners(request.user)

    # Her kullanıcı için son mesajı ekle
    user_data = []
    for u in users:
        last_msg = Message.objects.filter(
            sender__in=[request.user, u],
            receiver__in=[request.user, u]
        ).order_by('-timestamp').first()
        user_data.append({
            'user': u,
            'last_message': last_msg.content if last_msg else None,
            'last_message_time': last_msg.timestamp if last_msg else None,
        })

    return render(request, 'users/chat_list.html', {
    'users_data': user_data,
    'users': [entry['user'] for entry in user_data]  # 👈 Bu satırı ekle
    })


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'users/notifications.html', {'notifications': notifications})


@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')
    notifications.update(is_read=True)
    return render(request, 'users/notifications.html', {'notifications': notifications})

@login_required
def go_to_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()

        # Link varsa oraya yönlendir, yoksa fallback
        return redirect(notification.link or 'notification_list')
    except Notification.DoesNotExist:
        messages.error(request, "Bildirim bulunamadı.")
        return redirect('notification_list')

from users.tasks import notify_admin_teacher_registered

