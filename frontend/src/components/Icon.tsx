/** Inline SVG icons (no icon font, no network). */

const FILLED = new Set(["play", "pause"]);

const PATHS: Record<string, string> = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  lock: "M7 11V8a5 5 0 0110 0v3M6 11h12v9H6z",
  play: "M8 5.5v13l11-6.5z",
  pause: "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z",
  replay: "M4 12a8 8 0 108-8 8 8 0 00-6 2.7M4 4v4h4",
  fullscreen: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  info: "M12 8h.01M11 12h1v5h1M12 3a9 9 0 110 18 9 9 0 010-18z",
  clock: "M12 7v5l3 2M12 3a9 9 0 110 18 9 9 0 010-18z",
  flag: "M6 21V4M6 4h11l-2 4 2 4H6",
  left: "M15 18l-6-6 6-6",
  right: "M9 6l6 6-6 6",
  arrowLeft: "M19 12H5M11 18l-6-6 6-6",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  up: "M6 15l6-6 6 6",
  down: "M6 9l6 6 6-6",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  certificate: "M6 3h12v12H6zM9 7h6M9 10h4M9 15l-1 6 4-2 4 2-1-6",
  close: "M6 6l12 12M18 6L6 18",
  alert: "M12 8v5M12 16h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  question: "M9.5 9a2.5 2.5 0 115 .5c0 1.5-2.5 2-2.5 3.5M12 17h.01M12 3a9 9 0 110 18 9 9 0 010-18z",
};

export function Icon({ name, size = 20, className }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={FILLED.has(name) ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}
