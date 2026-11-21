import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ButtonPro } from "./Panel";

/**
 * Modal confirmation for destructive actions. Escape and the backdrop cancel (unless busy);
 * focus starts on Cancel and is kept inside the dialog.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  busy = false,
  busyLabel = "Working…",
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  busyLabel?: string;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const bodyId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    return () => previous?.focus?.();
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape" && !busy) {
      event.stopPropagation();
      onCancel();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      "button:not([disabled]), a[href]",
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-busy={busy || undefined}
        onKeyDown={onKeyDown}
        className="panel w-full max-w-md select-text shadow-2xl"
      >
        <div className="hairline-b nc-panel-header px-4 py-2.5">
          <h2 id={titleId} className="text-[14px] font-semibold text-ivory">
            {title}
          </h2>
        </div>
        <div id={bodyId} className="space-y-3 px-4 py-4 text-[12.5px] text-muted-foreground">
          {children}
          {error && (
            <p
              role="alert"
              className="rounded-sm border border-destructive/40 bg-destructive/10 px-2.5 py-2 text-destructive"
            >
              {error}
            </p>
          )}
        </div>
        <div className="hairline-t flex justify-end gap-2 px-4 py-3">
          <ButtonPro ref={cancelRef} variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </ButtonPro>
          <ButtonPro variant="danger" onClick={onConfirm} loading={busy}>
            {busy ? busyLabel : confirmLabel}
          </ButtonPro>
        </div>
      </div>
    </div>,
    document.body,
  );
}
