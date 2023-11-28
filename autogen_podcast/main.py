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

#nltk.download('punkt')

dotenv.load_dotenv()

assert os.environ.get("OPENAI_API_KEY") is not None, "OPENAI_API_KEY not found in .env file"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

artist = "The Doobie Brothers"
create_outline = False
create_script = False
create_audio = True

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
        with open('./temp_output/outline', "w") as f:
            f.write(outline)

        total_cost += cost
        total_tokens += tokens
        
        print(f"Iteration cost: {cost}, tokens: {tokens}")
        print(f"Total cost: {total_cost}, tokens: {total_tokens}")
    elif create_script:
        with open('./temp_output/outline', 'r') as f:
            outline = f.read()

    if create_script: #Create script
         # ----- Script Creation -----
        sections = outline.split("----------\n")
        starting_script = 0

        folder_path = './temp_output'
        # Loop through all files in the folder
        for filename in os.listdir(folder_path):
            # Check if 'script' is in the filename
            if 'script' in filename:
                # Construct full file path
                file_path = os.path.join(folder_path, filename)
                # Delete the file
                os.remove(file_path)

        for i, section in enumerate(sections[starting_script+1:]):
            i += starting_script
            # Import last sections script if not the first iteration
            if i > 0:
                with open(f'./output/script_{i-1}', 'r') as f:
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
            
            with open(f'./temp_output/script_{i}', "w") as f:
                f.write(script)

            cost, tokens = script_writer_orchestrator.get_cost_and_tokens()
            total_cost += cost
            total_tokens += tokens
            print(f"\nIteration cost: {cost}, tokens: {tokens}")
            print(f"Total cost: {total_cost}, tokens: {total_tokens}")

            print("\nSleeping for 60 seconds.")
            time.sleep(60)
    
        # Save entire script
        # Set the directory where your scripts are located
        folder_path = './temp_output'
        output_path = './full_scripts'

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
        with open(f'./full_scripts/{artist_name_formatted}_script.txt', 'r') as f:
            script = f.read()
        
        speech_cost = tts.process_script_and_generate_audio(script, './output/audio', artist)

        total_cost += speech_cost
        print(f"Total cost: {total_cost}, tokens: {total_tokens}")


if __name__ == '__main__':
    main()
