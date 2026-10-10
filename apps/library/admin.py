from django.contrib import admin

from .models import LibraryBook, LibraryBookCopy, LibraryCategory, LibraryFine, LibraryLoan, LibraryMember, LibraryReservation, LibraryShelf

admin.site.register(LibraryCategory)
admin.site.register(LibraryShelf)
admin.site.register(LibraryBook)
admin.site.register(LibraryBookCopy)
admin.site.register(LibraryMember)
admin.site.register(LibraryLoan)
admin.site.register(LibraryFine)
admin.site.register(LibraryReservation)
