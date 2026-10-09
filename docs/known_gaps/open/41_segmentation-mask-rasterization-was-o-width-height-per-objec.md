### [RESOLVED] Segmentation mask rasterization was O(width * height) per object
Was: `rasterize_instance_masks` ran one *full-image*
`matplotlib.path.Path.contains_points` pass per object, regardless of
how much screen space the object actually covered -- the same class of
gap as the LiDAR/depth-map entry above, just for a different (non-ray-
casting) algorithm.

Resolved by `_paint_silhouette`: each object's point-in-polygon test now
only runs over its own projected silhouette's pixel bounding box,
clipped to the image, instead of the full frame -- every pixel outside
that box is trivially outside a convex silhouette too, so this is an
*exact* optimization, not an approximation (verified directly against a
brute-force full-image reference across 100 randomized convex polygon
shapes/positions, including ones partially or fully outside the image,
in `test_segmentation.py`). For a small object in a large (e.g.
1920x1080) frame this is a two-to-three-order-of-magnitude reduction in
points tested -- exactly the "real HD-resolution frame" case this entry
originally called out as slow.

