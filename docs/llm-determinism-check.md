# LLM Determinism Check (§8.4)

**Date:** 2026-05-04T17:35:48.369073
**Model ID:** claude-3-sonnet-20240229
**Temperature:** 0.0
**Prompt:** `Explain why logging in from a new geolocation at 3 AM is suspicious, given the user has never done this before. Keep it to two sentences.`

## Results

| Run | Output Hash | Output Length |
|-----|-------------|---------------|
| 1 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 2 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 3 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 4 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 5 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 6 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 7 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 8 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 9 | `0a90ecb11622b669f62e8dc013b90eed1e49e51411d6d30df60b686b9389489a` | 150 |
| 10 | `489ad9fef30ebb28041fcc5d09730768b41d4bf944665000679c51cbae592b9f` | 151 |

## Conclusion

The provider **is NOT** byte-identical deterministic. Observed 2 unique outputs across 10 runs.
> **Note**: This confirms the architectural decision in §8.4: lineage is the single authoritative record, and the system must not rely on provider reproducibility.
