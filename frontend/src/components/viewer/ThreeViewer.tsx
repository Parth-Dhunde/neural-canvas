import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Environment, Lightformer } from "@react-three/drei";
import { Component, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ComponentRef, ReactNode } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Box, Camera, Maximize2, Download, Activity, Eye, EyeOff, RotateCw } from "lucide-react";
import { useAppStore } from "@/store/useAppStore";
import { useTheme } from "@/hooks/useTheme";
import { buildUrl } from "@/services/api";
import type { ExportManifestApi, MeshVariant } from "@/services/exports";
import type { ExportsStatus } from "@/hooks/useJobExports";
import { selectViewerMesh, viewableVariants } from "@/lib/meshSelection";
import { cn } from "@/lib/utils";

/** Largest model dimension after auto-framing, in scene units. */
const FRAMED_SIZE = 2.6;

type ModelState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; vertices: number; faces: number }
  | { kind: "error"; message: string };

export function ThreeViewer({
  className,
  jobId,
  jobLabel,
  manifest,
  manifestStatus,
  manifestError,
  onRetry,
}: {
  className?: string;
  jobId: string | null;
  jobLabel?: string;
  manifest: ExportManifestApi | null;
  manifestStatus: ExportsStatus;
  manifestError?: string | null;
  onRetry?: () => void;
}) {
  const viewer = useAppStore((s) => s.viewer);
  const setViewer = useAppStore((s) => s.setViewer);
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const { resolved: theme } = useTheme();
  const scene = SCENE_COLORS[theme];

  const [requestedVariant, setRequestedVariant] = useState<MeshVariant | null>(null);
  const [model, setModel] = useState<ModelState>({ kind: "idle" });
  const [modelHeight, setModelHeight] = useState(1);
  const [retryKey, setRetryKey] = useState(0);
  const controlsRef = useRef<ComponentRef<typeof OrbitControls> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => setRequestedVariant(null), [jobId]);

  const mesh = selectViewerMesh(manifest, requestedVariant);
  const variants = viewableVariants(manifest);
  const meshUrl = mesh
    ? `${buildUrl(mesh.url, backendUrl)}?v=${encodeURIComponent(mesh.version)}`
    : null;
  const downloadUrl = mesh ? buildUrl(mesh.url, backendUrl) : null;

  // Load outside React rendering: a failed load is handled here and never thrown into the R3F
  // tree. (R3F creates its root with reportError as onCaughtError, so an error caught by an
  // error boundary inside <Canvas> is still logged to the console as "Uncaught".)
  const [loaded, setLoaded] = useState<{ url: string; scene: THREE.Group } | null>(null);
  useEffect(() => {
    if (!meshUrl) {
      setModel({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setModel({ kind: "loading" });
    new GLTFLoader()
      .loadAsync(meshUrl)
      .then((gltf) => {
        if (cancelled) {
          disposeObject(gltf.scene);
          return;
        }
        setLoaded((previous) => {
          if (previous) disposeObject(previous.scene);
          return { url: meshUrl, scene: gltf.scene };
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : String(error);
        setModel({ kind: "error", message: `Failed to load mesh: ${message}` });
      });
    return () => {
      cancelled = true;
    };
  }, [meshUrl, retryKey]);
  // Free GPU buffers of the last mesh when the viewer unmounts.
  const loadedRef = useRef(loaded);
  loadedRef.current = loaded;
  useEffect(
    () => () => {
      if (loadedRef.current) disposeObject(loadedRef.current.scene);
    },
    [],
  );
  const readyScene = loaded && loaded.url === meshUrl ? loaded.scene : null;

  // Keep the shared viewer state in sync for other UI that reads it.
  const displayState: "empty" | "loading" | "loaded" | "error" =
    manifestStatus === "error" || model.kind === "error"
      ? "error"
      : manifestStatus === "loading" || model.kind === "loading"
        ? "loading"
        : model.kind === "loaded"
          ? "loaded"
          : "empty";
  useEffect(() => {
    if (viewer.displayState !== displayState) setViewer({ displayState });
  }, [displayState, setViewer, viewer.displayState]);

  const label = jobId ? (jobLabel ?? jobId) : "No model loaded";

  return (
    <div
      ref={containerRef}
      className={cn("relative flex h-full w-full flex-col overflow-hidden bg-viewport", className)}
    >
      <div className="hairline-b absolute inset-x-0 top-0 z-10 flex h-9 items-center gap-1.5 bg-background/70 px-2 backdrop-blur">
        <ViewerBtn
          icon={Box}
          active={viewer.wireframe}
          onClick={() => setViewer({ wireframe: !viewer.wireframe })}
          label="Wire"
        />
        <ViewerBtn
          icon={Camera}
          label="Reset"
          onClick={() => controlsRef.current?.reset()}
          disabled={model.kind !== "loaded"}
        />
        <ViewerBtn
          icon={Activity}
          active={viewer.showStats}
          onClick={() => setViewer({ showStats: !viewer.showStats })}
          label="Stats"
        />
        <ViewerBtn
          icon={Maximize2}
          label="Full"
          onClick={() => void containerRef.current?.requestFullscreen?.().catch(() => {})}
        />
        <div className="flex-1" />
        <div className="mono truncate text-[10px] uppercase tracking-widest text-subtle">
          {label}
        </div>
        {variants.length > 1 && mesh && (
          <div
            role="radiogroup"
            aria-label="Mesh version"
            className="ml-2 flex items-center gap-0.5 rounded-sm border border-border bg-surface-2 p-0.5"
          >
            {variants.map((variant) => (
              <button
                key={variant}
                role="radio"
                aria-checked={mesh.variant === variant}
                onClick={() => setRequestedVariant(variant)}
                className={cn(
                  "mono rounded-sm px-1.5 py-0.5 text-[10px] uppercase tracking-widest transition-colors",
                  mesh.variant === variant
                    ? "bg-selected/15 text-selected"
                    : "text-muted-foreground hover:text-ivory",
                )}
              >
                {variant}
              </button>
            ))}
          </div>
        )}
        {variants.length === 1 && mesh && (
          <span className="mono ml-2 rounded-sm border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
            {mesh.variant}
          </span>
        )}
        <div className="flex-1" />
        {downloadUrl ? (
          <a
            href={downloadUrl}
            download
            className="flex h-6 items-center gap-1.5 rounded-sm border border-border px-2 text-[10px] uppercase tracking-widest text-muted-foreground hover:border-border-strong hover:text-ivory"
          >
            <Download className="h-3 w-3" strokeWidth={1.6} />
            Export
          </a>
        ) : (
          <ViewerBtn icon={Download} label="Export" disabled />
        )}
      </div>

      <div className="absolute left-3 top-12 z-10">
        <div className="label-caps">Perspective · 35 mm</div>
      </div>

      {viewer.showStats && model.kind === "loaded" && (
        <div className="mono absolute right-3 top-12 z-10 rounded-sm border border-border bg-background/70 p-2.5 text-[10px] backdrop-blur">
          <div className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-muted-foreground">
            <span>mesh</span>
            <span className="text-ivory">{mesh?.variant}</span>
            <span>vertices</span>
            <span className="text-ivory">{model.vertices.toLocaleString()}</span>
            <span>faces</span>
            <span className="text-ivory">{model.faces.toLocaleString()}</span>
          </div>
        </div>
      )}

      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-1.5 rounded-sm border border-border bg-background/70 px-2 py-1 backdrop-blur">
        <span className="mono text-[10px] text-destructive">X</span>
        <span className="mono text-[10px] text-success">Y</span>
        <span className="mono text-[10px] text-info">Z</span>
      </div>

      <div className="relative h-full w-full">
        {meshUrl && (
          <Canvas
            camera={{ position: [3.6, 2.4, 3.6], fov: 35, near: 0.05, far: 200 }}
            gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
            dpr={[1, 2]}
            data-testid="mesh-canvas"
          >
            {/* Keyed by theme: R3F builds these from constructor args, which do not update in place. */}
            <color key={`bg-${theme}`} attach="background" args={[scene.background]} />
            <fog key={`fog-${theme}`} attach="fog" args={[scene.background, 9, 24]} />
            <ambientLight intensity={0.35} />
            <directionalLight position={[5, 8, 4]} intensity={1.4} color={scene.key} />
            <directionalLight position={[-5, 4, -4]} intensity={0.5} color={scene.rim} />
            {/* Local studio environment: rendered in-scene, no network fetch (the former
                preset loaded an HDR from a CDN and blocked the whole scene until it arrived). */}
            <Environment resolution={64} frames={1}>
              <Lightformer intensity={1.6} position={[0, 5, -5]} scale={[10, 5, 1]} />
              <Lightformer
                intensity={0.8}
                position={[-5, 1, 2]}
                rotation-y={Math.PI / 2}
                scale={[10, 2, 1]}
              />
              <Lightformer
                intensity={0.8}
                position={[5, 1, 2]}
                rotation-y={-Math.PI / 2}
                scale={[10, 2, 1]}
              />
            </Environment>
            <Grid
              args={[30, 30]}
              cellSize={0.3}
              cellThickness={0.5}
              cellColor={scene.cell}
              sectionSize={1.5}
              sectionThickness={0.8}
              sectionColor={scene.section}
              fadeDistance={18}
              fadeStrength={1}
              infiniteGrid
              position={[0, 0, 0]}
            />
            {/* Grid and lights render immediately; the model appears once loaded. The boundary only
                guards against render-time errors (load errors are handled in the effect above). */}
            {readyScene && (
              <ModelErrorBoundary
                key={`${meshUrl}-${retryKey}`}
                onError={(message) => setModel({ kind: "error", message })}
              >
                <GLBModel
                  scene={readyScene}
                  wireframe={viewer.wireframe}
                  onFramed={(info) => {
                    setModelHeight(info.height);
                    setModel({ kind: "loaded", vertices: info.vertices, faces: info.faces });
                  }}
                />
              </ModelErrorBoundary>
            )}
            <OrbitControls
              ref={controlsRef}
              target={[0, modelHeight / 2, 0]}
              enableDamping
              dampingFactor={0.08}
              minDistance={1.2}
              maxDistance={14}
            />
          </Canvas>
        )}

        {manifestStatus === "loading" || (model.kind === "loading" && meshUrl) ? (
          <Overlay>
            <LoadingState
              label={manifestStatus === "loading" ? "Checking mesh exports…" : "Loading mesh…"}
            />
          </Overlay>
        ) : null}
        {manifestStatus === "error" && (
          <Overlay>
            <ErrorState
              message={manifestError ?? "Could not load mesh exports."}
              onRetry={onRetry}
            />
          </Overlay>
        )}
        {model.kind === "error" && (
          <Overlay>
            <ErrorState message={model.message} onRetry={() => setRetryKey((n) => n + 1)} />
          </Overlay>
        )}
        {manifestStatus !== "loading" && manifestStatus !== "error" && !meshUrl && (
          <EmptyState hasJob={Boolean(jobId)} />
        )}
      </div>
    </div>
  );
}

/** Three.js scene colors per theme (WebGL cannot read CSS tokens directly). */
const SCENE_COLORS = {
  dark: {
    // Matches the dark theme's --viewport (blue-tinted graphite).
    background: "#0c0f14",
    key: "#f4ece0",
    rim: "#c8875a",
    cell: "#252a32",
    section: "#3a414c",
  },
  light: {
    background: "#ebe4d8",
    key: "#fffaf2",
    rim: "#a8653c",
    cell: "#d4c9b8",
    section: "#ab9d89",
  },
} as const;

function GLBModel({
  scene,
  wireframe,
  onFramed,
}: {
  scene: THREE.Group;
  wireframe: boolean;
  onFramed: (info: { height: number; vertices: number; faces: number }) => void;
}) {
  const gltf = { scene };
  const onFramedRef = useRef(onFramed);
  onFramedRef.current = onFramed;

  // Fit the model to the view: Stage 5 meshes use reconstruction-space units, so without this
  // the camera can end up inside the geometry. Center on X/Z and rest the model on the grid.
  useLayoutEffect(() => {
    const root = gltf.scene;
    root.position.set(0, 0, 0);
    root.scale.setScalar(1);
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = Number.isFinite(maxDim) && maxDim > 0 ? FRAMED_SIZE / maxDim : 1;
    const center = box.getCenter(new THREE.Vector3());
    root.scale.setScalar(scale);
    root.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);

    let vertices = 0;
    let faces = 0;
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const position = mesh.geometry.getAttribute("position");
      vertices += position?.count ?? 0;
      faces += mesh.geometry.index ? mesh.geometry.index.count / 3 : (position?.count ?? 0) / 3;
    });
    onFramedRef.current({ height: size.y * scale, vertices, faces });
  }, [gltf.scene]);

  useEffect(() => {
    gltf.scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const material = mesh.material as THREE.Material | THREE.Material[];
      const apply = (m: THREE.Material) => {
        if ("wireframe" in m) (m as THREE.MeshStandardMaterial).wireframe = wireframe;
      };
      if (Array.isArray(material)) material.forEach(apply);
      else apply(material);
    });
  }, [gltf.scene, wireframe]);

  return <primitive object={gltf.scene} />;
}

