# NeuralCanvas Backend

FastAPI backend for the NeuralCanvas 3D reconstruction platform.

## Requirements

- Python 3.11+
- pip
- COLMAP (for camera estimation)
- Built Instant-NGP at `engines/instant-ngp/`

## Installation

From the repository root:

```bash
cd website/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Build Instant-NGP (once) in `engines/instant-ngp/` following upstream instructions, then ensure `build/pyngp*.so` exists.

## Configuration

Copy `.env.example` to `.env`. All filesystem roots are **relative to the workspace root** (the directory containing `website/` and `engines/`):

| Variable | Default | Description |
|----------|---------|-------------|
| `JOBS_ROOT` | `jobs` | Job workspace directory |
| `ENGINES_ROOT` | `engines` | Engine implementations root |
| `INSTANT_NGP_ROOT` | `engines/instant-ngp` | Local Instant-NGP checkout |
| `INSTANT_NGP_PYTHON` | `python3` | Python interpreter for Instant-NGP (must match pyngp build) |
| `INSTANT_NGP_N_STEPS` | `35000` | Training steps |
| `MESH_RESOLUTION` | `256` | Marching cubes resolution |
| `MESH_DENSITY_THRESHOLD` | `2.5` | Marching cubes density threshold |

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Startup validation

On startup the backend logs:

```
Workspace:
✓ Found
Instant-NGP:
✓ Installed
Build:
✓ Found
Python Bindings:
✓ Found
Backend:
Ready
```

Validation does not crash the server. If Instant-NGP is missing or `INSTANT_NGP_PYTHON` does not match the compiled pyngp module, reconstruction returns structured errors (`INSTANT_NGP_UNAVAILABLE`, `PYTHON_VERSION_MISMATCH`).

Query runtime status via `GET /api/system/engines`.

## Architecture

```
PipelineManager
    └── ReconstructionStage / MeshGenerationStage
            └── ReconstructionService / MeshGenerationService
                    └── InstantNGPReconstructionEngine / InstantNGPMeshGenerationEngine
                            └── InstantNGPLauncher  (only module that runs Instant-NGP subprocesses)
```

Path resolution starts at `get_workspace_root()` in `app/core/paths.py`.

## Job layout

Each job lives under `jobs/job_<id>/`:

```
job_<id>/
├── uploaded_images/
├── masked_images/
├── camera/
├── instant_ngp/
│   └── snapshot.msgpack
├── meshes/
│   └── <run_id>/
│       ├── mesh.obj
│       ├── mesh.ply
│       └── mesh.glb
├── metadata.json
└── pipeline.json
```

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/api/system/engines` | Engine installation status |
| POST | `/api/jobs` | Create job |
| POST | `/api/jobs/{id}/upload` | Upload images |
| GET | `/api/jobs/{id}/pipeline` | Pipeline state |
| POST | `/api/jobs/{id}/pipeline/start` | Run pipeline |
| GET | `/api/jobs/{id}/mesh` | Stream mesh GLB (404 if missing) |

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Frontend integration

The frontend polls `GET /health` and `GET /api/system/engines` to populate the system status widget.

Set `VITE_BACKEND_URL=http://localhost:8000` in the frontend environment.
