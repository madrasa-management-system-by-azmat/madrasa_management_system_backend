import hashlib
import json
from django.apps import apps
from django.core import serializers as django_serializers
from django.db.models import Count,Q
from django.utils import timezone
from rest_framework import filters,status,viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from apps.users.tenancy import TenantScopedViewSetMixin
from apps.users.rbac import user_has_permission
from .models import ArchiveBatch,ArchivePolicy,ArchivedRecord,AuditEvent,LegalHold
from .serializers import ArchiveBatchSerializer,ArchivePolicySerializer,AuditEventSerializer,LegalHoldSerializer
from .services import audit_event,event_hash_payload

class AdminOnlyMixin:
 def initial(self,request,*args,**kwargs):
  super().initial(request,*args,**kwargs)
  profile=getattr(request.user,"profile",None)
  required="audit.view" if request.method in ("GET","HEAD","OPTIONS") else "audit.manage"
  if not request.user.is_superuser and (not profile or not user_has_permission(request.user,required)):raise PermissionDenied("You do not have the required audit permission.")
class AuditEventViewSet(AdminOnlyMixin,TenantScopedViewSetMixin,viewsets.ReadOnlyModelViewSet):
 queryset=AuditEvent.objects.select_related("actor");serializer_class=AuditEventSerializer;filter_backends=[filters.SearchFilter,filters.OrderingFilter];search_fields=["action","actor_label","entity_type","entity_id","entity_label","path"];ordering_fields=["created_at","category","action"]
 def get_queryset(self):
  q=super().get_queryset()
  for field in ["category","action","entity_type","actor"]:
   value=self.request.query_params.get(field)
   if value:q=q.filter(**{field:value})
  return q
 @action(detail=False,methods=["get"])
 def verify_chain(self,request):
  previous="";broken=[]
  for event in self.get_queryset().order_by("id"):
   payload=event_hash_payload(request_id=event.request_id,category=event.category,action=event.action,madrasa_id=event.madrasa_id,actor_id=event.actor_id,entity_type=event.entity_type,entity_id=event.entity_id,before=event.before,after=event.after,changes=event.changes,metadata=event.metadata,previous_hash=event.previous_hash,created_at=event.created_at)
   if event.previous_hash!=previous or AuditEvent.compute_hash(payload)!=event.event_hash:broken.append(event.id)
   previous=event.event_hash
  return Response({"valid":not broken,"checked":self.get_queryset().count(),"broken_event_ids":broken[:50]})
class ArchivePolicyViewSet(AdminOnlyMixin,TenantScopedViewSetMixin,viewsets.ModelViewSet):
 queryset=ArchivePolicy.objects.all();serializer_class=ArchivePolicySerializer
 def perform_create(self,s):s.save(madrasa=self.get_madrasa(),created_by=self.request.user)
