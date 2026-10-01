#!/usr/bin/env python3
"""
Benchmark the Private Sight pipeline performance.

Measures:
- Model size on disk
- OCR latency
- Total pipeline latency
- Peak RAM (if psutil available)

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --image demo_documents/prescription.png
    python scripts/benchmark.py --all
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_model_sizes() -> dict:
    """Get sizes of cached models."""
    cache_dir = os.path.expanduser("~/.EasyOCR/model")
    sizes = {}
    if os.path.exists(cache_dir):
        for fname in os.listdir(cache_dir):
            fpath = os.path.join(cache_dir, fname)
            if os.path.isfile(fpath):
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                sizes[fname] = round(size_mb, 2)
    return sizes


def get_peak_ram() -> float | None:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def benchmark_pipeline(image_path: str, runs: int = 1) -> dict:
    """Benchmark the complete pipeline."""
    from ml.pipeline import create_pipeline

    pipeline = create_pipeline()
    results = {"image": image_path, "runs": runs, "per_run": []}

    total_ms = 0.0
    for i in range(runs):
        print(f"  Run {i + 1}/{runs}...", end=" ", flush=True)
        start = time.time()
        analysis = pipeline.analyze(image_path)
        elapsed_ms = (time.time() - start) * 1000
        total_ms += elapsed_ms

        run_data = {
            "run": i + 1,
            "total_ms": round(elapsed_ms),
            "ocr_regions": len(analysis.ocr.regions) if analysis.ocr else 0,
            "ocr_confidence": analysis.ocr.confidence if analysis.ocr else 0,
            "doc_type": analysis.classification.document_type.value if analysis.classification else "unknown",
            "classification_confidence": analysis.classification.confidence if analysis.classification else 0,
        }
        results["per_run"].append(run_data)
        print(f"{elapsed_ms:.0f}ms")

    results["avg_total_ms"] = round(total_ms / runs)
    results["min_ms"] = min(r["total_ms"] for r in results["per_run"])
    results["max_ms"] = max(r["total_ms"] for r in results["per_run"])
    results["peak_ram_mb"] = get_peak_ram()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Private Sight pipeline performance"
    )
    parser.add_argument("--image", default="demo_documents/prescription.png",
                        help="Document image to benchmark")
    parser.add_argument("--all", action="store_true",
                        help="Benchmark all demo documents")
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of runs per document")
    args = parser.parse_args()

    print("=" * 60)
    print("  Private Sight — Performance Benchmark")
    print("=" * 60)
    print()

    # Model sizes
    print("📦 Model Sizes:")
    sizes = get_model_sizes()
    total_size = 0
    for name, size_mb in sorted(sizes.items()):
        print(f"  {name}: {size_mb} MB")
        total_size += size_mb
    print(f"  Total: {total_size:.2f} MB")
    print()

    # Check CPU info
    import platform
    print(f"🖥 Platform: {platform.platform()}")
    print(f"  Python: {sys.version.split()[0]}")
    try:
        import torch
        print(f"  PyTorch: {torch.__version__}")
    except ImportError:
        pass
    print()

    # Benchmark
    print("⏱ Pipeline Benchmarks:")
    print()

    if args.all:
        docs = [
            "demo_documents/prescription.png",
            "demo_documents/banking.png",
            "demo_documents/government_letter.png",
        ]
    else:
        docs = [args.image]

    all_results = []
    for doc_path in docs:
        if not os.path.exists(doc_path):
            print(f"  ⚠ Skipping {doc_path} — not found")
            continue

        print(f"📄 {doc_path}:")
        results = benchmark_pipeline(doc_path, runs=args.runs)
        all_results.append(results)

        print(f"  Average: {results['avg_total_ms']}ms")
        print(f"  Min: {results['min_ms']}ms, Max: {results['max_ms']}ms")
        if results.get("peak_ram_mb"):
            print(f"  Peak RAM: {results['peak_ram_mb']:.1f} MB")
        print()

    # Summary
    if len(all_results) > 1:
        avg_all = sum(r["avg_total_ms"] for r in all_results) / len(all_results)
        print(f"📊 Overall Average: {avg_all:.0f}ms across {len(all_results)} documents")
        print()


if __name__ == "__main__":
    main()
