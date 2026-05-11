import math
from typing import Dict

def compute_kl_divergence(p: float, q: float) -> float:
    if p <= 0 or q <= 0:
        return 0.0
    return p * math.log(p / q)

def get_laplace_prob(item_count: int, total_count: int, vocab_size: int, alpha: float = 1.0) -> float:
    return (item_count + alpha) / (total_count + alpha * vocab_size)

def compute_distribution_kl(dist_p: Dict[str, int], dist_q: Dict[str, int], alpha: float = 1.0) -> float:
    """Computes KL divergence between two histograms using Laplace smoothing."""
    # Build common vocabulary
    vocab = set(dist_p.keys()).union(set(dist_q.keys()))
    vocab_size = len(vocab)
    
    total_p = sum(dist_p.values())
    total_q = sum(dist_q.values())
    
    kl = 0.0
    for key in vocab:
        count_p = dist_p.get(key, 0)
        count_q = dist_q.get(key, 0)
        
        prob_p = get_laplace_prob(count_p, total_p, vocab_size, alpha)
        prob_q = get_laplace_prob(count_q, total_q, vocab_size, alpha)
        
        kl += prob_p * math.log(prob_p / prob_q)
    
    return kl

def exponential_decay(current_val: float, delta: float, half_life_days: float, time_delta_days: float) -> float:
    """Updates a value using exponential decay: V_new = V_old * (0.5 ^ (t/h)) + delta"""
    if half_life_days <= 0:
        return delta
    decay_factor = math.pow(0.5, time_delta_days / half_life_days)
    return current_val * decay_factor + delta
