import { create } from "zustand";
import { DEFAULT_BACKEND_URL } from "@/lib/constants";
import { INITIAL_BACKEND_HEALTH } from "@/lib/initialState/health";
import { INITIAL_HARDWARE } from "@/lib/initialState/hardware";
import { applyDeletedJobs } from "@/lib/jobTable";
import { createInitialPipeline } from "@/lib/pipeline";
import { logStreamChanged } from "@/lib/terminalLog";
import type {
  AppSettings,
  BackendConnectionStatus,
  BackendHealth,
  EngineId,
  HardwareInfo,
  Job,
  LogEntry,
  LogStreamState,
  PipelineExecution,
  PipelineStep,
  TerminalState,
  UploadState,
  ViewerState,
} from "@/types";

interface AppStore {
  // Backend
  backendHealth: BackendHealth;
  setBackendStatus: (status: BackendConnectionStatus) => void;
  setBackendHealth: (health: Partial<BackendHealth>) => void;

  // Engine
  selectedEngine: EngineId;
  setSelectedEngine: (engine: EngineId) => void;

  // Jobs
  jobs: Job[];
  currentJob: Job | null;
  setJobs: (jobs: Job[]) => void;
  setCurrentJob: (job: Job | null) => void;
  addJob: (job: Job) => void;
  /** Remove deleted jobs from every view (list, active job, viewer selection). */
  removeJobs: (ids: string[]) => { currentJobChanged: boolean };

  // Pipeline
  pipeline: PipelineStep[];
  setPipeline: (steps: PipelineStep[]) => void;
  resetPipeline: () => void;
  pipelineExecution: PipelineExecution | null;
  setPipelineExecution: (execution: PipelineExecution | null) => void;
  /** True while this tab awaits a blocking pipeline run request; speeds up log polling. */
  pipelineRequestActive: boolean;
  setPipelineRequestActive: (active: boolean) => void;

  // Hardware
  hardware: HardwareInfo;
  setHardware: (hardware: HardwareInfo) => void;

  // Viewer
  viewer: ViewerState;
  setViewer: (viewer: Partial<ViewerState>) => void;

  // Terminal
  terminal: TerminalState;
  setTerminal: (terminal: Partial<TerminalState>) => void;
  appendTerminalLine: (line: LogEntry) => void;
  appendTerminalLines: (lines: LogEntry[]) => void;
  /** Drop job-scoped lines (backend log + per-job action lines) when switching jobs. */
  removeJobTerminalLines: () => void;
  /** Clears the displayed lines only; the job's persisted log history is untouched. */
  clearTerminal: () => void;
  logStream: LogStreamState;
  setLogStream: (stream: Partial<LogStreamState>) => void;

  // Upload
  upload: UploadState;
  setUpload: (upload: Partial<UploadState>) => void;
  resetUpload: () => void;

  // Settings
  settings: AppSettings;
  setSettings: (settings: Partial<AppSettings>) => void;
}

/** Upper bound on terminal lines kept in the browser; the oldest are dropped first. */
export const MAX_TERMINAL_LINES = 5000;

function boundLines(lines: LogEntry[]): LogEntry[] {
  return lines.length > MAX_TERMINAL_LINES ? lines.slice(lines.length - MAX_TERMINAL_LINES) : lines;
}

export const DEFAULT_SETTINGS: AppSettings = {
  defaultEngine: "Instant-NGP",
  terminalOnLaunch: true,
  denseTables: false,
  backendUrl: DEFAULT_BACKEND_URL,
};

