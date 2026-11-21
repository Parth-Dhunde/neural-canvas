// Engine catalogue shown in the engine pickers. Runtime-import free (node --test).
import type { EngineId } from "@/types";

/** Engines the UI can show; only "available" ones are accepted by the backend. */
export type EngineOptionId = EngineId | "Text-to-3D";

export interface EngineOption {
  id: EngineOptionId;
  availability: "available" | "wip";
  /** Short explanation shown next to the option. */
  description: string;
}

export const ENGINE_OPTIONS: readonly EngineOption[] = [
  {
    id: "Instant-NGP",
    availability: "available",
    description: "Reconstructs a mesh from photographs using COLMAP and Instant-NGP.",
  },
  {
    id: "Text-to-3D",
    availability: "wip",
    description:
      "Generate a 3D model from a text prompt. Work in progress: not available yet, and no jobs can be submitted with it.",
  },
];

export function engineOption(id: string): EngineOption | undefined {
  return ENGINE_OPTIONS.find((option) => option.id === id);
}

/** True only for engines that a job can actually be created with. */
export function isSubmittableEngine(id: string): id is EngineId {
  return engineOption(id)?.availability === "available";
}
