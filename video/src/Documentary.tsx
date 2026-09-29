import React from "react";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Sequence,
  staticFile,
  useVideoConfig,
} from "remotion";
import { Captions } from "./components/Captions";
import { Credit } from "./components/Credit";
import { KenBurnsShot } from "./components/KenBurnsShot";
import type { DocumentaryProps } from "./schema";

// Shots are placed at absolute times taken from the TTS alignment so the
// picture always stays in sync with the narration. Each shot starts slightly
// early and fades in over the previous one (a crossfade that never shifts
// the timeline, unlike TransitionSeries which shortens it).
export const Documentary: React.FC<DocumentaryProps> = (props) => {
  const { fps } = useVideoConfig();
  const fade = Math.round(props.crossfadeSec * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {props.shots.map((shot, i) => {
        const start = Math.round(shot.startSec * fps);
        const end = Math.round(shot.endSec * fps);
        const lead = i === 0 ? 0 : Math.min(fade, start);
        return (
          <Sequence
            key={`${i}-${shot.src}`}
            name={`Shot ${i + 1}`}
            from={start - lead}
            durationInFrames={Math.max(1, end - start + lead)}
          >
            <KenBurnsShot shot={shot} fadeInFrames={lead} />
            {props.showCredits && shot.credit ? <Credit text={shot.credit} /> : null}
          </Sequence>
        );
      })}

      {props.audio.map((clip, i) => (
        <Sequence
          key={`audio-${i}`}
          name={`Narration ${i + 1}`}
          from={Math.round(clip.startSec * fps)}
          layout="none"
        >
          <Audio src={clip.src.startsWith("http") ? clip.src : staticFile(clip.src)} />
        </Sequence>
      ))}

      {props.showCaptions ? <Captions captions={props.captions} /> : null}
    </AbsoluteFill>
  );
};

export const calculateDocumentaryMetadata: CalculateMetadataFunction<
  DocumentaryProps
> = ({ props }) => {
  const safeTitle = props.title.replace(/[^\p{L}\p{N}]+/gu, "-").toLowerCase();
  return {
    fps: props.fps,
    width: props.width,
    height: props.height,
    durationInFrames: Math.max(1, Math.ceil(props.durationSec * props.fps)),
    defaultOutName: `${safeTitle || "documentary"}-${props.language}`,
  };
};
