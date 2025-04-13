from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Teacher, Student, Lesson

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
