"""Pure mesh-cleanup operations: validation, repair, Taubin smoothing, adaptive decimation.

Everything here works on in-memory ``trimesh.Trimesh`` objects (no file I/O) so it can be
tested with small synthetic meshes.

Mass properties are deliberately avoided: trimesh's ``mass_properties`` divides by volume to
get the center of mass, which emits ``RuntimeWarning: invalid value encountered in divide`` for
closed bodies with ~zero volume (collapsed marching-cubes cells). Orientation is fixed with a
signed volume computed directly, and zero-volume bodies are skipped and reported instead.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import trimesh
from trimesh import graph

# Faces whose area is below this fraction of (bounding-box diagonal)^2 count as zero-area.
ZERO_AREA_RELATIVE = 1e-12
# A closed body whose |volume| is below this fraction of diagonal^3 has no usable volume.
ZERO_VOLUME_RELATIVE = 1e-12
# Smoothing that shrinks the mean vertex distance from the centroid by more than this is
# reported. (The bounding box is a poor measure: it is set by the noise spikes smoothing removes.)
SHRINK_WARNING_RATIO = 0.03


class MeshCleanupError(Exception):
    """Raised when a mesh cannot be cleaned into usable geometry."""


@dataclass(frozen=True)
class CleanupParameters:
    """Tunable cleanup settings (see ``Settings.mesh_cleanup_*``)."""

    taubin_iterations: int = 10
    # Gentle defaults chosen from measurements on job_000006: main-body volume unchanged, medium
    # pieces keep >= 96% of volume (0.5/0.51 shrank them 6-12%), noise still clearly reduced.
    taubin_lambda: float = 0.33
    taubin_nu: float = 0.34
    # Pieces smaller than this are not smoothed: for 2-4 cell fragments there is no noise/shape
    # separation and Taubin only shrinks them (-23% volume at 12-59 faces). 0 smooths everything.
    smooth_min_component_faces: int = 60
    min_component_faces: int = 12
    decimate_min_faces: int = 50_000
    decimate_max_faces: int = 250_000

    def validate(self) -> None:
        """Raise ``ValueError`` for parameters that would make cleanup unstable or meaningless."""
        if self.taubin_iterations < 0:
            raise ValueError("taubin_iterations must be >= 0")
        if not (0 < self.taubin_lambda <= 1 and 0 < self.taubin_nu <= 1):
            raise ValueError("taubin_lambda and taubin_nu must be in (0, 1]")
        # Taubin's non-shrinking condition (trimesh docs): 0 < 1/lambda - 1/nu < 0.1.
        band = 1.0 / self.taubin_lambda - 1.0 / self.taubin_nu
        if self.taubin_iterations > 0 and not (0 < band < 0.1):
            raise ValueError(
                f"Taubin parameters need 0 < 1/lambda - 1/nu < 0.1 (got {band:.4f}); "
                "nu must be slightly larger than lambda"
            )
        if self.min_component_faces < 0:
            raise ValueError("min_component_faces must be >= 0")
        if self.smooth_min_component_faces < 0:
            raise ValueError("smooth_min_component_faces must be >= 0")
        if self.decimate_min_faces < 1:
            raise ValueError("decimate_min_faces must be >= 1")
        if self.decimate_max_faces < self.decimate_min_faces:
            raise ValueError("decimate_max_faces must be >= decimate_min_faces")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    """Geometry checks for a mesh (input or output)."""

    vertices: int = 0
    faces: int = 0
    invalid_face_indices: int = 0
    nonfinite_vertices: int = 0
    repeated_index_faces: int = 0
    zero_area_faces: int = 0
    bounds_finite: bool = False
    bounds: list[list[float]] | None = None
    extent: list[float] | None = None
    surface_area: float = 0.0
    components: int = 0
    closed_components: int = 0
    boundary_edges: int = 0
    nonmanifold_edges: int = 0
    watertight: bool = False
    winding_consistent: bool = False
    signed_volume: float | None = None
    usable: bool = False
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _diagonal(vertices: np.ndarray) -> float:
    if len(vertices) == 0:
        return 0.0
    return float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))


def _mean_radius(vertices: np.ndarray) -> float:
    if len(vertices) == 0:
        return 0.0
    return float(np.linalg.norm(vertices - vertices.mean(axis=0), axis=1).mean())


def _face_areas(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = vertices[faces]
    return 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)


def signed_volume(vertices: np.ndarray, faces: np.ndarray) -> float:
    """Signed volume via the divergence theorem; never divides (unlike center-of-mass code)."""
    if len(faces) == 0:
        return 0.0
    tri = vertices[faces]
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)


def validate_mesh(mesh: trimesh.Trimesh) -> ValidationReport:
    """Check geometry without modifying it. ``usable`` means it can be rendered and exported."""
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    report = ValidationReport(vertices=len(vertices), faces=len(faces))

    if len(vertices) == 0 or len(faces) == 0:
        report.problems.append("mesh has no vertices or no faces")
        return report

    in_range = (faces >= 0) & (faces < len(vertices))
    bad_index = ~in_range.all(axis=1)
    report.invalid_face_indices = int(bad_index.sum())

    finite_vertex = np.isfinite(vertices).all(axis=1)
    report.nonfinite_vertices = int((~finite_vertex).sum())

    valid = ~bad_index
    valid[valid] &= finite_vertex[faces[valid]].all(axis=1)
    good_faces = faces[valid]

    repeated = (
        (good_faces[:, 0] == good_faces[:, 1])
        | (good_faces[:, 1] == good_faces[:, 2])
        | (good_faces[:, 0] == good_faces[:, 2])
    )
    report.repeated_index_faces = int(repeated.sum())

    finite_vertices = vertices[finite_vertex]
    if len(finite_vertices) == 0:
        report.problems.append("no finite vertex coordinates")
        return report
    lo, hi = finite_vertices.min(axis=0), finite_vertices.max(axis=0)
    report.bounds = [lo.tolist(), hi.tolist()]
    report.extent = (hi - lo).tolist()
    report.bounds_finite = bool(np.isfinite(lo).all() and np.isfinite(hi).all())

    diagonal = _diagonal(finite_vertices)
    areas = _face_areas(vertices, good_faces) if len(good_faces) else np.zeros(0)
    zero_area = areas <= ZERO_AREA_RELATIVE * max(diagonal, 1e-30) ** 2
    report.zero_area_faces = int(zero_area.sum())
    report.surface_area = float(areas.sum())

    if report.invalid_face_indices:
        report.problems.append(f"{report.invalid_face_indices} faces reference missing vertices")
    if report.nonfinite_vertices:
        report.problems.append(f"{report.nonfinite_vertices} vertices have NaN/inf coordinates")
    if report.repeated_index_faces or report.zero_area_faces:
        report.problems.append(
            f"{report.repeated_index_faces} repeated-index and {report.zero_area_faces} "
            "zero-area (degenerate) faces"
        )

    # Topology is measured on all index-valid faces: zero-area slivers still close surfaces.
    topo_faces = good_faces[~repeated] if len(good_faces) else good_faces
    if len(topo_faces):
        raw_edges = topo_faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
        _, edge_use = np.unique(np.sort(raw_edges, axis=1), axis=0, return_counts=True)
        report.boundary_edges = int((edge_use == 1).sum())
        report.nonmanifold_edges = int((edge_use > 2).sum())
        report.watertight, report.winding_consistent = graph.is_watertight(raw_edges)
        adjacency = trimesh.Trimesh(vertices=vertices, faces=topo_faces, process=False).face_adjacency
        groups = graph.connected_components(adjacency, nodes=np.arange(len(topo_faces)))
        report.components = len(groups)
        report.closed_components = sum(
            1
            for group in groups
            if all(graph.is_watertight(topo_faces[group][:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)))
        )
        if report.watertight and report.winding_consistent:
            report.signed_volume = signed_volume(vertices, topo_faces)
    usable_faces = good_faces[~zero_area & ~repeated] if len(good_faces) else good_faces

    flat_dims = sum(1 for e in (report.extent or []) if e <= 1e-9 * max(diagonal, 1e-30))
    if not report.bounds_finite or diagonal <= 0:
        report.problems.append("bounds are not finite or have zero size")
    elif flat_dims >= 2:
        report.problems.append("geometry is degenerate (collapsed to a line or point)")

    report.usable = bool(
        len(usable_faces) > 0
        and report.bounds_finite
        and diagonal > 0
        and flat_dims < 2
        and report.surface_area > 0
    )
    if not report.usable:
        report.problems.append("no usable surface geometry")
    return report


def _keep_faces(mesh: trimesh.Trimesh, keep: np.ndarray) -> None:
    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()


def repair_mesh(mesh: trimesh.Trimesh) -> dict[str, int]:
    """Drop invalid, non-finite, collapsed and duplicate faces in place; return counts.

    Deliberately topology-preserving: vertices are not merged (coincident marching-cubes vertices
    belong to separate pieces that only touch, and merging creates non-manifold edges) and
    zero-area slivers with distinct vertices are kept (they close surfaces; deleting them opened
    ~2,000 boundary edges on job_000006). Only faces that reference a vertex twice are removed.
    """
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    counts: dict[str, int] = {}

    in_range = ((faces >= 0) & (faces < len(vertices))).all(axis=1)
    counts["invalid_index_faces_removed"] = int((~in_range).sum())
    keep = in_range.copy()
    finite_vertex = np.isfinite(vertices).all(axis=1)
    keep[keep] &= finite_vertex[faces[keep]].all(axis=1)
    counts["nonfinite_faces_removed"] = int(in_range.sum() - keep.sum())
    if not keep.all():
        _keep_faces(mesh, keep)

    faces = np.asarray(mesh.faces)
    collapsed = (faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 0] == faces[:, 2])
    counts["collapsed_faces_removed"] = int(collapsed.sum())
    if collapsed.any():
        _keep_faces(mesh, ~collapsed)

    unique = mesh.unique_faces()
    counts["duplicate_faces_removed"] = int((~unique).sum())
    if not unique.all():
        _keep_faces(mesh, unique)

    vertices = np.asarray(mesh.vertices)
    if len(mesh.faces):
        areas = _face_areas(vertices, np.asarray(mesh.faces))
        counts["zero_area_faces_kept"] = int(
            (areas <= ZERO_AREA_RELATIVE * max(_diagonal(vertices), 1e-30) ** 2).sum()
        )
    else:
        counts["zero_area_faces_kept"] = 0
    return counts


def remove_small_components(mesh: trimesh.Trimesh, min_faces: int) -> dict[str, int]:
    """Remove disconnected pieces with fewer than ``min_faces`` faces (floaters) in place."""
    if min_faces <= 0 or len(mesh.faces) == 0:
        return {"components_removed": 0, "component_faces_removed": 0}
    groups = graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)))
    keep = np.zeros(len(mesh.faces), dtype=bool)
    removed = 0
    for group in groups:
        if len(group) >= min_faces:
            keep[group] = True
        else:
            removed += 1
    faces_removed = int((~keep).sum())
    if faces_removed:
        _keep_faces(mesh, keep)
    return {"components_removed": removed, "component_faces_removed": faces_removed}


def orient_components(mesh: trimesh.Trimesh) -> dict[str, int]:
    """Make winding consistent and flip inside-out closed bodies, without mass properties."""
    if len(mesh.faces) == 0:
        return {"bodies_flipped": 0, "zero_volume_bodies": 0}
    trimesh.repair.fix_winding(mesh)
    faces = np.asarray(mesh.faces).copy()
    vertices = np.asarray(mesh.vertices)
    diagonal = _diagonal(vertices)
    groups = graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
    flipped = zero_volume = 0
    for group in groups:
        if len(group) < 4:
            continue
        body = faces[group]
        tight, wound = graph.is_watertight(body[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2))
        if not (tight and wound):
            continue
        volume = signed_volume(vertices, body)
        if abs(volume) <= ZERO_VOLUME_RELATIVE * max(diagonal, 1e-30) ** 3:
            zero_volume += 1  # orientation undefined; leave as is
            continue
        if volume < 0:
            faces[group] = body[:, ::-1]
            flipped += 1
    if flipped:
        mesh.faces = faces
    return {"bodies_flipped": flipped, "zero_volume_bodies": zero_volume}


def taubin_smooth(mesh: trimesh.Trimesh, params: CleanupParameters) -> dict[str, Any]:
    """Apply trimesh's Taubin (lambda/mu) filter in place and report shape change."""
    if params.taubin_iterations == 0 or len(mesh.faces) == 0:
        return {"applied": False, "reason": "disabled"}
    before = _diagonal(np.asarray(mesh.vertices))
    radius_before = _mean_radius(np.asarray(mesh.vertices))
    original = np.asarray(mesh.vertices).copy()
    frozen = np.zeros(0, dtype=np.int64)
    skipped = 0
    if params.smooth_min_component_faces > 0:
        faces = np.asarray(mesh.faces)
        small = [
            g
            for g in graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
            if len(g) < params.smooth_min_component_faces
        ]
        skipped = len(small)
        if small:
            frozen = np.unique(np.concatenate([faces[g].ravel() for g in small]))
    trimesh.smoothing.filter_taubin(
        mesh,
        lamb=params.taubin_lambda,
        nu=params.taubin_nu,
        iterations=params.taubin_iterations,
    )
    if len(frozen):
        # Pieces are disconnected, so restoring their vertices equals not smoothing them.
        vertices = np.asarray(mesh.vertices).copy()
        vertices[frozen] = original[frozen]
        mesh.vertices = vertices
    if not np.isfinite(mesh.vertices).all():
        raise MeshCleanupError("Taubin smoothing produced non-finite vertex coordinates")
    after = _diagonal(np.asarray(mesh.vertices))
    ratio = after / before if before > 0 else 1.0
    radius_after = _mean_radius(np.asarray(mesh.vertices))
    return {
        "applied": True,
        "algorithm": "taubin (trimesh.smoothing.filter_taubin)",
        "iterations": params.taubin_iterations,
        "lambda": params.taubin_lambda,
        "nu": params.taubin_nu,
        "small_components_not_smoothed": skipped,
        "smooth_min_component_faces": params.smooth_min_component_faces,
        "max_vertex_displacement": round(
            float(np.linalg.norm(np.asarray(mesh.vertices) - original, axis=1).max()), 6
        ),
        "bbox_diagonal_ratio": round(ratio, 6),
        "mean_radius_ratio": round(radius_after / radius_before, 6) if radius_before > 0 else 1.0,
    }


