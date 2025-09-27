# AuraLens - Multi-Agent Social Coach

AuraLens is a prototype for an AR-based social coach that provides real-time conversational advice. It uses a multi-modal AI system to analyze facial expressions and conversational context.

## Vision
Our goal is to create a tool that enhances emotional intelligence by providing users with expert-level social guidance during live conversations, delivered discreetly through an AR interface.

## Features
- **Real-time Facial Analysis:** Uses AWS Rekognition to extract emotional cues and facial features.
- **Conversational Context:** Incorporates user-provided text to understand the dialogue.
- **Multi-Agent LLM Panel:** Queries the Writer API to generate three distinct courses of action from different AI personas (Empathetic, Logical, Creative).
- **Hands-Free Voice Assistant:** Say "I'm listening" to dictate the last utterance into the text box or "let me think about this {name}" to capture a new frame and surface saved notes for that contact.
- **Heuristic Speaker Correlation:** Dictated utterances are matched to detected faces based on their dominant emotions for quick at-a-glance context.
- **Audio Recommendations:** Optional ElevenLabs integration narrates the three-agent advice as a spoken briefing.
- **Phone Coaching:** When Twilio and S3 are configured, AuraLens dials your phone and plays the synthesized advice automatically.

## Project Structure
- `app.py`: Streamlit shell that orchestrates UI flow and delegates to service classes.
- `auralens/config.py`: Environment-aware configuration dataclasses.
- `auralens/container.py`: Dependency container that wires AWS, Writer, ElevenLabs, and Twilio services.
- `auralens/services/`: Modular service classes for Rekognition, Writer, ElevenLabs, and call delivery.
- `auralens/analysis.py`: Conversation-to-face correlation heuristics.
- `auralens/voice_ui.py`: Web Speech API integration rendered as a reusable component.
- `auralens/advice.py`: Advice composer that formats persona guidance for narration.

## How to Run
1. Create a virtual environment and install dependencies: `python -m venv venv && source venv/bin/activate` then `pip install -r requirements.txt`
2. Create a `.env` file with your `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `WRITER_API_KEY`, and (optional) `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`.
   - For phone calls also add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `AURALENS_DEFAULT_TO_NUMBER`, and `AURALENS_AUDIO_BUCKET` (an S3 bucket the app can write to).
3. Run the Streamlit application: `streamlit run app.py`

## Voice & Audio Assistant (Optional)
- Open AuraLens in Chrome or another browser with Web Speech API support.
- Grant microphone access when prompted.
- Toggle **Enable voice assistant** in the sidebar.
- Say "I'm listening" to start/stop dictation. When active, the last spoken line fills the conversation field automatically.
- Say "let me think about this {name}" to trigger the Streamlit camera button and pull the matching entry from `notes.json` for quick context.
- If the browser stops listening, toggle the feature off/on to restart it.
- To hear the advice, add your ElevenLabs key and a valid voice ID (or name) to `.env`, enable **Play audio recommendations**, and Streamlit will render an embedded audio player for each set of guidance. Names are resolved to voice IDs automatically when possible; if in doubt, use an actual `voice_id` such as `21m00Tcm4TlvDq8ikWAM`.
- To receive a phone call, enable **Call me with recommendations**, provide a verified phone number, and ensure your Twilio and S3 settings are in place. The app uploads the MP3 to S3 with a 60-minute presigned link and Twilio plays it during the call.
