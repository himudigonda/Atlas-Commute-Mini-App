# [Project Name]

## 1. What are we actually solving?
* **The Problem:** [What is the user's pain?]
* **What kicks this off?:** [The input or event that starts the code]
* **When are we done?:** [Minimum requirements to complete]
* **When are we satisfied?:** [All requirements to be met]

## 2. The Data (What do we need?)
* **The Input:** [Raw request json contract]
* **PROCESSING STATE:** [What do the N agents need to see and do?]
* **The Final Answer:** [Raw response json contract]

## 3. The Agentic Graph Orchestration
* **Router (Flash):** Splits the work.
* **The Parallel Workers (N-Agents):** - Agent 1: [Task 1]
    - Agent 2: [Task 2]
    - Agent 3: [Task 3]
* **The Fixer (Pro):** Compiles the parallel results and decides the move.
* **Self-Correction:** [How we fix it if an agent hallucinates]

## 4. The Tech (Infrastructure)
* **Speed:** Using asyncio.gather to run agents simultaneously.
* **Storage:** Redis for caching so we don't repeat expensive work.
* **Observability:** Logging every step with Rich so we can see the concurrent flow.
* **Tracing:** Using LangSmith to trace the flow of the agents.
* **Testing:** Using pytest to test the flow of the agents.
* **Error Handling:** Using try-except blocks to handle errors gracefully.
