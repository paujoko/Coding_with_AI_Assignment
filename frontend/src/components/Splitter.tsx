import { useRef } from "react";

interface Props {
  container: React.RefObject<HTMLElement | null>; // the grid whose first column this resizes
  value: number | null; // width of the first column in px; null = the default
  onChange: (px: number | null) => void;
  min?: number;
  minRest?: number; // the second column never gets narrower than this
}

// A draggable line between chat and results, like the split view of an editor.
// Mouse, touch and keyboard (arrows, Home to reset); double-click resets as well.
export function Splitter({ container, value, onChange, min = 320, minRest = 380 }: Props) {
  const dragging = useRef(false);
  const clamp = (px: number) => {
    const width = container.current?.getBoundingClientRect().width ?? 1200;
    return Math.round(Math.min(Math.max(px, min), width - minRest));
  };
  const current = () => value ?? (container.current?.firstElementChild?.getBoundingClientRect().width ?? 480);

  return (
    <div
      className="splitter"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize chat and results"
      aria-valuenow={Math.round(current())}
      aria-valuemin={min}
      tabIndex={0}
      title="Drag to resize. Double-click to reset."
      onDoubleClick={() => onChange(null)}
      onPointerDown={(e) => {
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!dragging.current || !container.current) return;
        onChange(clamp(e.clientX - container.current.getBoundingClientRect().left));
      }}
      onPointerUp={(e) => {
        dragging.current = false;
        e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          onChange(clamp(current() + (e.key === "ArrowLeft" ? -40 : 40)));
        } else if (e.key === "Home") {
          e.preventDefault();
          onChange(null);
        }
      }}
    />
  );
}
