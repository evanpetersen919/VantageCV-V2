# Quality of Life & Research Checklist
## Domain-Specific Issues That AI and Humans Miss

**Purpose**: Catch subtle bugs, edge cases, and research validity issues before they cause problems.

This checklist is organized by domain (geometry, randomization, rendering, physics, etc.) with specific things to verify at each phase.

---

## SECTION A: Mathematical & Numerical Issues

### A.1 Floating-Point Precision

**Issue**: Geometric algorithms are sensitive to floating-point errors. Accumulated rounding errors cause:
- Road segments that are supposed to connect but have gaps
- Buildings that "almost" overlap but trigger false positives
- Intersection detection failures

**Checklist for Every Geometric Operation**:

- [ ] **Equality comparisons**: Never use `==` for floats
  ```python
  # WRONG
  if position[0] == 0.0:
      ...
  
  # RIGHT
  if np.abs(position[0]) < 1e-6:
      ...
  ```

- [ ] **Tolerance constants defined globally**
  ```python
  # At module top
  POSITION_TOLERANCE = 1e-6  # meters
  ANGLE_TOLERANCE = 1e-9     # radians
  LENGTH_TOLERANCE = 1e-4    # meters
  ```

- [ ] **Tolerance documented with rationale**
  ```python
  # Tolerance = 1e-6 meters = 1 micrometer
  # Smaller than GPS precision (0.01m), safe for road geometry
  POSITION_TOLERANCE = 1e-6
  ```

- [ ] **Numerical stability check for critical algorithms**
  - Delaunay triangulation: Check for degenerate triangles (area < 1e-9)
  - Matrix inversion: Check condition number
  - Linear system solving: Use numpy.linalg.lstsq (robust)

**Test Case to Add**:
```python
def test_floating_point_tolerance_in_road_network():
    """Verify nodes are merged when within tolerance"""
    gen = RoadNetworkGenerator(42, config)
    
    # Add two nodes very close together
    node1 = gen._find_or_create_node(np.array([100.0, 200.0]))
    node2 = gen._find_or_create_node(np.array([100.0 + 1e-7, 200.0]))  # 0.1 micrometer offset
    
    # Should be same node (merged due to tolerance)
    assert node1 == node2, "Nodes within tolerance should be merged"
```

---

### A.2 Random Seed Handling

**Issue**: Improper RNG management causes non-reproducibility:
- Different seeds produce identical scenarios
- Same seed produces different output on different runs
- Random state leaks between scenarios

**Checklist**:

- [ ] **Every class with randomness has seed parameter**
  ```python
  class RoadNetworkGenerator:
      def __init__(self, seed: int, config):
          self.seed = seed
          self.rng = np.random.RandomState(seed)  # Isolated RNG
  ```

- [ ] **RNG is instance-scoped, not global**
  ```python
  # WRONG - global state
  np.random.seed(42)
  def generate_roads():
      return np.random.uniform(0, 100)
  
  # RIGHT - instance scoped
  self.rng = np.random.RandomState(42)
  def generate_roads(self):
      return self.rng.uniform(0, 100)
  ```

- [ ] **No external randomness** (no `random.random()`, no `secrets.randbelow()`)
  ```python
  # WRONG - external randomness
  import random
  self.color = random.choice(colors)
  
  # RIGHT - use seeded RNG
  self.color = self.rng.choice(colors)
  ```

- [ ] **Seed chain documented**
  ```python
  """
  Seed derivation:
    base_seed (int64)
      └─ RoadNetworkGenerator seed = base_seed
      └─ LaneTopologyGenerator seed = base_seed + 1
      └─ BuildingPlacementGenerator seed = base_seed + 2
  
  This ensures independent but reproducible generation.
  """
  ```

- [ ] **Determinism test in every phase**
  ```python
  def test_determinism_same_seed():
      """Same seed → identical output"""
      gen1 = Generator(seed=42, config=cfg)
      gen2 = Generator(seed=42, config=cfg)
      
      output1 = gen1.generate(bounds)
      output2 = gen2.generate(bounds)
      
      assert np.allclose(output1, output2), "Non-deterministic output!"
  ```

---

### A.3 Array Indexing & Boundary Conditions

**Issue**: Off-by-one errors in iteration, slicing, and indexing cause:
- Last road segment missing
- First building misplaced
- Segmentation faults in C++

**Checklist**:

- [ ] **Loop bounds verified on paper**
  ```python
  # For N points, creating edges:
  # Should connect point[i] to point[i+1]
  # i should go 0 to N-2 (inclusive)
  # NOT 0 to N-1 (would access point[N])
  
  for i in range(len(points) - 1):  # NOT range(len(points))
      connect(points[i], points[i+1])
  ```

