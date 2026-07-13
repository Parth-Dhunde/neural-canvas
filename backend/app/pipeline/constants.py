"""Pipeline stage identifiers and display names."""

PIPELINE_STAGE_DEFINITIONS: tuple[tuple[int, str], ...] = (
    (1, "Upload"),
    (2, "Background Removal"),
    (3, "Camera Estimation"),
    (4, "Reconstruction"),
    (5, "Mesh Generation"),
    (6, "Mesh Cleanup"),
    (7, "Export"),
)

PIPELINE_STAGE_NAMES: tuple[str, ...] = tuple(name for _, name in PIPELINE_STAGE_DEFINITIONS)

UPLOAD_STAGE_ID = 1
BACKGROUND_REMOVAL_STAGE_ID = 2
CAMERA_ESTIMATION_STAGE_ID = 3
TRAINING_STAGE_ID = 4
MESH_GENERATION_STAGE_ID = 5
MESH_CLEANUP_STAGE_ID = 6
EXPORT_STAGE_ID = 7
