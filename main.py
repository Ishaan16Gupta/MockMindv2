import api_code_editor.groq_service as gq

from speech_portion.stt import listen

prompt = listen()

print(gq.call_groq(prompt,messages="Answer as a professional interviewer."))

