"""MCP tool layer."""

from app.tools.assets import run_dataset_profile_from_paths
from app.tools.assets import run_model_asset_profile
from app.tools.assets import run_train_model_bundle_from_paths
from app.tools.assets import setup_asset_tools
from app.tools.correction import run_correction_from_paths
from app.tools.correction import setup_correction_tools
from app.tools.data_analysis import run_data_analysis_from_paths
from app.tools.data_analysis import setup_data_analysis_tools
from app.tools.ensemble import run_ensemble_from_paths
from app.tools.ensemble import setup_ensemble_tools
from app.tools.forecast import run_forecast_from_paths
from app.tools.forecast import setup_forecast_tools
from app.tools.lifecycle import (
    run_calibration_from_paths,
    run_hpo_from_paths,
    run_lifecycle_smoke_from_paths,
    run_training_from_paths,
)
from app.tools.lifecycle import setup_lifecycle_tools
from app.tools.risk import run_risk_from_paths
from app.tools.risk import setup_risk_tools
from app.tools.warning import run_warning_from_paths
from app.tools.warning import setup_warning_tools


def setup_all_tools(mcp_server) -> None:
    setup_asset_tools(mcp_server)
    setup_forecast_tools(mcp_server)
    setup_data_analysis_tools(mcp_server)
    setup_ensemble_tools(mcp_server)
    setup_correction_tools(mcp_server)
    setup_risk_tools(mcp_server)
    setup_warning_tools(mcp_server)
    setup_lifecycle_tools(mcp_server)

__all__ = [
    "setup_all_tools",
    "run_calibration_from_paths",
    "run_dataset_profile_from_paths",
    "run_data_analysis_from_paths",
    "run_correction_from_paths",
    "run_ensemble_from_paths",
    "run_forecast_from_paths",
    "run_hpo_from_paths",
    "run_lifecycle_smoke_from_paths",
    "run_model_asset_profile",
    "run_risk_from_paths",
    "run_train_model_bundle_from_paths",
    "run_training_from_paths",
    "run_warning_from_paths",
    "setup_asset_tools",
    "setup_correction_tools",
    "setup_data_analysis_tools",
    "setup_ensemble_tools",
    "setup_forecast_tools",
    "setup_lifecycle_tools",
    "setup_risk_tools",
    "setup_warning_tools",
]
