from django.contrib import admin
from django.utils.translation import gettext_lazy as _
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

class LanguageFilter(admin.SimpleListFilter):
    title = _('language')
    parameter_name = 'language'

    def lookups(self, request, model_admin):
        return (
            ('python', _('Python')),
            ('javascript', _('JavaScript')),
            ('typescript', _('TypeScript')),
            ('jsx', _('JSX')),
            ('tsx', _('TSX')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'python':
            return queryset.filter(file_change__file_path__endswith='.py')
        if self.value() == 'javascript':
            return queryset.filter(file_change__file_path__endswith='.js')
        if self.value() == 'typescript':
            return queryset.filter(file_change__file_path__endswith='.ts')
        if self.value() == 'jsx':
            return queryset.filter(file_change__file_path__endswith='.jsx')
        if self.value() == 'tsx':
            return queryset.filter(file_change__file_path__endswith='.tsx')
        return queryset

@admin.register(CommitSymbolChange)
class CommitSymbolChangeAdmin(admin.ModelAdmin):
    list_display = ('symbol_name', 'symbol_type', 'change_type', 'file_change')
    list_filter = ('change_type', 'symbol_type', LanguageFilter, 'file_change__commit__repository')
    search_fields = ('symbol_name', 'file_change__file_path')
