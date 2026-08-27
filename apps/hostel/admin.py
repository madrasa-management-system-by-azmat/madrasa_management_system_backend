from django.contrib import admin

from .models import GatePass, HostelAllocation, HostelRoom, HostelWing

admin.site.register(HostelWing)
admin.site.register(HostelRoom)
admin.site.register(HostelAllocation)
admin.site.register(GatePass)
