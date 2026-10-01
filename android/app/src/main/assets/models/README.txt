Place exported ExecuTorch models here before building a release APK:

  text_detector.pte     (text region detection, e.g. CRAFT)
  text_recognizer.pte   (text recognition, e.g. CRNN)

Generate them with:

  python scripts/export_models.py --ocr

These files are bundled into the APK and loaded locally. They are never
downloaded at runtime, so the app works with the device in airplane mode.
