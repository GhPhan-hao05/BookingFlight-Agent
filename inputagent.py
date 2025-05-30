

import os
from typing import List, Dict, Any
import json
import requests
from datetime import datetime
from llama_index.llms.openai import OpenAI
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import Settings
from llama_index.core.chat_engine  import SimpleChatEngine
from llama_index.core.llms import ChatMessage, MessageRole
OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]= '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'
from web2 import *

class LlamaIndexTaskAgentWithSearch:
    def __init__(self, system_prompt, model_name = "gpt-4o"):

        # Configure the LLM
        self.llm = OpenAI(model=model_name, temperature=0.7, api_key=OPENAI_API_KEY)
        Settings.llm = self.llm
        Settings.context_window = 4096
        Settings.num_output = 1024


        # Store conversation history

# Create a memory buffer with the system prompt as the first message
        self.memory = ChatMemoryBuffer.from_defaults(token_limit=1000)

        # Create a chat engine with memory
        self.chat_engine = SimpleChatEngine.from_defaults(llm=self.llm, chat_memory=self.memory)
        self.conversation_history = []

        # Store the system prompt for future reference
        self.system_prompt = system_prompt

    def process_message(self, user_message: str) -> str:
        """
        1 vòng của hội thoại, nhận tin nhắn -> cập nhật lịch sử -> nhận câu trả lời -> cập nhật lịch sử

        Args:
            user_message: tin nhắn từ user

        Returns:
            phản hồi từ llm
        """
        # cập nhật lịch sử
        if len(self.conversation_history) == 0:
          self.conversation_history.append({"role": "user", "content": self.system_prompt})
          response = self.chat_engine.chat(self.system_prompt)
          return
        else:
          self.conversation_history.append({"role": "user", "content": user_message})
          #feed cho llm
          response = self.chat_engine.chat(user_message)
          #nhận respone
          response_text = response
          #cập nhật lịch sử
          self.conversation_history.append({"role": "assistant", "content": response_text})
          return response_text


    def get_conversation_history(self) -> List[Dict[str, str]]:
        return self.conversation_history

    def extract_final_request(self) -> str:

        # Prepare messages for the extraction query
        chat_history_str = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in self.conversation_history
        ])

        extraction_prompt = f"""
        Based on the following conversation, extract the final request details and personal information in natural language:

        {chat_history_str}

        return athe natural request about what user want about their flight according to history chat, notice when people give 1 option but after that they give another one, you should be careful about that.
        one more thing is just return what user request, what information user provide, dont ask addtion about mising because we alreeady asked and user dont wanna give the answer
        the output will like:
        Can find an economy-class flight from Houston to Phu Quoc on 03/08/2025?budget is $1,150, and I’d prefer Vietnam Airlines or Qatar Airways. Departure time should be around 6 PM. (may be have hotel near beach, hotel have gym...).
        My personal information is first, last name, email, phone, personal id, ...
        """

        # Create a list of messages for the extraction
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="You extract natural request from conversations."),
            ChatMessage(role=MessageRole.USER, content=extraction_prompt)
        ]

        # Get the extraction response
        extraction_response = self.llm.chat(messages)

        return extraction_response.message.content

def demo_conversation():#gemma 3 1b
    # Define your system prompt - this is where you define how your "employee" should behave
    system_prompt = """
    you are booking assistant, user will send an initial booking request in natural language. Your task is to analysis it, check feasibility, ask user questions to get enought information about flight booking and after is personal information
    for example for check feasibility: If the requested destination doesn't have an airport, you must suggest nearby airports; or user's budget is too low compared to the expected value of the flight, or lack of date, lack of seat class...

    When asking for more information about filght booking request, you need ask about to:
        1. Origin and destination cities
        2. Dates of travel, time to travel
        3. Price range
        4. Class preference (economy, business, etc.)
        5. Company (VietNam Airlines, Quatar Airways)
        notice: you should be ask user about those option, dont list all constrain and let user declare them by themself.
        -wrong way: choose date, choose class seat
        -right: It seem like you miss some information about date depart, the brand you prefer,... please tell me more about them
        Always verify that the requested service is actually possible before proceeding.
        remember, you just corrector, not booking reality flight.
    After get enought information about booking flight request. ask about personal information, including:
        first_name, last_name, phone, email, title (MR, MRS, MISS), id_number and date of birth 

    Follow these guidelines in every response:
    1. If the user's request lacks essential information, ask specific clarifying questions.
    2. If the user requests something impossible, explain and suggest reasonable alternatives.
    3. Think step by step before responding. dont ask too much, just ask about general information
    4. Maintain a helpful, professional tone throughout the conversation.
    """

    # Initialize the agent
    # For real search, provide your search API key: search_api_key="your_api_key_here"
    agent = LlamaIndexTaskAgentWithSearch(system_prompt=system_prompt)

    # Simulate a conversation
    print("Agent initialized. Type 'exit' to end the conversation.")
    print("Type 'ok' to get the final request summary.")
    print("\nStart your conversation:")
    final_request = 'aaa'
    i = 0

    while True:
      if i == 0:
        response = agent.process_message('hi')
        i+=1
        continue
      else:
        user_input = input("\nYou: ")

        if user_input.lower() == 'exit':
            return final_request


        if user_input.lower() == 'ok':
            print("\nFinal Request Summary:")
            final_request = agent.extract_final_request()
            print(final_request)
            continue

        response = agent.process_message(user_input)
        i+=1

        print(f"\nAssistant: {response}")

if __name__ == "__main__":
    request = demo_conversation()
    booking_agent = Agent(
        role="Booking specialist",
        goal=""" do booking flight process with these step: 
        (step 1) get input, understand and parse to get input for following step
        (step 2) insert depart city, destination city and day depart the information is fixed in tool;
        (step 3) filter flight by time and flight company (can filter with or without results), returrn note, result and seat options;
        (step 4) choose seat option best fit with user (class seat is prior condition) in cheapest price;
        (step 5) insert user information and choose luggage option if flight company offer (consider no luggage is 1 option)., when choose luggage option, please remain, thinking, reasoning how much luggage capacity extra user need, 
        because all flight have free 7kg of luggage, and some time in seat option which you chooose in previous already have some luggage capacity.
        for example, user have 24kg of luggage, but subtract for 7kg in default, user need 17kg extra luggage, but in seat class option you already choose option attach 20kg of luggage, so you should be choose option "no need luggage 0kg", that is 1 example you reference
        (step 6) if offer luggage option, choose option
        (step 7) go to payment page and done
        the tools need id of options, the id begin from 1, not 0
        some step willl return notice and some raw information like seat option, luggage option, you need to parse them, reasoning before feed to tools.
        Call tool step by step, reasoning each step to book the flight, and stop when booking success""",
        backstory="""
you are booking man and assistant, you understand process of booking flight, understand information return after task you done, reasoning, calculating and do booking for user.
        """,
        verbose=True,
        tools=[
            InsertInf(),
            FilterTool(),
            ChooseSeatOptionTool(),
            InsertPersonalInformationTool(),
            ChooseLuggageOptionTool(),
            GoToPayTool()
        ],
        max_iter = 10
    )

    input_task = Task(
        description=f"""{request}
        parse this input and feed for another task another tools""",
        agent=booking_agent,
        expected_output="return string all information about flight booking request"
    )
    booking_crew = Crew(
        agents=[booking_agent],
        tasks=[input_task ],#, insert_inf_task, filter_flight_task, choose_seat_options
        verbose=True,
        planning=True,
    )

    # Run the crew
    result = booking_crew.kickoff()
