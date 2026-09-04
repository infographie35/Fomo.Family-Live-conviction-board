import json
import logging
import re
from pathlib import Path

from ..config import FOMO_TOPIC_ID, TOPIC_FILE
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.topic")

_TOPIC_FILE_SCHEMA_VERSION = 2
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


class TopicMismatchError(ValueError):
    """Raised when the browser reports a different account during one process run."""


def _clean_uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if _UUID_RE.fullmatch(candidate) else None


class TopicManager:
    """Own the immutable Fomo account identity for one dashboard process.

    A schema-v2 ``fomo_topic.json`` is trusted at startup because it can only be
    written from the browser's ``trading_activity`` WebSocket subscription. On a
    first run, or after upgrading from the old URL-sniffing bridge, the first
    valid WebSocket topicId is persisted and becomes immutable until restart.

    ``FOMO_TOPIC_ID`` remains an explicit fallback for installations that choose
    to configure the account identity outside the browser bridge.
    """

    def __init__(self, path: Path = TOPIC_FILE, fallback: str = FOMO_TOPIC_ID) -> None:
        self.path = path
        self.fallback = _clean_uuid(fallback)
        self._topic_id, self._source = self._load_verified()
        if self._topic_id is None and self.fallback:
            self._topic_id = self.fallback
            self._source = "fallback"
        self._browser_checked = False

    def _load_verified(self) -> tuple[str | None, str]:
        if not self.path.exists():
            return None, "none"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Ignoring unreadable fomo_topic.json: %s", exc)
            return None, "none"

        if not isinstance(data, dict) or data.get("schemaVersion") != _TOPIC_FILE_SCHEMA_VERSION:
            logger.warning(
                "Ignoring legacy unverified fomo_topic.json; refresh the Fomo tab once "
                "so the WebSocket bridge can bind the account safely"
            )
            return None, "none"

        topic_id = _clean_uuid(data.get("topicId"))
        if not topic_id:
            logger.warning("Ignoring fomo_topic.json with an invalid topicId")
            return None, "none"
        return topic_id, "persisted"

    def _persist(self, topic_id: str) -> None:
        atomic_write_json(
            self.path,
            {
                "schemaVersion": _TOPIC_FILE_SCHEMA_VERSION,
                "topicId": topic_id,
                "verifiedSource": "trading_activity_ws",
            },
        )

    def ingest(self, topic_id: object) -> str:
        """Bind or verify the browser account once for this dashboard process.

        A persisted topicId is available immediately at startup. The first
        trading_activity subscribe frame seen afterwards verifies that the open
        Fomo page uses the same account. Once bound or verified, later subscribe
        frames cannot change the process account and require no further checks.
        """
        candidate = _clean_uuid(topic_id)
        if not candidate:
            raise ValueError("topicId is not a UUID")

        if self._browser_checked:
            return self._topic_id

        if self._topic_id is None:
            self._persist(candidate)
            self._topic_id = candidate
            self._source = "captured"
            self._browser_checked = True
            logger.info("Fomo account topicId bound from trading_activity WebSocket: %s", candidate)
            return candidate

        if candidate != self._topic_id:
            logger.warning(
                "Fomo account mismatch at browser verification: expected %s, received %s",
                self._topic_id,
                candidate,
            )
            raise TopicMismatchError(
                "Fomo account differs from the account bound at startup; to change accounts, "
                "stop the dashboard, delete fomo_topic.json, restart, then refresh Fomo once"
            )

        self._browser_checked = True
        logger.info("Fomo account topicId verified against the open Fomo page: %s", candidate)
        return self._topic_id

    def resolve(self) -> str | None:
        return self._topic_id

    @property
    def source(self) -> str:
        return self._source


topic_manager = TopicManager()
