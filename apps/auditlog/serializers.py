from rest_framework import serializers
from .models import ArchiveBatch,ArchivePolicy,ArchivedRecord,AuditEvent,LegalHold
class AuditEventSerializer(serializers.ModelSerializer):
 class Meta:model=AuditEvent;fields="__all__";read_only_fields=fields
class ArchivePolicySerializer(serializers.ModelSerializer):
 class Meta:model=ArchivePolicy;fields="__all__";read_only_fields=["madrasa","created_by"]
class ArchivedRecordSerializer(serializers.ModelSerializer):
 class Meta:model=ArchivedRecord;fields="__all__";read_only_fields=fields
class ArchiveBatchSerializer(serializers.ModelSerializer):
 records=ArchivedRecordSerializer(many=True,read_only=True)
 class Meta:model=ArchiveBatch;fields="__all__";read_only_fields=["madrasa","batch_number","status","record_count","manifest_hash","created_by","created_at","completed_at","restored_by","restored_at"]
class LegalHoldSerializer(serializers.ModelSerializer):
 class Meta:model=LegalHold;fields="__all__";read_only_fields=["madrasa","created_by","released_by","released_at"]
