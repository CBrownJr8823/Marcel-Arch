# MARCEL ARCH

**Security-first financial governance engine for contract-aware auditing, agent guardrails, and risk enforcement.**

MARCEL ARCH is a Python-based project designed to sit between enterprise financial workflows and autonomous AI-driven decision systems. Its purpose is to turn contract logic and financial controls into structured, enforceable rules that help reduce billing leakage, support auditability, and strengthen governance.

---

## Overview

As organizations adopt more AI-assisted workflows across finance, procurement, and operations, the risk of invalid decisions, control failures, and contract drift increases. MARCEL ARCH is built to help solve that problem by creating a control layer that can:

- Interpret financial and contract-based rules into structured logic.
- Flag discrepancies before they become larger financial losses.
- Support auditable, repeatable governance workflows.
- Provide a stronger foundation for secure AI-assisted financial automation.

---

## Core Capabilities

- **Contract-aware control logic** for translating policy and agreement terms into enforceable rules.
- **Financial discrepancy detection** to identify billing mismatches, overcharges, and governance exceptions.
- **Security-first workflow design** with data protection and validation in mind.
- **Structured agent orchestration** for future multi-step decision and review pipelines.
- **Audit support** through transparent, explainable outputs and reusable workflow patterns.

---

## Architecture Goals

MARCEL ARCH is being developed as a foundation for secure, policy-aware financial automation. The current design emphasizes:

- **Typed validation and structured outputs** using Pydantic-based patterns.
- **Workflow orchestration** for multi-step agent or rule pipelines.
- **PII-aware preprocessing** to reduce exposure of sensitive data.
- **Control-layer enforcement** to limit unsafe or unauthorized actions.
- **Modular design** so auditing, security, and execution components can evolve independently.

---

## Tech Stack

- **Language:** Python 3.12+
- **Validation / Agent Patterns:** Pydantic AI
- **Workflow Orchestration:** LangGraph
- **Security Focus:** PII masking, validation controls, secure processing patterns

Pydantic AI is designed for building production-grade AI workflows with type safety and structured validation, while LangGraph is a low-level orchestration framework for long-running, stateful agent workflows. [web:67][web:75]

---

## Why This Project Matters

MARCEL ARCH reflects an interest in building AI systems that are not only powerful, but governable. Instead of treating AI as an unrestricted decision-maker, this project treats it as a system that should operate within enforceable business, financial, and security boundaries.

This makes the project especially relevant for environments where accuracy, accountability, and controlled automation matter.

---

## Project Direction

Current and planned areas of improvement include:

- Stronger rule extraction from contracts and policy text.
- More robust discrepancy detection workflows.
- Better logging, tracing, and audit history.
- Expanded test coverage and validation scenarios.
- Hardening around security controls and failure handling.

---

## Getting Started

```bash
git clone https://github.com/CBrownJr8823/Marcel-Arch.git
cd Marcel-Arch
pip install -r requirements.txt
python main.py
