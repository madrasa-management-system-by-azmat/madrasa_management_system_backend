from django.contrib import admin
from .models import Certificate,CertificateEvent,CertificateNumberSequence,CertificateVerificationLog
for model in [CertificateNumberSequence,Certificate,CertificateEvent,CertificateVerificationLog]: admin.site.register(model)
