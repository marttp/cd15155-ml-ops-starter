"""
Smoke test to confirm the model loads correctly
and runs a basic inference.

Uses the same model loader as the service, including the supplied FinBERT
label correction. The correction stays in memory and does not edit Hub files.

Run:
    python scripts/smoke_test.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils import load_huggingface_classifier


def check_model():
    model_id = os.getenv("HF_MODEL_ID", "baptle/FinBERT_market_based")
    print(f"Loading {model_id} model...")
    try:
        classifier = load_huggingface_classifier(model_id)
        result = classifier("The company reported record profits this quarter.")
        assert result and result[0]["label"] in {"positive", "negative", "neutral"}
        print(f"Model loaded and inference OK  -->  {result[0]}")
        return True
    except Exception as e:
        print(f"[FAIL] Model check failed: {e}")
        return False


def main():
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 50)
    print("  FinBERT Market Smoke Test")
    print("=" * 50)

    passed = check_model()

    print("=" * 50)
    if passed:
        print("  All checks passed.")
        sys.exit(0)
    else:
        print("  Smoke test FAILED. Fix the errors above before continuing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
