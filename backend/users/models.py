# users/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models



class CustomUser(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)

class Lesson(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Student(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)  # ← BURASI

    def __str__(self):
        return self.user.username

class Teacher(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)  # ← BURASI
    about = models.TextField(blank=True, null=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True)
    graduated_school = models.CharField(max_length=100, blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)
    expertise_area = models.CharField(max_length=100, blank=True, null=True)

class AvailableSlot(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.teacher.user.username} - {self.date} ({self.start_time} - {self.end_time})"

class Appointment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    slot = models.ForeignKey(AvailableSlot, on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.username} -> {self.slot}"

class LessonAnnouncement(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True)

    # Öğrencinin başvururken dolduracağı yeni alanlar:
    student_requested_date = models.DateField(null=True, blank=True)
    student_requested_time = models.TimeField(null=True, blank=True)
    student_class_level = models.CharField(max_length=50, null=True, blank=True)
    student_request_detail = models.TextField(null=True, blank=True)

    # Başvuru kabul durumu:
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class ChatRequest(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_chat_requests')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_chat_requests')
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')  # aynı kişiye tekrar istek gönderilemesin

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username} ({'Kabul Edildi' if self.is_accepted else 'Bekliyor'})"


class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.content[:30]}"

class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    link = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {'OKUNDU' if self.is_read else 'YENİ'}"
