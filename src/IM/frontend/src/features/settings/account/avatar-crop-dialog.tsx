import * as Dialog from "@radix-ui/react-dialog";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "../../../i18n";

export interface PreparedAvatarSource {
  source: CanvasImageSource;
  width: number;
  height: number;
}

const MAX_WORKING_DIMENSION = 2048;
const CROP_RING_DIAMETER = 200;
const EXPORT_DIMENSION = 512;

/** Decode a validated local image file, pre-downscaling >2048px sources and revoking temporary ObjectURLs. */
export function loadAvatarImageSource(file: File): Promise<{
  prepared: PreparedAvatarSource;
  cleanup: () => void;
}> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    let revoked = false;
    const revoke = () => {
      if (!revoked) {
        revoked = true;
        URL.revokeObjectURL(objectUrl);
      }
    };
    const img = new Image();
    img.onload = () => {
      const naturalW = img.naturalWidth || img.width || EXPORT_DIMENSION;
      const naturalH = img.naturalHeight || img.height || EXPORT_DIMENSION;
      const scale =
        Math.max(naturalW, naturalH) > MAX_WORKING_DIMENSION
          ? MAX_WORKING_DIMENSION / Math.max(naturalW, naturalH)
          : 1;
      const targetW = Math.max(1, Math.round(naturalW * scale));
      const targetH = Math.max(1, Math.round(naturalH * scale));

      const workingCanvas = document.createElement("canvas");
      workingCanvas.width = targetW;
      workingCanvas.height = targetH;
      let ctx: CanvasRenderingContext2D | null = null;
      try {
        ctx = workingCanvas.getContext("2d");
      } catch {
        ctx = null;
      }
      if (ctx) {
        ctx.drawImage(img, 0, 0, targetW, targetH);
        // Working pixels live on the offscreen canvas; revoke file ObjectURL immediately.
        revoke();
        resolve({
          prepared: { source: workingCanvas, width: targetW, height: targetH },
          cleanup: revoke,
        });
        return;
      }
      // Headless test fallback when 2D canvas context is unavailable.
      resolve({
        prepared: { source: img, width: targetW, height: targetH },
        cleanup: revoke,
      });
    };
    img.onerror = () => {
      revoke();
      reject(new Error("avatar_decode_failed"));
    };
    img.src = objectUrl;
  });
}

function clampPanOffset(
  width: number,
  height: number,
  zoom: number,
  panX: number,
  panY: number,
): { x: number; y: number } {
  const baseScale = Math.max(CROP_RING_DIAMETER / width, CROP_RING_DIAMETER / height) * zoom;
  const maxX = Math.max(0, (width * baseScale - CROP_RING_DIAMETER) / 2);
  const maxY = Math.max(0, (height * baseScale - CROP_RING_DIAMETER) / 2);
  return {
    x: Math.max(-maxX, Math.min(maxX, panX)),
    y: Math.max(-maxY, Math.min(maxY, panY)),
  };
}

async function exportCroppedAvatarBlob(
  prepared: PreparedAvatarSource,
  zoom: number,
  panX: number,
  panY: number,
  fallbackFile: File,
): Promise<Blob> {
  const clamped = clampPanOffset(prepared.width, prepared.height, zoom, panX, panY);
  const out = document.createElement("canvas");
  out.width = EXPORT_DIMENSION;
  out.height = EXPORT_DIMENSION;
  let ctx: CanvasRenderingContext2D | null = null;
  try {
    ctx = out.getContext("2d");
  } catch {
    ctx = null;
  }
  if (!ctx || typeof out.toBlob !== "function") {
    return fallbackFile;
  }
  const baseScale = Math.max(EXPORT_DIMENSION / prepared.width, EXPORT_DIMENSION / prepared.height) * zoom;
  const drawW = prepared.width * baseScale;
  const drawH = prepared.height * baseScale;
  const drawX = (EXPORT_DIMENSION - drawW) / 2 + clamped.x * (EXPORT_DIMENSION / CROP_RING_DIAMETER);
  const drawY = (EXPORT_DIMENSION - drawH) / 2 + clamped.y * (EXPORT_DIMENSION / CROP_RING_DIAMETER);
  ctx.clearRect(0, 0, EXPORT_DIMENSION, EXPORT_DIMENSION);
  ctx.drawImage(prepared.source, drawX, drawY, drawW, drawH);

  const encode = (mime: string, quality?: number) =>
    new Promise<Blob | null>((resolve) => {
      try {
        out.toBlob((blob) => resolve(blob), mime, quality);
      } catch {
        resolve(null);
      }
    });

  const webp = await encode("image/webp", 0.9);
  if (webp && webp.size > 0 && webp.type === "image/webp") return webp;
  const png = await encode("image/png");
  if (png && png.size > 0) return png;
  return fallbackFile;
}

