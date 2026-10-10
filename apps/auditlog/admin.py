from django.contrib import admin
from .models import ArchiveBatch,ArchivePolicy,ArchivedRecord,AuditEvent,LegalHold

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
 list_display=("created_at","madrasa","category","action","actor_label","entity_type","entity_id")
 list_filter=("category","action","created_at");search_fields=("actor_label","entity_type","entity_id","entity_label","request_id")
 readonly_fields=[field.name for field in AuditEvent._meta.fields]
 def has_add_permission(self,request):return False
 def has_change_permission(self,request,obj=None):return False
 def has_delete_permission(self,request,obj=None):return False

admin.site.register(ArchivePolicy)
admin.site.register(ArchiveBatch)
admin.site.register(ArchivedRecord)
admin.site.register(LegalHold)
