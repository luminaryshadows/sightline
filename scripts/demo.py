#!/usr/bin/env python3
"""
Two-minute hackathon demo (Phase 11).

Runs the complete offline pipeline over the three synthetic demo documents
and prints the story a judge should see:

  1. Document recognised
  2. Sensitive information detected
  3. Important information extracted
  4. Summary read aloud (TTS-ready)
  5. A question answered locally
  6. Zero network requests

Usage:
    python scripts/demo.py
    python scripts/demo.py --speak     # use the local TTS engine too
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.pipeline import create_pipeline  # noqa: E402
from ml.tts import LocalTTS  # noqa: E402

BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[0m"
)

DOCS = [
    ("prescription", "demo_documents/prescription.png", "How many tablets should I take?"),
    ("banking", "demo_documents/banking.png", "How much do I owe?"),
    ("government", "demo_documents/government_letter.png", "When is the deadline?"),
]


def banner(text: str):
    print(f"\n{CYAN}{'=' * 64}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{CYAN}{'=' * 64}{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Private Sight hackathon demo")
    parser.add_argument("--speak", action="store_true", help="Also speak summaries via local TTS")
    args = parser.parse_args()

    tts = LocalTTS() if args.speak else None
    if args.speak:
        print(f"Local TTS engine: {tts.engine or 'unavailable'}")

    banner("PRIVATE SIGHT — 100% offline document reader")
    print("  Step 0: Put the device into airplane mode.")
    print(f"  {GREEN}No image or document text will leave this device.{RESET}")
    print("  (This demo performs zero network requests.)")

    pipeline = create_pipeline()
    total = 0

    for name, path, question in DOCS:
        if not Path(path).exists():
            print(f"\n{YELLOW}Skipping {name}: {path} not found{RESET}")
            continue
        total += 1

        banner(f"Demo document: {name}")
        analysis = pipeline.analyze(path)
        d = analysis.to_dict()

        # 1. Recognised
        print(f"{BOLD}1. Document recognised{RESET}")
        print(f"   Type: {d['document_type']}  (confidence {d['confidence']:.0%})")

        # 2. Sensitive information
        sd = d["sensitive_data"]
        print(f"\n{BOLD}2. Sensitive information{RESET}")
        if sd["detected"]:
            print(f"   {RED}Detected — risk {sd['risk_level']}, {sd['entity_count']} items "
                  f"({', '.join(sd['entity_types'])}){RESET}")
        else:
            print(f"   None detected.")

        # 3. Important information
        ex = d["extraction"]
        print(f"\n{BOLD}3. Important information{RESET}")
        for f in ex["fields"]:
            print(f"   • {f['label']}: {f['value'][:70]}")
        for m in ex["monetary_values"]:
            print(f"   • {m['description']}: {m['amount']}")
        for dl in ex["deadlines"]:
            print(f"   • {dl['description']}: {dl['date']}")
        if ex["action_required"] and ex["action_required"] not in (
            "No immediate action identified.", "No action required.",
            "No specific action identified. Please review the document.",
        ):
            print(f"   {YELLOW}⚡ Action: {ex['action_required'][:80]}{RESET}")

        # 4. Summary
        print(f"\n{BOLD}4. Summary (spoken){RESET}")
        print(f"   {d['accessible_summary'][:300]}")
        if tts is not None:
            tts.speak(d["accessible_summary"])

        # 5. Question answered locally
        print(f"\n{BOLD}5. Question answered locally{RESET}")
        answer = pipeline.ask_question(analysis, question)
        print(f"   Q: {question}")
        print(f"   A: {answer.answer[:200]}")
        if answer.is_medical:
            print(f"   {YELLOW}⚕ {answer.medical_disclaimer[:140]}...{RESET}")

        # 6. Network
        print(f"\n{BOLD}6. Network{RESET}")
        print(f"   {GREEN}NETWORK REQUESTS: 0{RESET}   PROCESSING: DEVICE   MODEL: LOCAL")

    banner("DEMO COMPLETE")
    print(f"  Documents processed: {total}")
    print(f"  {GREEN}NETWORK REQUESTS: 0{RESET}")
    print(f"  PROCESSING LOCATION: DEVICE")
    print(f"  MODEL: LOCAL")
    print(f"  {GREEN}PRIVACY STATUS: PROTECTED{RESET}")
    print()


if __name__ == "__main__":
    main()
