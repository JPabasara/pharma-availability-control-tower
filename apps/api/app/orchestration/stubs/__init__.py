"""Engine stubs package — contract-compatible stub providers for M1, M2, M3."""

from apps.api.app.orchestration.stubs.m1_stub import run as run_m1
from apps.api.app.orchestration.stubs.m2_stub import run as run_m2
from apps.api.app.orchestration.stubs.m3_stub import run as run_m3

__all__ = ["run_m1", "run_m2", "run_m3"]
