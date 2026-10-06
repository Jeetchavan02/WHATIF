from django.db import models

class Repository(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'repositories'

    def __str__(self):
        return self.name or self.url

class Commit(models.Model):
    id = models.IntegerField(primary_key=True)
    repository = models.ForeignKey(Repository, on_delete=models.DO_NOTHING)
    commit_hash = models.CharField(max_length=255)
    author_name = models.CharField(max_length=255)
    author_email = models.CharField(max_length=255)
    message = models.TextField()
    committed_at = models.DateTimeField()
    parent_hash = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'commits'

    def __str__(self):
        return self.commit_hash

class CommitFileChange(models.Model):
    id = models.IntegerField(primary_key=True)
    commit = models.ForeignKey(Commit, on_delete=models.DO_NOTHING)
    file_path = models.CharField(max_length=255)
    change_type = models.CharField(max_length=50)
    additions = models.IntegerField()
    deletions = models.IntegerField()
    old_path = models.CharField(max_length=255, null=True)
    new_path = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = 'commit_file_changes'

    def __str__(self):
        return f"{self.change_type} {self.file_path}"

class CommitSymbolChange(models.Model):
    id = models.IntegerField(primary_key=True)
    file_change = models.ForeignKey(CommitFileChange, on_delete=models.DO_NOTHING, db_column='commit_file_change_id')
    symbol_id = models.IntegerField(null=True)
    symbol_name = models.CharField(max_length=255)
    symbol_type = models.CharField(max_length=50)
    change_type = models.CharField(max_length=50)
    old_start_line = models.IntegerField(null=True)
    old_end_line = models.IntegerField(null=True)
    new_start_line = models.IntegerField(null=True)
    new_end_line = models.IntegerField(null=True)

    class Meta:
        managed = False
        db_table = 'commit_symbol_changes'

    def __str__(self):
        return f"{self.change_type} {self.symbol_name}"
