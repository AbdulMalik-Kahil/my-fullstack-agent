# ziris-x: AI-Powered Strategic Consultant for Corporate Management & Marketing

**Developed by Abdulmalik Kahil**

`ziris-x` is a production-ready, fullstack AI agent built with the **Gemini Agent Development Kit (ADK)**. It functions as a specialized strategic consultant for businesses, delivering expert-level insights and actionable recommendations in **corporate management** and **marketing systems**.

This blueprint demonstrates how to structure complex, human-in-the-loop agentic workflows using modular design, iterative refinement, and real-world data validation—all tailored for enterprise-grade advisory use cases.

<table>
  <thead>
    <tr>
      <th colspan="2">Key Features</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>🏗️</td>
      <td><strong>Fullstack & Production-Ready:</strong> Includes a React frontend and an ADK-powered FastAPI backend, deployable to <a href="https://cloud.google.com/run">Google Cloud Run</a> or <a href="https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview">Vertex AI Agent Engine</a>.</td>
    </tr>
    <tr>
      <td>🧠</td>
      <td><strong>Strategic Consulting Workflow:</strong> The agent uses Gemini to <strong>diagnose</strong> business challenges, <strong>formulate strategic plans</strong>, <strong>critically evaluate findings</strong>, and <strong>deliver boardroom-ready recommendations</strong> grounded in real-world data.</td>
    </tr>
    <tr>
      <td>🔄</td>
      <td><strong>Iterative & Human-in-the-Loop Engagement:</strong> Collaborates with the user to co-create and approve a consulting plan before autonomously executing deep-dive analysis, refining outputs through critique loops, and synthesizing executive-grade deliverables.</td>
    </tr>
  </tbody>
</table>

## 🚀 Getting Started: From Zero to Running Agent in 1 Minute

**Prerequisites:** **[Python 3.10+](https://www.python.org/downloads/)**, **[Node.js](https://nodejs.org/)**, **[uv](https://github.com/astral-sh/uv)**

You have two deployment options:

*   **A. [Google AI Studio](#a-google-ai-studio)**: Use an API key from Google AI Studio. Ideal for quick prototyping.
*   **B. [Google Cloud Vertex AI](#b-google-cloud-vertex-ai)**: Use an existing Google Cloud project with Vertex AI enabled. Recommended for production environments and includes CI/CD automation via the Agent Starter Pack.

---

### A. Google AI Studio

1. **Clone the repository**
   ```bash
   git clone https://github.com/google/adk-samples.git
   cd adk-samples/python/agents/gemini-fullstack
   ```

2. **Set environment variables**
   ```bash
   echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> app/.env
   echo "GOOGLE_API_KEY=YOUR_AI_STUDIO_API_KEY" >> app/.env
   ```

3. **Install and run**
   ```bash
   make install && make dev
   ```
   The agent will be available at `http://localhost:5173`.

---

### B. Google Cloud Vertex AI

1. **Create project from template**
   ```bash
   uvx agent-starter-pack create my-ziris-agent -a adk@gemini-fullstack
   ```
   You’ll be prompted to select a deployment target (Agent Engine or Cloud Run) and authenticate with your Google Cloud account.

2. **Install and run**
   ```bash
   cd my-ziris-agent && make install && make dev
   ```
   Access the agent at `http://localhost:5173`.

## ☁️ Cloud Deployment (Vertex AI Only)

Deploy to Google Cloud with a single command:
```bash
gcloud config set project YOUR_PROJECT_ID
make backend
```

For production-grade CI/CD pipelines, refer to the **[Agent Starter Pack Development Guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/development-guide.html#b-production-ready-deployment-with-ci-cd)**.

## Agent Architecture & Workflow

The backend agent (`app/agent.py`) follows a two-phase consulting methodology:

### Phase 1: Collaborative Strategy Design (Human-in-the-Loop)
- User submits a business challenge (e.g., “Improve our B2B marketing funnel”).
- `ziris-x` proposes a structured consulting plan with diagnostic and strategic goals.
- User reviews, refines, and explicitly approves the plan before execution.

Plan tags guide downstream processing:
- `[ANALYSIS]`: Diagnostic or research tasks (e.g., “Benchmark current sales conversion rates”).
- `[STRATEGY]`: Synthesis or deliverable tasks (e.g., “Design a lead-nurturing campaign framework”).
- `[MODIFIED]`, `[NEW]`, `[IMPLIED]`: Track user feedback and AI-initiated enhancements.

### Phase 2: Autonomous Execution & Delivery
1. **Outline**: Converts the approved plan into a professional report structure.
2. **Iterative Research Loop**:
   - Conducts targeted web research using best-in-class sources (McKinsey, HBR, Gartner, etc.).
   - A critic agent evaluates depth, relevance, and strategic rigor.
   - If gaps exist, the agent generates follow-up queries and re-searches.
3. **Final Report**: Composes an executive-ready deliverable with inline citations and actionable insights.

All behavior is configurable in `app/config.py` (e.g., model choice, max iterations).

## Customization

- **Agent Logic**: Modify prompts, tools, or workflow in `app/agent.py`.
- **Frontend Integration**: The UI recognizes specific agent names (e.g., `report_composer_with_citations`) to render outputs correctly. Renaming agents requires corresponding frontend updates.
- **Strategic Focus**: The entire pipeline is tuned for management and marketing contexts—replace or extend components to target other domains.

## Example Interaction

> **User**: Help me optimize our SaaS onboarding experience.  
>  
> **ziris-x**: Here’s a proposed consulting plan:  
> - [ANALYSIS] Map the current user onboarding journey and identify drop-off points.  
> - [ANALYSIS] Benchmark against industry leaders in B2B SaaS.  
> - [ANALYSIS] Assess effectiveness of in-app guidance and email sequences.  
> - [STRATEGY][IMPLIED] Propose a redesigned onboarding flow with key metrics.  
>  
> Would you like to adjust this plan before we proceed?  
>  
> **User**: Looks great—go ahead.  
>  
> *(Agent executes research, iterates, and delivers a cited strategic report.)*

## Technologies Used

**Backend**  
- Agent Development Kit (ADK)  
- FastAPI  
- Google Gemini (via Vertex AI or AI Studio)  

**Frontend**  
- React + Vite  
- Tailwind CSS  
- Shadcn UI  

## Disclaimer

This sample is provided by **Abdulmalik Kahil** for demonstration and educational purposes. It serves as a foundation for building domain-specific AI consultants. Users are responsible for security, testing, and compliance in production deployments.

---

**© 2025 Abdulmalik Kahil. All rights reserved.**
