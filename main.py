import api_code_editor.groq_service as gq

from speech_portion.stt import listen

from speech_portion.tts import speak

import time

start_time = time.perf_counter()

prompt = listen()
system_prompt = """
    Answer as a professional interviewer.
    Respond ONLY in JSON format like:
    {
    "type": "question | follow_up | feedback",
    "response": "your message"
    }
"""

# print(f"Prompt type is :{type(prompt)}")

response = gq.call_groq(system_prompt,[{"role": "user", "content": prompt}])

print(response["response"])

speak(
        text   = response["response"],
    )

end_time = time.perf_counter()
print(f"Total time taken: {end_time - start_time:.2f} seconds")

