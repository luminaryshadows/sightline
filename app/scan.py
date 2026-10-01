"""
CLI document scanner — main entry point for the Private Sight pipeline.

Usage:
    python -m app.scan <image_path>
    python -m app.scan demo_documents/prescription.png
    python -m app.scan demo_documents/prescription.png --json
    python -m app.scan demo_documents/prescription.png --question "How many tablets?"
"""

import argparse
import json
import os
import sys
import time

from ml.pipeline import create_pipeline, DocumentPipeline


def print_colored(text: str, color: str = ""):
    """Print with optional ANSI color."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    prefix = colors.get(color, "")
    suffix = colors["reset"] if prefix else ""
    print(f"{prefix}{text}{suffix}")


def print_analysis(analysis, show_full_text: bool = False):
    """Pretty-print document analysis results."""
    print_colored("\n" + "=" * 60, "cyan")
    print_colored("  PRIVATE SIGHT — Document Analysis", "bold")
    print_colored("=" * 60 + "\n", "cyan")

    # Quality
    if analysis.preprocessing:
        pq = analysis.preprocessing
        print_colored("📷 IMAGE QUALITY", "bold")
        print(f"  Brightness: {pq.brightness_score:.2f}  |  "
              f"Blur: {pq.blur_score:.2f}  |  "
              f"Contrast: {pq.contrast_score:.2f}")
        if pq.guidance_messages:
            for msg in pq.guidance_messages:
                print_colored(f"  ⚠ {msg}", "yellow")
        print()

    # Document type
    if analysis.classification:
        print_colored("📄 DOCUMENT TYPE", "bold")
        type_emoji = {
            "prescription": "💊",
            "banking": "🏦",
            "government": "🏛️",
            "bill": "🧾",
            "legal": "⚖️",
            "id": "🪪",
            "unknown": "❓",
        }
        dt = analysis.classification
        emoji = type_emoji.get(dt.document_type.value, "📄")
        conf_color = "green" if dt.confidence >= 0.7 else ("yellow" if dt.confidence >= 0.4 else "red")
        print(f"  {emoji} {dt.document_type.value.upper()}")
        print_colored(f"  Confidence: {dt.confidence:.2%}", conf_color)

        if dt.alternative_types:
            alts = ", ".join(f"{a.value} ({c:.0%})" for a, c in dt.alternative_types[:2])
            print(f"  Also considered: {alts}")
        print()

    # OCR Stats
    if analysis.ocr:
        print_colored("🔤 OCR RESULTS", "bold")
        print(f"  Text regions found: {len(analysis.ocr.regions)}")
        print(f"  Average confidence: {analysis.ocr.confidence:.2%}")
        if analysis.ocr.low_confidence_regions:
            print_colored(f"  Low-confidence regions: {len(analysis.ocr.low_confidence_regions)}", "yellow")
        print()

    # Sensitive Data
    if analysis.sensitive_data:
        sd = analysis.sensitive_data
        print_colored("🔒 SENSITIVE INFORMATION", "bold")
        status = "⚠ DETECTED" if sd.sensitive_information_detected else "✅ None detected"
        risk_color = "red" if sd.risk_level == "high" else ("yellow" if sd.risk_level in ("medium", "low") else "green")
        print_colored(f"  Status: {status}", risk_color)
        print(f"  Risk Level: {sd.risk_level.upper()}")
        if sd.sensitive_information_detected:
            print(f"  Entities found: {sd.entity_count}")
            type_counts = {}
            for e in sd.entities:
                type_counts[e.entity_type.value] = type_counts.get(e.entity_type.value, 0) + 1
            for t, c in sorted(type_counts.items()):
                print(f"    - {t}: {c}")
        print()

    # Extract
    if analysis.extraction:
        ex = analysis.extraction
        print_colored("📋 EXTRACTED INFORMATION", "bold")
        if ex.fields:
            for field in ex.fields:
                print(f"  {field.label}: {field.value[:100]}")
        if ex.monetary_values:
            for desc, amt in ex.monetary_values:
                print(f"  {desc}: {amt}")
        if ex.deadlines:
            for desc, date in ex.deadlines:
                print_colored(f"  ⏰ {desc}: {date}", "yellow")
        if ex.contacts:
            for t, v in ex.contacts:
                print(f"  📞 {t}: {v}")
        if ex.action_required and ex.action_required not in (
            "No immediate action identified.",
            "No action required.",
            "No specific action identified. Please review the document.",
        ):
            print_colored(f"  ⚡ ACTION: {ex.action_required}", "red")
        if ex.medical_disclaimer:
            print_colored(f"\n  ⚕ {ex.medical_disclaimer[:200]}...", "yellow")
        print()

    # Accessible summary
    print_colored("🗣 ACCESSIBLE SUMMARY", "bold")
    print(f"  {analysis.accessible_summary}")
    print()

    # Full text (if requested)
    if show_full_text and analysis.ocr:
        print_colored("📝 FULL OCR TEXT", "bold")
        print("-" * 40)
        print(analysis.ocr.full_text)
        print("-" * 40)
        print()

    # Warnings
    if analysis.warnings:
        print_colored("⚠ WARNINGS", "yellow")
        for w in analysis.warnings:
            print_colored(f"  • {w}", "yellow")
        print()

    print_colored(f"⏱ Processing time: {analysis.processing_time_ms:.0f}ms", "blue")
    print_colored("🔒 100% ON-DEVICE PROCESSING — No data sent to any server", "green")
    print_colored("=" * 60 + "\n", "cyan")


def main():
    parser = argparse.ArgumentParser(
        description="Private Sight — Privacy-first offline document analysis for visually impaired users",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.scan demo_documents/prescription.png
  python -m app.scan demo_documents/prescription.png --json
  python -m app.scan demo_documents/prescription.png --question "How many tablets?"
  python -m app.scan demo_documents/prescription.png --full-text
  python -m app.scan demo_documents/banking.png --json > result.json
        """,
    )
    parser.add_argument("image", help="Path to document image")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--full-text", action="store_true", help="Show full OCR text")
    parser.add_argument("--question", "-q", help="Ask a question about the document")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()

    # Validate image path
    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    print_colored(f"\n🔍 Analyzing: {args.image}", "cyan")
    print_colored("⏳ Initializing privacy-first document pipeline...\n", "blue")

    # Create pipeline and analyze
    try:
        pipeline = create_pipeline()
    except Exception as e:
        print_colored(f"Error initializing pipeline: {e}", "red")
        print("Make sure EasyOCR models are downloaded. Try running once with internet")
        print("to download models, then disable internet for subsequent runs.")
        sys.exit(1)

    try:
        analysis = pipeline.analyze(args.image)
    except Exception as e:
        print_colored(f"Error during analysis: {e}", "red")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Question answering (if requested)
    qa_answer = None
    if args.question:
        qa_answer = pipeline.ask_question(analysis, args.question)

    # Output
    if args.json:
        result = analysis.to_dict()
        if qa_answer:
            result["question_answering"] = {
                "question": qa_answer.question,
                "answer": qa_answer.answer,
                "confidence": qa_answer.confidence,
                "is_medical": qa_answer.is_medical,
            }
            if qa_answer.medical_disclaimer:
                result["question_answering"]["medical_disclaimer"] = qa_answer.medical_disclaimer
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_analysis(analysis, show_full_text=args.full_text)
        if qa_answer:
            print_colored("❓ QUESTION ANSWERING", "bold")
            print(f"  Q: {qa_answer.question}")
            print(f"  A: {qa_answer.answer}")
            if qa_answer.is_medical:
                print_colored(f"  ⚕ {qa_answer.medical_disclaimer[:200]}...", "yellow")
            print()


if __name__ == "__main__":
    main()
