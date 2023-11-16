import openai

def generate_speech_openai(prompt):
    speech_file_path = "../output/audio/speech.mp3"

    response = openai.audio.speech.create(
        model='tts-1',
        voice='alloy',
        input=prompt
    )
    response.stream_to_file(speech_file_path)