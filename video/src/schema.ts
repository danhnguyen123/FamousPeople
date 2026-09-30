import { z } from "zod";

// Must stay in sync with pipeline/src/docugen/timeline.py (Timeline model).

export const motionSchema = z.enum([
  "zoomIn",
  "zoomOut",
  "panLeft",
  "panRight",
  "panUp",
  "panDown",
]);

export const shotSchema = z.object({
  src: z.string(), // path relative to public/, e.g. "projects/demo/assets/001_a.jpg"
  startSec: z.number(),
  endSec: z.number(),
  motion: motionSchema,
  // Focus point (0..1) the camera drifts toward, e.g. a face center.
  focusX: z.number().min(0).max(1).default(0.5),
  focusY: z.number().min(0).max(1).default(0.4),
  credit: z.string().nullable().default(null),
});

export const audioClipSchema = z.object({
  src: z.string(),
  startSec: z.number(),
});

export const captionSchema = z.object({
  text: z.string(),
  startSec: z.number(),
  endSec: z.number(),
});

export const documentarySchema = z.object({
  title: z.string(),
  language: z.string(),
  fps: z.number().int().default(30),
  width: z.number().int().default(1920),
  height: z.number().int().default(1080),
  durationSec: z.number(),
  crossfadeSec: z.number().default(0.6),
  showCaptions: z.boolean().default(false),
  showCredits: z.boolean().default(false),
  audio: z.array(audioClipSchema),
  shots: z.array(shotSchema),
  captions: z.array(captionSchema),
});

export type Motion = z.infer<typeof motionSchema>;
export type Shot = z.infer<typeof shotSchema>;
export type DocumentaryProps = z.infer<typeof documentarySchema>;
