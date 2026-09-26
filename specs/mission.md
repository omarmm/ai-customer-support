# AI Customer Support Backend — Mission

## Purpose

Build a production-oriented AI-native customer support backend that demonstrates how LLMs, RAG, tools, agents, and deterministic backend business rules can work together safely.

## Problem

Traditional customer support backends rely heavily on deterministic workflows and require users to navigate predefined actions.

An AI-native support system should understand natural-language requests and use the appropriate knowledge and backend capabilities while keeping authorization and business-critical decisions under deterministic backend control.

## Goals

The system must demonstrate:

- Natural-language customer support
- LLM-based intent understanding
- Structured LLM outputs
- Retrieval-Augmented Generation (RAG)
- Tool calling
- Agentic workflows
- Deterministic business rules
- Authorization
- Observability
- Evaluation
- Production-oriented error handling

## Core Principle

The LLM may understand, reason, retrieve information, and propose actions.

The backend remains the final authority for:

- Authorization
- Business rules
- Data integrity
- Financial actions
- State changes
- Security-sensitive operations

## Scope

The initial system will support customer-support scenarios such as:

- Order inquiries
- Cancellation requests
- Refund eligibility
- Policy questions
- Order status

## Non-Goals

The system will not:

- Allow the LLM to directly modify business-critical state
- Treat generated text as authoritative business data
- Put business rules inside prompts
- Depend on a single LLM provider at the architecture level
- Build the entire system as one autonomous agent

## Development Philosophy

The project follows Specification-Driven Development.

Every subsystem must follow:

Specification
→ Architecture
→ Task
→ Implementation
→ Test
→ Verification

The specification is the source of truth.

Agents and developers must not invent requirements or architecture outside the specification.
