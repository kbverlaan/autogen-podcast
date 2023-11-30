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
        voice="echo", #shimmer
        input=text,
        response_format='flac'
    )
    response.stream_to_file(f"{path}")
    time.sleep(12)


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
    """Generate speech for each part of the script with pauses and save as audio files, starting from a specific part."""
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    start_at_part = 1  # Set the part number from where to start processing

    cost = 0
    for i, part in enumerate(parts[start_at_part - 1:], start=start_at_part):
        audio_segments = []

        # Track if there is any valid audio content
        has_audio_content = False

        for j, segment in enumerate(part):
            if isinstance(segment, str) and segment.strip():
                has_audio_content = True
                temp_path = os.path.join(output_folder, f"temp_{i}_{j}.flac")
                tts_function(segment, temp_path)
                cost += len(segment) * api_costs.tts

                try:
                    audio_segment = AudioSegment.from_file(temp_path, format="flac")
                    audio_segments.append(audio_segment)
                except Exception as e:
                    print(f"Error loading FLAC file: {temp_path}. Error: {e}")
                    continue

                os.remove(temp_path)
            elif isinstance(segment, float):
                pause = AudioSegment.silent(duration=int(segment * 1000))
                audio_segments.append(pause)

        # Only proceed with export if there's valid audio content
        if has_audio_content:
            combined_audio = sum(audio_segments)
            final_path = os.path.join(output_folder, f"part_{i}.flac")
            combined_audio.export(final_path, format="flac")
            print(f"Part {i} audio generated at {final_path}")
        else:
            print(f"Skipped part {i} due to no audio content.")

    return cost

def generate_tracklist(tracks, output_folder):
    """Generate a tracklist file containing each track in the format 'track by artist'."""
    # Ensure the output directory exists
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    # Path to the tracklist file
    tracklist_path = Path(output_folder) / "tracklist.txt"

    # Try writing the tracklist to the file
    try:
        with open(tracklist_path, 'w') as file:
            for track in tracks:
                file.write(f"{track}\n")
        print(f"Tracklist successfully written to {tracklist_path}")
    except Exception as e:
        print(f"Error writing tracklist: {e}")

def generate_sequence_file(parts, tracks, output_folder):
    """Generate a file indicating the sequence of audio parts and tracks."""
    with open(os.path.join(output_folder, "audio_sequence.txt"), 'w') as file:
        for i, (part, track) in enumerate(zip(parts, tracks), start=1):
            # Check if the part is not empty (has meaningful content)
            is_not_empty = any(isinstance(segment, str) and segment.strip() for segment in part)

            if is_not_empty:
                file.write(f"part_{i}\n")

            # Always write the track regardless of whether the part was empty
            file.write(f"{track}\n")

def create_playlist_from_list(song_list, artist_name):
    # Get these from your Spotify dashboard
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
    username = os.getenv('SPOTIFY_USERNAME')

    scope = "playlist-modify-public"  # needed to create a public playlist
    token = SpotifyOAuth(scope=scope, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, cache_path=None)

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

def mix_speech_with_music(speech_path, music_path, output_path, silence_duration=2000, volume_increase=4):
    # Load the speech and music files
    speech = AudioSegment.from_file(speech_path, format=speech_path.split('.')[-1])
    music = AudioSegment.from_file(music_path, format=music_path.split('.')[-1])

    # Reduce the volume of the music
    music = music - 11  # Decrease the volume by 13 dB

    # Calculate the time when the fade out should start
    fade_out_start = len(speech) - 5000  # 5 seconds before speech ends

    # Extend or trim the music track to fit the length of the speech + silence + fade out time
    total_duration = len(speech) + silence_duration + 3000  # Length of speech + 2 seconds before + 2 seconds after
    if len(music) < total_duration:
        music = music + music[:total_duration - len(music)]  # Extend music by repeating
    else:
        music = music[:total_duration]  # Trim music to the required length

    # Apply fade out to the music starting 5 seconds before the end of the speech
    music = music.fade_out(7000)

    # Create silence segments
    silence_segment = AudioSegment.silent(duration=silence_duration)
    silence_segment_end = AudioSegment.silent(duration=silence_duration+1000)

    # Overlay the speech on the music, starting after the initial silence
    combined = music.overlay(speech, position=silence_duration)

    # Add silence before and after the combined audio
    combined_with_silence = silence_segment + combined + silence_segment_end

    # Increase the volume of the combined audio
    final_combined = combined_with_silence + volume_increase

    # Export the result
    final_combined.export(output_path, format=output_path.split('.')[-1])

def process_directory_for_bgm(input_folder, music_path, output_folder, silence_duration=2000, volume_increase=4):
    """Add background music to all audio files in a directory, except the first and last files."""
    # Ensure the output directory exists
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    # Filter out non-audio files and sort the list
    def is_audio_file(filename):
        return filename.endswith(('.mp3', '.flac'))  # Add other audio formats if needed

    def sort_key(f):
        numbers = ''.join(filter(str.isdigit, f))
        return int(numbers) if numbers else float('inf')

    files = sorted(filter(is_audio_file, os.listdir(input_folder)), key=sort_key)

    for i, file in enumerate(files):
        # Construct the full file paths
        speech_path = os.path.join(input_folder, file)
        output_path = os.path.join(output_folder, file)

        original_audio = AudioSegment.from_file(speech_path)
        
        if original_audio is not None:
            # Check if it's the first or the last file
            if i == 0:
                # Add silence only at the end and increase the volume
                processed_audio = original_audio + AudioSegment.silent(duration=silence_duration)
                processed_audio += volume_increase

                # Export the processed audio
                processed_audio.export(output_path, format=speech_path.split('.')[-1])
                print(f"Copied {file} with silence at the end")
            elif i == len(files) - 1:
                # Add silence only at the beginning and increase the volume
                processed_audio = AudioSegment.silent(duration=silence_duration) + original_audio
                processed_audio += volume_increase
                
                # Export the processed audio
                processed_audio.export(output_path, format=speech_path.split('.')[-1])
                print(f"Copied {file} with silence at the beginning")
            else:
                # Add background music to the file
                mix_speech_with_music(speech_path, music_path, output_path, silence_duration, volume_increase)
                print(f"Processed {file} with background music")

# Main function to process script and generate audio
def process_script_and_generate_audio(script, artist_output_path, artist_name):
    parts, tracks = split_script_by_music_and_pauses(script)
    generate_tracklist(tracks, f'{artist_output_path}/scripts')
    generate_sequence_file(parts, tracks, f'{artist_output_path}/scripts')
    #create_playlist_from_list(tracks, artist_name)

    if False:
        speech_cost = generate_speech_and_save_with_pauses(parts, f'{artist_output_path}/audio/raw', generate_speech)
    else:
        speech_cost = 0

    process_directory_for_bgm(f'{artist_output_path}/audio/raw', 'background_music/background_1.wav', f'{artist_output_path}/audio/with_bgm')

    return speech_cost