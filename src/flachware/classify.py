"""Classify artwork images as art vs noise using CLIP zero-shot classification.

Many images on flachware.de are not actual artworks: gallery documentation,
event photos, flyers, portraits, screenshots. This module uses OpenAI's
CLIP model to score each image against art-related and noise-related text
prompts, producing a boolean is_art label.

Requires: torch, torchvision, transformers (install with uv sync --group analysis)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

BATCH_SIZE = 64

ART_PROMPTS = [
    "a painting",
    "a sculpture",
    "a drawing",
    "an artwork",
    "a print",
    "an art installation",
    "a photograph of art",
    "abstract art",
    "a sketch",
    "a ceramic artwork",
]

NOISE_PROMPTS = [
    "a photo of people at an event",
    "a group photo",
    "a gallery room",
    "an empty room",
    "a document",
    "text on a page",
    "a screenshot",
    "a flyer",
    "a poster with text",
    "a selfie",
]


def classify_images(paths: list[Path]) -> np.ndarray:
    """Score each image as art vs noise using CLIP zero-shot classification.

    For each image, computes cosine similarity against art and noise text
    prompts. The art score is the sum of softmax probabilities for art
    prompts (0.0 = certainly noise, 1.0 = certainly art).

    Returns a float numpy array of art scores.
    """
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = "mps" if torch.backends.mps.is_available() else "cpu"

    print("Loading CLIP model...")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = model.to(device)  # type: ignore[arg-type]
    model.eval()

    all_prompts = ART_PROMPTS + NOISE_PROMPTS
    text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True)
    text_inputs = {k: v.to(device) for k, v in text_inputs.items()}

    with torch.no_grad():
        text_features = model.get_text_features(**text_inputs)
        if not isinstance(text_features, torch.Tensor):
            text_features = text_features.pooler_output
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    scores: list[float] = []
    n_art = len(ART_PROMPTS)

    for i in tqdm(range(0, len(paths), BATCH_SIZE), desc="Classifying images"):
        batch_paths = paths[i : i + BATCH_SIZE]
        images = []
        for p in batch_paths:
            try:
                images.append(Image.open(p).convert("RGB"))
            except Exception:
                images.append(Image.new("RGB", (224, 224)))

        img_inputs = processor(images=images, return_tensors="pt", padding=True)
        img_inputs = {k: v.to(device) for k, v in img_inputs.items()}

        with torch.no_grad():
            img_features = model.get_image_features(**img_inputs)
            if not isinstance(img_features, torch.Tensor):
                img_features = img_features.pooler_output
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)

            logits = (img_features @ text_features.T) * 100
            probs = logits.softmax(dim=-1).cpu().numpy()
            art_scores = probs[:, :n_art].sum(axis=1)
            scores.extend(float(s) for s in art_scores)

    result = np.array(scores)
    n_art_count = (result > 0.5).sum()
    print(f"  Art (>0.5): {n_art_count}, Noise: {len(result) - n_art_count}")
    return result
