# Architecture

## Design Principles

1. **Privacy First**: No data leaves the device. Models run locally.
2. **Modular**: Each component is independently replaceable.
3. **Mobile-Ready**: Designed for CPU inference on mobile devices.
4. **Accessibility**: Output designed for screen readers and TTS.

## Component Design

### OCR (`ml/ocr/engine.py`)

Uses EasyOCR with CRAFT text detection and CRNN text recognition.
Both models are PyTorch-based and run on CPU.

- **Interface**: `DocumentOCR.process(image) → OCRResult`
- **Replacement**: Planned ExecuTorch `.pte` export for mobile

### Preprocessing (`ml/preprocessing/pipeline.py`)

Enhances images for OCR and provides accessibility guidance:
- Brightness normalization via CLAHE
- Blur detection via Laplacian variance
- Document boundary estimation via Canny + contour detection
- Spoken guidance for blind users

### Classifier (`ml/classifier/engine.py`)

Rule-based with keyword scoring for 7 document types.
Returns confidence scores and alternatives.

Future: Replace with lightweight PyTorch classifier combining
OCR text features with visual layout features.

### Sensitive Data Detector (`ml/sensitive_data/detector.py`)

Regex-based PII detection for:
- Phone numbers, emails, addresses, postcodes
- Account numbers, sort codes, credit card numbers
- Medication names, dosages
- National Insurance, NHS numbers
- Dates of birth, ID numbers
- Monetary values

Future: Add small PyTorch NER model for better name detection.

### Document Extractor (`ml/extraction/extractor.py`)

Document-type-specific structured extraction:
- Prescription: medication, dosage, frequency, instructions, warnings
- Banking: institution, amounts, references, dates, account info
- Bill: company, amount due, due date, payment instructions
- Government/Legal: organization, subject, deadlines, action required
- ID: name, DOB, document number, nationality, expiry

### Question Answering (`ml/qa/engine.py`)

Intent classification + keyword retrieval.
No LLM hallucinations — returns "not found" when information is unavailable.

Safety features:
- Medical disclaimer on all health-related answers
- Never invents medical advice
- Reports only what the document actually says

## Data Flow

```
User captures image
     ↓
Preprocessing (brightness, blur, edge detection)
     ↓
OCR (CRAFT detection → CRNN recognition → text assembly)
     ↓
Document Classification (regex pattern scoring → type + confidence)
     ↓
Sensitive Data Detection (regex patterns → entity list → risk level)
     ↓
Structured Extraction (type-specific regex → fields, amounts, deadlines)
     ↓
Accessible Summary (natural language assembly)
     ↓
Question Answering (intent matching → text retrieval → safe response)
```

## Mobile Deployment Plan

For Android deployment:
1. Export PyTorch models via `torch.export` → `.pte` files
2. Integrate ExecuTorch runtime in Android app
3. Use XNNPACK backend for CPU acceleration
4. Quantize models to int8 for smaller size and faster inference
5. CameraX for camera access with accessibility guidance
6. Android TextToSpeech for spoken output
7. Local SQLite/Room for optional document storage
