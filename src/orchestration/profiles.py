"""What the ``--profile v7`` generator selects unless the matching flag is given.

The v7 traffic template, ego views only (the parking-lot view supplied 22% of the images but 51%
of the trucks, and 72% of its boxes overlapped another against 7% in real data) and a lighter
share of parking lots. ``v6`` keeps the generator as it was.
"""

from pathlib import Path
from typing import Tuple

V6_CONFIG = Path("configs/scenario_templates/urban_dense.yaml")
V6_PARKING_LOT_FRACTION = 0.3
V7_CONFIG = Path("configs/scenario_templates/urban_dense_v7.yaml")
V7_VIEWS: Tuple[str, ...] = ("ego", "ego")
V7_PARKING_LOT_FRACTION = 0.1