def adaptive_target_faces(face_count: int, params: CleanupParameters) -> int | None:
    """Target face count, or ``None`` when the mesh is already simple enough.

    The target is the geometric mean of the input size and ``decimate_min_faces``, clamped to
    ``[decimate_min_faces, decimate_max_faces]``: large meshes are reduced more in relative terms,
    and meshes near the floor are barely touched. E.g. with the defaults (50k / 250k):
    60k -> 54.8k, 200k -> 100k, 919k -> 214k, 4M -> 250k.
    """
    if face_count <= params.decimate_min_faces:
        return None
    target = int(round(math.sqrt(face_count * params.decimate_min_faces)))
    target = max(params.decimate_min_faces, min(params.decimate_max_faces, target))
    return target if target < face_count else None


def decimate_mesh(mesh: trimesh.Trimesh, target_faces: int) -> trimesh.Trimesh:
    """Quadric-error edge-collapse decimation (fast-simplification), keeping vertex colors.

    trimesh's ``simplify_quadric_decimation`` wraps the same library but drops vertex colors,
    which carry all appearance for Instant-NGP meshes; the collapse mapping is replayed here
    to average each merged vertex's colors.
    """
    import fast_simplification

    points = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
    triangles = np.ascontiguousarray(mesh.faces, dtype=np.int64)
    _, _, collapses = fast_simplification.simplify(
        points, triangles, target_count=int(target_faces), return_collapses=True
    )
    new_points, new_faces, mapping = fast_simplification.replay_simplification(
        points, triangles, collapses
    )

    colors = None
    if mesh.visual.kind == "vertex":
        source = np.asarray(mesh.visual.vertex_colors, dtype=np.float64)
        sums = np.zeros((len(new_points), source.shape[1]))
        counts = np.zeros(len(new_points))
        valid = (mapping >= 0) & (mapping < len(new_points))
        np.add.at(sums, mapping[valid], source[valid])
        np.add.at(counts, mapping[valid], 1)
        colors = np.clip(np.round(sums / np.maximum(counts, 1)[:, None]), 0, 255).astype(np.uint8)

    return trimesh.Trimesh(
        vertices=new_points, faces=new_faces, vertex_colors=colors, process=False
    )


