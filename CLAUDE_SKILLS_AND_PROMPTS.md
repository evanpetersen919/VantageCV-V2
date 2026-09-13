# Claude Skills & Specialized Prompts
## Purpose-Built Prompts for Common Tasks in This Project

**Use these prompts when asking Claude for help on specific tasks.**

Each skill is designed to get Claude to think about this project's unique challenges.

---

## SKILL 1: Code Review for Geometric Algorithms

**When**: You've written a geometry function (lane boundaries, building placement, etc.) and want Claude to review it for correctness.

**Prompt**:

```
You are a computational geometry expert reviewing code for a procedural AV 
synthetic dataset generator.

I'm reviewing this [FUNCTION NAME] implementation:

[PASTE CODE]

This function is part of procedural generation for autonomous vehicle 
perception datasets. Geometric correctness is critical.

Please check for:

1. **Floating-point precision issues**
   - Are tolerances defined globally?
   - Are near-zero vectors handled?
   - Any division by near-zero values?
   - Correct use of np.isclose() vs ==?

2. **Degeneracy handling**
   - What happens with collinear points?
   - Nearly-parallel lines?
   - Nearly-zero area triangles?
   - Are degenerate cases documented?

3. **Array indexing correctness**
   - Any off-by-one errors?
   - Correct loop bounds (especially range(len(...)-1))?
   - Slice semantics ([start:end) is correct?
   - Edge cases: empty array, single element?

4. **Mathematical correctness**
   - Does the algorithm match the documented math?
   - Are all formulas correctly implemented?
   - Any sign errors (perpendicular computed correctly)?
   - Coordinate system assumptions stated?

5. **Numerical stability**
   - Does it work on extreme inputs (very small/large values)?
   - Are there any unstable operations (e.g., subtracting similar numbers)?
   - Would NaN or Inf propagate?

6. **Test coverage**
   - What edge cases need testing?
   - What degenerate cases should be checked?
   - What's the minimum test set?

Please flag any issues found and suggest fixes.
```

---

## SKILL 2: Mathematical Formulation Review

**When**: You want Claude to verify that your code matches the mathematical specification.

**Prompt**:

```
I'm implementing a procedural generation algorithm. Please verify the 
mathematical correctness.

**Mathematical specification:**
[PASTE MATH/PSEUDOCODE]

**My implementation:**
[PASTE CODE]

Please:

1. **Match specification to code**
   - Does each line of code correspond to the math?
   - Are variables named consistently?
   - Is the order of operations correct?

2. **Check numerical implementation**
   - Are there any precision losses?
   - Does the code handle edge cases the math assumes away?
   - Are approximations documented?

3. **Verify assumptions**
   - What preconditions must be met (non-empty array, etc.)?
   - What postconditions are guaranteed?
   - Are these checked at runtime?

4. **Find edge cases the math misses**
   - Empty input?
   - Single element?
   - Very large/small values?
   - Degenerate configurations?

5. **Suggest test cases**
   - What specific inputs should be tested?
   - What results should be verified?
   - How would you validate correctness?

Output:
- ✅ Matches specification or ❌ Issues found
- List of specific concerns
- Suggested test cases
```

---

## SKILL 3: Floating-Point Bug Detection

**When**: You have mysterious bugs that might be numerical precision issues.

**Prompt**:

```
I'm debugging numerical issues in a procedural generation system.

**Symptom**: [DESCRIBE THE BUG - e.g., "Road segments occasionally don't 
connect at intersections"]

**Related code**:
[PASTE RELEVANT FUNCTIONS]

This is geometric code where small numerical errors compound. Please check for:

1. **Precision analysis**
   - What's the expected precision of each value?
   - Where could accumulated rounding errors occur?
   - Are tolerances too strict or too loose?

2. **Specific precision antipatterns**
   - Direct equality comparison (== for floats)?
   - Equality after subtraction (a - b == 0)?
   - Normalized then unnormalized?
   - Operations on nearly-equal values?
   - Square roots then squaring?

3. **Stability of algorithms used**
   - Delaunay triangulation robust to degenerate input?
   - Solving linear systems condition number okay?
   - Intersection algorithms numerically stable?

4. **Tolerance values review**
   - Current tolerance: [VALUE]
   - Is this appropriate? (Physics scale analysis)
   - Too strict → false negatives, too loose → false positives?

5. **Fix recommendations**
   - Change tolerances?
   - Use different algorithm (more stable)?
   - Add explicit degenerate handling?
   - Change precision (float32 vs float64)?

Please identify the most likely numerical issue and suggest a fix with 
test case.
```

