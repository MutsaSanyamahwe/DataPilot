# DataPilot

> **An autonomous data analysis platform that turns raw datasets into actionable insights.**

 **Status: In Progress — V1 under active development**

---

## The Problem

Working with data often requires technical knowledge of spreadsheets, SQL, statistics, and visualization tools just to answer relatively simple questions.

Users may have a dataset full of valuable information, but extracting that value can involve:

- Cleaning messy data
- Understanding unfamiliar columns
- Calculating statistics
- Finding trends and correlations
- Identifying anomalies
- Creating visualizations
- Knowing which questions to ask in the first place

Existing AI-powered tools can make this easier, but often rely heavily on an LLM to perform the actual analysis. This can lead to unreliable calculations, unnecessary model usage, and limited transparency into how results were produced.

---

## The Idea

**DataPilot** is being built to make data analysis more accessible while keeping the analytical work deterministic and transparent.

Users will upload their datasets and DataPilot will automatically:

1. **Profile the data** — understand its structure, columns, types, missing values, and duplicates.
2. **Generate an initial overview** — provide useful statistics and insights before the user asks a question.
3. **Analyze the data** — perform statistical operations using Python, Pandas, and NumPy.
4. **Visualize results** — generate appropriate charts automatically.
5. **Understand natural-language questions** — use an LLM to translate user intent into structured analysis plans.
6. **Explain findings** — use an LLM to turn computed results into understandable explanations.

### Core Principle

> **The LLM should understand and explain the data — not replace the data analysis engine.**

Deterministic calculations remain in the backend, while AI is used where language understanding and reasoning provide the most value.

---

## V1 Architecture

```text
                         CSV Upload
                              │
                              ▼
                       Data Validation
                              │
                              ▼
                        Data Profiling
                              │
                              ▼
                   Automatic Data Overview
                              │
                              ▼
                        User Question
                              │
                              ▼
                   LLM Planning Service
                              │
                              ▼
                        Analysis Plan
                              │
                              ▼
                   Deterministic Engine
                      (Pandas / NumPy)
                              │
                       ┌──────┴──────┐
                       ▼             ▼
                    Results       Charts
                       │             │
                       └──────┬──────┘
                              ▼
                    LLM Explanation
                              │
                              ▼
                       Final Insight

```

Planned Analysis Capabilities

DataPilot's analysis engine will perform calculations directly using Python rather than asking an LLM to calculate results.

Planned capabilities include:

- Descriptive statistics
- Grouped summaries
- Frequencies and distributions
- Correlations
- Outlier detection
- Trend analysis
- Time-series analysis
- Pivot tables
- Top-N analysis
- Missing-value analysis
- Duplicate detection

## AI Architecture

V1 will use AI selectively rather than placing an LLM at the center of every operation.

**Planner**

The first LLM service converts a natural-language question into a structured analysis plan.

```
"What department has the highest average salary?"
                    │
                    ▼
              LLM Planner
                    │
                    ▼
              AnalysisPlan
```

**Analysis Engine**


The backend executes the plan deterministically.

```
AnalysisPlan
     │
     ▼
Pandas / NumPy
     │
     ▼
AnalysisResult

```

**Explainer**


A second LLM service receives the computed results and explains them in natural language.

```
AnalysisResult
     │
     ▼
LLM Explainer
     │
     ▼
Human-readable insight
```

This separation is intended to improve reliability, transparency, and control over LLM usage.

---

## Technology

### Backend

- Python
- FastAPI
- Pandas
- NumPy
- SQLAlchemy

### AI

- Large Language Models
- Structured analysis planning
- AI-generated explanations

### Data

- CSV datasets
- PostgreSQL / SQLAlchemy

## Planned

- Data visualization
- PDF / SVG reporting
- AI Agents
- RAG
- Multi-dataset analysis

---

## Project Structure

```
backend/
│
├── api/
├── analysis/
├── profiling/
├── cleaning/
├── planner/
├── charts/
├── reports/
├── models/
├── services/
├── sessions/
├── storage/
├── utils/
│
├── config.py
├── db.py
└── main.py

```

---

## Vision

DataPilot aims to make meaningful data analysis accessible to anyone, regardless of their technical background, while maintaining the reliability and transparency expected from a real analytical system.
