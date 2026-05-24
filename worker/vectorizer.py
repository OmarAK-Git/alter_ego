import numpy as np
import hashlib
import re

# Normalizer Version per SPEC §6.8
NORMALIZER_VERSION = "1.0-char-3gram-hash-128"

def normalize_command_line(cmd: str) -> str:
    """
    Normalizes command line strings for vectorization.
    
    Preserves: Alphanumeric characters, common delimiters, and arguments.
    Strips: Extra whitespace, specific hex-like patterns (potential session IDs/addresses).
    
    Rationale: 
    Preserving arguments is critical for detecting malicious flag usage (e.g., -ep, -EncodedCommand).
    Stripping arguments would create a massive blind spot for attackers to hide payloads.
    Prompt injection (e.g., "ignore previous instructions") is mitigated by using 
    character-level n-grams rather than word-level semantic embeddings, making the 
    vectorizer focus on structural patterns rather than semantic commands.
    """
    if not cmd:
        return ""
    # Lowercase
    cmd = cmd.lower()
    # Strip potential hex addresses (0x...)
    cmd = re.sub(r'0x[0-9a-f]+', '0xADDR', cmd)
    # Collapse whitespace
    cmd = " ".join(cmd.split())
    return cmd

def vectorize_command_line(cmd: str, dim: int = 128) -> np.ndarray:
    """
    Produces a deterministic character-level 3-gram hashing vector.
    """
    norm = normalize_command_line(cmd)
    vec = np.zeros(dim, dtype=np.float32)
    
    if not norm:
        return vec
        
    # Sliding window of 3-grams
    for i in range(len(norm) - 2):
        gram = norm[i:i+3]
        # Use SHA-256 for stable hashing across environments
        h = hashlib.sha256(gram.encode()).hexdigest()
        idx = int(h, 16) % dim
        vec[idx] += 1.0
        
    # L2 Normalization
    norm_val = np.linalg.norm(vec)
    if norm_val > 0:
        vec = vec / norm_val
        
    return vec

def compute_cosine_distance(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Returns cosine distance (1 - cosine similarity) between two unit vectors.
    Range: [0, 2]
    """
    # Dot product of unit vectors is cosine similarity
    sim = np.dot(v1, v2)
    # Clip to avoid floating point errors out of range [-1, 1]
    sim = np.clip(sim, -1.0, 1.0)
    return 1.0 - float(sim)
