"""The pedestrian-free config differs from the v7p config in the pedestrian density only."""

from pathlib import Path

from src.utils.config_loader import load_scenario_config

TEMPLATES = Path(__file__).resolve().parents[2] / "configs" / "scenario_templates"


def test_nopeds_config_changes_only_the_pedestrian_density() -> None:
    """Everything but ``pedestrian_density_fraction`` is equal between the two configs."""
    peds = load_scenario_config(TEMPLATES / "urban_dense_v7_peds.yaml").model_dump()
    nopeds = load_scenario_config(TEMPLATES / "urban_dense_v7_nopeds.yaml").model_dump()
    assert nopeds["pedestrian_density_fraction"] == (0.0, 0.0)
    assert peds["pedestrian_density_fraction"] == (0.3, 0.3)
    for config in (peds, nopeds):
        config.pop("pedestrian_density_fraction")
    assert peds == nopeds