/** Release GPU buffers and textures held by a loaded glTF scene. */
function disposeObject(root: THREE.Object3D) {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry?.dispose();
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      if (!material) continue;
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) value.dispose();
      }
      material.dispose();
    }
  });
}

class ModelErrorBoundary extends Component<
  { children: ReactNode; onError: (message: string) => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    this.props.onError(`Failed to load mesh: ${message}`);
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function Overlay({ children }: { children: ReactNode }) {
  return <div className="absolute inset-0 z-[5] bg-viewport/70">{children}</div>;
}

function ViewerBtn({
  icon: Icon,
  label,
  active,
  onClick,
  disabled,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  active?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex h-6 items-center gap-1.5 rounded-sm border px-2 text-[10px] uppercase tracking-widest disabled:pointer-events-none disabled:opacity-45",
        active
          ? "border-selected/55 bg-selected/12 text-selected"
          : "border-border text-muted-foreground hover:border-border-strong hover:text-ivory",
      )}
    >
      <Icon className="h-3 w-3" strokeWidth={1.6} />
      {label}
    </button>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="grid h-full place-items-center">
      <div className="flex flex-col items-center gap-3">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 rounded-full border-2 border-border" />
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-bronze" />
        </div>
        <div className="label-caps">{label}</div>
      </div>
    </div>
  );
}

