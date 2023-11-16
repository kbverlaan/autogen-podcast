from autogen_podcast.agents.prompts import USER_PROXY_PROMPT, OUTLINE_WRITER_PROMPT, OUTLINE_CRITIC_PROMPT, SCRIPT_CRITIC_PROMPT, SCRIPT_WRITER_PROMPT
from autogen_podcast.agents.configs import base_config
import autogen

# create our terminate msg function
def is_termination_msg(content):
    have_content = content.get("content", None) is not None
    if have_content and "APPROVED" in content['content']:
        return True
    return False
    
user_proxy = autogen.UserProxyAgent(
    name="Admin",
    system_message=USER_PROXY_PROMPT,
    code_execution_config=False,
    human_input_mode="ALWAYS",
    is_termination_msg=is_termination_msg
)

outline_writer = autogen.AssistantAgent(
    name="Outline_Writer",
    llm_config=base_config,
    system_message=OUTLINE_WRITER_PROMPT,
    code_execution_config=False,            
    human_input_mode="NEVER",
    is_termination_msg=is_termination_msg
)

outline_critic = autogen.AssistantAgent(
    name="Outline_Critic",
    llm_config=base_config,
    system_message=OUTLINE_CRITIC_PROMPT,
    code_execution_config=False,
    human_input_mode="NEVER",
    is_termination_msg=is_termination_msg,
)

def create_script_writer():
    return autogen.AssistantAgent(
        name="Script_Writer",
        llm_config=base_config,
        system_message=SCRIPT_WRITER_PROMPT,
        code_execution_config=False,            
        human_input_mode="NEVER",
        is_termination_msg=is_termination_msg
    )   

def create_script_critic():
    return autogen.AssistantAgent(
        name="Script_Critic",
        llm_config=base_config,
        system_message=SCRIPT_CRITIC_PROMPT,
        code_execution_config=False,
        human_input_mode="NEVER",
        is_termination_msg=is_termination_msg,
    )