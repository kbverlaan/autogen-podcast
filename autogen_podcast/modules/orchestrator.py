from typing import List, Tuple, Optional
from autogen_podcast.modules import llm
import autogen

class Orchestrator:
    def __init__(self, name: str, agents: List[autogen.ConversableAgent]):
        self.name = name
        self.agents = agents
        self.messages = []
        self.complete_keyword = 'APPROVED'
        self.error_keyword = 'ERROR'

        if len(agents) < 2:
            raise Exception("Orchestrator needs at least two agents")
        
    @property
    def total_agents(self):
        return len(self.agents)
    
    @property
    def last_message_is_dict(self):
        return isinstance(self.messages[-1], dict)
    
    @property
    def last_message_is_string(self):
        return isinstance(self.messages[-1], str)
    
    @property
    def last_message_is_func_call(self):
        return self.last_message_is_dict and self.latest_message.get(
            "function_call", None
        )

    @property 
    def last_message_is_content(self):
        return self.last_message_is_dict and self.latest_message.get("content", None)

    @property
    def latest_message(self) -> Optional[str]:
        if not self.messages:
            return None
        return self.messages[-1]

    def get_cost_and_tokens(self): 
        messages_as_str = ""

        for message in self.messages:
            if message is None:
                continue
            
            if isinstance(message, dict):
                content_from_dict = message.get('content', None)
                func_call_from_dict = message.get('function_call', None)
                content = content_from_dict or func_call_from_dict
                if not content:
                    continue
                messages_as_str += str(content)
            else:
                messages_as_str += str(message)

        return llm.estimate_price_and_tokens(messages_as_str)

    def add_message(self, message: str):
        self.messages.append(message)

    def has_functions(self, agent: autogen.ConversableAgent):
        return bool(agent._function_map)
    
    def basic_chat(
            self, 
            agent_a: autogen.ConversableAgent, 
            agent_b: autogen.ConversableAgent, 
            message: str,
    ):
        print(f"basic_chat: {agent_a.name} -> {agent_b.name}")

        agent_a.send(message, agent_b)

        reply = agent_b.generate_reply(sender=agent_a)

        self.add_message(reply)

        print("basic_chat(): replied with:", reply)
    
    def memory_chat(
            self, 
            agent_a: autogen.ConversableAgent, 
            agent_b: autogen.ConversableAgent, 
            message: str,
    ):
        print(f"memory_chat: {agent_a.name} -> {agent_b.name}")

        agent_a.send(message, agent_b)

        reply = agent_b.generate_reply(sender=agent_a)

        agent_b.send(message, agent_b)

        self.add_message(reply)

    def function_chat(
            self, 
            agent_a: autogen.ConversableAgent, 
            agent_b: autogen.ConversableAgent, 
            message: str
    ):
        print(f"function_call(): {agent_a.name} -> {agent_b.name}")

        self.basic_chat(agent_a, agent_a, message)

        assert self.last_message_is_content

        self.basic_chat(agent_a, agent_b, self.latest_message)
    
    def sequential_conversation(self, prompt: str) -> Tuple[bool, List[str]]:
        """
        Runs a sequential conversation between agents

        For example
            "Agent A" -> "Agent B" -> "Agent C" -> "Agent D" -> "Agent E" 
        """

        print(f"\n\n---------- {self.name} Orchestrator Starting ----------\n\n")

        self.add_message(prompt)

        for idx, agent in enumerate(self.agents):
            agent_a = self.agents[idx]
            agent_b = self.agents[idx + 1]

            print(f"\n\n--------- Running iteration {idx} with (agent_a: {agent_a.name}, agent_b: {agent_b.name}) ----------\n\n")

            # agent a -> chat -> agent_b
            if self.last_message_is_string:
                self.basic_chat(agent_a, agent_b, self.latest_message)

            #agent_a -> func() -> agent_b
            if self.last_message_is_func_call and self.has_functions(agent_a):
                self.function_chat(agent_a, agent_b, self.latest_message)
            
            if idx == self.total_agents - 2:
                print(f"---------- Orchestrator Complete --------- \n\n")

                was_succesful = self.complete_keyword in self.latest_message 

                if was_succesful:
                    print(f"✅ Orchestrator was succesful")
                else:
                    print(f"❌ Orchestrator failed")

                return was_succesful, self.messages
            
    def broadcast_conversation(self, prompt: str) -> Tuple[bool, List[str]]:
        """
        Runs a broadcast conversation between agents

        For example
            "Agent A" -> "Agent B"
            "Agent A" -> "Agent C" 
            "Agent A" -> "Agent D" 
            "Agent A" -> "Agent E" 
        """
        print(f"\n\n---------- {self.name} Orchestrator Starting ----------\n\n")

        self.add_message(prompt)

        broadcast_agent = self.agents[0]

        for idx, agent_iterate in enumerate(self.agents[1:]):
            print(f"\n\n--------- Running iteration {idx} with (agent_broadcast: {broadcast_agent.name}, agent_iteration: {agent_iterate.name}) ----------\n\n")

            # agent a -> chat -> agent_b
            if self.last_message_is_string:
                self.memory_chat(broadcast_agent, agent_iterate, prompt)

            #agent_a -> func() -> agent_b
            if self.last_message_is_func_call and self.has_functions(agent_iterate):
                self.function_chat(agent_iterate, agent_iterate, self.latest_message)
            
        print(f"---------- Orchestrator Complete --------- \n\n")

        print(f"✅ Orchestrator was succesful\n")

        return True, self.messages

    def feedback_conversation(self, prompt: str) -> Tuple[bool, List[str]]:
        """
        Runs a feedback-based conversation between agents, alternating turns.
        
        The conversation will continue until either the `complete_keyword` appears
        in the `latest_message` or a maximum of 5 turns are reached.
        
        Args:
            prompt (str): The initial prompt to start the conversation.

        Returns:
            Tuple[bool, List[str]]: Whether the `complete_keyword` was found and the list of messages.
        """
        
        print(f"\n\n---------- {self.name} Feedback Conversation Starting ----------\n\n")
        self.add_message(prompt)
        turn = 0

        #init conversation between admin and strategy planner
        agent_a = self.agents[turn % 2]
        agent_b = self.agents[1- (turn % 2)]

        if self.last_message_is_string:
            self.basic_chat(agent_a, agent_b, self.latest_message)

        #continue conversation between planner and auditor
        while self.complete_keyword not in self.latest_message:
            agent_a = self.agents[1 + turn % 2]  # This will alternate between 1 and 2
            agent_b = self.agents[3 - (turn % 2) - 1]  # This will also alternate between 1 and 2 but in the opposite order

            print(f"\n\n--------- Running iteration {turn} with (agent_a: {agent_a.name}, agent_b: {agent_b.name}) ----------\n\n")

            # agent a -> chat -> agent_b
            if self.last_message_is_string:
                self.basic_chat(agent_a, agent_b, self.latest_message)
            # agent_a -> func() -> agent_b
            elif self.last_message_is_func_call and self.has_functions(agent_a):
                self.function_chat(agent_a, agent_b, self.latest_message)

            turn += 1
            if turn > 6:
                print("Maximum turns reached. Terminating the conversation.")
                break
        else:
            print(f"✅ Orchestrator was successful as the complete keyword was found.")
            return True, self.messages

        print(f"❌ Orchestrator failed as the complete keyword wasn't found.")
        return False, self.messages

    def functional_monologue(self, prompt: str) -> Tuple[bool, List[str]]:
        print(f"\n\n---------- {self.name} Functional Monologue Starting ----------\n\n")
        self.add_message(prompt)

        broadcast_agent = self.agents[0]
        functional_agent = self.agents[1]

        turn = 0
        while self.complete_keyword not in self.latest_message:
            print(f"\n\n--------- Running iteration {turn} with (agent: {functional_agent.name}) ----------\n\n")

            # agent a -> chat -> agent_b
            if self.last_message_is_string:
                self.memory_chat(broadcast_agent, functional_agent, prompt)

            #agent_a -> func() -> agent_b
            if self.last_message_is_func_call and self.has_functions(functional_agent):
                self.function_chat(functional_agent, functional_agent, self.latest_message)

            turn += 1
            if turn > 4:
                print("Maximum turns reached. Terminating the conversation.")
                break
        else:
            print(f"✅ Orchestrator was successful as the complete keyword was found.")
            return True, self.messages

        print(f"❌ Orchestrator failed as the complete keyword wasn't found.")
        return False, self.messages