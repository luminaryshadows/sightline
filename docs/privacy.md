# Privacy Architecture

## Core Principle

**Nothing leaves the device.**

Every component of Private Sight runs locally. No image, OCR text,
personal information, or metadata is transmitted to any server.

## What Stays on Device

- Camera images
- OCR text output
- Extracted document fields
- User questions
- Classification results
- Sensitive entity data
- Model inference results

## No External Dependencies

- ❌ No OpenAI API
- ❌ No Google Gemini API
- ❌ No Claude API
- ❌ No cloud OCR services
- ❌ No remote model inference
- ❌ No telemetry or analytics
- ❌ No crash reporting services
- ❌ No usage tracking

## Model Storage

All ML models are stored locally:
- `~/.EasyOCR/model/` — CRAFT detection + CRNN recognition models
- `models/` — Future ExecuTorch `.pte` files

## One-Time Download

The only network activity is the initial model download during setup.
This can be done on a trusted network and the models persist locally
for all subsequent offline use.

## Document Storage

By default, documents are processed in memory only.
No persistent storage unless the user explicitly opts in.

A "DELETE CURRENT DOCUMENT" button clears:
- Captured image
- OCR text
- Extracted information
- All temporary files

## Data Minimization

The system extracts only what is needed:
- Fields relevant to the document type
- No full document text retention beyond the session
- No user identity stored or transmitted
- No document history unless explicitly saved

## Security Considerations

- No network permissions required at runtime
- Models run in-process, no IPC
- Airplane mode compatible
- No accounts, no authentication, no user tracking
