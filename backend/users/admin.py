from django.contrib import admin


from .models import CustomUser, Student, Teacher, Lesson, AvailableSlot, Appointment

admin.site.register(CustomUser)
admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Lesson)
admin.site.register(AvailableSlot)
admin.site.register(Appointment)
