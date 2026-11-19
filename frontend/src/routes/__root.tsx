import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { type ReactNode } from "react";

import appCss from "../styles.css?url";
import { APP_NAME, APP_SUBTITLE } from "@/lib/constants";
import { DesktopShell } from "@/components/shell/DesktopShell";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { SIDEBAR_INIT_SCRIPT } from "@/lib/sidebarLayout";

function NotFoundComponent() {
  return (
    <DesktopShell>
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="label-caps mb-3">Error 404</div>
          <h1 className="mono text-5xl text-ivory">NODE_NOT_FOUND</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            The requested route does not exist in the current session graph.
          </p>
          <Link
            to="/"
            className="mt-6 inline-flex items-center gap-2 border border-border-strong bg-surface-2 px-4 py-2 text-xs uppercase tracking-widest hover:bg-surface-3"
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    </DesktopShell>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <div className="label-caps mb-3">Fatal Exception</div>
        <h1 className="mono text-2xl text-ivory">Session halted</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {error.message || "An unexpected error occurred while rendering the workspace."}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="border border-bronze bg-bronze/10 px-4 py-2 text-xs uppercase tracking-widest text-bronze hover:bg-bronze/20"
          >
            Retry
          </button>
          <a
            href="/"
            className="border border-border-strong px-4 py-2 text-xs uppercase tracking-widest hover:bg-surface-2"
          >
            Reset Session
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: `${APP_NAME} — ${APP_SUBTITLE}` },
      {
        name: "description",
        content: `${APP_NAME} is ${APP_SUBTITLE.toLowerCase()}. Ingest, train, mesh, and export in one workflow.`,
      },
      { name: "author", content: APP_NAME },
      { name: "theme-color", content: "#111419" },
      {
        property: "og:title",
        content: `${APP_NAME} — ${APP_SUBTITLE}`,
      },
      {
        property: "og:description",
        content: APP_SUBTITLE,
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap",
      },
      { rel: "stylesheet", href: appCss },
      // Browsers that support SVG pick the vector icon; the multi-size .ico (16/32/48) and
      // 32px PNG are fallbacks. Sources and regeneration steps: public/icons/README.md.
      { rel: "icon", href: "/icons/favicon.svg", type: "image/svg+xml" },
      { rel: "icon", href: "/icons/favicon.ico", sizes: "48x48" },
      { rel: "icon", href: "/icons/favicon.png", type: "image/png", sizes: "32x32" },
      { rel: "apple-touch-icon", href: "/icons/apple-touch-icon.png", sizes: "180x180" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    // THEME_INIT_SCRIPT sets the theme class/style on <html> before first paint; React does
    // not manage those attributes (dark tokens are also the :root default without JS).
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: SIDEBAR_INIT_SCRIPT }} />
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <DesktopShell>
        <Outlet />
      </DesktopShell>
    </QueryClientProvider>
  );
}