---

## SKILL 4: Randomization & Reproducibility Audit

**When**: You want to verify that seeding is correct and deterministic.

**Prompt**:

```
I'm auditing randomization in a procedural generation module to ensure 
determinism and proper seed handling.

**Code to audit**:
[PASTE GENERATOR CLASS/FUNCTIONS]

Please verify:

1. **Seed isolation**
   - Is RNG stored as instance variable (not global)?
   - np.random.RandomState() used correctly?
   - No external randomness sources (random.choice, etc.)?
   - Are all random calls using self.rng?

2. **Determinism verification**
   - Would calling twice with same seed produce identical output?
   - Are there any sources of non-determinism (time.time(), os.urandom())?
   - Any shared state between instances?

3. **Seed propagation**
   - How are sub-generators seeded?
   - Are seeds derived deterministically from base seed?
   - Would different modules get independent randomness?

4. **Test cases needed**
   - Test same seed → identical output
   - Test different seeds → different output
   - Test that output actually uses randomness

5. **Edge case seeds**
   - Seed = 0 (often problematic)?
   - Seed = 2^31 - 1 (signed int boundary)?
   - Seed = 2^32 - 1 (uint32 boundary)?
   - Seed = 2^63 - 1 (int64 max)?

Please flag:
- Any violations of determinism
- Missing test cases
- Suggested fixes
```

---

## SKILL 5: Test Case Generation for Edge Cases

**When**: You want Claude to generate comprehensive test cases for a function.

**Prompt**:

```
Generate comprehensive test cases for this function:

[PASTE FUNCTION]

This is part of a procedural generation system for AV datasets. Correctness 
is critical.

For this function, generate pytest test cases covering:

1. **Normal cases** (expected usage)
   - Typical input size
   - Typical parameter values
   - Expected output properties

2. **Boundary cases**
   - Minimum valid input (e.g., empty array, single element)
   - Maximum reasonable input (e.g., 1000000 points)
   - Extreme parameter values

3. **Degenerate geometry** (if applicable)
   - Collinear points
   - Nearly-identical points
   - Nearly-parallel lines
   - Zero-area polygons

4. **Numerical edge cases**
   - Very large values (1e10)
   - Very small values (1e-10)
   - Mixed scales (1e-5 and 1e5 in same calculation)
   - NaN and Inf inputs (should handle gracefully)

5. **Performance cases**
   - Time complexity boundary (100, 1000, 10000 elements)
   - Memory complexity check

6. **Error cases**
   - Invalid input types
   - Out-of-range parameters
   - Impossible geometry
   - Should raise specific exceptions

For each test, provide:
- Test name
- Input setup
- Expected behavior
- Assertion

Generate as pytest functions, ready to paste into tests/.
```

---

## SKILL 6: Performance Profiling & Optimization

**When**: A function is too slow or you want to make it faster.

**Prompt**:

```
Help me optimize this function for performance.

**Current implementation**:
[PASTE CODE]

**Performance target**: [E.g., "Process 10,000 points in <1 second"]
**Current performance**: [E.g., "Takes 5 seconds"]
**Bottleneck**: [E.g., "Unknown, need profiling"]

Please:

1. **Identify complexity**
   - What's the Big-O complexity (time and space)?
   - Are there nested loops creating O(n²) or worse?
   - Any expensive library calls (sorting, triangulation)?

2. **Profiling recommendations**
   - How would you profile this?
   - Use: py-spy, memory-profiler, line-profiler?
   - What specific profiling command?

3. **Optimization ideas**
   - Algorithmic improvements (better algorithm)?
   - Data structure changes (dict vs list)?
   - Avoiding redundant computation?
   - Vectorization with NumPy?
   - Early exit conditions?

4. **Benchmarking strategy**
   - How to measure before/after?
   - What input sizes to test?
   - How many iterations for statistical significance?

5. **Trade-offs**
   - Speed vs readability?
   - Speed vs memory?
   - Speed vs precision?

Provide:
- Specific optimization changes (with code)
- Expected speedup (with justification)
- Benchmark command to verify
```