- [ ] **Slicing semantics verified**
  ```python
  # Python slicing: [start:end) — includes start, excludes end
  
  # WRONG — misses last element
  for i in range(len(array)):
      process(array[i:i+2])  # Last iteration: array[N-1:N+1] out of bounds
  
  # RIGHT
  for i in range(len(array) - 1):
      process(array[i:i+2])
  ```

- [ ] **Edge cases tested explicitly**
  ```python
  def test_single_element():
      """Single point should not crash"""
      result = generate_roads(np.array([[0, 0]]))
      assert len(result) == 0, "Single point: no roads"
  
  def test_two_elements():
      """Two points should create one road"""
      result = generate_roads(np.array([[0, 0], [10, 0]]))
      assert len(result) == 1, "Two points: one road"
  
  def test_many_elements():
      """Many points should work"""
      points = np.random.RandomState(42).uniform(0, 1000, (1000, 2))
      result = generate_roads(points)
      assert len(result) > 0
  ```

---

### A.4 Numerical Stability in Geometry

**Issue**: Algorithms lose precision on degenerate geometries:
- Very small angles → tangent blows up
- Nearly parallel lines → intersection undefined
- Nearly colinear points → area ≈ 0

**Checklist**:

- [ ] **Degenerate case handling documented**
  ```python
  def compute_perpendicular(v: np.ndarray) -> np.ndarray:
      """
      Compute perpendicular vector.
      
      Handles degenerate case: nearly-zero vector
      """
      length = np.linalg.norm(v)
      if length < 1e-9:  # Degenerate: vector too small
          return np.array([0, 1])  # Default perpendicular
      return np.array([-v[1], v[0]]) / length
  ```

- [ ] **Test on degenerate inputs**
  ```python
  def test_perpendicular_near_zero():
      """Near-zero vector should not divide by zero"""
      v = np.array([1e-10, 1e-10])
      perp = compute_perpendicular(v)
      assert np.isfinite(perp).all(), "NaN or inf in perpendicular"
  ```

- [ ] **Collinearity check in algorithms**
  ```python
  def compute_triangle_area(p1, p2, p3):
      """
      Compute triangle area using cross product.
      Handles collinear case (area ≈ 0).
      """
      area = 0.5 * np.abs(
          (p2[0] - p1[0]) * (p3[1] - p1[1]) -
          (p3[0] - p1[0]) * (p2[1] - p1[1])
      )
      
      if area < 1e-9:
          raise ValueError(f"Points are collinear (area={area})")
      
      return area
  ```

---

## SECTION B: Geometric Algorithms

### B.1 Road Network Topology

