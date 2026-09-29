import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-content-muted">
      <Loader2 className="h-5 w-5 animate-spin text-brand-400" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 py-10 px-6 text-center">
      <AlertTriangle className="h-6 w-6 text-red-400" />
      <p className="text-sm text-red-300">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-lg bg-red-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong bg-ink-700/50 py-12 px-6 text-center">
      <Inbox className="h-7 w-7 text-content-faint" />
      <p className="font-medium text-content-muted">{title}</p>
      {hint && <p className="text-sm text-content-faint">{hint}</p>}
    </div>
  );
}
