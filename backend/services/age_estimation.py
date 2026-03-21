import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_executor = ThreadPoolExecutor(max_workers=2)

# ViT age classifier (lazy loaded)
_vit_model = None
_vit_processor = None

# Age range midpoints for weighted expectation
AGE_RANGE_MIDPOINTS = {
    0: 1,    # "0-2"   → midpoint 1
    1: 6,    # "3-9"   → midpoint 6
    2: 14.5, # "10-19" → midpoint 14.5
    3: 24.5, # "20-29" → midpoint 24.5
    4: 34.5, # "30-39" → midpoint 34.5
    5: 44.5, # "40-49" → midpoint 44.5
    6: 54.5, # "50-59" → midpoint 54.5
    7: 64.5, # "60-69" → midpoint 64.5
    8: 75,   # "70+"   → midpoint 75
}


def _get_vit():
    global _vit_model, _vit_processor
    if _vit_model is not None:
        return _vit_model, _vit_processor

    import torch
    from transformers import ViTImageProcessor, ViTForImageClassification

    _vit_model = ViTForImageClassification.from_pretrained('nateraw/vit-age-classifier')
    _vit_processor = ViTImageProcessor.from_pretrained('nateraw/vit-age-classifier')
    _vit_model.eval()
    print("ViT age classifier loaded")
    return _vit_model, _vit_processor


def _estimate_age_vit(crop_path: str) -> dict | None:
    """Estimate age using ViT age classifier (trained on FairFace, good with children)."""
    import torch
    from PIL import Image

    try:
        model, processor = _get_vit()
        img = Image.open(crop_path).convert('RGB')
        inputs = processor(img, return_tensors='pt')

        with torch.no_grad():
            output = model(**inputs)

        proba = output.logits.softmax(1)[0]

        # Weighted expected age from probability distribution
        expected_age = sum(
            proba[i].item() * AGE_RANGE_MIDPOINTS[i]
            for i in range(len(proba))
        )

        # Also get the top prediction for label
        pred_idx = proba.argmax().item()
        pred_label = model.config.id2label[pred_idx]
        confidence = proba[pred_idx].item()

        return {
            "age": round(expected_age, 1),
            "age_range": pred_label,
            "confidence": round(confidence, 3),
            "method": "vit",
        }
    except Exception as e:
        print(f"ViT age estimation failed: {e}")
    return None


def _estimate_age_deepface(crop_path: str) -> float | None:
    """Fallback: estimate age using DeepFace."""
    from deepface import DeepFace
    try:
        result = DeepFace.analyze(
            img_path=crop_path,
            actions=["age"],
            detector_backend="skip",
            enforce_detection=False,
            silent=True,
        )
        if isinstance(result, list) and len(result) > 0:
            return float(result[0].get("age", 0))
        elif isinstance(result, dict):
            return float(result.get("age", 0))
    except Exception:
        pass
    return None


async def estimate_age(crop_path: str, user_dir: str = "/data",
                       image_path: str | None = None, bbox: dict | None = None) -> float | None:
    """Estimate age — tries ViT (best for children), falls back to DeepFace."""
    full_path = os.path.join(user_dir, crop_path) if not crop_path.startswith("/") else crop_path

    loop = asyncio.get_event_loop()

    # Best: ViT age classifier (good with all ages including children)
    result = await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_vit, full_path),
        timeout=30.0,
    )
    if result is not None:
        return result["age"]

    # Fallback: DeepFace on CPU
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_deepface, full_path),
        timeout=30.0,
    )


async def estimate_age_detailed(crop_path: str, user_dir: str = "/data") -> dict | None:
    """Estimate age with full details (range, confidence, method)."""
    full_path = os.path.join(user_dir, crop_path) if not crop_path.startswith("/") else crop_path

    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_vit, full_path),
        timeout=30.0,
    )
    if result is not None:
        return result

    age = await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_deepface, full_path),
        timeout=30.0,
    )
    if age is not None:
        return {"age": age, "age_range": None, "confidence": None, "method": "deepface"}
    return None


def build_age_year_mapping(
    tagged_photos: list[dict],
    age_estimates: list[dict],
    birth_year: int | None = None,
) -> dict[str, int]:
    """
    Build photo_id -> estimated_year mapping using:
    1. EXIF dates (trusted as-is)
    2. User tags (anchor points)
    3. Age estimates + interpolation for the rest
    """
    result = {}
    anchors = []

    tag_map = {t["photo_id"]: t["year"] for t in tagged_photos}
    age_map = {a["photo_id"]: a for a in age_estimates}

    for photo_id, year in tag_map.items():
        result[photo_id] = year
        if photo_id in age_map:
            age = age_map[photo_id]["estimated_age"]
            anchors.append((age, year))

    for ae in age_estimates:
        photo_id = ae["photo_id"]
        if photo_id in result:
            continue
        if ae.get("exif_date"):
            try:
                exif_year = int(ae["exif_date"][:4])
                if 1900 <= exif_year <= 2030:
                    result[photo_id] = exif_year
                    anchors.append((ae["estimated_age"], exif_year))
                    continue
            except (ValueError, TypeError):
                pass

    if birth_year is not None:
        for ae in age_estimates:
            photo_id = ae["photo_id"]
            if photo_id in result:
                continue
            if ae["estimated_age"] is not None:
                result[photo_id] = birth_year + round(ae["estimated_age"])
        return result

    if not anchors:
        return result

    anchors.sort(key=lambda x: x[0])

    if len(anchors) >= 2:
        anchor_ages = np.array([a[0] for a in anchors])
        anchor_years = np.array([a[1] for a in anchors])

        for ae in age_estimates:
            photo_id = ae["photo_id"]
            if photo_id in result:
                continue
            est_age = ae["estimated_age"]
            interpolated_year = np.interp(est_age, anchor_ages, anchor_years)
            result[photo_id] = round(float(interpolated_year))
    else:
        anchor_age, anchor_year = anchors[0]
        for ae in age_estimates:
            photo_id = ae["photo_id"]
            if photo_id in result:
                continue
            age_diff = ae["estimated_age"] - anchor_age
            result[photo_id] = round(anchor_year + age_diff)

    return result


def assign_era_buckets(
    photo_years: dict[str, int], min_photos_per_year: int = 2
) -> list[dict]:
    """Group photos into eras."""
    if not photo_years:
        return []

    from collections import Counter
    year_counts = Counter(photo_years.values())
    all_years = sorted(year_counts.keys())

    eras = []
    merge_buffer = []

    def flush_merge_buffer():
        if not merge_buffer:
            return
        buf_start = merge_buffer[0]
        buf_end = merge_buffer[-1]
        buf_photos = [pid for pid, y in photo_years.items() if buf_start <= y <= buf_end]
        label = str(buf_start) if buf_start == buf_end else f"{buf_start}–{buf_end}"
        eras.append({
            "era_start": buf_start,
            "era_end": buf_end,
            "label": label,
            "photo_ids": buf_photos,
        })
        merge_buffer.clear()

    for year in all_years:
        if year_counts[year] >= min_photos_per_year:
            flush_merge_buffer()
            photos = [pid for pid, y in photo_years.items() if y == year]
            eras.append({
                "era_start": year,
                "era_end": year,
                "label": str(year),
                "photo_ids": photos,
            })
        else:
            merge_buffer.append(year)

    flush_merge_buffer()

    eras.sort(key=lambda e: e["era_start"])
    return eras
