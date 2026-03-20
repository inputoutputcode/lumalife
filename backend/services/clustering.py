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


def cluster_faces(
    face_ids: list[str],
    embeddings: np.ndarray,
    excluded_pairs: list[tuple[str, str]] | None = None,
) -> dict[str, int]:
    """Cluster face embeddings using DBSCAN with optional negative feedback.
    
    excluded_pairs: list of (face_id_a, face_id_b) that should NOT be in the same cluster.
    These come from user deletions — if a face was removed from a cluster, it means
    it doesn't belong with the remaining faces.
    """
    if len(embeddings) < 2:
        if len(face_ids) == 1:
            return {face_ids[0]: 0}
        return {}

    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms

    # Compute cosine distance matrix
    from sklearn.metrics.pairwise import cosine_distances
    dist_matrix = cosine_distances(normalized)

    # Apply negative feedback: inflate distance for excluded pairs
    if excluded_pairs:
        id_to_idx = {fid: i for i, fid in enumerate(face_ids)}
        for fid_a, fid_b in excluded_pairs:
            if fid_a in id_to_idx and fid_b in id_to_idx:
                i, j = id_to_idx[fid_a], id_to_idx[fid_b]
                dist_matrix[i][j] = 2.0  # Max distance — ensure they never cluster
                dist_matrix[j][i] = 2.0

    # DBSCAN with precomputed distance matrix
    clustering = DBSCAN(
        eps=0.55,
        min_samples=2,
        metric="precomputed",
    ).fit(dist_matrix)

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