export const useAppStore = create<AppStore>((set, get) => ({
  backendHealth: INITIAL_BACKEND_HEALTH,
  setBackendStatus: (status) => set((s) => ({ backendHealth: { ...s.backendHealth, status } })),
  setBackendHealth: (health) => set((s) => ({ backendHealth: { ...s.backendHealth, ...health } })),

  selectedEngine: "Instant-NGP",
  setSelectedEngine: (engine) => set({ selectedEngine: engine }),

  jobs: [],
  currentJob: null,
  setJobs: (jobs) => set({ jobs }),
  setCurrentJob: (job) => set({ currentJob: job }),
  addJob: (job) => set((s) => ({ jobs: [job, ...s.jobs], currentJob: job })),
  removeJobs: (ids) => {
    const s = get();
    const next = applyDeletedJobs(
      { jobs: s.jobs, currentJob: s.currentJob, viewerJobId: s.viewer.selectedJobId },
      ids,
    );
    const currentJobChanged = next.currentJob?.id !== s.currentJob?.id;
    set({
      jobs: next.jobs,
      currentJob: next.currentJob,
      viewer: { ...s.viewer, selectedJobId: next.viewerJobId },
      ...(currentJobChanged
        ? {
            pipeline: createInitialPipeline(),
            pipelineExecution: null,
            logStream: { status: "no-job", jobId: null, error: null, truncated: false },
          }
        : {}),
    });
    return { currentJobChanged };
  },

  pipeline: createInitialPipeline(),
  setPipeline: (pipeline) => set({ pipeline }),
  resetPipeline: () => set({ pipeline: createInitialPipeline() }),
  pipelineExecution: null,
  // Polling calls these every tick; skip no-op updates so subscribers don't re-render.
  setPipelineExecution: (pipelineExecution) =>
    set((s) =>
      s.pipelineExecution?.status === pipelineExecution?.status &&
      s.pipelineExecution?.currentStageId === pipelineExecution?.currentStageId &&
      s.pipelineExecution?.lastError === pipelineExecution?.lastError
        ? s
        : { pipelineExecution },
    ),
  pipelineRequestActive: false,
  setPipelineRequestActive: (pipelineRequestActive) => set({ pipelineRequestActive }),

  upload: {
    status: "idle",
    progress: 0,
    error: null,
  },
  setUpload: (upload) => set((s) => ({ upload: { ...s.upload, ...upload } })),
  resetUpload: () => set({ upload: { status: "idle", progress: 0, error: null } }),

  hardware: INITIAL_HARDWARE,
  setHardware: (hardware) => set({ hardware }),

  viewer: {
    selectedJobId: null,
    wireframe: false,
    showStats: false,
    displayState: "empty",
    imageSource: "model",
  },
  setViewer: (viewer) => set((s) => ({ viewer: { ...s.viewer, ...viewer } })),

  terminal: {
    lines: [],
    autoScroll: true,
    searchQuery: "",
    open: true,
    height: 220,
  },
  setTerminal: (terminal) => set((s) => ({ terminal: { ...s.terminal, ...terminal } })),
  appendTerminalLine: (line) =>
    set((s) =>
      // A job-scoped message for a job that is no longer displayed (e.g. a long run request
      // finishing after the user switched jobs) would mix jobs; that job's log keeps the record.
      line.jobId && line.jobId !== s.currentJob?.id
        ? s
        : {
            terminal: {
              ...s.terminal,
              lines: boundLines([...s.terminal.lines, { source: "ui", ...line }]),
            },
          },
    ),
  appendTerminalLines: (lines) =>
    set((s) =>
      lines.length === 0
        ? s
        : { terminal: { ...s.terminal, lines: boundLines([...s.terminal.lines, ...lines]) } },
    ),
  removeJobTerminalLines: () =>
    set((s) => ({
      terminal: {
        ...s.terminal,
        lines: s.terminal.lines.filter((l) => l.source !== "job" && !l.jobId),
      },
    })),
  clearTerminal: () => set((s) => ({ terminal: { ...s.terminal, lines: [] } })),
  logStream: { status: "no-job", jobId: null, error: null, truncated: false },
  setLogStream: (stream) =>
    set((s) =>
      logStreamChanged(s.logStream, stream) ? { logStream: { ...s.logStream, ...stream } } : s,
    ),

  settings: DEFAULT_SETTINGS,
  setSettings: (settings) =>
    set((s) => {
      const next = { ...s.settings, ...settings };
      const backendHealth =
        settings.backendUrl !== undefined
          ? { ...s.backendHealth, url: settings.backendUrl }
          : s.backendHealth;
      if (settings.backendUrl === undefined || settings.backendUrl === s.settings.backendUrl) {
        return { settings: next, backendHealth };
      }
      // Jobs belong to the previous backend: drop them so nothing requests them from the new
      // URL (404s); useJobsSync reloads the job list once the new backend is reachable.
      return {
        settings: next,
        backendHealth,
        jobs: [],
        currentJob: null,
        pipeline: createInitialPipeline(),
        pipelineExecution: null,
      };
    }),
}));
