# AS-IS Architecture Diagrams

**Baseline:** 26/08/2026

## System context

```mermaid
flowchart TB
    USER[Operator] --> GH[GitHub Actions]
    GH --> MS[Master Scan]
    GH --> FM[Fast Monitor]
    YF[Yahoo Finance via yfinance] --> CORE[Trading Engine CORE]
    TV[TradingView Screener] --> CORE
    MS --> CORE
    FM --> CORE
    CORE --> STATE[State / Persistence]
    CORE --> EMAIL[Email Report]
    CORE --> WA[WhatsApp Alert]
    STATE --> LAB[Laboratory]
    LAB --> DASH[Dashboard / Site]
    EMAIL --> USER
    WA --> USER
    DASH --> USER
```

## Logical separation

```mermaid
flowchart LR
    subgraph CORE[CORE]
      C1[Data / Universe] --> C2[Indicators / Fundamentals]
      C2 --> C3[Scoring]
      C3 --> C4[Entry / RR / Sizing]
      C4 --> C5[Decision / Trigger]
    end

    subgraph PROD[PRODUCTION]
      P1[GitHub Actions] --> P2[Master Scan / Fast Monitor]
      P2 --> CORE
      C5 --> P3[State]
      C5 --> P4[Email / WhatsApp]
    end

    subgraph LAB[LABORATORY]
      L1[Opportunities] --> L2[Paper Positions]
      L2 --> L3[Evidence / Verdict]
    end

    P3 --> L1
```

## Parity migration

```mermaid
flowchart LR
    OLD[Frozen reference USA/Italy] --> TEST[Parity Tests / Checklist]
    NEW[Modular v2 engine] --> TEST
    TEST -->|within frozen tolerances| STREAK[Valid parity run]
    TEST -->|internal mismatch| RESET[Reset certification streak]
    TEST -->|external non-comparable| HOLD[Hold streak]
    STREAK --> EXIT[Parity exit after gate]
```

## Important AS-IS caveat

The modular v2 surface still uses/binds parts of the frozen reference implementation. The diagrams therefore describe logical responsibilities, not a claim that every box is already physically independent Python code.