export function AvatarCropDialog({
  open,
  prepared,
  sourceFile,
  saving,
  returnFocusRef,
  onReselect,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  prepared: PreparedAvatarSource | null;
  sourceFile: File | null;
  saving: boolean;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
  onReselect(): void;
  onCancel(): void;
  onConfirm(blob: Blob): void;
}) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number } | null>(null);
  const [zoom, setZoom] = useState(1.15);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  useEffect(() => {
    setZoom(1.15);
    setPan({ x: 0, y: 0 });
  }, [prepared]);

  const drawPreview = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !prepared) return;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext("2d");
    } catch {
      ctx = null;
    }
    if (!ctx) return;
    const clamped = clampPanOffset(prepared.width, prepared.height, zoom, pan.x, pan.y);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const previewCircle = 400; // 2x Retina inside 480x480 canvas (200px ring inside 240px stage)
    const baseScale = Math.max(previewCircle / prepared.width, previewCircle / prepared.height) * zoom;
    const drawW = prepared.width * baseScale;
    const drawH = prepared.height * baseScale;
    const drawX = (canvas.width - drawW) / 2 + clamped.x * 2;
    const drawY = (canvas.height - drawH) / 2 + clamped.y * 2;
    ctx.drawImage(prepared.source, drawX, drawY, drawW, drawH);
  }, [prepared, zoom, pan]);

  const bindCanvas = useCallback(
    (node: HTMLCanvasElement | null) => {
      canvasRef.current = node;
      if (node) {
        drawPreview();
      }
    },
    [drawPreview],
  );

  useLayoutEffect(() => {
    if (open) drawPreview();
  }, [open, drawPreview]);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !saving) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="im-avatar-crop-backdrop" />
        <Dialog.Content
          className="im-avatar-crop-dialog"
          data-testid="avatar-crop-dialog"
          onEscapeKeyDown={(event) => {
            if (saving) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (saving) event.preventDefault();
          }}
          onCloseAutoFocus={(event) => {
            if (returnFocusRef?.current) {
              event.preventDefault();
              returnFocusRef.current.focus();
            }
          }}
        >
          <div className="im-avatar-crop-head">
            <Dialog.Title className="im-avatar-crop-title">
              {t("settings.account.avatar.cropTitle")}
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              {t("settings.account.avatar.cropDescription")}
            </Dialog.Description>
            <button
              type="button"
              className="im-avatar-crop-close"
              aria-label={t("settings.account.avatar.close")}
              disabled={saving}
              onClick={onCancel}
            >
              ✕
            </button>
          </div>

          <div className="im-avatar-crop-stage-wrap">
            <div
              className="im-avatar-crop-viewport"
              data-testid="avatar-crop-viewport"
              onPointerDown={(event) => {
                if (!prepared || saving) return;
                event.currentTarget.setPointerCapture?.(event.pointerId);
                dragRef.current = {
                  startX: event.clientX - pan.x,
                  startY: event.clientY - pan.y,
                };
              }}
              onPointerMove={(event) => {
                if (!dragRef.current || !prepared || saving) return;
                const nextX = event.clientX - dragRef.current.startX;
                const nextY = event.clientY - dragRef.current.startY;
                setPan(clampPanOffset(prepared.width, prepared.height, zoom, nextX, nextY));
              }}
              onPointerUp={() => {
                dragRef.current = null;
              }}
              onPointerCancel={() => {
                dragRef.current = null;
              }}
            >
              <canvas ref={bindCanvas} width={480} height={480} />
              <div className="im-avatar-crop-mask-ring" aria-hidden="true" />
            </div>

            <div className="im-avatar-crop-controls">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <input
                type="range"
                min="1"
                max="2.8"
                step="0.02"
                value={zoom}
                disabled={saving}
                aria-label={t("settings.account.avatar.zoomLabel")}
                onChange={(event) => {
                  const nextZoom = Number(event.target.value);
                  setZoom(nextZoom);
                  if (prepared) {
                    setPan((prev) => clampPanOffset(prepared.width, prepared.height, nextZoom, prev.x, prev.y));
                  }
                }}
              />
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </div>
          </div>

          <div className="im-avatar-crop-foot">
            <button
              type="button"
              className="im-avatar-crop-reselect"
              disabled={saving}
              onClick={onReselect}
            >
              {t("settings.account.avatar.reselect")}
            </button>
            <div className="im-avatar-crop-foot-main">
              <button
                type="button"
                className="im-btn im-btn-muted"
                disabled={saving}
                onClick={onCancel}
              >
                {t("settings.account.avatar.cancel")}
              </button>
              <button
                type="button"
                className="im-btn im-btn-primary"
                data-testid="avatar-crop-confirm-btn"
                disabled={saving || !prepared || !sourceFile}
                onClick={async () => {
                  if (!prepared || !sourceFile || saving) return;
                  const blob = await exportCroppedAvatarBlob(prepared, zoom, pan.x, pan.y, sourceFile);
                  onConfirm(blob);
                }}
              >
                {t(saving ? "settings.account.actions.saving" : "settings.account.actions.save")}
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
