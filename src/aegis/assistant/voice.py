"""Optional voice I/O for Jarvis.

Kept fully separate so the core project has zero audio dependencies. Enable
with the ``[voice]`` extra:  ``pip install -e ".[voice]"``.

On Windows, ``pyttsx3`` uses the built-in SAPI5 voices, and
``SpeechRecognition`` uses Google's free recognizer over the network.
"""

from __future__ import annotations


class VoiceIO:
    """Microphone input and speaker output."""

    def __init__(self) -> None:
        import pyttsx3  # type: ignore
        import speech_recognition as sr  # type: ignore

        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._engine = pyttsx3.init()

    def listen(self) -> str:
        """Capture speech from the default microphone and transcribe it."""
        with self._sr.Microphone() as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = self._recognizer.listen(source)
        try:
            return self._recognizer.recognize_google(audio)
        except Exception:
            return ""

    def speak(self, text: str) -> None:
        """Speak the given text aloud."""
        self._engine.say(text)
        self._engine.runAndWait()
