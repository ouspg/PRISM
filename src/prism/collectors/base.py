"""Abstract base class for data collectors."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from prism.github_client import GitHubClient
from prism.models import Repo

log = logging.getLogger("prism.collector")


class BaseCollector(ABC):
    """Base collector that fetches data from GitHub and stores it in Postgres."""

    collector_name: str = "base"

    def __init__(self, client: GitHubClient, session: Session):
        self.client = client
        self.session = session

    @abstractmethod
    def collect(self, repo: Repo) -> int:
        """Collect data for a repo. Returns number of items collected."""
        ...

    def log_sync_start(self, repo: Repo) -> str:
        """Insert a sync_log entry with status='started'. Returns the log ID."""
        log_id = str(uuid.uuid4())
        self.session.execute(
            text("""
                INSERT INTO sync_log (id, repo_id, collector, status, started_at)
                VALUES (:id, :repo_id, :collector, 'started', :now)
            """),
            {
                "id": log_id,
                "repo_id": str(repo.id),
                "collector": self.collector_name,
                "now": datetime.now(UTC),
            },
        )
        self.session.commit()
        return log_id

    def log_sync_complete(
        self, log_id: str, items: int, error: str | None = None
    ) -> None:
        """Update sync_log entry with final status."""
        status = "failed" if error else "completed"
        self.session.execute(
            text("""
                UPDATE sync_log
                SET status = :status, finished_at = :now,
                    items_collected = :items, error = :error
                WHERE id = :id
            """),
            {
                "id": log_id,
                "status": status,
                "now": datetime.now(UTC),
                "items": items,
                "error": error,
            },
        )
        self.session.commit()

    def update_last_synced(self, repo: Repo) -> None:
        """Update repos.last_synced_at to now."""
        self.session.execute(
            text("UPDATE repos SET last_synced_at = :now WHERE id = :id"),
            {"now": datetime.now(UTC), "id": str(repo.id)},
        )
        self.session.commit()