@dataclass
class CleanupOutcome:
    mesh: trimesh.Trimesh
    input_validation: ValidationReport
    output_validation: ValidationReport
    steps: dict[str, Any]
    warnings: list[str]


def clean_mesh(source: trimesh.Trimesh, params: CleanupParameters) -> CleanupOutcome:
    """Run the full cleanup on a copy of ``source``; raise ``MeshCleanupError`` if unusable."""
    params.validate()
    warnings: list[str] = []
    input_validation = validate_mesh(source)
    if input_validation.vertices == 0 or input_validation.faces == 0:
        raise MeshCleanupError("Input mesh is empty (no vertices or faces).")

    mesh = source.copy()
    steps: dict[str, Any] = {"repair": repair_mesh(mesh)}
    if len(mesh.faces) == 0:
        raise MeshCleanupError("No valid faces remain after removing invalid geometry.")

    steps["floaters"] = remove_small_components(mesh, params.min_component_faces)
    if len(mesh.faces) == 0:
        raise MeshCleanupError(
            "All geometry was below the floater threshold "
            f"({params.min_component_faces} faces); lower MESH_CLEANUP_MIN_COMPONENT_FACES."
        )
    steps["orientation"] = orient_components(mesh)
    if steps["orientation"]["zero_volume_bodies"]:
        warnings.append(
            f"{steps['orientation']['zero_volume_bodies']} closed bodies have ~zero volume; "
            "their orientation was left unchanged"
        )

    smoothing = taubin_smooth(mesh, params)
    steps["smoothing"] = smoothing
    if smoothing.get("applied") and smoothing["mean_radius_ratio"] < 1 - SHRINK_WARNING_RATIO:
        warnings.append(
            f"smoothing shrank the mesh: mean radius is {smoothing['mean_radius_ratio']:.1%} of input"
        )

    faces_before = len(mesh.faces)
    target = adaptive_target_faces(faces_before, params)
    if target is None:
        steps["decimation"] = {
            "applied": False,
            "reason": f"{faces_before} faces <= threshold {params.decimate_min_faces}; already simple",
            "faces_before": faces_before,
        }
    else:
        area_before = float(mesh.area)
        decimated = decimate_mesh(mesh, target)
        faces_after = len(decimated.faces)
        if faces_after >= faces_before or faces_after == 0:
            raise MeshCleanupError(
                f"Decimation did not reduce the mesh ({faces_before} -> {faces_after} faces)."
            )
        steps["decimation"] = {
            "applied": True,
            "algorithm": "quadric error metric edge collapse (fast-simplification)",
            "target_faces": target,
            "faces_before": faces_before,
            "faces_after": faces_after,
            "surface_area_ratio": round(float(decimated.area) / area_before, 6) if area_before else None,
        }
        mesh = decimated
        steps["post_decimation_repair"] = repair_mesh(mesh)
        # Edge collapses can flip local winding; restore consistency like the first pass.
        steps["post_decimation_orientation"] = orient_components(mesh)
        if steps["post_decimation_orientation"]["zero_volume_bodies"]:
            warnings.append(
                f"{steps['post_decimation_orientation']['zero_volume_bodies']} closed bodies have "
                "~zero volume after decimation; their orientation was left unchanged"
            )

    output_validation = validate_mesh(mesh)
    if output_validation.boundary_edges > input_validation.boundary_edges:
        warnings.append(
            f"cleanup opened holes: {output_validation.boundary_edges} boundary edges "
            f"(input had {input_validation.boundary_edges})"
        )
    if output_validation.nonmanifold_edges > input_validation.nonmanifold_edges:
        warnings.append(
            f"cleanup added non-manifold edges: {output_validation.nonmanifold_edges} "
            f"(input had {input_validation.nonmanifold_edges})"
        )
    if output_validation.zero_area_faces:
        warnings.append(
            f"{output_validation.zero_area_faces} zero-area sliver faces kept to keep surfaces closed"
        )
    if not output_validation.usable:
        raise MeshCleanupError(
            "Cleaned mesh failed validation: " + "; ".join(output_validation.problems)
        )
    if output_validation.invalid_face_indices or output_validation.nonfinite_vertices:
        raise MeshCleanupError("Cleaned mesh still contains invalid indices or NaN/inf vertices.")
    return CleanupOutcome(mesh, input_validation, output_validation, steps, warnings)
