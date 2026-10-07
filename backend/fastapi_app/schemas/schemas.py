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
    language: Optional[str] = None
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

class GraphBuildResponse(BaseModel):
    repository_id: int
    nodes_created: int
    edges_created: int

class GraphEdgeResponse(BaseModel):
    id: int
    repository_id: int
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    edge_type: str
    created_at: datetime

    class Config:
        from_attributes = True

class GraphNodeDetailResponse(BaseModel):
    node: dict
    outgoing: List[GraphEdgeResponse] = []
    incoming: List[GraphEdgeResponse] = []

class ImpactNode(BaseModel):
    node_type: str
    node_id: int
    depth: int
    reason: str

class ImpactSourceNode(BaseModel):
    node_type: str
    node_id: int

class ImpactResponse(BaseModel):
    source: ImpactSourceNode
    affected: List[ImpactNode]

class HistoricalCoChangeNode(BaseModel):
    node_type: str
    node_id: int
    co_change_count: int
    probability: float

class HistoricalSourceNode(BaseModel):
    node_type: str
    node_id: int

class HistoricalCoChangeResponse(BaseModel):
    source: HistoricalSourceNode
    source_change_count: int
    co_changes: List[HistoricalCoChangeNode]

class WhatIfRequest(BaseModel):
    node_type: str
    node_id: int
    max_depth: int = 10
    historical_limit: int = 100

class WhatIfStructuralData(BaseModel):
    depth: int
    reason: str

class WhatIfHistoricalData(BaseModel):
    co_change_count: int
    co_change_rate: float

class WhatIfComponent(BaseModel):
    node_type: str
    node_id: int
    classification: str
    path: Optional[str] = None
    structural: Optional[WhatIfStructuralData] = None
    historical: Optional[WhatIfHistoricalData] = None

class WhatIfStructuralSummary(BaseModel):
    total_affected: int
    direct_affected: int
    transitive_affected: int

class WhatIfHistoricalSummary(BaseModel):
    source_change_count: int
    distinct_co_changed_files: int

class WhatIfResponse(BaseModel):
    source: HistoricalSourceNode
    structural_impact: WhatIfStructuralSummary
    historical_impact: WhatIfHistoricalSummary
    affected_components: List[WhatIfComponent]

class EvaluationRequest(BaseModel):
    commit_id: int
    source_file_id: int
    max_depth: int = 5

class EvaluationSet(BaseModel):
    count: int
    file_ids: List[int]

class EvaluationMetrics(BaseModel):
    precision: float
    recall: float
    f1: float

class EvaluationResponse(BaseModel):
    repository_id: int
    commit_id: int
    source_file_id: int
    actual_impact: EvaluationSet
    calculated_impact: EvaluationSet
    true_positives: EvaluationSet
    false_positives: EvaluationSet
    false_negatives: EvaluationSet
    metrics: EvaluationMetrics

class BenchmarkRequest(BaseModel):
    limit: int = 50
    max_depth: int = 5
    historical_limit: int = 50

class BenchmarkMethodMetrics(BaseModel):
    predicted_count: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float

class BenchmarkCase(BaseModel):
    commit_id: int
    commit_hash: str
    source_file_id: int
    source_file_path: str
    actual_impact_count: int
    structural: BenchmarkMethodMetrics
    historical: BenchmarkMethodMetrics
    combined: BenchmarkMethodMetrics

class BenchmarkAggregate(BaseModel):
    case_count: int
    mean_precision: float
    mean_recall: float
    mean_f1: float
    median_precision: float
    median_recall: float
    median_f1: float
    min_precision: float
    min_recall: float
    min_f1: float
    max_precision: float
    max_recall: float
    max_f1: float

class BenchmarkResponse(BaseModel):
    repository_id: int
    parameters: dict
    case_count: int
    structural: BenchmarkAggregate
    historical: BenchmarkAggregate
    combined: BenchmarkAggregate
    cases: List[BenchmarkCase]

