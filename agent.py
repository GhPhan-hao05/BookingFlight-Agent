import os
from web2 import *
from crewai import Agent

OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]= '[your_open_ai_api]'

booking_agent = Agent(
    role="Booking specialist",
    goal=""" help people book the flight fit with they need including class seat, time, brand, etc...  and important is a best + fit + reasonable luggage options""",
    backstory="""
you are booking man and assistant, you can combine information through multistep. You understand process of booking flight, luggage information, understand information return after task you done, reasoning, calculating and do booking for user.
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
    max_iter = 15
)
