"""Unit tests for the signal poles showing their intersection's phase (``signal_states``)."""

import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import TimeOfDay
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_edge_kit import edge_runs
from src.procedural.road_network import RoadNetworkGenerator
from src.procedural.signal_phasing import (
    EAST_WEST_AXIS,
    NORTH_SOUTH_AXIS,
    ApproachDirection,
    PhaseKind,
    SignalLight,
    SignalPhase,
    approach_light,
    classify_approach_direction,
)
from src.procedural.traffic_lights import (
    TRAFFIC_LIGHT_END_MARGIN_M,
    generate_traffic_light_pieces,
    signal_material_replacements,
)
from src.procedural.traffic_network import TrafficNetworkGenerator
from src.utils.config_loader import load_scenario_config
from tests.conftest import straight_road_lanes_and_edges

TEMPLATE = "configs/scenario_templates/urban_dense_v15.yaml"
OLD_TEMPLATE = "configs/scenario_templates/urban_dense_v14.yaml"
BOUNDS = (-150.0, -150.0, 150.0, 150.0)
SIGNALS = "/Game/VantageCV/Signals/"

# The six phases of one signal cycle, in the order ``compute_signal_plan`` builds them.
PHASES = [
    SignalPhase(0, PhaseKind.GREEN, NORTH_SOUTH_AXIS, 20.0),
    SignalPhase(1, PhaseKind.YELLOW_CHANGE, frozenset(), 4.0),
    SignalPhase(2, PhaseKind.ALL_RED, frozenset(), 2.0),
    SignalPhase(3, PhaseKind.GREEN, EAST_WEST_AXIS, 20.0),
    SignalPhase(4, PhaseKind.YELLOW_CHANGE, frozenset(), 4.0),
    SignalPhase(5, PhaseKind.ALL_RED, frozenset(), 2.0),
]


@pytest.mark.parametrize(
    "index,axis,expected",
    [
        (0, ApproachDirection.NORTH, SignalLight.GREEN),
        (0, ApproachDirection.SOUTH, SignalLight.GREEN),
        (0, ApproachDirection.EAST, SignalLight.RED),
        (1, ApproachDirection.SOUTH, SignalLight.YELLOW),
        (1, ApproachDirection.WEST, SignalLight.RED),
        (2, ApproachDirection.NORTH, SignalLight.RED),
        (2, ApproachDirection.EAST, SignalLight.RED),
        (3, ApproachDirection.WEST, SignalLight.GREEN),
        (3, ApproachDirection.NORTH, SignalLight.RED),
        (4, ApproachDirection.EAST, SignalLight.YELLOW),
        (4, ApproachDirection.SOUTH, SignalLight.RED),
        (5, ApproachDirection.WEST, SignalLight.RED),
    ],
)
def test_approach_light_follows_the_phase(index, axis, expected) -> None:
    """Green and yellow belong to the pair that owns the phase; everything else is red."""
    assert approach_light(PHASES[index], axis) is expected


def test_the_two_axes_are_never_both_green_or_both_yellow() -> None:
    """Whatever the phase, the crossing approaches never show the same go colour."""
    for phase in PHASES:
        lights = {
            approach_light(phase, ApproachDirection.NORTH),
            approach_light(phase, ApproachDirection.EAST),
        }
        assert SignalLight.RED in lights


def test_pedestrians_walk_only_while_their_approach_is_green() -> None:
    """The heads face back along the approach: walking figure on green, hand otherwise."""
    for light in SignalLight:
        replacements = signal_material_replacements(light)
        ped = "Walk" if light == SignalLight.GREEN else "Stop"
        assert (
            replacements["Prop_Emissive_Walk_01"]
            == f"{SIGNALS}MI_Ped_Front_{ped}.MI_Ped_Front_{ped}"
        )
        for slot in ("Prop_Emissive_Walk_02", "Prop_Emissive_Walk_03"):
            assert replacements[slot] == f"{SIGNALS}MI_Ped_Right_{ped}.MI_Ped_Right_{ped}"
        name = f"MI_Signal_{light.value.capitalize()}"
        assert replacements["Prop_Emissive_StopLight"] == f"{SIGNALS}{name}.{name}"


