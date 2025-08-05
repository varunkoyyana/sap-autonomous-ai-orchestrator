# Project Architecture

This document outlines the high-level architecture for the Autonomous SAP Workflow Orchestrator Powered by Generative AI Agents.

---

## System Overview

The system allows users to request SAP business processes in natural language. Via a frontend dashboard, requests are submitted to an API that orchestrates a series of specialized AI agents (for HR, Finance, Procurement, etc.). These agents communicate with both structured (relational) and unstructured (vector) data sources, and execute tasks by calling SAP APIs. Workflow status and results are continuously tracked and presented to the user.

---

## Component Diagram

<pre> ```mermaid flowchart LR A[User Interface&lt;br/&gt;(Streamlit/Dash/React)] B[Gateway API&lt;br/&gt;(FastAPI)] C[Agentic Orchestrator&lt;br/&gt;(LangChain/LangGraph)] D1[AI Agent - HR Domain] D2[AI Agent - Finance Domain] D3[AI Agent - Procurement Domain] E1[Vector Database&lt;br/&gt;(FAISS/Pinecone)] E2[Relational DB&lt;br/&gt;(PostgreSQL)] F[SAP/BTP APIs or Mock Services] A --> B B --> C C --> D1 C --> D2 C --> D3 D1 --> E1 D2 --> E1 D3 --> E1 D1 --> E2 D2 --> E2 D3 --> E2 D1 --> F D2 --> F D3 --> F C --> E2 ``` </pre>
## Component Explanations

- **User Interface:** Allows natural language input and shows workflow statuses.
- **Gateway API:** FastAPI service to receive and route requests.
- **Agentic Orchestrator:** Core logic (LangChain/LangGraph) that breaks requests into subtasks, selects appropriate agents.
- **AI Agents:** Microservices handling domain-specific tasks by accessing data and/or SAP functionality.
- **Vector Database:** Stores semantic document embeddings for AI-powered retrieval.
- **Relational DB:** Manages workflow states, structured records, and logs.
- **SAP APIs:** Real or mocked endpoints for SAP process execution.
