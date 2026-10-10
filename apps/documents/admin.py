from django.contrib import admin

from .models import Document, DocumentAccessGrant, DocumentAcknowledgement, DocumentAuditEvent, DocumentCategory, DocumentComment, DocumentFolder, DocumentLink, DocumentNumberSequence, DocumentVersion

admin.site.register(DocumentCategory)
admin.site.register(DocumentFolder)
admin.site.register(DocumentNumberSequence)
admin.site.register(Document)
admin.site.register(DocumentVersion)
admin.site.register(DocumentAccessGrant)
admin.site.register(DocumentLink)
admin.site.register(DocumentComment)
admin.site.register(DocumentAcknowledgement)
admin.site.register(DocumentAuditEvent)
