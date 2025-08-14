import requests
import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# -------------------------------------------------
# Configure logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = FastAPI()

# -------------------------------------------------
# Load HR reference documents and embeddings
# -------------------------------------------------
try:
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    DOC_PATH = os.path.join(os.path.dirname(__file__), "hr_docs.txt")
    with open(DOC_PATH, "r") as f:
        HR_DOCS = [line.strip() for line in f if line.strip()]
    HR_EMB = np.array(MODEL.encode(HR_DOCS))
    INDEX = faiss.IndexFlatL2(HR_EMB.shape[1])
    INDEX.add(HR_EMB)
    logging.info(f"Loaded {len(HR_DOCS)} HR documents.")
except Exception as e:
    logging.error("Failed to load HR docs or embeddings: %s", e)
    HR_DOCS = []
    INDEX = None

def search_docs(query, top_k=1):
    try:
        q_emb = MODEL.encode([query])
        D, I = INDEX.search(np.array(q_emb), top_k)
        return [HR_DOCS[i] for i in I[0]]
    except Exception as e:
        logging.error("Error searching HR docs: %s", e)
        return []

# -------------------------------------------------
# Load environment variables and LLM
# -------------------------------------------------
load_dotenv()

llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

SAP_API_URL_HR = os.getenv("SAP_API_URL_HR", "")
SAP_API_URL_LEAVE = os.getenv("SAP_API_URL_LEAVE", "")

def get_sap_token():
    """Fetch OAuth2 token from SAP BTP service key credentials."""
    token_url = os.getenv("SAP_TOKEN_URL")
    client_id = os.getenv("SAP_CLIENT_ID")
    client_secret = os.getenv("SAP_CLIENT_SECRET")

    if not all([token_url, client_id, client_secret]):
        msg = "Missing SAP OAuth2 credentials in .env"
        logging.error(msg)
        raise RuntimeError(msg)

    try:
        resp = requests.post(
            token_url,
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret)
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        logging.info("SAP token retrieved successfully.")
        return token
    except Exception as e:
        logging.error("Error fetching SAP token: %s", e)
        raise

def generate_answer(query, context):
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert HR assistant. Use the provided company HR documents to answer clearly and concisely."),
            ("human", "Question: {question}\nContext: {context}")
        ])
        return llm.invoke(prompt.format_messages(question=query, context=context)).content
    except Exception as e:
        logging.error("Error generating LLM answer: %s", e)
        return "Error generating answer."

# -------------------------------------------------
# Request model
# -------------------------------------------------
class TaskRequest(BaseModel):
    task: str

# -------------------------------------------------
# Health check endpoint
# -------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

# -------------------------------------------------
# Main endpoint for HR tasks (Onboarding + Leave)
# -------------------------------------------------
@app.post("/task")
def execute_task(request: TaskRequest):
    logging.info("Received task: %s", request.task)
    q = request.task.lower()

    try:
        if "policy" in q or "info" in q or "onboard" in q or "leave" in q:
            results = search_docs(request.task)
            context_doc = results[0] if results else ""
            answer = generate_answer(request.task, context_doc)

            # -------------------------------------------------
            # Onboarding section
            # -------------------------------------------------
            if "onboard" in q:
                payload = {
                    "employeeName": "Jane Doe",  # Replace or parse dynamically
                    "department": "IT",
                    "startDate": "2025-08-14"
                }
                try:
                    token = get_sap_token()
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    logging.info("Sending onboarding request to SAP: %s", SAP_API_URL_HR)
                    sap_resp = requests.post(SAP_API_URL_HR, json=payload, headers=headers)
                    sap_status = sap_resp.status_code

                    if sap_resp.headers.get("Content-Type", "").startswith("application/json"):
                        sap_result = sap_resp.json()
                    else:
                        sap_result = sap_resp.text

                    logging.info("SAP Onboarding API Response Status: %s", sap_status)
                except Exception as e:
                    sap_status = "ERROR"
                    sap_result = str(e)
                    logging.error("SAP onboarding API call failed: %s", e)

                return {
                    "result": answer,
                    "source_document": context_doc,
                    "sap_api_status": sap_status,
                    "sap_api_result": sap_result
                }

            # -------------------------------------------------
            # Leave request section
            # -------------------------------------------------
            if "leave" in q:
                payload = {
                    "employeeName": "John Smith",  # Replace or parse dynamically
                    "leaveType": "Annual",
                    "startDate": "2025-09-01",
                    "endDate": "2025-09-10"
                }
                try:
                    token = get_sap_token()
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    logging.info("Sending leave request to SAP: %s", SAP_API_URL_LEAVE)
                    sap_resp = requests.post(SAP_API_URL_LEAVE, json=payload, headers=headers)
                    sap_status = sap_resp.status_code

                    if sap_resp.headers.get("Content-Type", "").startswith("application/json"):
                        sap_result = sap_resp.json()
                    else:
                        sap_result = sap_resp.text

                    logging.info("SAP Leave API Response Status: %s", sap_status)
                except Exception as e:
                    sap_status = "ERROR"
                    sap_result = str(e)
                    logging.error("SAP leave API call failed: %s", e)

                return {
                    "result": answer,
                    "source_document": context_doc,
                    "sap_api_status": sap_status,
                    "sap_api_result": sap_result
                }

            # Generic HR info
            return {
                "result": answer,
                "source_document": context_doc
            }

        # Fallback
        return {
            "result": f"HR agent received unclassified task: '{request.task}'"
        }

    except Exception as e:
        logging.error("Unexpected error in execute_task: %s", e)
        return {
            "error": str(e),
            "message": "Internal server error during HR task processing."
        }
