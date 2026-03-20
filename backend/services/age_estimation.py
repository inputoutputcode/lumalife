import os
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_executor = ThreadPoolExecutor(max_workers=2)

MIVOLO_URL = os.environ.get("MIVOLO_URL", "http://mivolo:8010")

_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


def _estimate_age_deepface(crop_path: str) -> float | None:
    """Fallback: estimate age using DeepFace."""
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


async def _estimate_age_mivolo_crop(crop_path: str) -> dict | None:
    """Estimate age from a face crop via MiVOLO."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(crop_path, "rb") as f:
                resp = await client.post(
                    f"{MIVOLO_URL}/analyze-crop",
                    files={"file": ("face.jpg", f, "image/jpeg")},
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("age") is not None:
                    return {"age": float(data["age"]), "gender": data.get("gender")}
    except Exception as e:
        print(f"MiVOLO crop estimation failed: {e}")
    return None


async def _estimate_age_mivolo_full(image_path: str, bbox: dict) -> dict | None:
    """Estimate age from the FULL image + known face bbox (better accuracy with body context)."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(image_path, "rb") as f:
                resp = await client.post(
                    f"{MIVOLO_URL}/analyze-with-bbox",
                    files={"file": ("photo.jpg", f, "image/jpeg")},
                    data={
                        "x": str(bbox.get("x", 0)),
                        "y": str(bbox.get("y", 0)),
                        "w": str(bbox.get("w", 0)),
                        "h": str(bbox.get("h", 0)),
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("age") is not None:
                    return {"age": float(data["age"]), "gender": data.get("gender")}
    except Exception as e:
        print(f"MiVOLO full-image estimation failed: {e}")
    return None


async def estimate_age(crop_path: str, user_dir: str = "/data",
                       image_path: str | None = None, bbox: dict | None = None) -> float | None:
    """Estimate age — tries MiVOLO with full image + bbox first (best accuracy),
    falls back to crop-only, then DeepFace."""
    
    # Best: full image with bbox (face + body context)
    if image_path and bbox:
        result = await _estimate_age_mivolo_full(image_path, bbox)
        if result is not None:
            return result["age"]

    # Good: crop only via MiVOLO
    full_path = os.path.join(user_dir, crop_path) if not crop_path.startswith("/") else crop_path
    result = await _estimate_age_mivolo_crop(full_path)
    if result is not None:
        return result["age"]

    # Fallback: DeepFace on CPU
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_deepface, full_path),
        timeout=30.0,
    )


async def estimate_age_full(crop_path: str, user_dir: str = "/data") -> dict | None:
    """Estimate age + gender — tries MiVOLO first, falls back to DeepFace (age only)."""
    full_path = os.path.join(user_dir, crop_path) if not crop_path.startswith("/") else crop_path

    # Try MiVOLO first
    result = await _estimate_age_mivolo(full_path)
    if result is not None:
        return result

    # Fallback
    loop = asyncio.get_event_loop()
    age = await asyncio.wait_for(
        loop.run_in_executor(_executor, _estimate_age_deepface, full_path),
        timeout=30.0,
    )
    if age is not None:
        return {"age": age, "gender": None}
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

    # If birth year is known, use it directly for all untagged photos
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
    """Group photos into eras. Years with >= min_photos_per_year get their own era.
    Years with fewer photos are merged into ranges with adjacent years."""
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
