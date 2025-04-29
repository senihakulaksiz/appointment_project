from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Teacher, Student, Lesson, LessonAnnouncement

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    is_student = forms.BooleanField(required=False)
    is_teacher = forms.BooleanField(required=False)
    lesson = forms.ModelChoiceField(queryset=Lesson.objects.all(), required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 'is_student', 'is_teacher', 'lesson']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_student = self.cleaned_data['is_student']
        user.is_teacher = self.cleaned_data['is_teacher']

        if commit:
            user.save()
            if user.is_student:
                Student.objects.create(user=user)
            elif user.is_teacher:
                lesson = self.cleaned_data['lesson']
                Teacher.objects.create(user=user, lesson=lesson)
        return user
class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['about', 'graduated_school', 'years_of_experience', 'expertise_area']
        widgets = {
            'about': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'graduated_school': forms.TextInput(attrs={'class': 'form-control'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}),
            'expertise_area': forms.TextInput(attrs={'class': 'form-control'}),
        }


class LessonAnnouncementForm(forms.ModelForm):
    class Meta:
        model = LessonAnnouncement
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class ApplyToAnnouncementForm(forms.ModelForm):
    class Meta:
        model = LessonAnnouncement
        fields = ['student_requested_date', 'student_requested_time', 'student_class_level', 'student_request_detail']
        widgets = {
            'student_requested_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'student_requested_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'student_class_level': forms.TextInput(attrs={'class': 'form-control'}),
            'student_request_detail': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
