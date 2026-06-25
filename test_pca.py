"""Test the PCA computation endpoint/function.

Run with: python test_pca.py
"""
from gex_viewer import _compute_pca


def main():
    result = _compute_pca()
    print(f"PCA status: {result.get('status')}")
    assert result["status"] == "ok", f"PCA failed: {result.get('reason')}"
    assert result["n_samples"] > 0, "No samples used"
    assert result["n_features"] > 0, "No features used"
    assert len(result["explained_variance_ratio"]) > 0, "No explained variance returned"
    assert len(result["components"]) > 0, "No components returned"
    print(f"PASS: PCA computed on {result['n_samples']} samples with {result['n_features']} features")
    print(f"  First 3 explained variance ratios: {result['explained_variance_ratio'][:3]}")
    print(f"  HMM features: {result['hmm_features']}")


if __name__ == "__main__":
    main()
