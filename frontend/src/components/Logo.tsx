// Brand mark: a white isometric cube on a near-black tile, in the spirit of the
// Outbox Labs logo. Kept as a standalone component so it's easy to restyle.

export function LogoMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <div
      className={`flex items-center justify-center rounded-lg bg-black ring-1 ring-white/10 ${className}`}
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
        {/* top face */}
        <path d="M12 2 L21 7 L12 12 L3 7 Z" fill="#ffffff" />
        {/* left face */}
        <path d="M3 7 L12 12 L12 22 L3 17 Z" fill="#ffffff" fillOpacity="0.6" />
        {/* right face */}
        <path d="M21 7 L12 12 L12 22 L21 17 Z" fill="#ffffff" fillOpacity="0.85" />
      </svg>
    </div>
  );
}
