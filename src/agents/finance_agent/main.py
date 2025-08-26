import requests
import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
import faiss
import numpy as np
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------------------------------
# Configure logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = FastAPI()

# -------------------------------------------------
# OpenAI Embedding Function (replacing HuggingFace)
# -------------------------------------------------
def get_openai_embedding(texts):
    """Use OpenAI embeddings instead of HuggingFace"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if isinstance(texts, str):
            texts = [texts]
            
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-ada-002"
        )
        
        embeddings = [item.embedding for item in response.data]
        return np.array(embeddings)
        
    except Exception as e:
        logging.error(f"OpenAI embedding error: {e}")
        raise

# -------------------------------------------------
# Load Finance reference documents and embeddings
# -------------------------------------------------
try:
    DOC_PATH = os.path.join(os.path.dirname(__file__), "finance_docs.txt")
    with open(DOC_PATH, "r") as f:
        FINANCE_DOCS = [line.strip() for line in f if line.strip()]
    
    logging.info(f"Loaded {len(FINANCE_DOCS)} Finance document lines from {DOC_PATH}")
    logging.info(f"First document: {FINANCE_DOCS[0] if FINANCE_DOCS else 'NONE'}")
    
    FIN_EMB = get_openai_embedding(FINANCE_DOCS)
    INDEX = faiss.IndexFlatL2(FIN_EMB.shape[1])
    INDEX.add(FIN_EMB)
    logging.info(f"Successfully created embeddings and index with OpenAI")
    
except Exception as e:
    logging.error("Failed to load Finance docs or embeddings: %s", e)
    logging.error(f"Current working directory: {os.getcwd()}")
    logging.error(f"Files in current directory: {os.listdir('.')}")
    FINANCE_DOCS = []
    INDEX = None

def search_docs(query, top_k=3):
    """Search for relevant Finance documents"""
    try:
        if INDEX is None or len(FINANCE_DOCS) == 0:
            logging.warning("No Finance documents available for search")
            return []
            
        q_emb = get_openai_embedding([query])
        D, I = INDEX.search(q_emb, top_k)
        results = [FINANCE_DOCS[i] for i in I[0] if i < len(FINANCE_DOCS)]
        
        # Debug logging
        logging.info(f"Search query: {query}")
        logging.info(f"Found {len(results)} relevant documents")
        for i, doc in enumerate(results):
            logging.info(f"Doc {i}: {doc[:100]}...")
            
        return results
    except Exception as e:
        logging.error("Error searching Finance docs: %s", e)
        return []

# -------------------------------------------------
# Load environment variables and LLM
# -------------------------------------------------
load_dotenv()

llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

SAP_API_URL_INVOICE = os.getenv("SAP_API_URL_INVOICE", "")

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

def detect_intent(query: str):
    """Detect if query is informational or action-based"""
    action_patterns = [
        "apply for", "submit", "request", "create", "process",
        "want to", "need to", "how do i submit", "help me apply",
        "start", "begin", "initiate", "upload", "send"
    ]
    
    info_patterns = [
        "what is", "how many", "tell me", "count of", "policy",
        "information", "explain", "describe", "about", "details",
        "process", "procedure", "steps"
    ]
    
    query_lower = query.lower()
    
    # Check for action intent first
    if any(pattern in query_lower for pattern in action_patterns):
        return "action"
    elif any(pattern in query_lower for pattern in info_patterns):
        return "information"
    else:
        # Default to information for safety
        return "information"

def generate_answer(query, context_docs):
    """Generate answer using retrieved documents as context"""
    try:
        if not context_docs:
            context = "No relevant company documents found."
        else:
            context = "\n\n".join(context_docs)
        
        # Debug logging
        logging.info(f"Context being sent to LLM: {context[:300]}...")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Finance assistant for this company. 
            Use ONLY the provided company Finance documents to answer questions accurately. 
            If the information is not in the documents, say so clearly.
            Be specific and cite the exact information from the documents."""),
            ("human", "Company Finance Documents:\n{context}\n\nQuestion: {question}\n\nAnswer based on the company documents:")
        ])
        
        response = llm.invoke(prompt.format_messages(question=query, context=context))
        
        # Debug logging
        logging.info(f"LLM response: {response.content[:200]}...")
        
        return response.content
    except Exception as e:
        logging.error("Error generating LLM answer: %s", e)
        return "Error generating answer."

def process_invoice_action(query, context_answer, context_docs):
    """Process invoice action with SAP API call"""
    payload = {
        "invoiceNumber": "INV-20230815-001",  # This should be extracted from user input
        "vendorName": "ACME Supplies",
        "amount": 1250.0,
        "currency": "USD",
        "dueDate": "2025-09-30"
    }
    
    try:
        token = get_sap_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        logging.info("Sending invoice request to SAP: %s", SAP_API_URL_INVOICE)
        sap_resp = requests.post(SAP_API_URL_INVOICE, json=payload, headers=headers)
        sap_status = sap_resp.status_code

        if sap_resp.headers.get("Content-Type", "").startswith("application/json"):
            sap_result = sap_resp.json()
        else:
            sap_result = sap_resp.text

        logging.info("SAP Invoice API Response Status: %s", sap_status)
        
        return {
            "result": context_answer,
            "source_document": "\n".join(context_docs) if context_docs else "",
            "sap_api_status": sap_status,
            "sap_api_result": sap_result,
            "action_performed": "invoice_submitted"
        }
        
    except Exception as e:
        sap_status = "ERROR"
        sap_result = str(e)
        logging.error("SAP invoice API call failed: %s", e)
        
        return {
            "result": context_answer,
            "source_document": "\n".join(context_docs) if context_docs else "",
            "sap_api_status": sap_status,
            "sap_api_result": sap_result,
            "action_performed": "invoice_failed"
        }

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
# Debug endpoint
# -------------------------------------------------
@app.get("/debug")
def debug_info():
    return {
        "message": "FINANCE AGENT WITH OPENAI EMBEDDINGS",
        "timestamp": "2025-08-21-9:09PM",
        "finance_docs_count": len(FINANCE_DOCS),
        "sample_finance_doc": FINANCE_DOCS[0] if FINANCE_DOCS else "NO DOCS LOADED",
        "index_status": "LOADED" if INDEX is not None else "NOT LOADED"
    }

# -------------------------------------------------
# Main endpoint for Finance tasks
# -------------------------------------------------
@app.post("/task")
def execute_task(request: TaskRequest):
    logging.info("Received task: %s", request.task)
    
    try:
        # Step 1: Always retrieve relevant documents first
        relevant_docs = search_docs(request.task)
        
        # Step 2: Generate answer using retrieved context
        answer = generate_answer(request.task, relevant_docs)
        
        # Step 3: Detect intent (information vs action)
        intent = detect_intent(request.task)
        
        logging.info(f"Intent detected: {intent}")
        
        # Step 4: Handle based on intent and topic
        query_lower = request.task.lower()
        
        # Action-based requests
        if intent == "action":
            if "invoice" in query_lower:
                return process_invoice_action(request.task, answer, relevant_docs)
            # Add more finance actions here as needed
        
        # Information-based requests (default)
        return {
            "result": answer,
            "source_document": "\n".join(relevant_docs) if relevant_docs else "",
            "intent_detected": intent
        }

    except Exception as e:
        logging.error("Unexpected error in execute_task: %s", e)
        return {
            "error": str(e),
            "message": "Internal server error during Finance task processing."
        }