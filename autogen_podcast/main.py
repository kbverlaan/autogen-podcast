import os
from autogen_podcast.modules import llm, log, orchestrator, tts
from autogen_podcast.agents.inits import user_proxy, outline_writer, outline_critic, create_script_writer, create_script_critic
from autogen_podcast.agents.prompts import OPENING_PROMPT
import dotenv
import argparse
import autogen
import nltk
from nltk.tokenize import sent_tokenize
import time 
from pathlib import Path


#nltk.download('punkt')

dotenv.load_dotenv()

assert os.environ.get("OPENAI_API_KEY") is not None, "OPENAI_API_KEY not found in .env file"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

artist = "The Rolling Stones"
create_outline = False
create_script = False
create_audio = False
add_bgm = False
create_playlist = True

def main():
    #logging
    # Set up logging to file
    log.setup_logging()

    #Track cost
    total_cost = 0
    total_tokens = 0
    artist_name_formatted = artist.lower().replace(' ', '_')

    if create_outline: #Create outline
        prompt = f"Create an outline for a podcast that gives an introduction around the discography of {artist}.\n" + OPENING_PROMPT

        # ----- Outline Creation ------
        outline_creation_orchestrator = orchestrator.Orchestrator(
            name="Outline Creation",
            agents=[user_proxy, outline_writer, outline_critic]
        )

        _, strategy_messages = outline_creation_orchestrator.feedback_conversation(prompt)
        cost, tokens = outline_creation_orchestrator.get_cost_and_tokens()
        outline = strategy_messages[-2]

        output_folder = f'./output/{artist}/scripts'
        Path(output_folder).mkdir(parents=True, exist_ok=True)
        with open(f'{output_folder}/outline.txt', "w") as f:
            f.write(outline)

        total_cost += cost
        total_tokens += tokens
        
        print(f"Iteration cost: {cost}, tokens: {tokens}")
        print(f"Total cost: {total_cost}, tokens: {total_tokens}")
    elif create_script:
        with open(f'./output/{artist}/scripts/outline.txt', 'r') as f:
            outline = f.read()

    if create_script: #Create script
         # ----- Script Creation -----
        sections = outline.split("----------\n")
        starting_script = 0
        
        # Determine and create path for script parts
        folder_path = f'./output/{artist}/scripts/script_parts'
        Path(folder_path).mkdir(parents=True, exist_ok=True)

        # Delete old scripts
        # Loop through all files in the folder
        for filename in os.listdir(folder_path):
            # Check if 'script' is in the filename
            if 'script' in filename:
                # Construct full file path
                file_path = os.path.join(folder_path, filename)
                # Delete the file
                os.remove(file_path)

        for i, section in enumerate(sections[starting_script+1:]):
            # Create starting point
            i += starting_script

            # Determine script path
            file_path = os.path.join(folder_path, f'script_{i-1}')

            # Import last sections script if not the first iteration
            if i > 0:
                with open(file_path, 'r') as f:
                    LAST_SECTION_SCRIPT = f.read() 
                last_three_sentences = ' '.join([sentence for sentence in sent_tokenize(LAST_SECTION_SCRIPT) if not sentence.endswith('?')][-3:])
            else:
                INTRODUCTION = "\n\nBegin the podcast introduction for 'Rhythm and Roots' following the provided outline. "

            prompt = f"""Write the part of the script for the following section outline: \n {section}"""
            if i != 0:
                prompt = prompt + f"""\n\nUse the following last sentences of the previous section to create a smooth transition.\nLAST SENTENCES OF PREVIOUS SECTION\n--- {last_three_sentences} ---"""
            else:
                prompt = INTRODUCTION + prompt
        
            # Insert last script and section as a prompt into feedback conversation function
            script_writer = create_script_writer()
            script_critic = create_script_critic()

            script_writer_orchestrator = orchestrator.Orchestrator(
                name=f"Script no. {i} Creation",
                agents=[user_proxy, script_writer, script_critic]
            )
            _, strategy_messages = script_writer_orchestrator.feedback_conversation(prompt)
            script = strategy_messages[-2]
            
            with open(os.path.join(folder_path, f'script_{i}'), "w") as f:
                f.write(script)

            cost, tokens = script_writer_orchestrator.get_cost_and_tokens()
            total_cost += cost
            total_tokens += tokens
            print(f"\nIteration cost: {cost}, tokens: {tokens}")
            print(f"Total cost: {total_cost}, tokens: {total_tokens}")

            print("\nSleeping for 30 seconds.")
            time.sleep(30)
    
        # Save entire script
        # Set the directory where your scripts are located
        output_path = f'./output/{artist}/scripts'

        # List all the files in the directory and sort them
        file_list = sorted([f for f in os.listdir(folder_path) if f.startswith('script_')])

        # Create a new file to combine all scripts
        with open(f'{output_path}/{artist_name_formatted}_script.txt', 'w') as outfile:
            for script_file in file_list:
                with open(os.path.join(folder_path, script_file), 'r') as infile:
                    # Write the content of each script file to the combined script file
                    outfile.write(infile.read() + '\n\n')  # Adds a newline between each script for readability
        
        print('Script Exported')
        print(f"Total cost: {total_cost}, tokens: {total_tokens}")

    if create_audio:
        # Determine path
        artist_folder_path = f'./output/{artist}'

        with open(f'{artist_folder_path}/scripts/{artist_name_formatted}_script.txt', 'r') as f:
            script = f.read()
        
        speech_cost = tts.process_script_and_generate_audio(script, f'{artist_folder_path}')

        total_cost += speech_cost
        print(f"Total cost: {total_cost}, tokens: {total_tokens}")
    
    if add_bgm:
        tts.process_directory_for_bgm(f'{artist_folder_path}/audio/raw', 'background_music/background_1.wav', f'{artist_folder_path}/audio/with_bgm')

    if create_playlist:
        artist_folder_path = f'./output/{artist}'
        with open(f'{artist_folder_path}/scripts/{artist_name_formatted}_script.txt', 'r') as f:
            script = f.read()

        _, tracks = tts.split_script_by_music_and_pauses(script)
        tts.create_playlist_from_list(tracks, artist)


if __name__ == '__main__':
    main()
