from dotenv import load_dotenv
import os
from typing import Annotated,Literal
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from pydantic import BaseModel,Field
from traitlets.traitlets import G
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Union

load_dotenv()

llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", 
    google_api_key=os.getenv("GEMINI_API_KEY"))

#Base Model on pydantic
#Classifier를 위해 type 설정 후 그에 따른 설명을 읽고 답변 생성(모델 생성)?
class MessageTypeClassifier(BaseModel):
    message_type:Literal["emotional","logical"]=Field(
        ...,
        description="Classify if the message requires an emotional (therapist) or logical response"
    )

#이런 형식으로 메세지를 받는다는 뜻인듯
#| in Python <= 3.9 would be Union[type1, type2] in a more general case
class State(TypedDict):
    messages:Annotated[list,add_messages]
    message_type: str | None 


def classify_message(stat:State):
    last_message=stat["messages"][-1]
    classifier_llm=llm.with_structured_output(MessageTypeClassifier)

    result=classifier_llm.invoke([
        {
            "role":"system",
            "content": """Classify the user message as either:

            - 'emotional': if it asks for emotional support, therapy, deals with feelings, or **personal issues.**
            - 'logical': if it asks for facts, information, logical analysis, or **practical solutions.**
            """
            },
        {
            "role":"user",
            "content":last_message.content
        } 
           
    ])
    return{"message_type":result.message_type}

def router(stat:State):
    message_type=stat["message_type"]
    if message_type=="emotional":
        return {"next":"therapist"}
    
    return {"next":"logical"}

def therapist_agent(stat:State):
    last_message=stat["messages"][-1]

    message=[
        {"role":"system",
        "content":"""You are a therapist. You are given a user 
        message and you need to respond  to it in a way that is helpful and supportive."""
        },
        {
            "role":"user",
            "content":last_message.content
        }
    ]
    reply=llm.invoke(message)
    return{"messages":[{"role":"assistant", "content":reply.content}]}

#두개의 다른 agent를 생성 했음
def logical_agent(stat:State):
    last_message=stat["messages"][-1]

    message=[
        {"role":"system",
        "content":"""You are a logical agent. You are given a user 
        message and you need to respond  to it in a way that is helpful and logical."""
        },
        {
            "role":"user",
            "content":last_message.content
        }
    ]
    reply=llm.invoke(message)
    return{"messages":[{"role":"assistant", "content":reply.content}]}

graph_builder=StateGraph(State)

graph_builder.add_node("classifier",classify_message)
graph_builder.add_node("router",router)
graph_builder.add_node("therapist",therapist_agent)
graph_builder.add_node("logical",logical_agent)

graph_builder.add_edge(START,"classifier")
graph_builder.add_edge("classifier","router")

graph_builder.add_conditional_edges(
    "router",
    lambda state:state.get("next"),
    {"therapist":"therapist", "logical":"logical"}
)

graph_builder.add_edge("therapist",END)
graph_builder.add_edge("logical",END)

graph=graph_builder.compile()

def run_chatbot():
    state ={"messages":[],"message_type":None}

    while True:
        user_input=input("Message: ")
        if user_input=="exit":
            print("Bye")
            break
        
        state["messages"]=state.get("messages",[])+[
            {"role":"user","content":user_input}
        ] 

        state=graph.invoke(state)

        if state.get("messages") and len(state["messages"]) > 0:
            last_message=state["messages"][-1]
            print(f"Assistant: {last_message.content}")

if __name__=="__main__":
    run_chatbot()