from django.contrib import admin
from .models import Repository, Commit, CommitFileChange

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ('commit_hash', 'author_name', 'committed_at', 'repository')
    search_fields = ('commit_hash', 'author_name', 'message')
    list_filter = ('repository', 'committed_at')

@admin.register(CommitFileChange)
class CommitFileChangeAdmin(admin.ModelAdmin):
    list_display = ('file_path', 'change_type', 'commit')
    list_filter = ('change_type', 'commit__commit_hash')
