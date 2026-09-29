import type { DocumentaryProps } from "./schema";

// Preview data for the Studio. Real renders pass --props=<timeline.json>
// produced by the Python pipeline (see ../pipeline).
export const sampleProps: DocumentaryProps = {
  title: "Sample documentary",
  language: "en",
  fps: 30,
  width: 1920,
  height: 1080,
  durationSec: 9,
  crossfadeSec: 0.6,
  showCaptions: true,
  showCredits: true,
  audio: [],
  shots: [
    {
      src: "sample/sample-1.jpg",
      startSec: 0,
      endSec: 4.5,
      motion: "zoomIn",
      focusX: 0.5,
      focusY: 0.4,
      credit: "Sample image",
    },
    {
      src: "sample/sample-2.jpg",
      startSec: 4.5,
      endSec: 9,
      motion: "panRight",
      focusX: 0.5,
      focusY: 0.4,
      credit: null,
    },
  ],
  captions: [
    { text: "In 1994, she was already a household name.", startSec: 0, endSec: 4.5 },
    { text: "But the cameras only told half the story.", startSec: 4.5, endSec: 9 },
  ],
};