---

## SKILL 7: Geometry Visualization & Debugging

**When**: Geometric output looks wrong and you want to debug visually.

**Prompt**:

```
I need to visualize procedural generation output to debug what's wrong.

**What I generated**: [E.g., "Road network with 50 nodes and 100 edges"]

**What looks wrong**: [E.g., "Roads have gaps, buildings overlap, lanes 
aren't parallel"]

**Available tools**: Python (Matplotlib, Plotly), could export to UE5

Please provide code to:

1. **Visualize the output**
   ```python
   # Show [nodes, edges, buildings, lanes, etc.]
   # Color-code by property [road type, building density, etc.]
   # Overlay multiple layers
   ```

2. **Debug specific issues**
   - Show nodes that violate constraints
   - Highlight overlapping objects
   - Show boundary violations
   - Annotate with ID/properties

3. **Interactive inspection**
   - Plotly for zooming/clicking on objects
   - Show object properties on hover
   - Toggle layers on/off

4. **Export for manual inspection**
   - GeoJSON for Google Maps/QGIS
   - OBJ/FBX for viewing in 3D viewer
   - High-res PNG for documentation

Example output:
```python
# [PROVIDE WORKING CODE I CAN RUN]
# python debug_visualization.py --input scenario_001.json --output debug.html
```

Make visualization code reusable for future debugging.
```

---

## SKILL 8: Documentation & Type Hints

**When**: You want Claude to add comprehensive documentation.

**Prompt**:

```
Please add professional documentation to this function/class:

[PASTE CODE]

Requirements:
- NumPy-style docstring (Args, Returns, Raises, Notes, Examples)
- Full type hints (Python 3.11 style)
- Complexity analysis (Big-O)
- Assumptions documented
- Edge cases mentioned
- References to papers/algorithms if applicable

Format:

```python
def my_function(
    param1: np.ndarray,
    param2: float,
    seed: int
) -> Tuple[Dict[int, Node], Dict[int, Edge]]:
    \"\"\"
    Brief description of what this does.

    Longer description explaining the algorithm and why it's done this way.
    Reference any papers or mathematical foundations.

    Parameters
    ----------
    param1 : np.ndarray
        Description of param1, including shape, dtype, and constraints
    param2 : float
        Description of param2, valid range, and what it controls
    seed : int
        Random seed for reproducibility. Must be in [0, 2^63-1]

    Returns
    -------
    nodes : Dict[int, Node]
        Mapping of node_id to Node object. All nodes reachable via BFS.
    edges : Dict[int, Edge]
        Mapping of edge_id to Edge object. Bidirectional roads have paired edges.

    Raises
    ------
    ValueError
        If param2 is outside valid range
    QhullError
        If Delaunay triangulation fails (degenerate input)

    Notes
    -----
    Time complexity: O(N log N) due to Delaunay triangulation
    Space complexity: O(N) for node/edge storage

    This function uses Delaunay triangulation from scipy.spatial.
    The algorithm is based on [PAPER REFERENCE].

    Examples
    --------
    >>> points = np.array([[0, 0], [10, 0], [5, 10]])
    >>> nodes, edges = my_function(points, param2=0.5, seed=42)
    >>> len(nodes)
    3
    >>> len(edges) >= 3
    True

    See Also
    --------
    related_function : Does something related
    \"\"\"
```

Apply this style to all functions in [MODULE NAME].
```

---

## SKILL 9: Test Coverage Analysis

**When**: You want to ensure tests cover all important cases.

**Prompt**:

```
Analyze test coverage for this module and suggest improvements.

**Module being tested**: [PASTE MODULE CODE]

**Current tests**: [PASTE TEST FILE]

Please:

1. **Coverage analysis**
   - Which functions have tests?
   - Which functions are missing tests?
   - Which lines are never executed in tests?
   
   Run this to check:
   ```bash
   pytest --cov=src/procedural/[module] tests/
   ```

2. **Test completeness**
   - Are edge cases tested? (empty input, single element, huge input)
   - Are error cases tested? (invalid input, constraint violations)
   - Are boundary conditions tested? (off-by-one errors)?

3. **Untested code paths**
   - If-branches that aren't exercised?
   - Exception handlers never triggered?
   - Optional parameters not tested?

4. **Missing test patterns**
   - Determinism tests (same seed → same output)?
   - Performance tests (completes in time budget)?
   - Consistency tests (output has expected properties)?
   - Integration tests (works with other modules)?

5. **Suggested new tests**
   For each gap, provide:
   ```python
   def test_[specific_case]():
       \"\"\"Test [what this covers]\"\"\"
       # [Test code]
   ```

Aim for >90% coverage. Flag any untestable code as suspicious (might have bug).
```

