import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  BookOpen,
  Boxes,
  Camera,
  CheckCircle2,
  Download,
  FolderOpen,
  Gauge,
  Lightbulb,
  ListChecks,
  Sparkles,
  TerminalSquare,
  Wrench,
  XCircle,
} from "lucide-react";
import { PageHeader, Panel } from "@/components/ui-pro/Panel";
import { PIPELINE_STEP_NAMES } from "@/lib/constants";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/guide")({
  component: GuidePage,
  head: () => ({
    meta: [
      { title: "Guide — NeuralCanvas" },
      {
        name: "description",
        content:
          "How to photograph an object, run the seven-stage reconstruction pipeline, read the statistics and export your 3D model.",
      },
    ],
  }),
});

const SECTIONS = [
  { id: "what", label: "What NeuralCanvas does" },
  { id: "nerf", label: "What is a NeRF?" },
  { id: "multiview", label: "How multi-view reconstruction works" },
  { id: "photos", label: "Taking good photos" },
  { id: "upload", label: "Create a job and upload" },
  { id: "stages", label: "The seven pipeline stages" },
  { id: "monitor", label: "Monitoring progress and logs" },
  { id: "stats", label: "Reading the statistics" },
  { id: "viewer", label: "Inspecting the model" },
  { id: "cleanup", label: "Mesh cleanup" },
  { id: "export", label: "Exporting GLB, OBJ and PLY" },
  { id: "troubleshooting", label: "Troubleshooting" },
  { id: "tips", label: "Tips for better results" },
] as const;

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function GuidePage() {
  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Getting started"
        title="How to use NeuralCanvas"
        description="A beginner's walkthrough: from photographing an object to downloading a 3D model. No 3D or machine-learning experience needed."
        actions={
          <Link
            to="/"
            className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-bronze/55 bg-bronze/12 px-3 text-[12px] font-medium uppercase tracking-wider text-bronze transition-colors hover:bg-bronze/20"
          >
            Open the dashboard
          </Link>
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 p-4 sm:p-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <nav aria-label="Guide sections" className="min-w-0 lg:sticky lg:top-4 lg:self-start">
          <div className="label-caps mb-2 hidden lg:block">On this page</div>
          <ol className="flex gap-1.5 overflow-x-auto pb-1 lg:flex-col lg:gap-0.5 lg:overflow-visible">
            {SECTIONS.map((section, index) => (
              <li key={section.id} className="shrink-0">
                <a
                  href={`#${section.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    scrollToSection(section.id);
                  }}
                  className="flex items-center gap-2 rounded-sm border border-border px-2.5 py-1.5 text-[12px] whitespace-nowrap text-muted-foreground lg:whitespace-normal transition-colors hover:bg-surface-2 hover:text-ivory lg:border-transparent"
                >
                  <span className="mono text-[10px] text-subtle">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {section.label}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <article className="min-w-0 space-y-6 text-[13px] leading-relaxed text-foreground">
          <Section id="what" icon={Sparkles} title="What NeuralCanvas does">
            <p>
              NeuralCanvas turns a set of ordinary photographs of an object into a 3D model you can
              rotate, inspect and download. You take photos all the way around something (a shoe, a
              mug, a sculpture), upload them, and the app works out where each photo was taken from,
              learns the object's shape and colour, and builds a 3D mesh from it.
            </p>
            <p>
              Everything runs on your own computer: the photos never leave it, and there are no paid
              services involved. Reconstruction needs an NVIDIA GPU. On the RTX 2050 laptop GPU this
              project was built on, training a 100-photo object took about 21 minutes; camera
              estimation adds a few more minutes on the CPU.
            </p>
            <Callout tone="info" title="One mode today">
              NeuralCanvas currently has one workflow: <strong>photos → 3D model</strong>, using the
              Instant-NGP engine. Generating models from a text description is a possible future
              addition, but it is not available yet.
            </Callout>
          </Section>

          <Section id="nerf" icon={Lightbulb} title="What is a NeRF?">
            <p>
              A <strong>NeRF</strong> (Neural Radiance Field) is a small neural network that learns
              to answer one question:{" "}
              <em>
                “if I look at this point in space from this direction, what colour is it, and is
                anything there?”
              </em>{" "}
              It learns the answer by comparing what it predicts with your photos, thousands of
              times per second, until its predictions match them.
            </p>
            <p>
              Once trained, the NeRF knows where the object is solid. NeuralCanvas then samples that
              solidity on a 3D grid and turns the boundary into a triangle mesh (a{" "}
              <em>marching cubes</em> step), which is what you download. NeuralCanvas uses{" "}
              <strong>Instant-NGP</strong>, an NVIDIA implementation that trains a NeRF in minutes
              rather than hours.
            </p>
          </Section>

          <Section id="multiview" icon={Camera} title="How multi-view reconstruction works">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_260px] md:items-center">
              <div className="space-y-3">
                <p>
                  Every photo shows the object from one viewpoint. On its own, a single photo cannot
                  tell how deep anything is. With many overlapping photos, the same surface details
                  appear in several images from slightly different angles, and that difference
                  reveals depth, exactly like your two eyes do.
                </p>
                <p>
                  That is why the <strong>overlap between neighbouring photos</strong> matters so
                  much: the camera-estimation stage matches details across photos to find where each
                  one was taken. Photos that share nothing with the others cannot be placed.
                </p>
              </div>
              <CameraRingDiagram />
            </div>
          </Section>

          <Section id="photos" icon={Camera} title="Taking good photos">
            <p>
              The quality of the result depends far more on the photos than on any setting. Aim for{" "}
              <strong>24 to 500 sharp photos</strong> (around 60–150 works well for most objects)
              taken in one or two full circles around the object.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <DoList
                title="Do"
                items={[
                  "Walk around the object, taking a photo every few steps so neighbouring photos overlap by well over half.",
                  "Take a second, higher circle looking slightly down, so the top is covered too.",
                  "Keep the whole object in frame and roughly centred.",
                  "Use even, constant lighting; overcast daylight or a bright room is ideal.",
                  "Keep the camera steady and the object perfectly still.",
                  "Use a plain, uncluttered background that contrasts with the object.",
                ]}
              />
              <DontList
                title="Avoid"
                items={[
                  "Blurry photos: motion blur or missed focus confuses camera estimation.",
                  "Changing the lighting, flash, or moving shadows between shots.",
                  "Many near-identical photos from the same spot; they add no new information.",
                  "Gaps: any side no photo sees will be guessed or missing.",
                  "Transparent, mirror-like or very shiny objects; reflections look different from every angle.",
                  "Plain, textureless surfaces with no detail to match (add a patterned mat underneath).",
                ]}
              />
            </div>
            <Callout tone="info" title="File limits">
              JPG, JPEG or PNG; up to 50 MB and 40 megapixels per image. PNGs with transparency are
              accepted. Phone photos at normal resolution are fine.
            </Callout>
          </Section>

          <Section id="upload" icon={FolderOpen} title="Create a job and upload your photos">
            <Steps
              steps={[
                <>
                  Open the{" "}
                  <Link to="/" className="text-bronze underline-offset-2 hover:underline">
                    Dashboard
                  </Link>
                  . A <strong>job</strong> is one reconstruction: its photos, progress and results
                  are kept together.
                </>,
                <>
                  Click <strong>Create New Job</strong>. To come back to earlier work, use the{" "}
                  <strong>Continue existing job</strong> menu, or the play button next to a job on
                  the{" "}
                  <Link to="/jobs" className="text-bronze underline-offset-2 hover:underline">
                    Jobs
                  </Link>{" "}
                  page.
                </>,
                <>
                  Drag your photos (or a whole folder) onto the <strong>Ingest</strong> area, or use{" "}
                  <strong>Browse files</strong> / <strong>Browse folder</strong>. A progress bar
                  shows the upload; thumbnails appear when it finishes.
                </>,
                <>
                  Click <strong>Start Reconstruction</strong> (or{" "}
                  <strong>Run remaining stages</strong> on the Pipeline panel). The stages then run
                  one after another without further input.
                </>,
              ]}
            />
            <Screenshot name="ingest" alt="The Ingest panel with uploaded thumbnails" />
          </Section>

          <Section id="stages" icon={ListChecks} title="The seven pipeline stages">
            <PipelineDiagram />
            <ol className="mt-4 grid gap-3 md:grid-cols-2">
              {STAGE_DETAILS.map((stage, index) => (
                <li key={stage.title} className="nc-tile rounded-sm border border-border p-3">
                  <div className="flex items-baseline gap-2">
                    <span className="mono text-[11px] text-bronze">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-[13px] font-medium text-ivory">{stage.title}</span>
                  </div>
                  <p className="mt-1.5 text-[12px] text-muted-foreground">{stage.body}</p>
                </li>
              ))}
            </ol>
          </Section>

          <Section id="monitor" icon={TerminalSquare} title="Monitoring progress and logs">
            <ul className="list-disc space-y-1.5 pl-5">
              <li>
                The <strong>Pipeline</strong> panel shows each stage with a progress bar and a
                status badge. Click a stage row to see the log lines from that stage.
              </li>
              <li>
                The top bar shows the active job and which stage is running (for example{" "}
                <span className="mono">Step 4 / 7 · Reconstruction</span>).
              </li>
              <li>
                The <strong>Terminal</strong> at the bottom streams every log line live. You can
                search it, copy it, clear the display (the saved history is kept) and jump to the
                newest line. Training prints a line every 5% with the current loss.
              </li>
              <li>
                A job's status is one of: <Badge>Waiting</Badge> (not finished, nothing running),{" "}
                <Badge>Running</Badge>, <Badge>Completed</Badge> (all seven stages done) or{" "}
                <Badge tone="destructive">Failed</Badge> (a stage stopped with an error; hover the
                job to see it). These come from the saved pipeline state, so they stay correct after
                a restart.
              </li>
            </ul>
            <Callout tone="warning" title="Keep the backend running">
              A run executes inside the backend process. Stopping or restarting the backend during a
              run interrupts it; the job then shows <strong>Waiting</strong> and you can start it
              again from the interrupted stage.
            </Callout>
            <Screenshot name="pipeline" alt="Pipeline panel with seven completed stages" />
          </Section>

          <Section id="stats" icon={Gauge} title="Reading the hardware and training statistics">
            <dl className="grid gap-3 md:grid-cols-2">
              {STAT_DETAILS.map((stat) => (
                <div key={stat.term} className="nc-tile rounded-sm border border-border p-3">
                  <dt className="label-caps">{stat.term}</dt>
                  <dd className="mt-1 text-[12px] text-muted-foreground">{stat.body}</dd>
                </div>
              ))}
            </dl>
            <Callout tone="info" title="“Not recorded” and “Not evaluated”">
              NeuralCanvas never fills a card with a guess. <strong>Not recorded</strong> means the
              value was not captured for that run (for example peak VRAM for runs made before VRAM
              recording existed). <strong>Not evaluated</strong> means the measurement is not part
              of the pipeline at all (PSNR). A real zero is shown as 0.
            </Callout>
            <Screenshot name="snapshot" alt="Pipeline Snapshot card with training statistics" />
          </Section>

          <Section id="viewer" icon={Boxes} title="Inspecting the model in the viewer">
            <Steps
              steps={[
                <>
                  Open{" "}
                  <Link to="/viewer" className="text-bronze underline-offset-2 hover:underline">
                    Viewer
                  </Link>{" "}
                  and pick a job from the list on the left.
                </>,
                <>
                  <strong>3D Model</strong> shows the mesh: drag to orbit, scroll to zoom,
                  right-drag to pan. <strong>Wire</strong> shows the triangles,{" "}
                  <strong>Stats</strong> the vertex and face counts, <strong>Reset</strong>{" "}
                  re-centres the camera and <strong>Full</strong> goes full screen.
                </>,
                <>
                  Switch between <strong>Cleaned</strong> (after Stage 6) and{" "}
                  <strong>Original</strong> (straight from Stage 5) to compare them.
                </>,
                <>
                  <strong>Original Images</strong> and <strong>Masked Images</strong> show your
                  photos before and after background removal. That is the quickest way to spot a
                  photo where part of the object was cut away.
                </>,
              ]}
            />
            <Screenshot
              name="viewer"
              alt="Viewer showing a mesh, the inspector and export buttons"
            />
          </Section>

          <Section id="cleanup" icon={Wrench} title="Mesh cleanup">
            <p>
              Cleanup is automatic: Stage 6 runs on every reconstruction. It repairs broken
              triangles, deletes tiny floating pieces (fewer than 12 faces by default), smooths the
              surface slightly (Taubin smoothing, which avoids shrinking) and reduces very dense
              meshes. The original Stage 5 mesh is always kept untouched next to the cleaned one.
            </p>
            <p>
              The cleanup settings live in the backend configuration file (
              <span className="mono">backend/.env</span>, the{" "}
              <span className="mono">MESH_CLEANUP_*</span> values); they are not adjustable from the
              web interface yet. To re-run cleanup after changing them, see the README section
              “Using the application”.
            </p>
          </Section>

          <Section id="export" icon={Download} title="Exporting GLB, OBJ and PLY">
            <p>
              When Stage 7 finishes, the Viewer's <strong>Export</strong> panel offers the cleaned
              mesh as <strong>GLB</strong>, <strong>OBJ</strong> and <strong>PLY</strong>, with the
              original mesh in the same formats underneath. The{" "}
              <Link to="/history" className="text-bronze underline-offset-2 hover:underline">
                History
              </Link>{" "}
              page lists every finished job and its exports.
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <FormatCard
                name="GLB"
                body="Best for most uses: web viewers, Blender, game engines. One file with colours."
              />
              <FormatCard
                name="OBJ"
                body="Widely supported by 3D tools. Colours are stored per vertex, which some tools ignore."
              />
              <FormatCard
                name="PLY"
                body="Common in 3D scanning and point-cloud tools. Keeps vertex colours."
              />
            </div>
            <p className="text-[12px] text-muted-foreground">
              Models are coloured per vertex rather than with image textures. FBX, USDZ and STL
              buttons are shown for the future but are not available.
            </p>
          </Section>

          <Section
            id="troubleshooting"
            icon={AlertTriangle}
            title="Common errors and troubleshooting"
          >
            <div className="space-y-2">
              {TROUBLESHOOTING.map((item) => (
                <details
                  key={item.problem}
                  className="group nc-tile rounded-sm border border-border p-3 open:bg-surface-2"
                >
                  <summary className="cursor-pointer list-none text-[13px] font-medium text-ivory marker:hidden">
                    <span className="mr-2 inline-block text-bronze transition-transform group-open:rotate-90">
                      ›
                    </span>
                    {item.problem}
                  </summary>
                  <div className="mt-2 space-y-1 pl-5 text-[12px] text-muted-foreground">
                    {item.fix}
                  </div>
                </details>
              ))}
            </div>
          </Section>

          <Section id="tips" icon={CheckCircle2} title="Tips for better reconstructions">
            <ul className="list-disc space-y-1.5 pl-5">
              <li>
                Fill most of the frame with the object; small objects in big photos lose detail.
              </li>
              <li>Two or three circles at different heights beat one circle with many photos.</li>
              <li>
                Put the object on a textured, non-shiny surface so cameras have detail to lock on
                to.
              </li>
              <li>
                Check the Masked Images tab after Stage 2; re-shoot photos where the object was cut
                away.
              </li>
              <li>
                The underside of an object resting on a table is never photographed, so it will be
                guessed; flip the object and shoot a second set if it matters.
              </li>
              <li>
                Start with a medium set (60–100 photos) to check your setup before shooting
                hundreds.
              </li>
            </ul>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link
                to="/"
                className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-bronze/55 bg-bronze/12 px-3 text-[12px] font-medium uppercase tracking-wider text-bronze transition-colors hover:bg-bronze/20"
              >
                Start a reconstruction
              </Link>
              <Link
                to="/viewer"
                className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border-strong px-3 text-[12px] font-medium uppercase tracking-wider text-ivory transition-colors hover:bg-surface-2"
              >
                Open the viewer
              </Link>
            </div>
          </Section>
        </article>
      </div>
    </div>
  );
}

const STAGE_DETAILS = [
  {
    title: PIPELINE_STEP_NAMES[0],
    body: "Your photos are checked (format, size), saved into the job and given thumbnails.",
  },
  {
    title: PIPELINE_STEP_NAMES[1],
    body: "Each photo is cut out from its background with rembg, so the model learns the object rather than the room.",
  },
  {
    title: PIPELINE_STEP_NAMES[2],
    body: "COLMAP finds matching details between photos and works out where the camera stood for each one. Fails clearly if too few photos can be placed.",
  },
  {
    title: PIPELINE_STEP_NAMES[3],
    body: "Instant-NGP trains the NeRF on your photos and camera positions (35,000 steps by default, about 20 minutes on an RTX 2050).",
  },
  {
    title: PIPELINE_STEP_NAMES[4],
    body: "The trained NeRF is sampled on a 3D grid and turned into a coloured triangle mesh (marching cubes).",
  },
  {
    title: PIPELINE_STEP_NAMES[5],
    body: "The mesh is repaired, floating fragments are removed, the surface is smoothed and very large meshes are simplified.",
  },
  {
    title: PIPELINE_STEP_NAMES[6],
    body: "The original and cleaned meshes are checked on disk and offered for download as GLB, OBJ and PLY.",
  },
];

const STAT_DETAILS = [
  {
    term: "Hardware · Runtime",
    body: "Live CPU and GPU utilisation, GPU memory (VRAM), driver, CUDA version and temperatures, read from the backend machine every 1.5 s while the dashboard is open.",
  },
  {
    term: "Loss (train)",
    body: "How far the NeRF's predictions are from your photos at the end of training. Lower is better; it should fall steadily during a healthy run.",
  },
  {
    term: "Throughput",
    body: "Training speed in steps per second. It depends on your GPU and on how much of the scene is occupied.",
  },
  {
    term: "Checkpoints",
    body: "How many trained-model snapshots were saved (normally 1, the final one).",
  },
  {
    term: "Peak VRAM",
    body: "The most GPU memory the training process used. Useful for knowing how much headroom your card has.",
  },
  {
    term: "Training time · Pipeline time",
    body: "Training time is Stage 4 alone. Pipeline time adds up the measured run time of all seven stages (idle time between runs is not counted).",
  },
  {
    term: "Active jobs · Completed · 7d",
    body: "Active counts only jobs that are running or queued. Completed · 7d counts jobs that finished in the last seven days.",
  },
  {
    term: "Median PSNR",
    body: "An image-quality score. The pipeline does not compute it yet, so it reads “Not evaluated”.",
  },
];

const TROUBLESHOOTING: { problem: string; fix: ReactNode }[] = [
  {
    problem: "The badge says “Disconnected” or nothing loads",
    fix: (
      <>
        <p>
          The web page cannot reach the backend. Make sure the backend is running (see the README)
          and that Settings → Performance → Backend URL points to it (default{" "}
          <span className="mono">http://localhost:8000</span>).
        </p>
      </>
    ),
  },
  {
    problem: "“COLMAP is unavailable” in Camera Estimation",
    fix: (
      <p>
        COLMAP is not installed or the backend cannot find it. Install COLMAP or set{" "}
        <span className="mono">COLMAP_BINARY</span> in <span className="mono">backend/.env</span> to
        the full path of the executable, restart the backend, then retry the job.
      </p>
    ),
  },
  {
    problem: "Camera estimation failed: too few images registered",
    fix: (
      <p>
        COLMAP could not place enough of your photos. Usually the photos overlap too little, are
        blurry, or show a plain surface with no detail. Add photos between existing ones, re-shoot
        blurry ones, or put the object on a textured mat.
      </p>
    ),
  },
  {
    problem: "Instant-NGP is “not ready” or reports a Python version mismatch",
    fix: (
      <p>
        The backend must run Instant-NGP with the same Python version it was built for. Set{" "}
        <span className="mono">INSTANT_NGP_PYTHON</span> in{" "}
        <span className="mono">backend/.env</span> to the full path of that interpreter (for example
        the backend's own <span className="mono">.venv/bin/python</span>) and restart the backend.
      </p>
    ),
  },
  {
    problem: "CUDA out of memory during training",
    fix: (
      <p>
        The GPU ran out of memory. Close other programs using the GPU (games, other renderers,
        browsers with heavy WebGL pages), use fewer or smaller photos (around 800–1600 px wide is
        plenty), and do not run two reconstructions at once.
      </p>
    ),
  },
  {
    problem: "Parts of the object are missing",
    fix: (
      <p>
        Check the Masked Images tab: background removal sometimes cuts away thin or low-contrast
        parts. Also make sure some photos actually see the missing side. Re-shoot with a contrasting
        background and better coverage.
      </p>
    ),
  },
  {
    problem: "The mesh has many small fragments or a rough surface",
    fix: (
      <p>
        Compare the Cleaned and Original meshes in the viewer; cleanup removes the smallest pieces.
        Remaining fragments usually come from reflections, background clutter or areas few photos
        cover. Better photos help most.
      </p>
    ),
  },
  {
    problem: "An upload is rejected",
    fix: (
      <p>
        Only JPG, JPEG and PNG are accepted, each up to 50 MB and 40 megapixels. The error message
        names the file and the reason.
      </p>
    ),
  },
  {
    problem: "Training takes a long time",
    fix: (
      <p>
        35,000 steps take roughly 20 minutes on an entry-level GPU; that is normal. The Training
        line in the terminal shows the progress percentage.
      </p>
    ),
  },
];

function Section({
  id,
  icon: Icon,
  title,
  children,
}: {
  id: string;
  icon: typeof BookOpen;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-4">
      <Panel bodyClassName="space-y-3 p-4 sm:p-5">
        <h2
          id={`${id}-title`}
          className="flex items-center gap-2.5 text-[16px] font-semibold tracking-tight text-ivory"
        >
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-sm border border-bronze/40 bg-bronze/10">
            <Icon className="h-3.5 w-3.5 text-bronze" strokeWidth={1.7} />
          </span>
          {title}
        </h2>
        {children}
      </Panel>
    </section>
  );
}

function Callout({
  tone,
  title,
  children,
}: {
  tone: "info" | "warning";
  title: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-sm border p-3 text-[12px]",
        tone === "info" ? "border-info/40 bg-info/8" : "border-warning/45 bg-warning/8",
      )}
    >
      <div className={cn("label-caps mb-1", tone === "info" ? "!text-info" : "!text-warning")}>
        {title}
      </div>
      <div className="text-muted-foreground">{children}</div>
    </div>
  );
}

function Steps({ steps }: { steps: ReactNode[] }) {
  return (
    <ol className="space-y-2.5">
      {steps.map((step, index) => (
        <li key={index} className="flex gap-3">
          <span className="mono grid h-6 w-6 shrink-0 place-items-center rounded-full border border-bronze/50 bg-bronze/10 text-[11px] text-bronze">
            {index + 1}
          </span>
          <div className="pt-0.5">{step}</div>
        </li>
      ))}
    </ol>
  );
}

function DoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-sm border border-success/35 bg-success/6 p-3">
      <div className="label-caps mb-2 !text-success">{title}</div>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-[12px]">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" strokeWidth={1.8} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DontList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-sm border border-destructive/35 bg-destructive/6 p-3">
      <div className="label-caps mb-2 !text-destructive">{title}</div>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-[12px]">
            <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" strokeWidth={1.8} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone?: "destructive" }) {
  return (
    <span
      className={cn(
        "mono rounded-sm border px-1.5 py-px text-[10px] uppercase tracking-widest",
        tone === "destructive"
          ? "border-destructive/40 text-destructive"
          : "border-border-strong text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

function FormatCard({ name, body }: { name: string; body: string }) {
  return (
    <div className="nc-tile rounded-sm border border-border p-3">
      <div className="mono text-[14px] text-bronze">.{name.toLowerCase()}</div>
      <p className="mt-1 text-[12px] text-muted-foreground">{body}</p>
    </div>
  );
}

/** Real screenshot of the running app, in the variant matching the current theme. */
function Screenshot({ name, alt }: { name: string; alt: string }) {
  return (
    <figure className="overflow-hidden rounded-sm border border-border bg-viewport">
      <img
        src={`/guide/${name}-light.png`}
        alt={alt}
        loading="lazy"
        className="block w-full dark:hidden"
      />
      <img
        src={`/guide/${name}-dark.png`}
        alt={alt}
        loading="lazy"
        className="hidden w-full dark:block"
      />
    </figure>
  );
}

function CameraRingDiagram() {
  const cameras = Array.from({ length: 10 }, (_, i) => (i / 10) * Math.PI * 2);
  return (
    <svg
      viewBox="0 0 240 200"
      role="img"
      aria-label="Diagram: cameras placed in a ring around an object, each pointing at it"
      className="w-full text-bronze"
    >
      <ellipse
        cx="120"
        cy="105"
        rx="92"
        ry="62"
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.25"
        strokeDasharray="3 4"
      />
      {cameras.map((angle) => {
        const x = 120 + Math.cos(angle) * 92;
        const y = 105 + Math.sin(angle) * 62;
        return (
          <g key={angle}>
            <line x1={x} y1={y} x2="120" y2="100" stroke="currentColor" strokeOpacity="0.18" />
            <rect
              x={x - 7}
              y={y - 5}
              width="14"
              height="10"
              rx="2"
              fill="var(--color-surface-3)"
              stroke="currentColor"
              strokeWidth="1.2"
            />
          </g>
        );
      })}
      <path
        d="M104 118 l16 -34 l16 34 z"
        fill="var(--color-bronze)"
        fillOpacity="0.25"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <text
        x="120"
        y="194"
        textAnchor="middle"
        className="mono"
        fontSize="10"
        fill="var(--color-subtle)"
      >
        overlapping views around the object
      </text>
    </svg>
  );
}

function PipelineDiagram() {
  return (
    <div className="overflow-x-auto pb-1">
      <ol className="flex min-w-[640px] items-center gap-1.5" aria-label="Pipeline order">
        {PIPELINE_STEP_NAMES.map((name, index) => (
          <li key={name} className="flex flex-1 items-center gap-1.5">
            <div className="flex-1 rounded-sm border border-bronze/40 bg-bronze/8 px-2 py-2 text-center">
              <div className="mono text-[10px] text-bronze">
                {String(index + 1).padStart(2, "0")}
              </div>
              <div className="mt-0.5 text-[11px] leading-tight text-ivory">{name}</div>
            </div>
            {index < PIPELINE_STEP_NAMES.length - 1 && (
              <span aria-hidden className="text-subtle">
                →
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
