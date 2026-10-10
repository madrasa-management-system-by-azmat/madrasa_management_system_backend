from django.contrib import admin
from .models import AlumniEngagement, DisciplineAction, DisciplineAppeal, DisciplineCategory, DisciplineIncident, RewardCategory, RewardNomination, TrainingEnrollment, TrainingProgram
for model in [DisciplineCategory,DisciplineIncident,DisciplineAction,DisciplineAppeal,TrainingProgram,TrainingEnrollment,RewardCategory,RewardNomination,AlumniEngagement]: admin.site.register(model)
