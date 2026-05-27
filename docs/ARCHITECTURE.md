# Architecture

This document covers the architectural layout of the `zwcad-ai-modifier` framework (HS-CAD-clone).

## Project Overview

`zwcad-ai-modifier` is designed as a hybrid integration layer between LISP macros, direct COM API bindings (via `comtypes` and `pywin32`), and AI orchestration for architectural drawing analysis.

## Core Pillars

1. **Adapters Layer**:
   - COM Adapter (`comtypes`, `pywin32` bindings to ZWCAD 2025/2026).
   - LISP Bridge (for lightweight block counting and text extraction).
   - PyRx Adapter (for direct C++ boundary integration).

2. **AI Analysis & Parsing**:
   - Semantic text and vector validation engines.
   - Command schema validator translating natural language requests into structured CAD edits.

3. **Verification Harness**:
   - Automated boundary checking.
   - Diff validation and safety gates to prevent destructive operations.

## Build and Deploy Flow

- The framework is running on Windows locally alongside ZWCAD.
- Local executions are verified via `pytest` and pre-live dry run reports before changes are applied.