class ArchiveBatchViewSet(AdminOnlyMixin,TenantScopedViewSetMixin,viewsets.ReadOnlyModelViewSet):
 queryset=ArchiveBatch.objects.prefetch_related("records");serializer_class=ArchiveBatchSerializer
 @action(detail=False,methods=["post"])
 def create_batch(self,request):
  entity_type=request.data.get("entity_type");ids=request.data.get("ids",[])
  if not entity_type or not isinstance(ids,list) or not ids:return Response({"detail":"entity_type and ids are required."},status=400)
  try:app_label,model_name=entity_type.split(".");model=apps.get_model(app_label,model_name)
  except Exception:return Response({"detail":"Unsupported entity type."},status=400)
  if not hasattr(model,"madrasa_id") and "madrasa" not in [f.name for f in model._meta.fields]:return Response({"detail":"Entity is not tenant scoped."},status=400)
  holds=LegalHold.objects.filter(madrasa=self.get_madrasa(),is_active=True).filter(Q(ends_at__isnull=True)|Q(ends_at__gt=timezone.now())).filter(Q(entity_type="")|Q(entity_type=entity_type)).filter(Q(entity_id="")|Q(entity_id__in=[str(x) for x in ids]))
  if holds.exists():return Response({"detail":"One or more records are under legal hold."},status=400)
  rows=list(model.objects.filter(madrasa=self.get_madrasa(),pk__in=ids))
  if not rows:return Response({"detail":"No matching tenant records were found."},status=404)
  records=json.loads(django_serializers.serialize("json",rows));batch=ArchiveBatch.objects.create(madrasa=self.get_madrasa(),batch_number=f"ARC-{self.get_madrasa().id}-{timezone.now():%Y%m%d%H%M%S%f}",criteria={"entity_type":entity_type,"ids":ids},created_by=request.user)
  manifest=[]
  for row,instance in zip(records,rows):
    status_field=next((name for name in ("status","lifecycle_status") if hasattr(instance,name) and "archived" in dict(instance._meta.get_field(name).choices)),"")
    snap=row["fields"];digest=hashlib.sha256(json.dumps(snap,sort_keys=True,default=str).encode()).hexdigest();ArchivedRecord.objects.create(madrasa=self.get_madrasa(),batch=batch,entity_type=entity_type,entity_id=str(instance.pk),entity_label=str(instance)[:300],snapshot=snap,snapshot_hash=digest,source_status=str(getattr(instance,status_field,"")),source_status_field=status_field);manifest.append(digest)
    if status_field:setattr(instance,status_field,"archived");instance.save(update_fields=[status_field])
  batch.status="completed";batch.record_count=len(records);batch.manifest_hash=hashlib.sha256("".join(manifest).encode()).hexdigest();batch.completed_at=timezone.now();batch.save(update_fields=["status","record_count","manifest_hash","completed_at"]);audit_event(category="archive",action="archive_batch",madrasa=self.get_madrasa(),actor=request.user,entity=batch,metadata={"count":len(records),"entity_type":entity_type});return Response(self.get_serializer(batch).data,status=201)
 @action(detail=True,methods=["post"])
 def restore(self,request,pk=None):
  batch=self.get_object()
  if batch.status!="completed":return Response({"detail":"Only completed archive batches can be restored."},status=400)
  restored=0
  for record in batch.records.all():
   try:app_label,model_name=record.entity_type.split(".");model=apps.get_model(app_label,model_name);instance=model.objects.filter(madrasa=self.get_madrasa(),pk=record.entity_id).first()
   except Exception:instance=None
  if instance and record.source_status_field and hasattr(instance,record.source_status_field):
   setattr(instance,record.source_status_field,record.source_status);instance.save(update_fields=[record.source_status_field]);ArchivedRecord.objects.filter(pk=record.pk).update(restored_at=timezone.now());restored+=1
  batch.status="restored";batch.restored_by=request.user;batch.restored_at=timezone.now();batch.save(update_fields=["status","restored_by","restored_at"]);audit_event(category="archive",action="restore_batch",madrasa=self.get_madrasa(),actor=request.user,entity=batch,metadata={"restored":restored});return Response(self.get_serializer(batch).data)
class LegalHoldViewSet(AdminOnlyMixin,TenantScopedViewSetMixin,viewsets.ModelViewSet):
 queryset=LegalHold.objects.all();serializer_class=LegalHoldSerializer
 def perform_create(self,s):s.save(madrasa=self.get_madrasa(),created_by=self.request.user)
 @action(detail=True,methods=["post"])
 def release(self,request,pk=None):
  h=self.get_object();h.is_active=False;h.released_by=request.user;h.released_at=timezone.now();h.save(update_fields=["is_active","released_by","released_at"]);return Response(self.get_serializer(h).data)
class AuditDashboardViewSet(AdminOnlyMixin,TenantScopedViewSetMixin,viewsets.ViewSet):
 queryset=AuditEvent.objects.none()
 def list(self,request):
  q=AuditEvent.objects.filter(madrasa=self.get_madrasa());return Response({"events":q.count(),"today":q.filter(created_at__date=timezone.localdate()).count(),"security":q.filter(category="security").count(),"deletes":q.filter(action="delete").count(),"archives":ArchiveBatch.objects.filter(madrasa=self.get_madrasa()).count(),"legal_holds":LegalHold.objects.filter(madrasa=self.get_madrasa(),is_active=True).count(),"by_category":list(q.values("category").annotate(count=Count("id"))),"recent":AuditEventSerializer(q[:15],many=True).data})
