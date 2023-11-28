from pathlib import Path
from openai import OpenAI
from pydub import AudioSegment, silence
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import re
from autogen_podcast.modules import api_costs

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

def generate_speech(text, path):
    """Generate speech from text using OpenAI's text-to-speech API and save to a file."""
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice="echo",
        input=text
    )
    response.stream_to_file(f"{path}")
    time.sleep(2)


def split_script_by_music_and_pauses(text):
    """Split the script by music cues and pauses, returning a list of parts and a list of tracks."""
    text = text.replace('\\', '')

    # Extracting the tracks
    tracks = re.findall(r'\[play: "(.*?)" by (.*?)\]', text)
    formatted_tracks = [f"{track[0]} by {track[1]}" for track in tracks]

    # Splitting the script
    parts = re.split(r'\[play: ".*?" by .*?\]', text)
    final_output = []

    for part in parts:
        matches = re.findall(r'(.*?)\[pause (\d+(\.\d+)?) second(s)?\]', part)
        output = []
        for match in matches:
            sentence = match[0].strip()
            duration = match[1]
            output.extend([sentence, float(duration)])

        if matches and part.endswith(matches[-1][0]):
            output.append(part[part.rfind(matches[-1][0]) + len(matches[-1][0]):].strip())

        final_output.append(output)

    return final_output, formatted_tracks

def generate_speech_and_save_with_pauses(parts, output_folder, tts_function):
    """Generate speech for each part of the script with pauses and save as audio files."""
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    cost = 0
    for i, part in enumerate(parts):
        audio_segments = []
        for segment in part:
            if isinstance(segment, str) and segment:
                temp_path = os.path.join(output_folder, f"temp_{i}.mp3")
                tts_function(segment, temp_path)
                cost += len(segment) * api_costs.tts

                try:
                    audio_segment = AudioSegment.from_file(temp_path, format="mp3")
                    audio_segments.append(audio_segment)
                except Exception as e:
                    print(f"Error loading MP3 file: {temp_path}. Error: {e}")
                    continue

                os.remove(temp_path)
            elif isinstance(segment, int):
                pause = silence.AudioSegment.silent(duration=segment * 1000)
                audio_segments.append(pause)

        combined_audio = sum(audio_segments)
        final_path = os.path.join(output_folder, f"part_{i + 1}.mp3")
        combined_audio.export(final_path, format="mp3")
        print(f"Part {i + 1} audio generated at {final_path}")
    
    return cost

def generate_tracklist(tracks, output_folder):
    """Generate a tracklist file containing each track in the format 'track by artist'."""
    with open(os.path.join(output_folder, "tracklist.txt"), 'w') as file:
        for track in tracks:
            file.write(f"{track}\n")

def generate_sequence_file(parts, tracks, output_folder):
    """Generate a file indicating the sequence of audio parts and tracks."""
    with open(os.path.join(output_folder, "audio_sequence.txt"), 'w') as file:
        for i, track in enumerate(tracks):
            file.write(f"part_{i + 1}\n")
            file.write(f"{track}\n")

def create_playlist_from_list(song_list, artist_name):
    # Get these from your Spotify dashboard
    client_id = 'a298df0bd1be49c5a8972d808bdcf72e'
    client_secret = '4c7c54319bd74cc58c9555d3e2ed52a0'
    redirect_uri = 'http://localhost:8000/callback/'  # your application's redirect URI
    username = 'verlaanutrecht'  # your username or Spotify User ID

    scope = "playlist-modify-public"  # needed to create a public playlist
    token = SpotifyOAuth(scope=scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

    sp = spotipy.Spotify(auth_manager=token)

    # create a new playlist
    playlist_name = f"{artist_name} on R&R"
    playlist = sp.user_playlist_create(username, playlist_name, public=True)
    playlist_id = playlist['id']

    # list for storing uris
    uris = []

    print('Creating playlist...')
    
    # Process each line in the song_list
    for song_artist in song_list:
        song_artist = song_artist.strip()  # Remove leading/trailing whitespace
        if not song_artist:
            continue  # Skip empty lines
        
        # Separate song and artist
        song, artist = re.match(r'^(.+) by (.+)$', song_artist).groups()
        
        # Search for the song
        print(f"Searching for: {song_artist}")
        query = f"track:{song} artist:{artist}"
        result = sp.search(query, type='track', limit=1)
        tracks = result['tracks']['items']
        
        if tracks:
            # If the song was found, store its URI
            uris.append(tracks[0]['uri'])
        else:
            print(f"Track not found: {song_artist}")
    
    # Add songs to the playlist
    if uris:
        sp.playlist_add_items(playlist_id, uris)
        print("Tracks added to the playlist.")
    else:
        print("No tracks were found.")

# Main function to process script and generate audio
def process_script_and_generate_audio(script, output_path, artist_name):
    parts, tracks = split_script_by_music_and_pauses(script)
    generate_tracklist(tracks, './temp_output')
    generate_sequence_file(parts, tracks, output_path)
    #create_playlist_from_list(tracks, artist_name)

    if True:
        speech_cost = generate_speech_and_save_with_pauses(parts, output_path, generate_speech)
    else:
        speech_cost = 0

    return speech_cost