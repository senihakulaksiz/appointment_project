# users/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

@shared_task
def notify_admin_teacher_registered(teacher_username, teacher_email):
    User = get_user_model()
    admins = User.objects.filter(is_superuser=True)
    for admin in admins:
        send_mail(
            subject='📢 Yeni Öğretmen Kaydı',
            message=f'{teacher_username} ({teacher_email}) adlı öğretmen sisteme kaydoldu.',
            from_email='noreply@appointment.com',
            recipient_list=[admin.email],
        )
