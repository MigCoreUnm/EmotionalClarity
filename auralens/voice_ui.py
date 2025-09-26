"""Streamlit helper for embedding voice controls."""

from __future__ import annotations

from textwrap import dedent

import streamlit as st
import streamlit.components.v1 as components


class VoiceControlRenderer:
    """Encapsulates the Web Speech API injection logic."""

    PHOTO_HOTWORD = "let me think about this"
    LISTEN_HOTWORD = "listen"

    @classmethod
    def render(cls, enable: bool) -> None:
        enable_flag = str(enable).lower()
        status_color = "#0b8043" if enable else "#5f6368"
        status_text = (
            f'Say "{cls.LISTEN_HOTWORD}" to capture conversation or "{cls.PHOTO_HOTWORD}" to snap a photo.'
            if enable
            else "Voice control off."
        )

        voice_html = dedent(
            f"""
            <div id="auralens-voice-status" style="font: 500 0.9rem/1.6 'Source Sans Pro', sans-serif; color: {status_color};">
                {status_text}
            </div>
            <script>
            (function() {{
                const enable = {enable_flag};
                const photoHotword = "{cls.PHOTO_HOTWORD}";
                const listenHotword = "{cls.LISTEN_HOTWORD}";
                const statusEl = document.getElementById("auralens-voice-status");
                const Streamlit = window.parent?.Streamlit || window.Streamlit;

                if (!window.__auralensVoiceCtrl) {{
                    window.__auralensVoiceCtrl = {{}};
                }}

                const ctrl = window.__auralensVoiceCtrl;

                const updateStatus = (text, color) => {{
                    if (!statusEl) return;
                    statusEl.textContent = text;
                    if (color) {{
                        statusEl.style.color = color;
                    }}
                }};

                const pushEvent = (payload) => {{
                    if (!Streamlit || !Streamlit.setComponentValue) return;
                    try {{
                        Streamlit.setComponentValue(payload);
                    }} catch (err) {{
                        console.warn("Unable to push event", err);
                    }}
                }};

                const doc = window.parent?.document || document;
                const setConversationInput = (value) => {{
                    if (!doc) return;
                    const labels = Array.from(doc.querySelectorAll('label'));
                    const targetLabel = labels.find(l => l.innerText && l.innerText.trim().startsWith('What was the last thing'));
                    if (!targetLabel) return;
                    const input = targetLabel.parentElement?.querySelector('input');
                    if (!input) return;
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(input, value);
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }};

                if (!enable) {{
                    ctrl.keepAlive = false;
                    ctrl.dictationActive = false;
                    if (ctrl.recognition) {{
                        try {{ ctrl.recognition.stop(); }} catch (err) {{ console.warn(err); }}
                    }}
                    updateStatus("Voice control off.", "#5f6368");
                    return;
                }}

                if (ctrl.unsupported) {{
                    updateStatus("Voice control not supported in this browser.", "#d93025");
                    return;
                }}

                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) {{
                    ctrl.unsupported = true;
                    updateStatus("Voice control not supported in this browser.", "#d93025");
                    return;
                }}

                if (!ctrl.recognition) {{
                    const recognition = new SpeechRecognition();
                    recognition.continuous = true;
                    recognition.interimResults = true;
                    recognition.lang = "en-US";

                    const toggleDictation = () => {{
                        ctrl.dictationActive = !ctrl.dictationActive;
                        const ts = Date.now();
                        pushEvent({{ type: 'listening_state', active: ctrl.dictationActive, ts }});
                        updateStatus(
                            ctrl.dictationActive
                                ? 'Dictation on. Speak naturally to capture the last utterance.'
                                : `Say "${{listenHotword}}" to capture conversation or "${{photoHotword}}" to snap a photo.`,
                            ctrl.dictationActive ? '#0b8043' : '#1a73e8'
                        );
                    }};

                    recognition.onstart = () => {{
                        if (ctrl.dictationActive) {{
                            updateStatus('Dictation on. Speak naturally to capture the last utterance.', '#0b8043');
                        }} else {{
                            updateStatus(`Say "${{listenHotword}}" to capture conversation or "${{photoHotword}}" to snap a photo.`, '#0b8043');
                        }}
                    }};

                    recognition.onerror = (event) => updateStatus(`Voice control error: ${{event.error}}`, '#d93025');

                    recognition.onend = () => {{
                        if (ctrl.keepAlive) {{
                            try {{ recognition.start(); }} catch (err) {{ console.warn(err); }}
                        }} else {{
                            updateStatus('Voice control off.', '#5f6368');
                        }}
                    }};

                    recognition.onresult = (event) => {{
                        for (let i = event.resultIndex; i < event.results.length; i++) {{
                            const result = event.results[i];
                            const transcriptRaw = result[0].transcript.trim();
                            if (!transcriptRaw) continue;

                            const normalized = transcriptRaw.toLowerCase();

                            if (result.isFinal) {{
                                if (normalized === listenHotword || normalized === `${{listenHotword}}.` || normalized === `${{listenHotword}},`) {{
                                    toggleDictation();
                                    continue;
                                }}

                                if (normalized.includes(photoHotword)) {{
                                    const now = Date.now();
                                    if (!ctrl.lastTrigger || now - ctrl.lastTrigger > 2500) {{
                                        ctrl.lastTrigger = now;
                                        updateStatus('Triggering camera…', '#1a73e8');
                                        const buttons = doc.querySelectorAll('button');
                                        const target = Array.from(buttons).find(btn => /take photo/i.test(btn.innerText));
                                        if (target) {{
                                            target.click();
                                            setTimeout(() => updateStatus(
                                                ctrl.dictationActive
                                                    ? 'Dictation on. Speak naturally to capture the last utterance.'
                                                    : `Say "${{listenHotword}}" to capture conversation or "${{photoHotword}}" to snap a photo.`,
                                                '#0b8043'
                                            ), 1600);
                                        }} else {{
                                            updateStatus('Camera button not found. Click the Streamlit window and try again.', '#d93025');
                                        }}
                                    }}
                                    continue;
                                }}

                                if (ctrl.dictationActive) {{
                                    const ts = Date.now();
                                    pushEvent({{ type: 'utterance', text: transcriptRaw, ts }});
                                    try {{
                                        setConversationInput(transcriptRaw);
                                    }} catch (err) {{
                                        console.warn('Unable to populate conversation input', err);
                                    }}
                                }}
                            }}
                        }}
                    }};

                    ctrl.recognition = recognition;
                }}

                ctrl.keepAlive = true;

                try {{
                    ctrl.recognition.start();
                }} catch (err) {{
                    if (err && err.message && err.message.includes('start')) {{
                        console.warn('Speech recognition already running.');
                    }} else {{
                        console.error(err);
                    }}
                }}
            }})();
            </script>
            """
        )

        return components.html(voice_html, height=0)
