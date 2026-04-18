# EduOrchestrator: Autonomous Educational AI Agent System

![EduOrchestrator Banner](https://via.placeholder.com/1200x300?text=EduOrchestrator+-+Context-Aware+Agent+Architecture)

EduOrchestrator is a robust, schema-aware AI orchestration system designed to act as an autonomous educational companion. Built upon a Supervisor-Agent graph architecture, the system translates natural language queries into deterministic, validated tool executions while dynamically adapting to the user's emotional state, mastery level, and preferred teaching style.

---

## 🎯 Problem Statement

Naive LLM implementations (e.g., standard RAG pipelines or basic chat wrappers) suffer from severe limitations in educational contexts:
- **Hallucinations in Structured Tasks:** They struggle to output reliable, typed parameters for programmatic tools.
- **Context Blindness:** They treat an anxious beginner the exact same way they treat a confident expert.
- **Execution Failures:** They lack introspective mechanisms to detect when a generated output violates strict schema constraints, leading to application crashes.
- **Lack of Verification:** They assume the answer provided is always correct without an observational verification step.

## 💡 Solution Overview

EduOrchestrator solves this by introducing a highly structured, stateful LangGraph pipeline. Rather than generating a single monolithic response, the orchestrator breaks down interactions into isolated, deterministic nodes. It explicitly decouples reasoning, tool selection, schema validation, and execution. If an LLM hallucinates a parameter, the system intercepts it, auto-repairs the schema, or queries the user for clarification before any code execution occurs.

---

## 🏗️ System Architecture

The core of the system is a **Stateful Cyclic Graph** (built via LangGraph). Unlike a standard linear pipeline or simple DAG, this architecture supports **backtracking and self-correction loops** where the graph can re-route itself to fix validation errors or clarify intents before reaching the final output.

1. **Intake & Profiling:** The API receives the request, associates it with a JWT auth token, and pulls the active student's mastery and emotional profile.
2. **Context Analysis:** The system injects contextual modifiers into the state (e.g., `Style = Socratic`, `Difficulty Level = 3`).
3. **Reasoning Engine:** An LLM determines the user's true intent, flags required tools, and builds a initial thought process.
4. **Tool Selection:** A hybrid keyword-ranker + LLM overrides static rankings using the student profile heuristics.
5. **Schema Extraction:** The LLM extracts specific constraints based on the target tool schema.
6. **Validation & Self-Correction:** Verifies types, bounds, and enums. If the output is invalid, the graph **loops back** to the error handler or extractor to repair the payload autonomously.
7. **Execution:** The validated payload is routed to one of 18 dedicated Python tools.
8. **Observation & Finalization:** The execution output is synthesized and verified. If quality is low, the graph can loop back for a retry.

---

## 🧩 Key Components

- **Context Analyzer:** Intercepts the request and merges external DB data (Mastery Level 1-10, Emotion, Style) into the graph state.
- **Reasoner (LLM-based):** Determines the trajectory of the conversation. Output is strictly bounded to an intent classification and a confidence score.
- **Tool Selector (Hybrid):** Uses rapid textual overlap ranking, modified dynamically by contextual math overrides, falling back to a secondary LLM pick only if confidence drops below safe bounds.
- **Extractor:** Operates with forced JSON compliance to extract exactly what the selected tool's Pydantic schema demands.
- **Validator:** A strict constraint engine. If a schema requires an integer between 1-5 and the extractor produces `'three'`, the validator repairs it to `3`. If the extractor produces `9`, the Validator flags the error and triggers the Clarification node.
- **Observer:** Evaluates the tool's raw JSON output against the original user query to ensure the tool actually solved the problem before presenting it to the user.

---

## 🔧 Tool Integration & Registry

The system utilizes a decoupled tool design, supporting exactly 18 specific educational primitives (e.g., `concept_visualizer`, `mock_test`, `debate_speech_generator`). 

- **Schema Handling:** Tools declare their parameters using standard Python dictionaries reflecting strict typing schemas.
- **Integration Validation:** The Orchestrator does not have hardcoded paths to tools. The Tool Registry dynamically loads schemas. If a tool requires `["topic", "subject"]` and `subject` is missing, the graph blocks execution.

## 📥 Parameter Extraction Logic

The system distinguishes between **Explicit** and **Implicit** inference.
- **Explicit Inference:** The user says "Generate 5 flashcards for biology". The extractor maps `num_cards=5` and `subject=biology`.
- **Implicit Inference:** The user says "Generate flashcards." The extractor pulls `subject` from the persistent Conversation Session Context, and implicitly defaults `num_cards` based on the student's mastery level.
- **Ambiguity:** If inference confidence is too low, the Validator reroutes the graph to the direct chat responder to explicitly ask the user for the missing parameter.

---

## 🛡️ Error Handling Strategy

EduOrchestrator rejects silent failures. 
- **Auto-Clarification:** If a required parameter is unrecoverable, the graph shifts to a `clarify` node, pausing orchestration and generating a polite follow-up to the user.
- **Retry Logic:** If a tool execution fails (e.g., API timeout), the Executor node traps the exception, increments a retry counter, and re-executes. If `max_retries` is hit, it formats an elegant fallback response.

---

## 🗄️ Database Design (Supabase PostgreSQL)

Persistence is handled asynchronously via SQLAlchemy with strict relational mapping.

- **student_profiles:** `user_id` linked securely to Supabase `auth.users`. Tracks `learning_level`, `token_balance`, `emotional_state`, and `teaching_style`.
- **conversation_sessions:** `session_id`, `message_count`.
- **conversation_messages:** Tracks raw text AND orchestration metadata (`tool_used`, `confidence`, `latency_ms`, `workflow_steps`) for advanced reconstruction.
- **tool_execution_logs:** Discrete telemetry for every tool invocation.

---

## 🔐 Authentication Flow

Secure and stateless.
1. Frontend uses `@supabase/ssr` to handle Google/Email OAuth.
2. The browser generates an active JWT session.
3. Every fetch request to FastAPI attaches the Bearer JWT.
4. FastAPI's Auth Middleware explicitly decodes the `sub` against the database to guarantee isolated user environments.

---

## 📐 Evaluation Framework

The repository includes a dedicated rigorous evaluation suite (`parameter_extraction_evaluation.ipynb`, `tool_integration_evaluation.ipynb`). 

- **Datasets:** Tests the graph against 100+ edge-case prompts (ambiguous inputs, context-switching, malicious prompts).
- **LLM-as-Judge:** Uses an external evaluating LLM to score the orchestration logic across precision, recall, schema compliance, and robustness against hallucinations.

---

## 🔁 Example Flow

**User Input:** *"I'm really struggling and feeling anxious about my upcoming exam on cellular respiration. Help me study."*

1. **Context Analyzer:** Flags `emotional_state: anxious`, `mastery_level: 2`.
2. **Reasoner:** Intent = `assessment_prep`.
3. **Tool Selector:** Keyword ranker suggests `mock_test`. Context heurister steps in: *Penalty applied due to 'anxious' state.* Ranker pivots to `concept_explainer`.
4. **Extractor:** Isolates `concept: "cellular respiration"`.
5. **Validator:** Schema matches.
6. **Executor:** `concept_explainer` triggers.
7. **Observer:** Approves output.
8. **Output:** System formats a gentle, scaffolded explanation tailored to a beginner.

---

## 🚀 Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/eduorchestrator.git
cd eduorchestrator

# 2. Backend Setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Environment Variables
cp .env.example .env
# Fill in OPENAI_API_KEY, DATABASE_URL, SUPABASE_URL, etc.

# 4. Apply Database Schema
# Execute `supabase_schema.sql` in your Supabase dashboard IDE.

# 5. Run the Backend
uvicorn app.main:app --reload

# 6. Frontend Setup (New Terminal)
cd ../frontend
npm install
npm run dev
```

---

## 📈 Future Improvements

- **Dedicated Observability:** Integration with Helicone / PromptLayer for latency analytics and token heatmaps.
- **Caching Layer:** Redis integration for tool output caching (e.g., repeatedly requested standard definitions).
- **Tool Expansion:** RAG integration for PDF textbook querying and visual/audio generation endpoints.

---

## 💼 Tech Highlights (For Engineering Teams)

- **Strict Type Enforcement:** Comprehensive use of Pydantic and TypeScript interfaces.
- **Fault-Tolerant Pipelines:** Implementation of LangGraph supervisor nodes preventing endless agent loops.
- **Schema-Driven Architecture:** Complete decoupling of tool logic from graph orchestration.
- **True Stateless APIs:** PostgreSQL-based persistence allowing seamless horizontal scaling of the FastAPI backend.