---

## SKILL 10: Compatibility & Integration Checking

**When**: You're integrating modules or changing code and want to verify nothing breaks.

**Prompt**:

```
I'm integrating these modules and want to verify compatibility.

**Module A**: [PASTE MODULE A]

**Module B**: [PASTE MODULE B]

**Expected integration**: Module B takes output from Module A

Please check:

1. **Type compatibility**
   - Does Module B expect the exact types Module A produces?
   - Any type mismatches in data structures?
   - Are numpy dtypes compatible (float32 vs float64)?

2. **Data format compatibility**
   - Shape of arrays (Module A produces [N,2], Module B expects [N,2])?
   - Ordering of data?
   - Units (meters? degrees? radians?)?

3. **Semantic compatibility**
   - Do the semantics align? (Both treating position as [x,y] in same coordinate system?)
   - Assumptions about data (sorted? unique? within bounds?)?
   - State expectations (Module B requires Module A to run first)?

4. **Error handling**
   - If Module A fails, does Module B gracefully handle it?
   - Are error types compatible?
   - Should Module A validate input for Module B?

5. **Integration test**
   Provide test case:
   ```python
   def test_integration_a_to_b():
       # Generate output from Module A
       output_a = module_a.generate(...)
       
       # Feed to Module B
       output_b = module_b.process(output_a)
       
       # Verify expectations
       assert ...
   ```

Flag any compatibility issues and suggest fixes.
```

---

## SKILL 11: Debugging Reproducibility Issues

**When**: Same seed produces different output on different runs.

**Prompt**:

```
I have a reproducibility issue: same seed sometimes produces different output.

**Symptom**: 
[E.G., "Running with seed=42 produces N nodes on first run, but N±1 on 
another run"]

**Code to debug**:
[PASTE GENERATOR CLASS]

This is critical for dataset reproducibility. Please check:

1. **Global state pollution**
   - Any global variables modified?
   - Module-level imports that modify state?
   - Environment variables affecting randomness?
   - Any np.random.seed() calls (should use RandomState)?

2. **RNG initialization**
   - Is self.rng = np.random.RandomState(seed) done?
   - Is seed used directly as int64 or somehow transformed?
   - Are all random calls going through self.rng?

3. **Floating-point instability**
   - Are results dependent on floating-point rounding (non-deterministic)?
   - Should use integer arithmetic where possible?
   - Any algorithm that could have multiple valid solutions?

4. **Hidden randomness**
   - External library calls with optional randomness?
   - Multithreading (race conditions)?
   - Hashing of mutable objects?

5. **Test for reproducibility**
   Provide this test:
   ```python
   def test_complete_reproducibility():
       for seed in [0, 1, 42, 2**31-1, 2**32-1]:
           result1 = generate(seed)
           result2 = generate(seed)
           
           # Bit-identical comparison
           assert (result1 == result2).all()
   ```

Likely issues ranked by probability:
1. ...
2. ...
3. ...
```

---

## SKILL 12: Code Quality & Standards Enforcement

**When**: You want to ensure code meets the project's professional standards.

**Prompt**:

```
Please review this code for professional quality standards.

[PASTE CODE]

Check against these project standards:

**Naming Conventions**
- Classes: PascalCase ✓/✗
- Functions: snake_case ✓/✗
- Constants: UPPER_SNAKE_CASE ✓/✗
- Private members: _leading_underscore ✓/✗

**Type Hints**
- All function parameters typed ✓/✗
- All return types specified ✓/✗
- Complex types use from typing import ✓/✗

**Docstrings**
- All functions have docstrings ✓/✗
- NumPy-style format ✓/✗
- Parameters documented ✓/✗
- Returns documented ✓/✗
- Raises documented ✓/✗
- Examples provided ✓/✗

**Error Handling**
- No bare except: ✓/✗
- Specific exception types caught ✓/✗
- Errors logged with context ✓/✗
- Meaningful error messages ✓/✗

**Code Style**
- PEP 8 compliant ✓/✗
- Line length ≤ 100 ✓/✗
- Imports sorted and grouped ✓/✗
- No trailing whitespace ✓/✗

**Constants & Magic Numbers**
- No hardcoded numbers (constants defined) ✓/✗
- All constants named and documented ✓/✗

**Testing**
- Unit tests present ✓/✗
- Edge cases covered ✓/✗
- Error cases tested ✓/✗
- Performance tested ✓/✗

For each ✗, provide:
- Specific issue (line number)
- How to fix it
- Fixed code

Then provide a summary of violations and fixes needed.
```

