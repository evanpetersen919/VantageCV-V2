### [DEFERRED] 3D ground-truth boxes and the LiDAR sensor model are not wired into the live pipeline or export
Every object already carries a real 3D box (center, dimensions, heading --
`BoundingBox3D`) that drives occlusion ray-casting and 2D projection
(`src/ground_truth/occlusion.py`, `bbox_2d.py`), and `src/sensors/lidar_model.py`
implements a real ray-cast LiDAR point-cloud simulation against mesh triangles
with its own spatial acceleration structure and tests -- but neither is called
anywhere in `src/orchestration/` or `bin/`: no live-generated dataset produces
point clouds, and the exported COCO annotations carry only the projected 2D
box and segmentation polygon, never the 3D box fields. The intended future use
is a 3D-detection-from-LiDAR task, where the already-computed 3D boxes are the
natural label format -- deferred until that task actually starts, since
exporting 3D boxes with no point clouds to pair them with would just be dead
data in the schema.

