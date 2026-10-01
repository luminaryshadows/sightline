# Private Sight — Project Plan & Build Specification

> The authoritative spec this repository is built against: a privacy-first,
> fully-offline document-reading assistant for blind and low-vision users.
> Core rule: **nothing leaves the device.**
>
> Extracted from the project brief authored 2026-10-01. Source transcripts and
> session logs are deliberately **not** committed to this repository.

---

You are the lead ML engineer and full-stack mobile engineer for an Imperial College hackathon project.

Build a WORKING MVP of a privacy-first, fully offline AI visual assistant for blind and visually impaired users.

## PROJECT GOAL

The application allows a blind or low-vision user to point their phone camera at a sensitive document such as:

- medical prescription
- bank statement or banking letter
- government letter
- bill
- legal document
- identification document

The system must understand the document and read the important information aloud WITHOUT uploading the image, OCR text, or personal information to any server.

The core rule is:

## NOTHING LEAVES THE DEVICE.

The application must continue to function when Wi-Fi and mobile data are completely disabled.

## TECH STACK

Use:

- Python 3.11+
- PyTorch for ML development
- torchvision where useful
- Hugging Face PyTorch models only where lightweight enough
- ExecuTorch for mobile deployment
- quantization where appropriate
- XNNPACK as the default CPU backend
- Android/Kotlin for the first mobile prototype
- CameraX for camera access
- Android TextToSpeech for spoken output
- local storage only
- no external cloud APIs
- no OpenAI API
- no Gemini API
- no Claude API
- no external OCR API
- no telemetry
- no remote analytics

Keep the code modular so an iOS/Core ML version can be added later.

## IMPORTANT DEVELOPMENT STRATEGY

Do not try to build every advanced feature immediately.

Build this project incrementally and maintain a working application after every phase.

## PHASE 1 — WORKING LOCAL PYTHON PROTOTYPE

First create a desktop/local prototype so the complete AI pipeline works before mobile integration.

The pipeline should be:

Image
→ image preprocessing
→ document detection/cropping
→ OCR
→ document classification
→ sensitive information detection
→ structured information extraction
→ accessible summary
→ question answering
→ text-to-speech-ready output

Create a CLI and simple local testing UI.

The prototype must accept an image from disk and return:

1. OCR text
2. detected document type
3. detected sensitive information
4. important extracted fields
5. short accessible summary
6. confidence scores
7. warnings when confidence is low

## PHASE 2 — PYTORCH OCR

Implement OCR locally using a PyTorch-compatible approach.

Prefer the smallest practical model that can provide good document OCR.

The architecture should separately support:

- text region detection
- text recognition

Do not make the entire system dependent on one massive vision-language model.

Optimize for:

- CPU inference
- low memory usage
- mobile deployment
- English first
- clear printed documents

Create interfaces such as:

DocumentOCR
DocumentClassifier
SensitiveDataDetector
DocumentExtractor
OfflineQuestionAnswerer

Each module must be replaceable independently.

## PHASE 3 — DOCUMENT CLASSIFICATION

Create a lightweight PyTorch classifier capable of classifying documents into:

- prescription
- banking
- government
- bill/invoice
- legal
- ID
- unknown

Use OCR text plus visual features where useful.

For the hackathon MVP, rules combined with a lightweight PyTorch classifier are acceptable.

Always return a confidence score.

## PHASE 4 — SENSITIVE INFORMATION DETECTION

Detect sensitive information locally.

Examples:

- person names
- phone numbers
- email addresses
- addresses
- account numbers
- credit/debit card-like numbers
- identification numbers
- medication names
- dosage information
- medical information
- monetary values

Use a combination of:

- regex
- rule-based detection
- small PyTorch NLP model where useful

Never upload detected information anywhere.

Return structured output such as:

{
  "document_type": "prescription",
  "sensitive_information_detected": true,
  "entities": [],
  "important_fields": {},
  "summary": "",
  "confidence": 0.0
}

## PHASE 5 — DOCUMENT-SPECIFIC EXTRACTION

Do not simply read the entire document word by word.

Extract useful information depending on document type.

PRESCRIPTION:
- medication
- dosage
- frequency
- instructions
- warnings
- doctor/pharmacy if available

BANKING:
- institution
- amount
- transaction/reference
- payment date
- account information
- action required

BILL:
- company
- amount due
- due date
- reference
- payment instructions

GOVERNMENT/LEGAL LETTER:
- organisation
- subject
- deadline
- action required
- contact details

The main user experience should answer:

"What is this document?"

"What is important?"

"Do I need to do anything?"

"When?"

## PHASE 6 — OFFLINE QUESTION ANSWERING

Allow the user to ask questions about the CURRENT scanned document.

Examples:

"How many tablets should I take?"

"When is my payment due?"

"How much do I owe?"

"What action do I need to take?"

"Who sent this letter?"

Question answering must operate ONLY on information extracted from the document.

For the initial MVP, use retrieval + deterministic extraction rather than requiring a huge LLM.

If a small local PyTorch language model is practical, implement it as an OPTIONAL module.

Never hallucinate missing information.

If information is unavailable, respond:

