export type JobStatus =
  "waiting" | "queued" | "running" | "completed" | "failed" | "paused" | "cancelled";

export type PipelineStepStatus =
  "waiting" | "queued" | "running" | "completed" | "failed" | "cancelled";

export type EngineId = "Instant-NGP";

export type BackendConnectionStatus = "connected" | "connecting" | "disconnected" | "error";

export type LogLevel = "info" | "warn" | "error" | "ok";

export interface LogEntry {
  time: string;
  level: LogLevel;
  msg: string;
  /** "job" lines come from the backend pipeline log; "ui" lines from dashboard actions. */
  source?: "job" | "ui";
  jobId?: string;
  seq?: number;
  stageId?: number | null;
}

export type PipelineExecutionStatus = "idle" | "running" | "paused" | "cancelled";

export interface PipelineExecution {
  status: PipelineExecutionStatus;
  currentStageId: number | null;
  lastError: string | null;
}

/** State of the dashboard's live pipeline log polling. */
export interface LogStreamState {
  status: "no-job" | "loading" | "live" | "idle" | "disconnected" | "error";
  jobId: string | null;
  error: string | null;
  /** Older entries were dropped from the backend memory buffer (full history is on disk). */
  truncated: boolean;
}

export interface MeshInfo {
  url?: string;
  format?: string;
  vertices?: number;
  faces?: number;
  size?: string;
  boundingBox?: string;
}

export interface Metric {
  label: string;
  value: string;
  hint?: string;
  tone?: "bronze" | "success" | "warning" | "default";
}

/** Stage 4 training measurements; null fields were not recorded for this job. */
export interface TrainingMetrics {
  finalLoss: number | null;
  lastLoggedStep: number | null;
  totalSteps: number | null;
  meanStepsPerSecond: number | null;
  checkpointCount: number | null;
  peakVramMib: number | null;
  /** "pipeline": recorded while training; "training_log": read back from an older log. */
  source: string | null;
}

export interface JobOutputs {
  mesh: boolean;
  cleanedMesh: boolean;
  exports: Record<string, string[]>;
}

export interface Job {
  id: string;
  name: string;
  engine: EngineId;
  jobType?: string;
  /** Backend-derived lifecycle status (authoritative). */
  status: JobStatus;
  progress: number;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  trainingDurationSeconds?: number | null;
  pipelineDurationSeconds?: number | null;
  trainingMetrics?: TrainingMetrics | null;
  /** Failing stage and persisted error message, when the job stopped on an error. */
  failedStage?: { id: number; name: string } | null;
  lastError?: string | null;
  psnrDb?: number | null;
  jobOutputs?: JobOutputs;
  /** Formatted training duration, shown in job tables. */
  duration?: string;
  imageCount?: number;
  uploadedAt?: string | null;
  imageFilenames?: string[];
  /** Job-relative Stage 5 GLB path, when a mesh has been generated. */
  meshPath?: string | null;
  /** Stage 6 outcome: "succeeded" | "failed" | null when cleanup has not run. */
  meshCleanupStatus?: string | null;
  vertexCount?: number;
  triangleCount?: number;
  images?: number;
  owner?: string;
  logs: LogEntry[];
  outputs: MeshInfo[];
  metrics: Metric[];
  previewMesh?: MeshInfo;
}

export interface PipelineStep {
  id: number;
  name: string;
  status: PipelineStepStatus;
  progress: number;
  duration: string;
  logs: LogEntry[];
}

export interface HardwareInfo {
  status: string;
  gpu: string;
  driver: string;
  cuda: string;
  memory: string;
  temperature: string;
}

export type ComponentStatus = "ready" | "missing" | "compiling" | "unavailable" | "disconnected";

export interface EngineStatusInfo {
  installed: boolean;
  compiled?: boolean;
  python_bindings?: boolean;
  ready?: boolean;
  python_version_match?: boolean;
  message?: string | null;
  errors?: string[];
}

export interface SystemEnginesResponse {
  workspace: { found: boolean; ready?: boolean };
  instant_ngp: EngineStatusInfo;
  backend: { ready: boolean };
}

export interface SystemHealthSummary {
  workspace: ComponentStatus;
  instantNgp: ComponentStatus;
  backend: ComponentStatus;
}

export interface BackendHealth {
  status: BackendConnectionStatus;
  url: string;
  lastHeartbeat: string | null;
  apiVersion: string | null;
  endpoints: string[];
  system?: SystemHealthSummary;
}

export type ViewerDisplayState = "empty" | "loading" | "loaded" | "error";

export type ViewerImageSource = "model" | "original" | "masked";

export interface ViewerState {
  selectedJobId: string | null;
  wireframe: boolean;
  showStats: boolean;
  displayState: ViewerDisplayState;
  imageSource: ViewerImageSource;
}

export interface TerminalState {
  lines: LogEntry[];
  autoScroll: boolean;
  searchQuery: string;
  open: boolean;
  height: number;
}

export interface AppSettings {
  defaultEngine: EngineId;
  meshQuality: number;
  backgroundRemoval: boolean;
  autoCameraEstimation: boolean;
  meshCleanup: boolean;
  exportFormat: string;
  precision: string;
  rayBatchSize: number;
  terminalOnLaunch: boolean;
  denseTables: boolean;
  backendUrl: string;
}

export type UploadStatus = "idle" | "uploading" | "success" | "error";

export interface UploadState {
  status: UploadStatus;
  progress: number;
  error: string | null;
}
