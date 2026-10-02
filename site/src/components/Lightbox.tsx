import { useEffect, useRef } from "react";
import { X } from "lucide-react";

export type Shot = { src: string; alt: string; width: number; height: number };

/** Full-screen view of a screenshot. Closes on Escape, the close button, or a click outside the image. */
export default function Lightbox({ shot, onClose }: { shot: Shot | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!shot) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [shot, onClose]);

  if (!shot) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={shot.alt}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/75 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-4 right-4 grid size-10 cursor-pointer place-items-center rounded-full bg-white text-ink shadow-lg hover:bg-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      >
        <X size={20} />
      </button>
      <img
        src={shot.src}
        alt={shot.alt}
        width={shot.width}
        height={shot.height}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[88vh] max-w-[min(1400px,94vw)] rounded-xl bg-white object-contain shadow-2xl"
      />
    </div>
  );
}
