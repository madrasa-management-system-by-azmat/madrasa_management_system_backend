from django.contrib import admin

from .models import FatwaAttachment, FatwaCategory, FatwaInquiry, FatwaNumberSequence, FatwaPublication, FatwaReference, FatwaRequester, FatwaRevision, FatwaTag, FatwaWorkflowEvent

admin.site.register(FatwaCategory)
admin.site.register(FatwaTag)
admin.site.register(FatwaNumberSequence)
admin.site.register(FatwaInquiry)
admin.site.register(FatwaRequester)
admin.site.register(FatwaRevision)
admin.site.register(FatwaReference)
admin.site.register(FatwaAttachment)
admin.site.register(FatwaWorkflowEvent)
admin.site.register(FatwaPublication)
