# Private Sight — Android App

Fully offline, accessibility-first document reader for blind and low-vision users.

## Privacy by construction

- **No `INTERNET` permission** is declared in `AndroidManifest.xml`. Without it the
  operating system refuses to open a network socket from this process.
- A strict `network_security_config.xml` denies all cleartext traffic as a second layer.
- `allowBackup="false"` and `data_extraction_rules.xml` exclude everything from backup
  and device transfer.
- Models are bundled in `app/src/main/assets/models/` and loaded locally.

## Requirements

- Android Studio (Koala or newer)
- JDK 17
- Android SDK 34, minimum SDK 26 (Android 8.0)

## Build

```bash
cd android
./gradlew assembleDebug        # debug APK
./gradlew test                 # JVM unit tests (no device needed)
./gradlew installDebug         # install on a connected device
```

The first `./gradlew` invocation downloads the Gradle distribution and Android
dependencies (build-time only — the app itself never uses the network).

## Model setup (before a release build)

Export the ExecuTorch models and place them in `app/src/main/assets/models/`:

```bash
cd ..                        # back to the repo root
python scripts/export_models.py --ocr
cp models/*.pte android/app/src/main/assets/models/
```

Then uncomment the ExecuTorch dependency in `app/build.gradle.kts`.
Until models are present the app still runs and reports that OCR models are missing.

## Screens

| Screen | Purpose |
|--------|---------|
| `MainActivity` | SCAN DOCUMENT: live camera guidance, capture, results, questions, delete |
| `PrivacyActivity` | Privacy Mode: the four guarantees + delete-all |
| `DeveloperActivity` | NETWORK REQUESTS: 0, PROCESSING LOCATION: DEVICE, etc. |

## Accessibility

- Every control is a ≥56dp touch target with a `contentDescription`.
- Camera guidance is spoken automatically ("Move closer.", "Hold steady.").
- Results are announced with `announceForAccessibility` and spoken via TTS.
- Spoken question input, with large question buttons as a guaranteed fallback.
- Guidance speech is throttled so it never becomes noisy.

## Architecture

```
MainActivity
  ├── camera/CaptureGuide          live frame assessment (Kotlin port)
  ├── camera/DocumentCaptureAnalyzer  CameraX ImageAnalysis.Analyzer
  ├── camera/Guidance              fixed spoken strings
  ├── tts/SpeechEngine             Android TextToSpeech wrapper
  ├── analysis/DocumentAnalyzer    pipeline orchestrator
  │     ├── analysis/OcrEngine           ExecuTorch (.pte) OCR
  │     ├── analysis/DocumentClassifier  rule-based
  │     ├── analysis/SensitiveDataDetector
  │     ├── analysis/DocumentExtractor
  │     └── analysis/OfflineQuestionAnswerer
  ├── storage/DocumentStore        in-memory + delete
  └── voice/QuestionInput          offline-capable speech input
```

The analysis classes are line-for-line ports of the Python reference in `ml/`,
so behaviour and unit tests match across desktop and mobile.