def _scenario(template: str, seed: int):
    return generate_scenario(
        seed, load_scenario_config(template), BOUNDS, "s", time_of_day=TimeOfDay.DAY
    )


def test_off_by_default_and_the_v15_template_turns_it_on() -> None:
    """Earlier templates keep every pole in the asset's default state."""
    assert load_scenario_config(OLD_TEMPLATE).signal_states is False
    assert load_scenario_config(TEMPLATE).signal_states is True
    plain = _scenario(OLD_TEMPLATE, 80003)
    assert plain.traffic_light_pieces
    assert all(piece.material_replacements is None for piece in plain.traffic_light_pieces)


def test_poles_stand_only_at_signalized_nodes_and_match_their_phase() -> None:
    """With the feature on, every pole sits at an intersection with a signal, and the colour it
    shows is the colour that intersection's phase gives its approach."""
    scenario = _scenario(TEMPLATE, 80003)
    signalized = [
        node_id
        for node_id, control in scenario.traffic.traffic_controls.items()
        if control.value == "traffic_light"
    ]
    assert signalized
    assert scenario.traffic_light_pieces
    assert len(scenario.traffic_light_pieces) <= 4 * len(signalized)
    for piece in scenario.traffic_light_pieces:
        assert piece.material_replacements is not None
        assert set(piece.material_replacements) == {
            "Prop_Emissive_StopLight",
            "Prop_Emissive_Walk_01",
            "Prop_Emissive_Walk_02",
            "Prop_Emissive_Walk_03",
        }


def test_each_pole_shows_the_colour_its_phase_gives_its_approach() -> None:
    """Fix every signalized node on one phase and check each pole against ``approach_light``."""
    config = load_scenario_config(TEMPLATE)
    nodes, edges = RoadNetworkGenerator(80003, config).generate(BOUNDS)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    signalized = [n for n, c in traffic.traffic_controls.items() if c.value == "traffic_light"]
    assert signalized
    seen = set()
    for phase in PHASES:
        phases = {node_id: phase for node_id in signalized}
        pieces = generate_traffic_light_pieces(lanes, edges, phases)
        runs = [
            run
            for run in edge_runs(lanes, edges)
            if run.length > TRAFFIC_LIGHT_END_MARGIN_M and edges[run.edge_id].end_node_id in phases
        ]
        assert len(pieces) == len(runs) > 0
        for piece, run in zip(pieces, runs):
            light = approach_light(phase, classify_approach_direction(edges[run.edge_id]))
            assert piece.material_replacements == signal_material_replacements(light)
            seen.add(light)
    assert seen == set(SignalLight)


def test_an_unsignalized_approach_gets_no_pole_when_the_feature_is_on() -> None:
    """With phases given but none for the node, no pole is placed; without phases it still is."""
    lanes, edges = straight_road_lanes_and_edges(100.0)
    assert generate_traffic_light_pieces(lanes, edges)
    assert not generate_traffic_light_pieces(lanes, edges, {})


def test_serializer_carries_the_replacements_and_leaves_other_assets_alone() -> None:
    """The traffic-light assets carry their slot replacements; nothing else gains any."""
    scenario = _scenario(TEMPLATE, 80003)
    payload = serialize_scenario(scenario, None)
    poles = [asset for asset in payload["assets"] if "StopLight" in asset["asset_path"]]
    assert len(poles) == len(scenario.traffic_light_pieces) > 0
    assert all("Prop_Emissive_StopLight" in asset["material_replacements"] for asset in poles)
    others = [asset for asset in payload["assets"] if "StopLight" not in asset["asset_path"]]
    assert not any(SIGNALS in str(asset.get("material_replacements", "")) for asset in others)
