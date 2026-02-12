"""
EDI Transaction Log — Audit Trail for Enterprise Compliance

Every EDI document processed by ShelfOps is logged here for:
  - Audit compliance (SOX, retail trading partner requirements)
  - Debugging failed document processing
  - Reprocessing capability (raw content preserved)
  - Integration monitoring dashboards

Enterprise retailers like Target require their trading partners
to maintain a complete audit trail of all EDI transactions.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from db.session import Base


class EDITransactionLog(Base):
    """
    Audit log for every EDI document processed.

    Tracks the full lifecycle of each document:
        received → parsed → validated → loaded → archived

    Errors at any stage are captured with details for debugging.
    """

    __tablename__ = "edi_transaction_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.integration_id"), nullable=True)

    # Document identification
    edi_type = Column(String(10), nullable=False)  # "846", "856", "810", "850"
    direction = Column(String(10), nullable=False)  # "inbound" or "outbound"
    document_id = Column(String(255))  # ISA control number or internal ID
    partner_id = Column(String(255))  # Trading partner identifier

    # Processing status
    status = Column(String(20), nullable=False, default="received")
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_details = Column(Text)  # Error message if failed

    # Content (for audit trail and reprocessing)
    filename = Column(String(500))  # Original filename
    file_size_bytes = Column(Integer)
    raw_content = Column(Text)  # Full EDI document (can be large)
    parsed_summary = Column(JSON, default={})  # Key fields extracted for quick reference

    # Timestamps
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_at = Column(DateTime)
    loaded_at = Column(DateTime)
    archived_at = Column(DateTime)

    __table_args__ = (
        Index("ix_edi_log_customer_status", "customer_id", "status"),
        Index("ix_edi_log_type_date", "edi_type", "received_at"),
        Index("ix_edi_log_partner", "partner_id", "received_at"),
        CheckConstraint("edi_type IN ('846', '856', '810', '850', '855', '997')", name="ck_edi_type"),
        CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_edi_direction"),
        CheckConstraint(
            "status IN ('received', 'parsed', 'validated', 'loaded', 'archived', 'error', 'reprocessing')",
            name="ck_edi_status",
        ),
    )
