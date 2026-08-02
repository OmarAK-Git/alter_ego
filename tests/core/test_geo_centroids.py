from core.geo_centroids import GEO_CENTROIDS, haversine_km, lookup_centroid


def test_all_synthetic_generator_labels_have_centroids():
    # Labels currently emitted by batch/synthetic/generator.py EntityProfile.geography
    # and the hardcoded "RU-Moscow" injection.
    expected_labels = {"US-East", "US-West", "EU-Central", "AP-South", "US-East-DC1", "RU-Moscow"}
    missing = expected_labels - set(GEO_CENTROIDS.keys())
    assert not missing, f"missing centroid entries: {missing}"


def test_lookup_unknown_label_returns_none():
    assert lookup_centroid("Atlantis") is None


def test_haversine_known_distance():
    # NYC to LA is approximately 3936 km.
    nyc = (40.7128, -74.0060)
    la = (34.0522, -118.2437)
    dist = haversine_km(nyc, la)
    assert 3800 < dist < 4100