**Issue**: Invalid road networks cause traffic simulation to fail:
- Disconnected components (vehicle can't reach some area)
- Cycles that shouldn't exist (invalid shortcuts)
- Invalid intersections (degree < 2)

**Checklist**:

- [ ] **Connectivity test: Graph is connected**
  ```python
  def test_road_network_connected():
      """All nodes reachable via BFS"""
      gen = RoadNetworkGenerator(42, cfg)
      nodes, edges = gen.generate(bounds)
      
      # BFS from first node
      start = next(iter(nodes))
      visited = {start}
      queue = [start]
      
      while queue:
          node_id = queue.pop(0)
          for edge_id in nodes[node_id].outgoing_edges:
              next_id = edges[edge_id].end_node_id
              if next_id not in visited:
                  visited.add(next_id)
                  queue.append(next_id)
      
      # All nodes visited?
      assert len(visited) == len(nodes), \
          f"Network disconnected: {len(visited)} / {len(nodes)}"
  ```

- [ ] **No self-loops or duplicate edges**
  ```python
  def test_no_self_loops():
      """No edge connects node to itself"""
      for edge in edges.values():
          assert edge.start_node_id != edge.end_node_id, \
              f"Self-loop: edge {edge.edge_id}"
  
  def test_no_duplicate_edges():
      """No two edges connect same pair of nodes"""
      edge_pairs = set()
      for edge in edges.values():
          pair = (edge.start_node_id, edge.end_node_id)
          assert pair not in edge_pairs, f"Duplicate edge: {pair}"
          edge_pairs.add(pair)
  ```

- [ ] **Node degree valid** (≥ 1 for connected component)
  ```python
  def test_node_degree_valid():
      """All nodes have ≥1 edge"""
      for node_id, node in nodes.items():
          degree = len(node.incoming_edges) + len(node.outgoing_edges)
          assert degree >= 1, f"Node {node_id}: isolated (degree={degree})"
  ```

---

### B.2 Lane Boundary Computation

**Issue**: Incorrect lane boundaries cause:
- Vehicles spawning outside lanes
- Lane-to-lane transitions fail
- Rendering shows lane boundaries offset incorrectly

**Checklist**:

- [ ] **Lane boundaries perpendicular to centerline**
  ```python
  def test_lane_boundary_perpendicular():
      """Left/right boundaries perpendicular to centerline"""
      centerline = np.array([[0, 0], [10, 0], [20, 5]])
      left, right = compute_lane_boundaries(centerline, width=10, lanes=2)
      
      # For each segment, check perpendicularity
      for i in range(len(centerline) - 1):
          # Centerline direction
          c_dir = centerline[i+1] - centerline[i]
          c_dir = c_dir / np.linalg.norm(c_dir)
          
          # Left boundary direction
          l_dir = left[i+1] - left[i]
          l_dir = l_dir / np.linalg.norm(l_dir)
          
          # Should be perpendicular (dot product ≈ 0)
          dot = np.dot(c_dir, l_dir)
          assert np.abs(dot) < 1e-6, f"Not perpendicular: dot={dot}"
  ```

- [ ] **Lane width preserved**
  ```python
  def test_lane_width_constant():
      """Distance between left and right boundary = road_width"""
      centerline = np.array([[0, 0], [10, 0]])
      width = 12.0
      left, right = compute_lane_boundaries(centerline, width=width, lanes=2)
      
      # At each point, distance should be ~width
      for i in range(len(left)):
          dist = np.linalg.norm(left[i] - right[i])
          assert np.abs(dist - width) < 0.1, \
              f"Width mismatch at {i}: {dist} vs {width}"
  ```

- [ ] **No lane crossing at intersections**
  ```python
  def test_lanes_not_crossing_at_intersection():
      """Lanes should not cross at intersection node"""
      # Generate two roads meeting at intersection
      # Verify lanes don't cross
      pass
  ```

---

### B.3 Building Placement & Overlap Detection

**Issue**: Building overlaps cause:
- Physics collisions in UE5
- Invalid scenarios (buildings in roads)
- Rendering artifacts

**Checklist**:

- [ ] **No building-to-building overlaps**
  ```python
  def test_buildings_not_overlapping():
      """No two buildings overlap"""
      buildings = generate_buildings(blocks, seed=42, config=cfg)
      
      for i, b1 in enumerate(buildings):
          for b2 in buildings[i+1:]:
              # AABB overlap test
              if (b1.x - b1.w/2 < b2.x + b2.w/2 and
                  b1.x + b1.w/2 > b2.x - b2.w/2 and
                  b1.y - b1.h/2 < b2.y + b2.h/2 and
                  b1.y + b1.h/2 > b2.y - b2.h/2):
                  pytest.fail(f"Buildings {i} and {i+j} overlap")
  ```

- [ ] **No building-to-road overlaps**
  ```python
  def test_buildings_not_in_roads():
      """No building intersects with road"""
      for building in buildings:
          for road in roads:
              assert not aabb_intersects(building.aabb, road.aabb), \
                  f"Building in road: {building.id} on {road.id}"
  ```

- [ ] **All buildings within bounds**
  ```python
  def test_buildings_within_bounds():
      """All buildings inside scenario bounds"""
      x_min, y_min, x_max, y_max = bounds
      for building in buildings:
          assert building.x - building.w/2 >= x_min
          assert building.x + building.w/2 <= x_max
          assert building.y - building.h/2 >= y_min
          assert building.y + building.h/2 <= y_max
  ```

- [ ] **Building density matches config**
  ```python
  def test_building_density_matches_config():
      """Actual density ~= configured density (within ±10%)"""
      expected_density = config.building_density
      area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
      actual_count = len(buildings)
      expected_count = expected_density * area / avg_building_area
      
      error = abs(actual_count - expected_count) / expected_count
      assert error < 0.1, f"Density error: {error*100}%"
  ```

---

## SECTION C: Randomization & Coverage

### C.1 Seed-Based Determinism

**Issue**: Randomization doesn't produce expected distribution:
- Same seed produces different results (non-deterministic)
- Different seeds produce similar results (insufficient randomness)
- Seed space isn't uniformly explored

**Checklist**:

- [ ] **Determinism: identical seed → identical output**
  ```python
  def test_determinism():
      """Same seed reproduces exactly"""
      result1 = generate(seed=42, config=cfg)
      result2 = generate(seed=42, config=cfg)
      
      # Bit-identical (no floating point variance)
      assert (result1 == result2).all()
  ```

- [ ] **Coverage: different seeds produce different results**
  ```python
  def test_seed_coverage():
      """Different seeds produce different results"""
      results = [generate(seed=i, config=cfg) for i in range(10)]
      
      # Results should differ
      for i in range(len(results)):
          for j in range(i+1, len(results)):
              diff = np.mean(np.abs(results[i] - results[j]))
              assert diff > 1.0, f"Seeds {i} and {j} too similar"
  ```

- [ ] **Distribution matches expectation** (if documented)
  ```python
  def test_building_height_distribution():
      """Building heights follow configured distribution"""
      heights = [b.height for b in buildings]
      
      # Should be uniformly distributed in [min_height, max_height]
      assert min(heights) >= config.building_heights[0]
      assert max(heights) <= config.building_heights[1]
      
      # Mean should be roughly (min + max) / 2
      mean = np.mean(heights)
      expected_mean = (config.building_heights[0] + config.building_heights[1]) / 2
      assert np.abs(mean - expected_mean) < expected_mean * 0.1  # ±10%
  ```

- [ ] **Seed space uniformly sampled**
  ```python
  def test_seed_space_coverage():
      """Seeds 0, 2^32, 2^63 all work"""
      for seed in [0, 1, 2**31 - 1, 2**31, 2**32 - 1, 2**32, 2**63 - 1]:
          result = generate(seed=seed, config=cfg)
          assert len(result) > 0, f"Seed {seed} failed"
  ```

---

## SECTION D: Rendering & Visualization

### D.1 Mesh Geometry Correctness

**Issue**: Invalid meshes crash UE5 or render incorrectly:
- Degenerate triangles (area ≈ 0)
- Non-manifold geometry (edges with >2 faces)
- NaN/Inf vertices
- Wrong winding order (flipped normals)

**Checklist**:

- [ ] **All vertices are finite**
  ```python
  def test_mesh_vertices_finite():
      """No NaN or Inf in vertices"""
      for vertex in vertices:
          assert np.isfinite(vertex).all(), \
              f"Non-finite vertex: {vertex}"
  ```

- [ ] **No degenerate triangles**
  ```python
  def test_no_degenerate_triangles():
      """Triangle area > min_threshold"""
      for i in range(0, len(triangles), 3):
          v0 = vertices[triangles[i]]
          v1 = vertices[triangles[i+1]]
          v2 = vertices[triangles[i+2]]
          
          area = 0.5 * np.abs(
              (v1[0] - v0[0]) * (v2[1] - v0[1]) -
              (v2[0] - v0[0]) * (v1[1] - v0[1])
          )
          
          assert area > 1e-6, f"Degenerate triangle: area={area}"
  ```

- [ ] **Correct winding order (CCW for UE5)**
  ```python
  def test_triangle_winding():
      """Triangles wound counter-clockwise"""
      for i in range(0, len(triangles), 3):
          v0 = vertices[triangles[i]]
          v1 = vertices[triangles[i+1]]
          v2 = vertices[triangles[i+2]]
          
          # Cross product should point up (positive Z)
          cross = (v1 - v0).cross(v2 - v0)
          assert cross.z > 0, f"Triangle {i}: wrong winding"
  ```

- [ ] **Bounds sensible**
  ```python
  def test_mesh_bounds():
      """Mesh within scenario bounds"""
      x_min, y_min, x_max, y_max = bounds
      for vertex in vertices:
          assert x_min - 100 <= vertex.x <= x_max + 100
          assert y_min - 100 <= vertex.y <= y_max + 100
  ```

---

### D.2 Material & Texture Assignment

**Issue**: Materials not applied correctly:
- Textures flipped or tiled incorrectly
- Material not found (crashes in UE5)
- Procedural material parameters invalid

**Checklist**:

- [ ] **All referenced materials exist**
  ```python
  def test_material_references_valid():
      """All material names are valid"""
      for mesh in meshes:
          assert mesh.material in VALID_MATERIALS, \
              f"Unknown material: {mesh.material}"
  ```

- [ ] **Material parameters in valid range**
  ```python
  def test_material_parameters_valid():
      """Procedural material parameters valid"""
      for material in materials:
          assert 0.0 <= material.roughness <= 1.0
          assert 0.0 <= material.metallic <= 1.0
          assert material.emission_intensity >= 0.0
  ```

- [ ] **UV coordinates valid** (if using textures)
  ```python
  def test_uv_coordinates_valid():
      """UV coords in [0, 1] or reasonable wrap"""
      for uv in uv_coordinates:
          assert -0.1 <= uv.x <= 1.1, f"UV X out of range: {uv.x}"
          assert -0.1 <= uv.y <= 1.1, f"UV Y out of range: {uv.y}"
  ```

---

## SECTION E: Camera & Sensor Geometry

### E.1 Camera Projection Mathematics

**Issue**: Incorrect projection causes:
- Bounding boxes misaligned with objects
- Annotations outside image bounds
- Invalid camera intrinsics

**Checklist**:

- [ ] **Camera intrinsics mathematically valid**
  ```python
  def test_camera_intrinsics_valid():
      """Focal length, principal point sensible"""
      K = camera.get_intrinsic_matrix()
      
      # Focal length > 0
      assert K[0, 0] > 0, "Focal length X invalid"
      assert K[1, 1] > 0, "Focal length Y invalid"
      
      # Principal point inside image
      assert 0 <= K[0, 2] <= width
      assert 0 <= K[1, 2] <= height
      
      # Symmetric focal length (square pixels)
      assert np.abs(K[0, 0] - K[1, 1]) < 1.0
  ```

- [ ] **Extrinsics are valid rigid transformation**
  ```python
  def test_camera_extrinsics_valid():
      """Rotation matrix is orthogonal, translation sensible"""
      R = camera.get_rotation_matrix()
      t = camera.get_translation_vector()
      
      # R @ R^T = I (orthogonality)
      should_be_identity = R @ R.T
      assert np.allclose(should_be_identity, np.eye(3), atol=1e-6)
      
      # det(R) = 1 (not reflection)
      assert np.abs(np.linalg.det(R) - 1.0) < 1e-6
      
      # Translation within scenario bounds
      assert np.linalg.norm(t) < 1000  # < 1km
  ```

- [ ] **Projected points within image bounds**
  ```python
  def test_projection_in_bounds():
      """All projected 3D points map to valid 2D coordinates"""
      for point_3d in scenario_points:
          point_2d = camera.project(point_3d)
          
          # Should be in image or just outside (for partial occlusion)
          assert -100 <= point_2d.x <= width + 100
          assert -100 <= point_2d.y <= height + 100
  ```

- [ ] **Distortion model consistent**
  ```python
  def test_distortion_model_consistency():
      """Distortion doesn't create NaNs"""
      for point_2d in [(0, 0), (100, 100), (w/2, h/2), (w-1, h-1)]:
          distorted = apply_distortion(point_2d, camera.distortion_coeffs)
          assert np.isfinite(distorted).all()
  ```

---

### E.2 LiDAR Point Cloud

**Issue**: Invalid point clouds:
- Points outside max_range
- Duplicate points
- NaN/Inf coordinates
- Wrong number of points

**Checklist**:

- [ ] **All points within max range**
  ```python
  def test_lidar_points_in_range():
      """All LiDAR points within max_range"""
      max_range = config.lidar.max_range
      for point in lidar_points:
          distance = np.linalg.norm(point)
          assert distance <= max_range, f"Point {distance}m > max {max_range}m"
  ```

- [ ] **Point count matches resolution**
  ```python
  def test_lidar_point_count():
      """Point count = H_res * V_res (approximately)"""
      h_res = config.lidar.horizontal_resolution
      v_res = config.lidar.vertical_resolution
      expected_count = h_res * v_res
      actual_count = len(lidar_points)
      
      # Allow 10% loss due to occlusion
      assert actual_count > expected_count * 0.9, \
          f"Too few points: {actual_count} < {expected_count * 0.9}"
  ```

- [ ] **No duplicate points**
  ```python
  def test_no_duplicate_lidar_points():
      """All points unique (within tolerance)"""
      for i, p1 in enumerate(lidar_points):
          for p2 in lidar_points[i+1:]:
              distance = np.linalg.norm(p1 - p2)
              assert distance > 1e-6, "Duplicate point"
  ```

- [ ] **Azimuth/elevation distribution uniform**
  ```python
  def test_lidar_angular_distribution():
      """Points uniformly distributed in azimuth/elevation"""
      azimuths = np.arctan2(points[:, 1], points[:, 0])
      elevations = np.arctan2(points[:, 2], 
                             np.sqrt(points[:, 0]**2 + points[:, 1]**2))
      
      # Should span full range
      assert np.min(azimuths) < -np.pi * 0.9
      assert np.max(azimuths) > np.pi * 0.9
      assert np.min(elevations) < config.lidar.vertical_fov[0] * DEG2RAD * 0.9
      assert np.max(elevations) > config.lidar.vertical_fov[1] * DEG2RAD * 0.9
  ```

---

## SECTION F: Ground Truth Annotations

### F.1 Bounding Box Correctness

**Issue**: Invalid annotations:
- Boxes outside image bounds
- Box coordinates in wrong order (x_max < x_min)
- Box area = 0
- Boxes don't match actual objects

**Checklist**:

- [ ] **2D boxes within image bounds**
  ```python
  def test_2d_boxes_in_bounds():
      """All 2D boxes inside image"""
      for box in boxes_2d:
          x1, y1, x2, y2 = box
          assert x1 >= 0 and x2 <= width
          assert y1 >= 0 and y2 <= height
          assert x1 < x2, "x1 >= x2"
          assert y1 < y2, "y1 >= y2"
  ```

- [ ] **3D boxes valid geometry**
  ```python
  def test_3d_boxes_valid():
      """3D boxes have positive dimensions"""
      for box in boxes_3d:
          length, width, height = box.dimensions
          assert length > 0 and width > 0 and height > 0
          assert length < 50  # Reasonable for vehicles
          assert width < 30
          assert height < 10
  ```

- [ ] **Box count matches objects**
  ```python
  def test_annotation_count_matches_objects():
      """Number of annotations = number of visible objects"""
      visible_objects = [o for o in scenario.objects if o.is_visible]
      annotations = extract_annotations(frame)
      
      assert len(annotations) == len(visible_objects), \
          f"Annotation count mismatch: {len(annotations)} vs {len(visible_objects)}"
  ```

- [ ] **Visibility flag is correct**
  ```python
  def test_visibility_flag_correct():
      """Visibility flag matches actual visibility"""
      for annotation in annotations:
          if annotation.visibility > 0.5:
              # Object is mostly visible: should appear large in image
              box_area = annotation.area
              image_area = width * height
              assert box_area > image_area * 0.01, \
                  f"Visible object too small: {box_area}"
  ```

- [ ] **Occlusion flags valid**
  ```python
  def test_occlusion_flag_bounds():
      """Occlusion in [0, 1]"""
      for annotation in annotations:
          assert 0.0 <= annotation.occlusion <= 1.0
  ```

---

### F.2 Segmentation Mask Quality

**Issue**: Bad masks cause model training to fail:
- Empty masks (count = 0)
- Masks outside image bounds
- Overlapping instance masks
- Semantic class mismatch

**Checklist**:

- [ ] **No empty masks**
  ```python
  def test_no_empty_masks():
      """Each instance has >0 pixels"""
      for mask_id, mask in segmentation_masks.items():
          pixel_count = np.sum(mask > 0)
          assert pixel_count > 0, f"Empty mask: {mask_id}"
  ```

- [ ] **Instance masks don't overlap**
  ```python
  def test_instance_masks_no_overlap():
      """No pixel assigned to multiple instances"""
      combined = np.zeros_like(segmentation_masks[0])
      for mask in segmentation_masks.values():
          overlap = combined & mask
          assert np.sum(overlap) == 0, "Overlapping instance masks"
          combined |= mask
  ```

- [ ] **Semantic class valid**
  ```python
  def test_semantic_class_valid():
      """Semantic class in valid range"""
      for class_id in semantic_segmentation.flat:
          assert class_id in VALID_CLASS_IDS, \
              f"Invalid class: {class_id}"
  ```

- [ ] **Mask-annotation alignment**
  ```python
  def test_mask_annotation_alignment():
      """Mask area roughly matches annotation box area"""
      for annotation in annotations:
          mask = segmentation_masks[annotation.object_id]
          mask_area = np.sum(mask > 0)
          box_area = annotation.area
          
          # Allow 20% difference
          error = np.abs(mask_area - box_area) / box_area
          assert error < 0.2, \
              f"Mask-box area mismatch: {error*100}%"
  ```

---

## SECTION G: Domain-Specific Edge Cases

### G.1 Urban Scenarios

**Issue**: Urban-specific problems:
- Intersections with >4 roads (invalid)
- Lane transition too abrupt
- Building density too high (no roads)
- One-way streets handled incorrectly

**Checklist**:

- [ ] **Intersection degree valid** (2-4)
  ```python
  def test_intersection_degree_valid():
      """Intersections are T-junction or 4-way"""
      for node in nodes.values():
          if node.is_intersection:
              degree = len(node.incoming) + len(node.outgoing)
              assert degree in [2, 3, 4], f"Invalid degree: {degree}"
  ```

- [ ] **Lane count consistent**
  ```python
  def test_lane_count_consistent():
      """Forward and reverse edges have same lane count"""
      for edge in edges.values():
          if edge.reverse_edge_id is not None:
              reverse_edge = edges[edge.reverse_edge_id]
              assert edge.num_lanes == reverse_edge.num_lanes, \
                  "Lane count mismatch on reverse edge"
  ```

- [ ] **One-way streets marked**
  ```python
  def test_oneway_streets_marked():
      """One-way streets have reverse_edge_id = None"""
      for edge in edges.values():
          if edge.is_oneway:
              assert edge.reverse_edge_id is None
  ```

---

### G.2 Highway Scenarios

**Issue**: Highway-specific problems:
- Lane count < 2 (not a highway)
- Speed limit too low
- On-ramp/off-ramp connectivity wrong
- Merges/splits not handled

**Checklist**:

- [ ] **Highway lane count valid** (≥2 per direction)
  ```python
  def test_highway_minimum_lanes():
      """Highways have ≥2 lanes per direction"""
      for edge in edges.values():
          if edge.road_type == RoadType.HIGHWAY:
              assert edge.num_lanes >= 2
  ```

- [ ] **Highway speed limit high** (≥80 km/h)
  ```python
  def test_highway_speed_limit():
      """Highways speed ≥80 km/h"""
      for edge in edges.values():
          if edge.road_type == RoadType.HIGHWAY:
              assert edge.speed_limit_kmh >= 80
  ```

- [ ] **On-ramps properly connected**
  ```python
  def test_onramp_connectivity():
      """On-ramp connects surface street to highway"""
      for ramp in onramps:
          start_type = edges[ramp.start_edge].road_type
          end_type = edges[ramp.end_edge].road_type
          
          # Expect: surface → highway or highway → surface
          assert (start_type != end_type)
  ```

---

## SECTION H: Export & Validation

### H.1 COCO JSON Format

**Issue**: Invalid COCO export:
- Missing required fields
- Annotation ID collision
- Image_id doesn't exist
- Category_id invalid
- Malformed JSON

**Checklist**:

- [ ] **COCO schema validation**
  ```python
  def test_coco_schema_valid():
      """COCO JSON follows official schema"""
      from pycocotools.coco import COCO
      
      coco = COCO("annotations.json")
      # If this doesn't crash, schema is valid
  ```

- [ ] **Required fields present**
  ```python
  def test_coco_required_fields():
      """All required COCO fields present"""
      required = ['images', 'annotations', 'categories']
      for field in required:
          assert field in coco_data
  ```

- [ ] **No ID collisions**
  ```python
  def test_coco_no_id_collisions():
      """Image IDs, annotation IDs are unique"""
      image_ids = [img['id'] for img in images]
      ann_ids = [ann['id'] for ann in annotations]
      
      assert len(image_ids) == len(set(image_ids))
      assert len(ann_ids) == len(set(ann_ids))
  ```

- [ ] **Image references valid**
  ```python
  def test_coco_image_references():
      """All annotation image_ids reference existing images"""
      image_ids = {img['id'] for img in images}
      for ann in annotations:
          assert ann['image_id'] in image_ids
  ```

- [ ] **Category references valid**
  ```python
  def test_coco_category_references():
      """All annotation category_ids valid"""
      valid_categories = {cat['id'] for cat in categories}
      for ann in annotations:
          assert ann['category_id'] in valid_categories
  ```

- [ ] **JSON serializable**
  ```python
  def test_coco_json_serializable():
      """COCO data can be JSON serialized/deserialized"""
      import json
      
      # Serialize
      json_str = json.dumps(coco_data)
      
      # Deserialize
      parsed = json.loads(json_str)
      
      # Should match
      assert len(parsed['images']) == len(coco_data['images'])
  ```

---

### H.2 Dataset Consistency

**Issue**: Dataset-wide inconsistencies:
- Annotation counts vary wildly by frame
- Class distribution unbalanced
- Missing frames in sequence
- Duplicate frames

**Checklist**:

- [ ] **Frame sequence complete**
  ```python
  def test_frame_sequence_complete():
      """No missing frames in sequence"""
      frame_ids = sorted([f['frame_id'] for f in dataset])
      for i in range(len(frame_ids) - 1):
          assert frame_ids[i+1] == frame_ids[i] + 1, \
              f"Missing frame: {frame_ids[i]} → {frame_ids[i+1]}"
  ```

- [ ] **No duplicate frames**
  ```python
  def test_no_duplicate_frames():
      """No two frames are identical"""
      frame_hashes = set()
      for frame in dataset:
          frame_hash = hash(frame['image'].tobytes())
          assert frame_hash not in frame_hashes
          frame_hashes.add(frame_hash)
  ```

- [ ] **Annotation count variation sensible**
  ```python
  def test_annotation_count_reasonable():
      """Annotation count doesn't vary wildly"""
      counts = [len(frame['annotations']) for frame in dataset]
      mean = np.mean(counts)
      std = np.std(counts)
      
      # No frame should have wildly different count
      for count in counts:
          assert np.abs(count - mean) < 3 * std, \
              f"Outlier annotation count: {count}"
  ```

- [ ] **Class distribution matches config**
  ```python
  def test_class_distribution_matches_config():
      """Vehicle type distribution matches config"""
      vehicle_types = {}
      for frame in dataset:
          for ann in frame['annotations']:
              vtype = ann['category']
              vehicle_types[vtype] = vehicle_types.get(vtype, 0) + 1
      
      total = sum(vehicle_types.values())
      distribution = {k: v/total for k, v in vehicle_types.items()}
      
      # Compare to config
      for vtype, expected_ratio in config.vehicle_mix.items():
          actual_ratio = distribution.get(vtype, 0)
          error = np.abs(actual_ratio - expected_ratio)
          assert error < 0.05, \
              f"Distribution mismatch: {vtype} {error*100}%"
  ```

---

## SECTION I: Performance & Profiling

### I.1 Memory Usage

**Issue**: Memory leaks or excessive allocation:
- Memory grows unbounded
- Arrays not freed
- RNG state leaks

**Checklist**:

- [ ] **Memory doesn't grow unbounded**
  ```python
  def test_memory_usage_bounded():
      """Memory usage bounded as generation proceeds"""
      import tracemalloc
      
      tracemalloc.start()
      
      for i in range(100):
          scenario = generate_scenario(seed=i)
          del scenario  # Should free
      
      current, peak = tracemalloc.get_traced_memory()
      
      # Peak memory should be <2GB
      assert peak < 2 * 1024 * 1024 * 1024, f"Peak: {peak} bytes"
  ```

- [ ] **No lingering references**
  ```python
  def test_no_lingering_references():
      """Generated objects can be garbage collected"""
      import gc
      
      gen = RoadNetworkGenerator(42, config)
      nodes, edges = gen.generate(bounds)
      
      del gen
      gc.collect()
      
      # nodes, edges should still work
      assert len(nodes) > 0
  ```

---

### I.2 Computation Time

**Issue**: Performance regression:
- Generation slower than expected
- No timeout on slow operations

**Checklist**:

- [ ] **Each phase has performance targets**
  ```python
  def test_road_network_generation_performance():
      """Road network generates in <5s per km²"""
      bounds = (-500, -500, 500, 500)  # 1km x 1km
      
      import time
      start = time.perf_counter()
      gen = RoadNetworkGenerator(42, config)
      gen.generate(bounds)
      elapsed = time.perf_counter() - start
      
      assert elapsed < 5.0, f"Too slow: {elapsed}s"
  ```

- [ ] **Scaling performance measured**
  ```python
  def test_scaling_performance():
      """Performance scales linearly with area"""
      times = {}
      for area_mult in [1, 4, 9, 16]:  # 1x, 2x, 3x, 4x
          bounds = (-500*np.sqrt(area_mult), -500*np.sqrt(area_mult),
                   500*np.sqrt(area_mult), 500*np.sqrt(area_mult))
          
          start = time.perf_counter()
          gen = RoadNetworkGenerator(42, config)
          gen.generate(bounds)
          times[area_mult] = time.perf_counter() - start
      
      # Should scale roughly linearly (or better)
      # time[4] should be ~4x time[1]
      ratio = times[4] / times[1]
      assert 2.0 < ratio < 6.0  # Linear ± tolerance
  ```

---

## SECTION J: Version Control & Reproducibility

### J.1 Scenario Versioning

**Issue**: Scenario definitions change, breaking reproducibility:
- Config file changed, old seed produces different scenario
- Code algorithm changed, old seed invalid

**Checklist**:

- [ ] **Config version tracked**
  ```python
  # configs/scenario_templates/urban_dense.yaml
  version: "1.0"  # Increment when format changes
  
  # If you change grid_perturbation_ratio from 0.15 to 0.2:
  # → Increment to version: "1.1"
  ```

- [ ] **Code version tagged**
  ```bash
  # git tag
  git tag v0.1.0  # Marks exact code version
  git show v0.1.0:src/procedural/road_network.py
  
  # Can reproduce old scenarios:
  # git checkout v0.1.0
  # python generate_dataset.py seed=<old_seed>
  ```

- [ ] **Metadata includes versions**
  ```python
  # Output metadata.json
  {
      "scenario_id": "proc_scenario_0001",
      "seed": 42,
      "git_commit": "abc1234def567",  # git rev-parse HEAD
      "git_tag": "v0.1.0",            # git describe --tags
      "config_version": "1.0",
      "python_version": "3.11.8",
      "numpy_version": "1.26.3"
  }
  ```

---

## Summary Checklist

Use this before each release:

- [ ] **Math**: Floating point tolerance, numerical stability, edge cases
- [ ] **Randomization**: Seed determinism, coverage, no global RNG
- [ ] **Geometry**: Topology valid, boundaries correct, no overlaps
- [ ] **Rendering**: Meshes valid, materials assigned, no NaN/Inf
- [ ] **Sensors**: Camera/LiDAR valid, projections correct
- [ ] **Annotations**: Boxes valid, segmentation correct, counts match
- [ ] **Export**: COCO valid, NuScenes valid, JSON parseable
- [ ] **Performance**: Memory bounded, time targets met, scales correctly
- [ ] **Versioning**: Config versioned, code tagged, metadata tracked

**If ANY checklist item fails → DO NOT SHIP**

---

**Keep this file open while implementing. Check items as you implement.**