function EmptyState({ hasJob }: { hasJob: boolean }) {
  return (
    <div className="grid h-full place-items-center">
      <div className="flex flex-col items-center gap-3">
        <div className="grid h-14 w-14 place-items-center rounded-sm border border-dashed border-border-strong">
          <EyeOff className="h-6 w-6 text-subtle" strokeWidth={1.4} />
        </div>
        <div className="label-caps">No model loaded</div>
        <div className="mono max-w-xs text-center text-[11px] text-subtle">
          {hasJob
            ? "This job has no mesh yet. Run the pipeline through Mesh Generation to view it here."
            : "Select a job with a completed reconstruction to preview its mesh."}
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="grid h-full place-items-center">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <div className="grid h-14 w-14 place-items-center rounded-sm border border-destructive/40 bg-destructive/10">
          <Eye className="h-6 w-6 text-destructive" strokeWidth={1.4} />
        </div>
        <div className="label-caps text-destructive">Failed to load mesh</div>
        <div className="mono text-[11px] text-muted-foreground">{message}</div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mono flex h-7 items-center gap-1.5 rounded-sm border border-border px-2.5 text-[11px] uppercase tracking-widest text-muted-foreground hover:border-border-strong hover:text-ivory"
          >
            <RotateCw className="h-3 w-3" strokeWidth={1.6} />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
