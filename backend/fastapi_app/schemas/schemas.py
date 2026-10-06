from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class RepositoryCreate(BaseModel):
    url: str
    name: Optional[str] = None

class RepositoryResponse(BaseModel):
    id: int
    name: Optional[str]
    url: str
    created_at: datetime

    class Config:
        from_attributes = True

class AnalysisRunResponse(BaseModel):
    id: int
    repository_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True

class FileResponse(BaseModel):
    id: int
    repository_id: int
    path: str
    language: Optional[str]
    size: int
    created_at: datetime

    class Config:
        from_attributes = True

class DependencyResponse(BaseModel):
    id: int
    repository_id: int
    source_file_id: int
    target_file_id: Optional[int]
    dependency_type: str
    target_name: Optional[str]

    class Config:
        from_attributes = True

class SymbolResponse(BaseModel):
    id: int
    file_id: int
    name: str
    symbol_type: str
    start_line: int
    end_line: Optional[int]

    class Config:
        from_attributes = True

class CommitFileChangeResponse(BaseModel):
    id: int
    commit_id: int
    file_path: str
    change_type: str
    additions: int
    deletions: int
    old_path: Optional[str] = None
    new_path: Optional[str] = None

    class Config:
        from_attributes = True

class CommitResponse(BaseModel):
    id: int
    repository_id: int
    commit_hash: str
    author_name: str
    author_email: str
    message: str
    committed_at: datetime
    parent_hash: Optional[str] = None
    created_at: datetime
    file_changes: Optional[List[CommitFileChangeResponse]] = []

    class Config:
        from_attributes = True

class HistoryStatsResponse(BaseModel):
    total_commits: int
    total_additions: int
    total_deletions: int
    total_modified_files: int
    total_added_files: int
    total_deleted_files: int
    total_renamed_files: int
    most_frequently_changed_files: List[dict]

class CommitSymbolChangeResponse(BaseModel):
    id: int
    symbol_name: str
    symbol_type: str
    change_type: str
    old_start_line: Optional[int] = None
    old_end_line: Optional[int] = None
    new_start_line: Optional[int] = None
    new_end_line: Optional[int] = None

    class Config:
        from_attributes = True

class FileChangeWithSymbolsResponse(BaseModel):
    path: str
    change_type: str
    symbols: List[CommitSymbolChangeResponse] = []

class CommitChangesResponse(BaseModel):
    commit: str
    files: List[FileChangeWithSymbolsResponse] = []

class ChangeMapSymbolResponse(BaseModel):
    name: str
    change_type: str
    dependencies: List[str] = []

class ChangeMapFileResponse(BaseModel):
    path: str
    symbols: List[ChangeMapSymbolResponse] = []

class ChangeMapCommitResponse(BaseModel):
    commit: str
    files: List[ChangeMapFileResponse] = []
