"""Optional CLIP reranking: how well an image fits the scene description.

Install with `pip install -e ".[clip]"`. Used only as a semantic reranker,
never to decide who is in the picture.
"""

from __future__ import annotations

import io
import logging

from .http import client

log = logging.getLogger(__name__)


class ClipRanker:
    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        import open_clip  # noqa: F401  (raises ImportError when the extra is missing)
        import torch

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=self.device
        )
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval()

    def score_urls(self, prompt: str, urls: list[str]) -> list[float | None]:
        from PIL import Image

        images, positions = [], []
        for i, url in enumerate(urls):
            try:
                data = client().get(url).raise_for_status().content
                images.append(self.preprocess(Image.open(io.BytesIO(data)).convert("RGB")))
                positions.append(i)
            except Exception as exc:  # a broken thumbnail should not stop the run
                log.debug("clip: cannot load %s: %s", url, exc)
        out: list[float | None] = [None] * len(urls)
        if not images:
            return out
        torch = self.torch
        with torch.no_grad():
            image_features = self.model.encode_image(torch.stack(images).to(self.device))
            text_features = self.model.encode_text(self.tokenizer([prompt]).to(self.device))
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            sims = (image_features @ text_features.T).squeeze(-1).tolist()
        for pos, sim in zip(positions, sims):
            # Raw cosine similarity for a good match sits around 0.25 to 0.35.
            out[pos] = max(0.0, min(1.0, (sim - 0.12) / 0.23))
        return out


def load_ranker(enabled: bool) -> ClipRanker | None:
    if not enabled:
        return None
    try:
        return ClipRanker()
    except ImportError:
        log.info("CLIP not installed; semantic reranking disabled")
        return None
