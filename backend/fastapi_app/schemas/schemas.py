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
