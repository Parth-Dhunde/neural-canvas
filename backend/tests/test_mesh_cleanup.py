"""Tests for Stage 6 mesh cleanup: validation, repair, Taubin smoothing, adaptive decimation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.config import Settings
from app.engines.mesh_cleanup.processing import (
    CleanupParameters,
    MeshCleanupError,
    adaptive_target_faces,
    clean_mesh,
    orient_components,
    remove_small_components,
    repair_mesh,
    taubin_smooth,
    validate_mesh,
)
from app.engines.mesh_cleanup.trimesh_cleanup import TrimeshMeshCleanupEngine
from app.jobs.repository import JobRepository
from app.models.job import Job
from app.services.mesh_cleanup_service import MeshCleanupError as ServiceCleanupError
from app.services.mesh_cleanup_service import MeshCleanupService

JOB_ID = "job_000401"
RUN = "2026-10-15T090328_577266_0000"


def _noisy_sphere(subdivisions: int = 3, noise: float = 0.03, seed: int = 0) -> trimesh.Trimesh:
    sphere = trimesh.creation.icosphere(subdivisions=subdivisions)
    rng = np.random.default_rng(seed)
    radial = 1.0 + rng.normal(0.0, noise, len(sphere.vertices))
    vertices = sphere.vertices * radial[:, None]
    # Color by height so decimation's color transfer can be checked.
    colors = np.zeros((len(vertices), 4), dtype=np.uint8)
    colors[:, 0] = np.clip((vertices[:, 2] + 1.1) / 2.2 * 255, 0, 255).astype(np.uint8)
    colors[:, 3] = 255
    return trimesh.Trimesh(vertices=vertices, faces=sphere.faces, vertex_colors=colors, process=False)


def _radius_std(mesh: trimesh.Trimesh) -> float:
    return float(np.linalg.norm(mesh.vertices - mesh.vertices.mean(axis=0), axis=1).std())


# ---------------------------------------------------------------- parameters


@pytest.mark.parametrize(
    "kwargs",
    [
        {"taubin_lambda": 0.5, "taubin_nu": 0.5},  # 1/l - 1/n == 0: no anti-shrink band
        {"taubin_lambda": 0.5, "taubin_nu": 0.45},  # nu < lambda
        {"taubin_lambda": 0.3, "taubin_nu": 0.9},  # band far above 0.1
        {"taubin_iterations": -1},
        {"min_component_faces": -1},
        {"decimate_min_faces": 10_000, "decimate_max_faces": 5_000},
    ],
)
def test_invalid_parameters_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        CleanupParameters(**kwargs).validate()


def test_default_parameters_are_valid() -> None:
    CleanupParameters().validate()
    settings = Settings()
    assert settings.mesh_cleanup_taubin_nu > settings.mesh_cleanup_taubin_lambda


# ---------------------------------------------------------------- smoothing


def test_taubin_reduces_noise_without_shrinking() -> None:
    mesh = _noisy_sphere(subdivisions=4)
    before_std = _radius_std(mesh)
    before_volume = mesh.volume
    info = taubin_smooth(mesh, CleanupParameters())
    assert info["applied"] is True and info["iterations"] == 10
    # Gentle defaults (0.33/0.34) remove ~39% of the radial noise on this sphere.
    assert _radius_std(mesh) < 0.7 * before_std
    assert abs(mesh.volume / before_volume - 1) < 0.05  # Taubin keeps volume (plain Laplacian shrinks)
    assert 0.98 < info["mean_radius_ratio"] < 1.02  # no measurable shrinkage


def test_plain_laplacian_would_shrink_more_than_taubin() -> None:
    taubin = _noisy_sphere(subdivisions=4)
    laplacian = _noisy_sphere(subdivisions=4)
    volume = taubin.volume
    taubin_smooth(taubin, CleanupParameters())
    # trimesh rescales Laplacian results by default; disable that to see raw Laplacian shrinkage.
    trimesh.smoothing.filter_laplacian(laplacian, lamb=0.5, iterations=10, volume_constraint=False)
    assert abs(taubin.volume - volume) < abs(laplacian.volume - volume)


def test_smoothing_can_be_disabled() -> None:
    mesh = _noisy_sphere()
    original = mesh.vertices.copy()
    info = taubin_smooth(mesh, CleanupParameters(taubin_iterations=0))
    assert info == {"applied": False, "reason": "disabled"}
    assert np.array_equal(mesh.vertices, original)


# ---------------------------------------------------------------- decimation


def test_adaptive_target_is_geometric_mean_clamped() -> None:
    params = CleanupParameters(decimate_min_faces=50_000, decimate_max_faces=250_000)
    assert adaptive_target_faces(40_000, params) is None
    assert adaptive_target_faces(50_000, params) is None
    assert adaptive_target_faces(200_000, params) == 100_000
    assert adaptive_target_faces(919_200, params) == 214_383
    assert adaptive_target_faces(4_000_000, params) == 250_000
    targets = [adaptive_target_faces(n, params) for n in (60_000, 120_000, 400_000, 900_000)]
    assert targets == sorted(targets)  # larger inputs keep more faces in absolute terms
    ratios = [t / n for t, n in zip(targets, (60_000, 120_000, 400_000, 900_000))]
    assert ratios == sorted(ratios, reverse=True)  # ...but are reduced more in relative terms


def test_decimation_really_reduces_triangles_and_keeps_shape_and_colors() -> None:
    mesh = _noisy_sphere(subdivisions=6, noise=0.0)  # 81,920 faces
    params = CleanupParameters(decimate_min_faces=5_000, decimate_max_faces=50_000, taubin_iterations=0)
    outcome = clean_mesh(mesh, params)
    step = outcome.steps["decimation"]
    expected_target = adaptive_target_faces(len(mesh.faces), params)
    assert step["applied"] is True and step["target_faces"] == expected_target
    assert len(outcome.mesh.faces) < len(mesh.faces)
    assert abs(len(outcome.mesh.faces) - expected_target) <= 0.02 * expected_target
    assert abs(outcome.mesh.volume / mesh.volume - 1) < 0.02
    assert outcome.output_validation.watertight and outcome.output_validation.usable
    # Colors survive the collapse mapping and still follow height.
    colors = outcome.mesh.visual.vertex_colors[:, 0].astype(float)
    assert outcome.mesh.visual.kind == "vertex"
    assert np.corrcoef(colors, outcome.mesh.vertices[:, 2])[0, 1] > 0.98


def test_small_mesh_is_not_decimated() -> None:
    mesh = _noisy_sphere(subdivisions=3)
    outcome = clean_mesh(mesh, CleanupParameters(taubin_iterations=0))
    assert outcome.steps["decimation"]["applied"] is False
    assert "already simple" in outcome.steps["decimation"]["reason"]
    assert len(outcome.mesh.faces) == len(mesh.faces)


# ---------------------------------------------------------------- validation and repair


def test_validation_flags_invalid_geometry() -> None:
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [np.nan, 0, 0]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 1, 9], [0, 1, 3], [0, 0, 1], [0, 1, 2]])
    report = validate_mesh(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
    assert report.invalid_face_indices == 1
    assert report.nonfinite_vertices == 1
    assert report.repeated_index_faces == 1
    assert report.bounds_finite and report.usable
    assert any("missing vertices" in p for p in report.problems)


def test_empty_and_collapsed_meshes_are_unusable() -> None:
    assert not validate_mesh(trimesh.Trimesh()).usable
    line = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [2, 0, 0]], faces=[[0, 1, 2]], process=False
    )
    report = validate_mesh(line)
    assert not report.usable and report.zero_area_faces == 1


def test_repair_removes_invalid_collapsed_and_duplicate_faces() -> None:
    base = trimesh.creation.box()
    vertices = np.vstack([base.vertices, [[np.inf, 0, 0]], base.vertices[:1]])  # inf + coincident copy
    faces = np.vstack(
        [
            base.faces,
            [[0, 1, 99]],  # out of range
            [[0, 1, 8]],  # touches the inf vertex
            [[0, 0, 1]],  # collapsed: references vertex 0 twice
            [[0, 9, 1]],  # zero-area (vertex 9 coincides with 0) but distinct indices: kept
            base.faces[:1],  # duplicate face
        ]
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    counts = repair_mesh(mesh)
    assert counts["invalid_index_faces_removed"] == 1
    assert counts["nonfinite_faces_removed"] == 1
    assert counts["collapsed_faces_removed"] == 1
    assert counts["duplicate_faces_removed"] == 1
    assert counts["zero_area_faces_kept"] == 1
    assert "vertices_merged" not in counts  # coincident vertices are not merged
    assert len(mesh.faces) == len(base.faces) + 1
    assert np.isfinite(mesh.vertices).all()


def _closed_sphere_with_sliver() -> trimesh.Trimesh:
    """Closed icosphere where one vertex is pulled onto an edge, making a near-zero-height sliver.

    Marching-cubes output contains many such slivers; deleting them opens holes.
    """
    sphere = trimesh.creation.icosphere(subdivisions=2)
    faces = np.asarray(sphere.faces)
    a, b, v = faces[0]
    vertices = sphere.vertices.copy()
    vertices[v] = (vertices[a] + vertices[b]) / 2 + 1e-9 * vertices[v]
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def test_closed_mesh_with_sliver_stays_closed() -> None:
    mesh = _closed_sphere_with_sliver()
    before = validate_mesh(mesh)
    assert before.boundary_edges == 0
    # The previous repair deleted faces thinner than 1e-6 * diagonal; on this closed mesh that
    # deletes the sliver and opens a hole (the job_000006 regression: 1,189 boundary edges).
    diagonal = float(np.linalg.norm(mesh.extents))
    thin = ~mesh.nondegenerate_faces(height=1e-6 * diagonal)
    assert thin.sum() == 1
    old_behaviour = mesh.copy()
    old_behaviour.update_faces(~thin)
    assert validate_mesh(old_behaviour).boundary_edges == 3
    outcome = clean_mesh(mesh, CleanupParameters(taubin_iterations=0, min_component_faces=0))
    after = outcome.output_validation
    assert after.boundary_edges == 0, "cleanup must not open holes"
    assert after.nonmanifold_edges == 0
    assert after.closed_components == after.components == 1
    assert len(outcome.mesh.faces) == len(mesh.faces)
    assert not any("opened holes" in w for w in outcome.warnings)


def test_validation_reports_topology() -> None:
    closed = validate_mesh(trimesh.creation.icosphere(subdivisions=1))
    assert (closed.boundary_edges, closed.nonmanifold_edges, closed.closed_components) == (0, 0, 1)
    sphere = trimesh.creation.icosphere(subdivisions=1)
    open_mesh = trimesh.Trimesh(vertices=sphere.vertices, faces=sphere.faces[1:], process=False)
    report = validate_mesh(open_mesh)
    assert report.boundary_edges == 3 and report.closed_components == 0 and not report.watertight


def test_small_components_are_not_smoothed_but_large_ones_are() -> None:
    big = _noisy_sphere(subdivisions=3)  # 1,280 faces
    small = trimesh.creation.icosahedron()  # 20 faces
    small.vertices = small.vertices * 0.2 + 5
    mesh = trimesh.util.concatenate([big, small])
    n_big = len(big.vertices)
    before = mesh.vertices.copy()
    info = taubin_smooth(mesh, CleanupParameters(smooth_min_component_faces=60))
    assert info["small_components_not_smoothed"] == 1
    assert np.array_equal(mesh.vertices[n_big:], before[n_big:])  # small piece untouched
    assert not np.allclose(mesh.vertices[:n_big], before[:n_big])  # large piece smoothed
    everything = trimesh.util.concatenate([big, small])
    taubin_smooth(everything, CleanupParameters(smooth_min_component_faces=0))
    assert not np.allclose(everything.vertices[n_big:], before[n_big:])


def test_floaters_below_threshold_are_removed() -> None:
    body = trimesh.creation.icosphere(subdivisions=2)
    speck = trimesh.creation.icosahedron()  # 20 faces
    speck.vertices = speck.vertices * 0.01 + 5
    tiny = trimesh.Trimesh(vertices=[[9, 9, 9], [9.1, 9, 9], [9, 9.1, 9]], faces=[[0, 1, 2]])
    mesh = trimesh.util.concatenate([body, speck, tiny])
    info = remove_small_components(mesh, min_faces=12)
    assert info == {"components_removed": 1, "component_faces_removed": 1}
    assert len(mesh.faces) == len(body.faces) + len(speck.faces)  # 20-face piece is kept
    assert remove_small_components(mesh, min_faces=0)["components_removed"] == 0


def test_zero_volume_closed_body_is_reported_without_runtime_warning() -> None:
    # A flattened octahedron is closed and consistently wound but has zero volume: exactly the
    # case where trimesh's center-of-mass division emits "invalid value encountered in divide".
    octa = trimesh.creation.icosahedron()
    flat = trimesh.Trimesh(vertices=octa.vertices * [1, 1, 0], faces=octa.faces, process=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        info = orient_components(flat)
    assert info["zero_volume_bodies"] == 1 and info["bodies_flipped"] == 0


def test_inside_out_body_is_flipped() -> None:
    box = trimesh.creation.box()
    inverted = trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:, ::-1], process=False)
    assert inverted.volume < 0
    assert orient_components(inverted)["bodies_flipped"] == 1
    assert inverted.volume > 0


def test_cleanup_of_empty_or_fully_degenerate_input_fails_clearly() -> None:
    with pytest.raises(MeshCleanupError, match="empty"):
        clean_mesh(trimesh.Trimesh(), CleanupParameters())
    degenerate = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [2, 0, 0]], faces=[[0, 1, 2]], process=False
    )
    with pytest.raises(MeshCleanupError):
        clean_mesh(degenerate, CleanupParameters())


def test_full_cleanup_emits_no_runtime_warnings() -> None:
    mesh = trimesh.util.concatenate([_noisy_sphere(subdivisions=4), trimesh.creation.icosahedron()])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        outcome = clean_mesh(mesh, CleanupParameters())
    assert outcome.output_validation.usable


# ---------------------------------------------------------------- engine (files) and service


def _tetrahedron_floater() -> trimesh.Trimesh:
    """A closed 4-face speck far from the main body (below the 12-face floater threshold)."""
    tet = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
        faces=[[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]],
        process=False,
    )
    tet.vertices = tet.vertices * 0.02 + 4
    return tet


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def stage5_job(tmp_path: Path):
    settings = Settings(JOBS_ROOT=str(tmp_path / "jobs"))
    repository = JobRepository(settings=settings)
    repository.create_folder_structure(JOB_ID)
    run_dir = repository.jobs_root / JOB_ID / "meshes" / RUN
    run_dir.mkdir(parents=True)
    mesh = trimesh.util.concatenate([_noisy_sphere(subdivisions=4), _tetrahedron_floater()])
    for fmt in ("ply", "obj", "glb"):
        mesh.export(str(run_dir / f"mesh.{fmt}"), file_type=fmt)
    job = Job(id=JOB_ID, name=JOB_ID, engine="Instant-NGP", mesh_path=f"meshes/{RUN}/mesh.glb")
    repository.save(job)
    originals = {p.name: _sha(p) for p in run_dir.iterdir()}
    return settings, repository, run_dir, originals


def test_engine_writes_separate_validated_outputs_and_keeps_originals(stage5_job) -> None:
    settings, repository, run_dir, originals = stage5_job
    engine = TrimeshMeshCleanupEngine(settings=settings, repository=repository)
    logs: list[str] = []
    result = engine.clean(repository.get(JOB_ID), log=lambda m, level="info": logs.append(m))

    assert result.success, result.message
    out_dir = repository.jobs_root / JOB_ID / result.data["output"]["dir"]
    assert out_dir.parent == run_dir / "cleanup"
    for fmt in ("ply", "obj", "glb"):
        info = result.data["output"]["files"][fmt]
        path = repository.jobs_root / JOB_ID / info["path"]
        assert path.is_file() and info["faces"] == result.data["output"]["faces"]
    report = json.loads((out_dir / "cleanup.json").read_text())
    assert report["status"] == "succeeded"
    assert report["validation"]["output"]["usable"] is True
    assert report["parameters"]["taubin_nu"] == 0.34
    assert report["parameters"]["smooth_min_component_faces"] == 60
    assert report["steps"]["floaters"]["components_removed"] == 1
    # Stage 5 originals are untouched and no temporary directories remain.
    assert {p.name: _sha(p) for p in run_dir.iterdir() if p.is_file()} == originals
    assert not [p for p in (run_dir / "cleanup").iterdir() if p.name.startswith(".tmp")]


def test_failed_export_discards_partial_output_and_keeps_originals(stage5_job, monkeypatch) -> None:
    settings, repository, run_dir, originals = stage5_job
    real_export = trimesh.Trimesh.export

    def failing_export(self, file_obj=None, file_type=None, **kwargs):
        if file_type == "glb":
            raise OSError("disk full")
        return real_export(self, file_obj, file_type=file_type, **kwargs)

    monkeypatch.setattr(trimesh.Trimesh, "export", failing_export)
    engine = TrimeshMeshCleanupEngine(settings=settings, repository=repository)
    result = engine.clean(repository.get(JOB_ID))

    assert result.success is False and "disk full" in result.message
    assert list((run_dir / "cleanup").iterdir()) == []  # no partial or temp output left
    assert {p.name: _sha(p) for p in run_dir.iterdir() if p.is_file()} == originals


def test_missing_or_unsafe_source_is_rejected(stage5_job) -> None:
    settings, repository, run_dir, _ = stage5_job
    engine = TrimeshMeshCleanupEngine(settings=settings, repository=repository)
    job = repository.get(JOB_ID)
    for mesh_path in (None, "meshes/../../../outside/mesh.glb", "meshes/nope/mesh.glb"):
        job.mesh_path = mesh_path
        result = engine.validate(job)
        assert result.success is False and result.error_code == "SOURCE_MESH_MISSING"


def test_service_records_success_and_failure_in_metadata(stage5_job) -> None:
    settings, repository, run_dir, _ = stage5_job
    service = MeshCleanupService(
        repository, TrimeshMeshCleanupEngine(settings=settings, repository=repository)
    )
    summary = asyncio.run(service.clean(JOB_ID))
    stored = repository.get(JOB_ID).mesh_cleanup
    assert stored["status"] == "succeeded" and stored["cleanup_id"] == summary["cleanup_id"]
    assert stored["source"]["dir"] == f"meshes/{RUN}"
    assert stored["output"]["files"]["glb"]["path"].endswith("/mesh.glb")

    first_dir = repository.jobs_root / JOB_ID / stored["output"]["dir"]
    first_files = {p.name: _sha(p) for p in first_dir.iterdir()}

    (run_dir / "mesh.ply").write_bytes(b"")  # source becomes unusable
    with pytest.raises(ServiceCleanupError):
        asyncio.run(service.clean(JOB_ID))
    failed = repository.get(JOB_ID).mesh_cleanup
    assert failed["status"] == "failed" and failed["error"]
    # The previous successful cleanup is still referenced and its files are untouched.
    assert failed["previous_success"]["cleanup_id"] == summary["cleanup_id"]
    assert {p.name: _sha(p) for p in first_dir.iterdir()} == first_files
    assert [p.name for p in (run_dir / "cleanup").iterdir()] == [first_dir.name]

    # A second failure keeps pointing at the last success.
    with pytest.raises(ServiceCleanupError):
        asyncio.run(service.clean(JOB_ID))
    assert repository.get(JOB_ID).mesh_cleanup["previous_success"]["cleanup_id"] == summary["cleanup_id"]
