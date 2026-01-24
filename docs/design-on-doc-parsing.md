# Design: Income & Tax Parsing Architecture

## Overview

This document explains the **design decisions, trade-offs, and architecture** behind the Income & Tax Module's paystub and W-2 parsing.

> **Deterministic data ingestion first. Agentic intelligence second.**

Parsing financial documents is fundamentally different from analyzing them. This design deliberately separates **extraction** from **reasoning** to ensure correctness, auditability, and long-term maintainability.

---

## Core Design Principles

1. **Correctness beats cleverness**
2. **Deterministic before probabilistic**
3. **Explainable before intelligent**
4. **Validated before visualized**
5. **Agentic reasoning only after trusted data**

---

## Parsing Strategy

### Why Deterministic Parsing (pdfplumber + Regex)

All Microsoft and University of Utah payroll documents are parsed using:
- `pdfplumber` for text extraction
- Regex-based label matching
- Explicit numeric normalization
- Strong arithmetic invariants

**Payroll documents have properties that favor deterministic parsing:**

| Property | Implication |
|----------|-------------|
| Fixed labels | Regex matching is reliable |
| Structured totals | Arithmetic invariants detect errors |
| Repeating layouts | Parsers stay stable over years |
| Regulated format | Low entropy, low ambiguity |
| Digitally generated | Text-based, not scanned |

**Examples of stable labels:**
- `TOTAL EARNINGS`
- `NET PAY`
- `FEDERAL INCOME TAX`
- `SOCIAL SECURITY TAX`
- `WITHHOLDING — UT`

The system anchors extraction on **semantic labels**, not spatial layout or AI inference.

### Parsing Flow

```
PDF
 ↓
pdfplumber.extract_text()
 ↓
Stable labels (regex)
 ↓
Monetary values
 ↓
Normalized schema
 ↓
Validation invariants
```

---

## Why AI Document Intelligence Is Not Used for Ingestion

AI-based OCR / Document Intelligence (Azure, OCR + LLMs) was **evaluated and prototyped**, but intentionally excluded from the primary ingestion path because it's not very accurate.

### Observed Failure Modes

| Failure | Impact |
|---------|--------|
| Column confusion | CURRENT vs YTD swapped |
| Rate vs amount | $86.67 parsed as gross pay |
| Label ambiguity | Taxes misclassified |
| Non-determinism | Different results per run |
| Silent plausibility | Numbers look right but aren't |

These failures are **rare but catastrophic** in financial systems.

> A payroll parser must be **boring, predictable, and auditable**.

### Deterministic vs AI Parsing Comparison

| Dimension | Deterministic | AI / OCR |
|-----------|---------------|----------|
| Correctness | ✅ High | ⚠️ Probabilistic |
| Explainability | ✅ Full | ❌ Limited |
| Testability | ✅ Easy | ❌ Hard |
| Cost | ✅ Free | ❌ Per-document |
| Latency | ✅ Low | ❌ External |
| Auditability | ✅ Strong | ❌ Weak |
| Hallucination risk | ✅ None | ⚠️ Present |

For payroll ingestion, **deterministic parsing clearly dominates**.

---

## Role of AI in This System

AI is not removed — it is **used deliberately where it excels**.

### AI Is Used For
- Income trend analysis
- Anomaly detection
- Tax optimization insights
- Explanation & summarization
- Action recommendations
- User-facing intelligence

### AI Is NOT Used For
- Extracting raw financial numbers
- Deciding column semantics
- Resolving numeric ambiguity
- Ingestion of regulated documents

This separation is intentional and mirrors real financial systems.

---

## Fallback Strategy (Future-Ready)

The architecture allows an **AI fallback layer** only when:
- PDFs are scanned or image-based
- Employer format is unknown
- Deterministic parsing fails

Even then:
- AI outputs must pass validation invariants
- Results are explicitly marked as inferred
- Deterministic data always wins if present

---

## Why This Matters for Agentic Systems

> Agentic systems are only as good as their inputs.
> Bad ingestion → confident but wrong agents.

This design ensures:
- Agents reason over **trusted data**
- Errors are detected early
- Insights are defensible
- Recommendations are safe

---

## Long-Term Scalability

| Challenge | Design Mitigation |
|-----------|-------------------|
| New employers | Add parser, reuse schema |
| Layout drift | Label-based matching |
| Tax law changes | Central aggregation logic |
| Scale to users | No external parsing services |
| Compliance | Full audit trail |

---

## Summary

| Aspect | Approach |
|--------|----------|
| **Parsing** | Deterministic, explainable, validated |
| **Schema** | Unified, sparse, extensible |
| **Intelligence** | Agentic, insight-focused |
| **Trust model** | Arithmetic invariants first |
| **AI usage** | Reasoning, not ingestion |

> **If a value can be extracted deterministically, it must be.**
> **AI should explain numbers — not invent them.**
