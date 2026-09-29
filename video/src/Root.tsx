import React from "react";
import { Composition } from "remotion";
import { calculateDocumentaryMetadata, Documentary } from "./Documentary";
import { sampleProps } from "./sampleProps";
import { documentarySchema } from "./schema";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Documentary"
        component={Documentary}
        schema={documentarySchema}
        defaultProps={sampleProps}
        calculateMetadata={calculateDocumentaryMetadata}
        durationInFrames={270}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
