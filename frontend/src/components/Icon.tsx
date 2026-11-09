// One small authored icon set: 16px grid, 1.5px stroke, round caps. No emoji, no glyphs.
const PATHS = {
  plus: "M8 3.5v9M3.5 8h9",
  check: "M3.5 8.5l3 3 6-7",
  arrowRight: "M3 8h10M9 4l4 4-4 4",
  send: "M3 8h9.5M8.5 4l4 4-4 4",
  lock: "M5 7V5.5a3 3 0 0 1 6 0V7M4 7h8v6H4z",
  undo: "M5.5 4L3 6.5 5.5 9M3 6.5h6.5a3.5 3.5 0 0 1 0 7H6",
  pencil: "M10.5 3l2.5 2.5L6 12.5H3.5V10z",
  close: "M4 4l8 8M12 4l-8 8",
  alert: "M8 2.5L14 13H2zM8 6.5v3M8 11.2v.1",
  external: "M9 3h4v4M13 3L7.5 8.5M11.5 9.5V13h-8.5V4.5H7",
  matrix: "M3 3h10v10H3zM3 6.5h10M6.5 3v10",
  list: "M5.5 4.5H13M5.5 8H13M5.5 11.5H13M3 4.5h.1M3 8h.1M3 11.5h.1",
  image: "M2.5 3.5h11v9h-11zM2.5 10l3-3 3 3 2-2 3 3",
  code: "M6 4.5L2.5 8 6 11.5M10 4.5L13.5 8 10 11.5",
  sparkle: "M8 2.5v3M8 10.5v3M2.5 8h3M10.5 8h3",
  chevron: "M6 4l4 4-4 4",
  paperclip: "M10.5 5.5l-4.3 4.3a1.4 1.4 0 0 0 2 2l4.6-4.6a2.8 2.8 0 0 0-4-4L4.3 7.7a4.2 4.2 0 0 0 6 6l3.2-3.2",
  file: "M9 2.5H4.5v11h7V5zM9 2.5V5h2.5",
  arrowUp: "M8 13V3M4 7l4-4 4 4",
  arrowDown: "M8 3v10M4 9l4 4 4-4",
  copy: "M5.5 5.5V3h7.5v7.5h-2.5M3 5.5h7.5V13H3z",
  download: "M8 2.5v8M4.5 7l3.5 3.5L11.5 7M3 13.5h10",
  panel: "M2.5 3.5h11v9h-11zM9.5 3.5v9",
  spinner: "M8 2.5a5.5 5.5 0 1 0 5.5 5.5",
  settings: "M3 4.5h6M12 4.5h1M3 11.5h1M7 11.5h6M10.5 3v3M5.5 10v3",
  help: "M6.2 6.2a1.9 1.9 0 1 1 2.7 1.7c-.6.3-.9.7-.9 1.3v.3M8 11.6v.1",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