---

## SKILL 13: Research Validity & Sim2Real

**When**: You want to validate that your synthetic data is useful for real AV perception.

**Prompt**:

```
I want to validate that my synthetic dataset is useful for training 
AV perception models.

**Synthetic data characteristics**:
- Resolution: [e.g., 1920x1080]
- Sensor: [e.g., RGB camera]
- Scenarios: [e.g., 1000 urban scenes, 500 highway]
- Object types: [e.g., car, truck, pedestrian]
- Annotation types: [e.g., 3D bboxes, segmentation]

**Reference real data**: [if you have some]
- [Dataset name, characteristics]

Please evaluate:

1. **Domain gap analysis**
   - What visual characteristics differ from real images?
   - Photorealism assessment?
   - Lighting/weather coverage?
   - Sensor parameter accuracy?

2. **Coverage validation**
   - Do scenarios cover real-world cases? (rush hour traffic, night driving, rain?)
   - Balanced class distribution? (equal car/truck/pedestrian?)
   - Edge cases included? (occlusions, small objects, far objects?)

3. **Transferability concerns**
   - Will models trained on this data work on real sensors?
   - What adaptation might be needed?
   - What's most likely to transfer poorly?

4. **Dataset quality for training**
   - Annotation accuracy?
   - Consistency across frames?
   - Any systematic biases?

5. **Recommendations**
   - What to add to improve transferability?
   - What's good enough to skip?
   - How much synthetic vs real data needed for good transfer?

6. **Validation metrics**
   If you had real data, suggest metrics to measure sim2real gap:
   - Fréchet distance on object counts?
   - KL-divergence on class distribution?
   - Feature-space comparison (if you extract features)?

Provide a research-level assessment of whether this dataset would be useful 
for AV perception training.
```

---

## How to Use These Skills

### Example: Debugging a Geometric Issue

```
I'm getting weird road networks where some segments have gaps.

This is SKILL 5 territory.

Prompt:
```
[SKILL 5 PROMPT]
[PASTE MY CODE]
```

Claude will generate test cases for edge cases I might not have thought of.
```

### Example: Optimizing Performance

```
Road network generation is too slow (10 seconds for 1km²).
Target is <5 seconds.

This is SKILL 6.

Prompt:
```
[SKILL 6 PROMPT]
[PASTE CODE]
Target: <5 seconds for 1km²
Current: 10 seconds
```

Claude will profile, identify bottlenecks, and suggest optimizations.
```

### Example: Ensuring Code Quality

```
Before committing code, I want to ensure it meets standards.

This is SKILL 12.

Prompt:
```
[SKILL 12 PROMPT]
[PASTE ALL CODE IN MODULE]
```

Claude will checklist every standard and provide fixes.
```

---

## Using Skills Together

**Typical workflow**:

1. **Write code** (SKILL 8: Good documentation helps)
2. **Review for correctness** (SKILL 1: Geometric correctness)
3. **Add tests** (SKILL 5: Edge case generation)
4. **Measure coverage** (SKILL 9: Coverage analysis)
5. **Optimize if needed** (SKILL 6: Performance)
6. **Final quality check** (SKILL 12: Code standards)
7. **Validate research value** (SKILL 13: Sim2real)

---

## Pro Tips

- **Copy the skill prompt exactly** (they're tested and refined)
- **Provide complete context** (don't omit code, it makes Claude less helpful)
- **Use markdown code blocks** when pasting code
- **For bugs**: Include error message, expected behavior, actual behavior
- **For performance**: Include current metrics and targets
- **Be specific**: "code review" is less helpful than "check for floating-point bugs"

---

**Next time you're stuck on a task, find the relevant skill above and use it.**
