import { TOWNSHIP_NAME } from "@/lib/config";

/** Title row of a module page; global status, site and operator live in <AppHeader>. */
export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="relative z-30 flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <div className="min-w-0">
        <h1 className="truncate text-base font-semibold text-ink">{title}</h1>
        <p className="truncate text-xs text-muted">{subtitle ?? TOWNSHIP_NAME}</p>
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}
