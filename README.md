# Private Sight 🕶️

**Privacy-first, fully offline AI visual assistant for blind and visually impaired users.**

Imperial College Hackathon Project — 2026

---

## What It Does

Private Sight reads sensitive documents aloud using only on-device AI.
**Nothing leaves the device.** No cloud, no API calls, no telemetry.

Point a phone camera at a medical prescription, bank statement, government
letter, bill, or ID document — the system:

1. Detects and crops the document
2. Reads the text (OCR)
3. Classifies the document type
4. Detects sensitive information (names, account numbers, medications, etc.)
5. Extracts important information (dosages, amounts, deadlines)
6. Reads a spoken summary
7. Answers questions about the document

**Works in airplane mode.**

---

## Quick Start

### Prerequisites

- Python 3.11+
- macOS, Linux, or Windows

### Install

```bash
cd private-sight
pip install -r requirements.txt
```

### One-Time Model Download

EasyOCR models are cached locally after first download.
Run once with internet:

```bash
python3 -c "import easyocr; easyocr.Reader(['en'], gpu=False)"
```

After this, **disconnect from the internet** — everything works offline.

### Scan a Document

```bash
# Basic scan
python -m app.scan demo_documents/prescription.png

# JSON output (for integration)
python -m app.scan demo_documents/prescription.png --json

# Ask a question
python -m app.scan demo_documents/prescription.png --question "How many tablets?"

# Show full OCR text
python -m app.scan demo_documents/prescription.png --full-text
```

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
private-sight/
├── app/                    # CLI application
│   └── scan.py             # Main CLI entry point
├── ml/                     # ML pipeline modules
│   ├── preprocessing/      # Image quality & enhancement
│   ├── ocr/                # PyTorch-based OCR (EasyOCR)
│   ├── classifier/         # Document type classification
│   ├── sensitive_data/     # PII & sensitive data detection
│   ├── extraction/         # Structured field extraction
│   ├── qa/                 # Offline question answering
│   └── pipeline.py         # End-to-end pipeline orchestrator
├── demo_documents/         # Synthetic demo documents
│   ├── prescription.png
│   ├── banking.png
│   └── government_letter.png
├── tests/                  # Automated tests
├── models/                 # Exported model files (ExecuTorch)
├── scripts/                # Export, benchmark, utility scripts
├── docs/                   # Architecture and privacy docs
└── android/                # Android app (Kotlin)
```

---

## Architecture

Each module is independently replaceable:

| Module | Interface | Current Implementation |
|--------|-----------|----------------------|
| OCR | `DocumentOCR` | EasyOCR (CRAFT + CRNN) |
| Classification | `DocumentClassifier` | Regex rules + keyword scoring |
| Sensitive Data | `SensitiveDataDetector` | Regex patterns |
| Extraction | `DocumentExtractor` | Doc-type-specific regex |
| QA | `OfflineQuestionAnswerer` | Keyword retrieval |

### Pipeline Flow

```
Image → Preprocess → OCR → Classify → Detect Sensitive Data → Extract → Summary
                                                                      ↓
                                                              Question Answering
```

---

## Demo Documents

Three safe, synthetic documents for testing (no real personal data):

1. **Prescription** — Amoxicillin 500mg for Jamie Chen
2. **Bank Statement** — Metropolitan Bank statement with transactions
3. **Government Letter** — HMRC tax return reminder

---

## Privacy Guarantees

- ✅ 100% on-device processing
- ✅ No image upload
- ✅ No text upload
- ✅ No cloud APIs (no OpenAI, Gemini, Claude, etc.)
- ✅ No telemetry
- ✅ No analytics
- ✅ No account required
- ✅ Works in airplane mode
- ✅ Models run locally on CPU

---

## Safety Features

### Medical Documents

The system distinguishes between **what the document says** and **medical advice**.
It reads prescription instructions verbatim and never invents medical recommendations.

### Confidence Handling

- Low-confidence OCR regions are flagged with warnings
- Critical fields (dosage, amounts, account numbers) use stricter thresholds
- "I am not confident I read this correctly" warnings when quality is poor

---

## Current Status

**Phase 1-6 Complete**: Full Python prototype working with all pipeline stages.

### To Do (Next Phases)
- [ ] ExecuTorch export for mobile deployment
- [ ] Android app with CameraX integration
- [ ] Accessible camera guidance (spoken positioning)
- [ ] PyTorch NER model for better name/entity detection
- [ ] Small PyTorch classifier for visual features
- [ ] iOS/Core ML port

---

## Hackathon Demo Script

1. **Put phone in airplane mode**
2. Open app → "SCAN DOCUMENT"
3. Hold phone over a prescription
4. App guides: "Document detected. Hold steady."
5. App announces: "This is a prescription for Amoxicillin 500mg. Take ONE capsule THREE times daily."
6. App: "Sensitive information detected. Processing is 100% on-device."
7. Tap "Ask Question" → "How many tablets should I take?"
8. App: "Take ONE capsule THREE times daily."
9. Developer screen: "NETWORK REQUESTS: 0 | PROCESSING LOCATION: DEVICE"

---

## License

MIT
