import api_code_editor.groq_service as gq

from speech_portion.stt import listen

prompt = listen()
system_prompt = """
    Answer as a professional interviewer.
    Respond ONLY in JSON format like:
    {
    "type": "question | follow_up | feedback",
    "response": "your message"
    }
"""

print(f"Prompt type is :{type(prompt)}")

print(gq.call_groq(system_prompt,[{"role": "user", "content": prompt}]))

