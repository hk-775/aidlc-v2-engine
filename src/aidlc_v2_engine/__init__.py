"""AI-DLC v2 Engine: a local, human-governed methodology control plane."""

from aidlc_v2_engine.catalog import STAGES
from aidlc_v2_engine.models import Actor
from aidlc_v2_engine.persistence import JsonProjectRepository
from aidlc_v2_engine.service import LifecycleService

__all__ = ["Actor", "JsonProjectRepository", "LifecycleService", "STAGES"]
__version__ = "0.1.0"
