import { cn } from "@/lib/utils";
import { forwardRef, type ReactNode } from "react";

export function Panel({
  title,
  action,
  children,
  className,
  bodyClassName,
  dense,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  dense?: boolean;
}) {
  return (
    <div className={cn("panel flex flex-col overflow-hidden", className)}>
      {title !== undefined && (
        <div className="hairline-b flex min-h-9 shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 nc-panel-header px-3 py-1.5">
          <div className="label-caps">{title}</div>
          {action}
        </div>
      )}
      <div className={cn(dense ? "" : "p-4", "min-h-0 flex-1", bodyClassName)}>{children}</div>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="hairline-b flex flex-wrap items-end justify-between gap-4 bg-surface/40 nc-page-header px-4 py-4 sm:px-6">
      <div className="min-w-0">
        {eyebrow && <div className="label-caps mb-1.5">{eyebrow}</div>}
        <h1 className="text-[22px] font-semibold tracking-tight text-ivory">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-[13px] text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "bronze" | "success" | "warning" | "destructive";
}) {
  const toneMap = {
    bronze: "text-bronze",
    success: "text-success",
    warning: "text-warning",
    destructive: "text-destructive",
  } as const;
  return (
    <div className="nc-tile rounded-sm border border-border p-3">
      <div className="label-caps">{label}</div>
      <div
        className={cn(
          "mono mt-1.5 text-[20px] font-medium tracking-tight text-ivory",
          tone && toneMap[tone],
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-[11px] text-subtle">{hint}</div>}
    </div>
  );
}

type ButtonProProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  /** "bronze" is the accent variant (blue); "warm" is reserved for the primary call to action;
   * "danger" is for destructive actions. */
  variant?: "default" | "bronze" | "warm" | "ghost" | "outline" | "danger";
  size?: "sm" | "md";
  /** Shows a spinner, disables the button and sets aria-busy. */
  loading?: boolean;
  /** Why the button is unavailable; disables it and shows the reason on hover. */
  reason?: string | null;
};

export const ButtonPro = forwardRef<HTMLButtonElement, ButtonProProps>(function ButtonPro(
  {
    children,
    variant = "default",
    size = "md",
    loading = false,
    reason,
    className,
    disabled,
    type = "button",
    ...props
  },
  ref,
) {
  const variants = {
    default:
      "bg-surface-2 border border-border text-ivory hover:border-border-strong hover:bg-surface-3 active:bg-surface-3",
    bronze:
      "bg-bronze/12 border border-bronze/55 text-bronze hover:bg-bronze/20 hover:border-bronze/75 active:bg-bronze/25",
    warm: "nc-cta border border-warm/80 text-warm-foreground shadow-sm hover:brightness-105 active:brightness-95",
    ghost: "text-muted-foreground hover:bg-surface-2 hover:text-ivory active:bg-surface-3",
    outline:
      "border border-border-strong text-ivory hover:bg-surface-2 hover:border-selected/45 active:bg-surface-3",
    danger:
      "bg-destructive/12 border border-destructive/55 text-destructive hover:bg-destructive/20 hover:border-destructive/75 active:bg-destructive/25",
  };
  const sizes = { sm: "h-7 px-2.5 text-[11px]", md: "h-8 px-3 text-[12px]" };
  const button = (
    <button
      {...props}
      ref={ref}
      type={type}
      disabled={disabled || loading || Boolean(reason)}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm font-medium uppercase tracking-wider transition-[color,background-color,border-color,filter] duration-150 disabled:pointer-events-none",
        // Disabled: a distinct neutral look (not a faded copy of the enabled colours).
        variant === "ghost"
          ? "disabled:text-subtle/70"
          : "disabled:border-border disabled:bg-surface-3/55 disabled:bg-none disabled:text-subtle disabled:shadow-none",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading && (
        <span
          aria-hidden
          className="h-3 w-3 animate-spin rounded-full border-[1.5px] border-current border-r-transparent"
        />
      )}
      {children}
    </button>
  );
  if (!reason) return button;
  // Disabled buttons receive no pointer events, so the tooltip lives on a wrapper.
  return (
    <span title={reason} className="inline-flex cursor-not-allowed">
      {button}
      <span className="sr-only">({reason})</span>
    </span>
  );
});