"I could not find that information in the document."

For medical information, do not invent or infer medical advice. Read and explain what is actually written.

## PHASE 7 — ACCESSIBLE CAMERA EXPERIENCE

Build an Android camera interface optimized for blind users.

The interface should provide spoken guidance such as:

"Document not fully visible."

"Move phone left."

"Move phone upward."

"Move closer."

"Too dark."

"Hold steady."

"Document captured."

Use computer vision locally to estimate:

- document boundaries
- blur
- brightness
- orientation
- whether all four corners are visible

The user should be able to capture a document without needing to see the screen.

Use large accessible controls and Android accessibility labels.

## PHASE 8 — ANDROID APPLICATION

Create an Android app using Kotlin.

Main screen:

## SCAN DOCUMENT

After scanning:

- document type
- important information
- Read Summary button
- Read Full Document button
- Ask Question button
- Sensitive Information button
- Scan Again button

The app should automatically speak important results.

Implement voice input if practical using an OFFLINE-capable Android speech recognizer.

If offline voice recognition cannot be guaranteed, provide large accessible text/question buttons as a fallback.

## PHASE 9 — EXECUTORCH DEPLOYMENT

Export appropriate PyTorch models using torch.export and ExecuTorch.

Generate .pte model files.

Integrate them into the Android application.

Prefer:

- quantized models
- XNNPACK acceleration
- small model sizes
- low RAM usage

Create scripts such as:

scripts/export_ocr.py
scripts/export_classifier.py
scripts/export_ner.py
scripts/benchmark.py

Measure:

- model size
- OCR latency
- total pipeline latency
- peak RAM if practical

## PHASE 10 — PRIVACY MODE

Create an obvious Privacy Mode screen.

Show:

"100% ON-DEVICE PROCESSING"

"No image or document text is uploaded."

"No account required."

"No cloud processing."

Provide an optional button:

## DELETE CURRENT DOCUMENT

Delete:

- captured image
- OCR text
- extracted information
- temporary files

Do not permanently store documents unless the user explicitly chooses to.

## PHASE 11 — HACKATHON DEMO MODE

Create three SAFE synthetic sample documents:

1. prescription
2. bank/payment notice
3. government letter

Do not use real people's personal information.

Include them in:

demo_documents/

The demo should show:

1. Put phone into airplane mode.
2. Scan document.
3. Application recognizes document.
4. Application announces sensitive information was found.
5. Application extracts important information.
6. Application reads summary aloud.
7. User asks a question.
8. Application answers locally.
9. Show that zero network requests were made.

Add an optional developer screen showing:

NETWORK REQUESTS: 0

PROCESSING LOCATION: DEVICE

MODEL: LOCAL

PRIVACY STATUS: PROTECTED

## DESIGN PRIORITIES

Prioritize in this exact order:

1. Works reliably
2. Completely offline
3. Accessibility
4. Privacy
5. Fast inference
6. Accuracy
7. Visual polish

Do NOT spend large amounts of time styling the UI before the AI pipeline works.

## ARCHITECTURE

Structure the repository approximately as:

```
private-sight/
  README.md
  requirements.txt
  pyproject.toml

  ml/
    ocr/
    classifier/
    sensitive_data/
    extraction/
    qa/
    preprocessing/

  models/

  scripts/
    export_models.py
    benchmark.py

  demo_documents/

  tests/

  android/
    app/

  docs/
    architecture.md
    privacy.md
    demo.md
```

## TESTING

Add automated tests for:

- OCR
- document classification
- sensitive information detection
- field extraction
- question answering
- document deletion
- offline behavior

Test malformed and blurry images.

## CRITICAL SAFETY REQUIREMENT

For medication/prescription documents, the system must distinguish between:

## WHAT THE DOCUMENT SAYS

and

## MEDICAL ADVICE.

It may read:

"Take one tablet twice daily."

if that is written on the prescription.

It must never invent instructions or recommend changing medication.

## CONFIDENCE HANDLING

Never pretend to know uncertain text.

For low-confidence OCR, say:

"I am not confident I read this correctly. Please scan the document again."

For critical values such as:

- medication dosage
- payment amounts
- deadlines
- account numbers

use a stricter confidence threshold.

## CODE QUALITY

Write:

- clean modular code
- type hints
- useful comments
- README setup instructions
- architecture documentation

Do not leave critical functionality as TODO placeholders.

Do not fake model outputs.

If a model is unavailable, implement the smallest actually-working alternative.

## DEVELOPMENT PROCESS

Work autonomously through the project.

At each stage:

1. inspect the existing repository
2. implement the next smallest functional component
3. run it
4. test it
5. fix errors
6. continue

Do not merely generate source files and assume they work.

Actually run the tests and prototype.

Start with Phase 1.

Before touching Android, prove this command works:

python -m app.scan demo_documents/prescription.png

It should return a complete structured analysis of the document.

Once the Python pipeline works reliably, move on to ExecuTorch export and Android integration.

At the end, provide:

- working repository
- setup instructions
- commands to run it
- Android build instructions
- model information
- benchmark results
- known limitations
- a 2-minute hackathon demo script
