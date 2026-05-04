import math

def compute_kl_divergence(p: float, q: float) -> float:
    if p == 0 or q == 0:
        return 0.0
    return p * math.log(p / q)

def get_laplace_prob(item_count: int, total_count: int, vocab_size: int, alpha: float = 1.0) -> float:
    return (item_count + alpha) / (total_count + alpha * vocab_size)
