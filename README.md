# AI Mock Interview System
*Agentic AI for Realistic Interview Preparation*

---

## Overview

The AI Mock Interview System is a real-time, agentic AI platform designed to simulate human-like interview experiences. Unlike conventional tools that rely on static question banks, this system dynamically adapts to candidate responses, conducts follow-up questioning, and evaluates candidates across technical, communication, and behavioral dimensions.

---

## Problem

Existing mock interview platforms fall short in several key areas:

- No personalization — identical questions across all candidates
- Absence of real-time follow-up or cross-questioning
- Rigid, scripted conversation flow
- Surface-level evaluation limited to answer correctness
- No unified assessment of coding, reasoning, and behavioral skills

*Informed by findings from arXiv:2506.16542 (Multimodal AI Mock Interviews)*

---

## Solution

We built an agentic AI interviewer that:

- Adapts in real time based on candidate responses
- Conducts dynamic cross-questioning to probe depth and edge cases
- Evaluates both code quality and thought process simultaneously
- Delivers actionable post-interview feedback
- Maintains a natural, low-latency conversational flow

---

## Key Features

### Personalized Interviews
- Resume-based question generation
- Company-specific difficulty modes
- Adjustable interview complexity

### Dynamic Cross-Questioning
- Contextual follow-up questions derived from answers
- Probes reasoning, edge cases, and optimizations

### Real-Time Coding Evaluation
- Monaco-style embedded code editor
- Live code execution via Judge0 / Piston
- AI feedback on correctness, efficiency, and code clarity

### Human-Like Conversation
- Real-time voice interaction with natural turn-taking
- Low-latency end-to-end response (~600ms)

### Post-Interview Analysis
- Confidence scoring
- Filler word detection
- Communication clarity metrics
- Code quality assessment

---

## System Architecture

```
Candidate → VAD → STT → Groq LLM → TTS → Response
```

---

## Current Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Voice Activity Detection | Silero VAD |
| Speech-to-Text | DeepGram |
| Text-to-Speech | DeepGram |
| AI Core | Groq |
| Backend | Flask |
| Code Execution | Python exec |
| Analysis | Custom confidence model, code analyzer |

---

## Target Performance

| Component | Latency |
|---|---|
| VAD | ~10ms |
| STT | ~300ms |
| LLM | ~200ms |
| TTS | ~400ms |
| **End-to-End** | **~600ms** |

---

## MVP Scope

- Technical interviews
- Voice interaction
- Coding evaluation
- Core feedback metrics

---

## Future Scope

- Multi-domain interview support
- Distinct interviewer personas
- Non-verbal behavior analysis
- Longitudinal performance tracking
- 3D avatar integration

---

## Team

| Name |
|---|
| Ishaan Gupta |
| Satvik Aggarwal |
| Shruthi Sivaprasad |
| Yuvraj Tyagi |
