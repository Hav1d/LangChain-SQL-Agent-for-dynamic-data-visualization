from .rfm_engine import RFMEngine
from .report_generator import ReportGenerator


def __getattr__(name):
    if name == "RFMClustering":
        from .clustering import RFMClustering
        return RFMClustering
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["RFMEngine", "RFMClustering", "ReportGenerator"]
