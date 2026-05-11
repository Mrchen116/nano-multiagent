import { useState, type DragEvent, type ReactNode } from "react";

export interface AttachmentDropzoneProps {
  onAdd(files: File[]): void;
  children: ReactNode;
  className?: string;
}

/**
 * Thin div wrapper that emits dropped files via `onAdd`. The composer owns
 * the resulting attachment state — this component only handles the DnD
 * surface so the textarea + chip strip can live unchanged inside.
 *
 * `data-dragging` lets the consumer style the active state purely in CSS.
 */
export function AttachmentDropzone({ onAdd, children, className }: AttachmentDropzoneProps) {
  const [dragging, setDragging] = useState(false);

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
  }

  function handleDragEnter(e: DragEvent<HTMLDivElement>) {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length === 0) return;
    onAdd(dropped);
  }

  return (
    <div
      className={className}
      data-dragging={dragging}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {children}
    </div>
  );
}
