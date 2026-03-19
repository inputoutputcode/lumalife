import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

import numpy as np

# user_dir passed per-call now
_executor = ThreadPoolExecutor(max_workers=2)

_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


def _estimate_age_sync(crop_path: str) -> float | None:
    """Estimate age from a face crop image."""
    DeepFace = _get_deepface()

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


async def estimate_age(crop_path: str, user_dir: str = "/data") -> float | None:
    """Async wrapper for age estimation."""
    loop = asyncio.get_event_loop()
    full_path = os.path.join(user_dir, crop_path) if not crop_path.startswith("/") else crop_path
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_sync, full_path),
        timeout=30.0,
    )


def build_age_year_mapping(
    tagged_photos: list[dict],
    age_estimates: list[dict],
) -> dict[str, int]:
    """
    Build photo_id -> estimated_year mapping using:
    1. EXIF dates (trusted as-is)
    2. User tags (anchor points)
    3. Age estimates + interpolation for the rest

    tagged_photos: [{"photo_id": str, "year": int}]
    age_estimates: [{"photo_id": str, "estimated_age": float, "exif_date": str|None}]
    """
    result = {}
    anchors = []  # (estimated_age, known_year) pairs

    # Build anchor points from tagged photos + their age estimates
    tag_map = {t["photo_id"]: t["year"] for t in tagged_photos}
    age_map = {a["photo_id"]: a for a in age_estimates}

    for photo_id, year in tag_map.items():
        result[photo_id] = year
        if photo_id in age_map:
            age = age_map[photo_id]["estimated_age"]
            anchors.append((age, year))

    # Add EXIF-dated photos
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

    if not anchors:
        # No anchors — use age estimates relative to current year
        from datetime import datetime
        current_year = datetime.now().year
        for ae in age_estimates:
            if ae["photo_id"] not in result:
                birth_year_est = current_year - ae["estimated_age"]
                result[ae["photo_id"]] = round(birth_year_est + ae["estimated_age"])
        return result

    # Sort anchors by age
    anchors.sort(key=lambda x: x[0])

    # For untagged/undated photos, interpolate using age + anchor curve
    if len(anchors) >= 2:
        anchor_ages = np.array([a[0] for a in anchors])
        anchor_years = np.array([a[1] for a in anchors])

        for ae in age_estimates:
            photo_id = ae["photo_id"]
            if photo_id in result:
                continue
            est_age = ae["estimated_age"]
            # Linear interpolation
            interpolated_year = np.interp(est_age, anchor_ages, anchor_years)
            result[photo_id] = round(float(interpolated_year))
    else:
        # Single anchor point
        anchor_age, anchor_year = anchors[0]
        for ae in age_estimates:
            photo_id = ae["photo_id"]
            if photo_id in result:
                continue
            age_diff = ae["estimated_age"] - anchor_age
            result[photo_id] = round(anchor_year + age_diff)

    return result


def assign_era_buckets(
    photo_years: dict[str, int], bucket_size: int = 5
) -> list[dict]:
    """Group photos into era buckets of ~bucket_size years."""
    if not photo_years:
        return []

    years = list(photo_years.values())
    min_year = min(years)
    max_year = max(years)

    # Align bucket starts to multiples of bucket_size
    bucket_start = (min_year // bucket_size) * bucket_size
    bucket_end = ((max_year // bucket_size) + 1) * bucket_size

    eras = []
    current = bucket_start
    while current < bucket_end:
        era_start = current
        era_end = current + bucket_size - 1
        era_photos = [
            pid for pid, y in photo_years.items()
            if era_start <= y <= era_end
        ]
        if era_photos:
            eras.append({
                "era_start": era_start,
                "era_end": era_end,
                "label": f"{era_start}–{era_end}",
                "photo_ids": era_photos,
            })
        current += bucket_size

    return eras
