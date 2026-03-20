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
    photo_years: dict[str, int], min_photos_per_year: int = 3
) -> list[dict]:
    """Group photos into eras. Years with >= min_photos_per_year get their own era.
    Years with fewer photos are merged into ranges with adjacent years."""
    if not photo_years:
        return []

    # Count photos per year
    from collections import Counter
    year_counts = Counter(photo_years.values())
    all_years = sorted(year_counts.keys())

    # Separate years that stand alone vs need merging
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

    # Sort by era_start
    eras.sort(key=lambda e: e["era_start"])
    return eras
