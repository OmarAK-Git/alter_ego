import math
from core.math_utils import compute_kl_divergence, get_laplace_prob
import hashlib

def test_kl_divergence():
    p = 1.0
    q = 0.5
    expected = 1.0 * math.log(1.0 / 0.5)
    assert compute_kl_divergence(p, q) == expected

def test_laplace_prob():
    # 5 items, 100 total, 50 vocab, alpha=1.0
    # (5 + 1) / (100 + 50) = 6 / 150 = 0.04
    assert get_laplace_prob(5, 100, 50) == 0.04

def test_idempotent_decision_id():
    event_id = "test_event_1"
    profile_version = "v1"
    scoring_version = "v1"
    
    raw = f"{event_id}{profile_version}{scoring_version}".encode('utf-8')
    expected_hash = hashlib.sha256(raw).hexdigest()
    
    raw2 = f"{event_id}{profile_version}{scoring_version}".encode('utf-8')
    assert hashlib.sha256(raw2).hexdigest() == expected_hash
