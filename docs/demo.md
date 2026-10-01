# Hackathon Demo Script (2 minutes)

## Setup (Before Demo)

1. Open terminal in `private-sight/` directory
2. Ensure models are cached: verify `~/.EasyOCR/model/` exists
3. Turn off Wi-Fi or demonstrate airplane mode

## Demo Flow

### Step 1: Show Privacy (10 seconds)

```
"I'll show you Private Sight — a privacy-first document reader
for visually impaired users. My phone is in airplane mode.
No data will leave this device."
```

### Step 2: Scan Prescription (25 seconds)

```bash
python -m app.scan demo_documents/prescription.png
```

Point to:
- "DOCUMENT TYPE: 💊 PRESCRIPTION"
- "SENSITIVE INFORMATION: ⚠ DETECTED"
- Risk level: HIGH
- Extracted: Amoxicillin, dosage, doctor, pharmacy
- Medical disclaimer

### Step 3: Question Answering (20 seconds)

```bash
python -m app.scan demo_documents/prescription.png --question "How many tablets should I take?"
```

Shows: "Take ONE capsule THREE times daily" with medical disclaimer.

### Step 4: Scan Bank Statement (25 seconds)

```bash
python -m app.scan demo_documents/banking.png
```

Point to:
- "DOCUMENT TYPE: 🏦 BANKING"
- Monetary values extracted
- Account information detected

### Step 5: Scan Government Letter (20 seconds)

```bash
python -m app.scan demo_documents/government_letter.png
```

Point to:
- "DOCUMENT TYPE: 🏛️ GOVERNMENT"
- Deadline extracted: "31 January 2027"
- Action required detected

### Step 6: Show JSON Output & Developer Stats (20 seconds)

```bash
python -m app.scan demo_documents/prescription.png --json 2>/dev/null | python3 -m json.tool
```

Explain the structured output for screen reader integration.

Show:
- "100% ON-DEVICE PROCESSING"
- Processing time displayed
- All warnings and confidences

## Key Talking Points

1. **Privacy**: No cloud, no API, no uploads. Models run on CPU.
2. **Accessibility**: Designed for blind users — spoken summaries, guidance.
3. **Safety**: Medical disclaimer, never invents advice, confidence warnings.
4. **Modular**: Each component replaceable, ready for ExecuTorch mobile export.
5. **Practical**: Works on 3 real document types with high accuracy.

## Demo Documents Are Synthetic

All demo documents contain fictional data:
- "Jamie Chen" — not a real person
- "OAKWOOD MEDICAL CENTRE" — not a real clinic
- "METROPOLITAN BANK PLC" — not a real bank
- HMRC letter with fictional reference numbers
