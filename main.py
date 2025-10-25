from dotenv import load_dotenv
from typing import Annotated,Literal
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import add_message
from langchain.chat_models import init_chat_model
from pydantic import BaseModel,Field
from typing_extensions import TypedDict

load_dotenv()

llm=init_chat_model(model="gpt-4o-mini",
api_key=os.getenv("OPENAI_API_KEY"))

#이런 형식으로 메세지를 받는다는 뜻인듯
class State(TypedDict):
    messages:Annotated[list,add_message]

graph_builder=StateGraph(State)

#class State(TypedDict):의 내용
def chatbot(state:State):
    return{"messages":llm.invoke(state["messages"])}

#말 그대로 Graph 노드 및 엣지 추가
graph_builder.add_node("chatbot",chatbot)#Graph 빌더에 노드 추가
graph_builder.add_edge(START,"chatbot")#START에서 chatbot으로 이동
graph_builder.add_edge("chatbot",END)#END에서 chatbot으로 이동

graph=graph_builder.compile()

user_input=input("Enter a message: ")
state=graph.invoke({"messages":[{"role":"user","content":user_input}]})