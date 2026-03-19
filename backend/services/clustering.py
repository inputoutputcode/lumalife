import json

import numpy as np
from sklearn.cluster import DBSCAN


def load_embeddings(face_records: list[dict]) -> tuple[list[str], np.ndarray]:
    """Load embeddings from face records (from DB query results).

    face_records: list of dicts with 'face_id' and 'embedding' (list[float] or JSON string).
    """
    face_ids = []
    embeddings = []

    for face in face_records:
        embedding = face.get("embedding")
        if embedding is None:
            continue

        # Handle string (from DB vector::text cast) or list
        if isinstance(embedding, str):
            embedding = json.loads(embedding)

        if embedding and len(embedding) > 0:
            face_ids.append(face["face_id"])
            embeddings.append(embedding)

    if not embeddings:
        return [], np.array([])

    return face_ids, np.array(embeddings)


def cluster_faces(face_ids: list[str], embeddings: np.ndarray) -> dict[str, int]:
    """Cluster face embeddings using DBSCAN. Returns face_id -> cluster_id mapping."""
    if len(embeddings) < 2:
        if len(face_ids) == 1:
            return {face_ids[0]: 0}
        return {}

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms

    # Cosine distance via DBSCAN
    clustering = DBSCAN(
        eps=0.68,
        min_samples=2,
        metric="cosine",
    ).fit(normalized)

    labels = clustering.labels_

    result = {}
    for face_id, label in zip(face_ids, labels):
        result[face_id] = int(label)  # -1 means noise/unclustered

    return result


def get_cluster_stats(assignments: dict[str, int]) -> list[dict]:
    """Get cluster sizes sorted by largest first."""
    clusters: dict[int, int] = {}
    for face_id, cluster_id in assignments.items():
        if cluster_id == -1:
            continue
        clusters[cluster_id] = clusters.get(cluster_id, 0) + 1

    sorted_clusters = sorted(clusters.items(), key=lambda x: x[1], reverse=True)
    return [{"cluster_id": cid, "face_count": count} for cid, count in sorted_clusters]
