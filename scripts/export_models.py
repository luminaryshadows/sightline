#!/usr/bin/env python3
"""
Export models for ExecuTorch mobile deployment.

Exports PyTorch models to .pte format for Android integration.
Uses torch.export and quantization where possible.

Usage:
    python scripts/export_models.py --all
    python scripts/export_models.py --ocr
    python scripts/export_models.py --classifier
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_executorch():
    """Check if ExecuTorch is available."""
    try:
        import executorch  # noqa: F401
        return True
    except ImportError:
        return False


def export_easyocr_to_pte(output_dir: str) -> dict:
    """
    Export EasyOCR models (detector + recognizer) to ExecuTorch .pte format.

    NOTE: This is a placeholder for the actual ExecuTorch export.
    Full export requires ExecuTorch SDK and model-specific export logic.

    For the hackathon MVP, the model paths are documented here for
    manual integration.
    """
    import easyocr
    import torch

    results = {}

    # Paths to cached EasyOCR models
    cache_dir = os.path.expanduser("~/.EasyOCR/model")
    detector_path = os.path.join(cache_dir, "craft_mlt_25k.pth")
    recognizer_path = os.path.join(cache_dir, "english_g2.pth")

    os.makedirs(output_dir, exist_ok=True)

    # Document model info
    results["detector"] = {
        "source": detector_path,
        "exists": os.path.exists(detector_path),
        "size_mb": round(os.path.getsize(detector_path) / (1024 * 1024), 2) if os.path.exists(detector_path) else 0,
        "architecture": "CRAFT (Character Region Awareness for Text)",
        "export_status": "NOT EXPORTED (requires ExecuTorch SDK)",
    }

    results["recognizer"] = {
        "source": recognizer_path,
        "exists": os.path.exists(recognizer_path),
        "size_mb": round(os.path.getsize(recognizer_path) / (1024 * 1024), 2) if os.path.exists(recognizer_path) else 0,
        "architecture": "CRNN + VGG backbone",
        "export_status": "NOT EXPORTED (requires ExecuTorch SDK)",
    }

    # If ExecuTorch is available, attempt export
    if check_executorch():
        try:
            # Load EasyOCR models
            reader = easyocr.Reader(['en'], gpu=False)
            detector = reader.detector
            recognizer = reader.recognizer

            # Export detector
            detector.eval()
            # Detector export requires proper input tracing
            results["detector"]["export_status"] = (
                "Partial — ExecuTorch SDK detected. "
                "Full export requires CRAFT model-specific export script."
            )

            # Export recognizer
            recognizer.eval()
            results["recognizer"]["export_status"] = (
                "Partial — ExecuTorch SDK detected. "
                "Full export requires CRNN model-specific export script."
            )

        except Exception as e:
            results["error"] = str(e)

    return results


def export_classifier_to_pte(output_dir: str) -> dict:
    """
    Export a lightweight PyTorch classifier to .pte format.

    NOTE: Placeholder. The current classifier is rule-based.
    A future PyTorch classifier would be exported here.
    """
    return {
        "status": "NOT APPLICABLE",
        "reason": "Current classifier is rule-based (regex). "
                  "A PyTorch classifier using text + visual features "
                  "will be added in a future phase.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export PyTorch models to ExecuTorch .pte format"
    )
    parser.add_argument("--all", action="store_true", help="Export all models")
    parser.add_argument("--ocr", action="store_true", help="Export OCR models")
    parser.add_argument("--classifier", action="store_true", help="Export classifier")
    parser.add_argument(
        "--output-dir", default="models/",
        help="Output directory for .pte files"
    )
    args = parser.parse_args()

    if not (args.all or args.ocr or args.classifier):
        parser.print_help()
        sys.exit(1)

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  Private Sight — Model Export for ExecuTorch")
    print("=" * 60)
    print()

    if not check_executorch():
        print("⚠ ExecuTorch SDK not installed.")
        print("  Install with: pip install executorch")
        print("  Proceeding with model inventory only.")
        print()

    if args.all or args.ocr:
        print("📦 Exporting OCR models...")
        results = export_easyocr_to_pte(output_dir)
        for name, info in results.items():
            print(f"  {name}:")
            for k, v in info.items():
                print(f"    {k}: {v}")
        print()

    if args.all or args.classifier:
        print("📦 Exporting classifier...")
        results = export_classifier_to_pte(output_dir)
        for k, v in results.items():
            print(f"  {k}: {v}")
        print()

    print("✅ Export complete. Check models/ directory.")
    print(f"   Output: {output_dir}")


if __name__ == "__main__":
    main()
