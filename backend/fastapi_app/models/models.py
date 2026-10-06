from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis_runs = relationship("AnalysisRun", back_populates="repository")
    files = relationship("File", back_populates="repository")
    dependencies = relationship("Dependency", back_populates="repository")

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    status = Column(String, default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    repository = relationship("Repository", back_populates="analysis_runs")

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    path = Column(String, index=True)
    language = Column(String)
    size = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="files")
    symbols = relationship("Symbol", back_populates="file")

class Symbol(Base):
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    name = Column(String, index=True)
    symbol_type = Column(String)
    start_line = Column(Integer)
    end_line = Column(Integer, nullable=True)

    file = relationship("File", back_populates="symbols")

class Dependency(Base):
    __tablename__ = "dependencies"
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"))
    source_file_id = Column(Integer, ForeignKey("files.id"))
    target_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    dependency_type = Column(String)
    target_name = Column(String, nullable=True) # Unresolved targets

    repository = relationship("Repository", back_populates="dependencies")
    source_file = relationship("File", foreign_keys=[source_file_id])
    target_file = relationship("File", foreign_keys=[target_file_id])
