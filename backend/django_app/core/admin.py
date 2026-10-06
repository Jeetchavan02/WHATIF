from django.contrib import admin
from .models import Repository, Commit, CommitFileChange, CommitSymbolChange

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ('commit_hash', 'author_name', 'committed_at', 'repository')
    search_fields = ('commit_hash', 'author_name', 'message')
    list_filter = ('repository', 'committed_at')

@admin.register(CommitFileChange)
class CommitFileChangeAdmin(admin.ModelAdmin):
    list_display = ('file_path', 'change_type', 'commit')
    list_filter = ('change_type', 'commit__commit_hash')

@admin.register(CommitSymbolChange)
class CommitSymbolChangeAdmin(admin.ModelAdmin):
    list_display = ('symbol_name', 'symbol_type', 'change_type', 'file_change')
    list_filter = ('change_type', 'symbol_type', 'file_change__commit__repository')
    search_fields = ('symbol_name',)
