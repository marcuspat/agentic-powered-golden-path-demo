# Context Map (Diagrams)

This document supplements [`../04-context-map.md`](../04-context-map.md) with rendered diagrams. All diagrams are written in Mermaid so they render natively on GitHub.

## High-level context map

```mermaid
flowchart LR
    subgraph External["External Systems"]
        GH[GitHub API]
        OR[OpenRouter LLM]
        K8S[Kubernetes API]
        ARGO[ArgoCD]
        TKN[Tekton]
        GRA[Grafana / Prometheus]
    end

    subgraph Core["Core Domain"]
        BC1[BC-1: Onboarding]
    end

    subgraph Supporting["Supporting Subdomains"]
        BC2[BC-2: Stack Catalog]
        BC3[BC-3: Source Provisioning]
        BC4[BC-4: GitOps Configuration]
        BC5[BC-5: Deployment Orchestration]
        BC7[BC-7: Observability]
        BC8[BC-8: Continuous Integration]
    end

    subgraph Generic["Generic Subdomains"]
        BC6[BC-6: Platform Provisioning]
    end

    BC1 -- "C/S + ACL" --> OR
    BC1 -- "Partnership" --> BC2
    BC1 -- "C/S" --> BC3
    BC1 -- "C/S" --> BC4
    BC1 -- "C/S" --> BC5

    BC3 -- "Conformist" --> BC2
    BC4 -- "Conformist" --> BC2

    BC3 -- "ACL" --> GH
    BC4 -- "ACL" --> GH

    BC5 -- "ACL" --> K8S
    BC5 -- "ACL" --> ARGO

    BC8 -- "writes commits" --> BC4
    BC8 -- "ACL" --> TKN

    BC7 -- "subscribes to events" --> BC5
    BC7 -- "ACL" --> GRA

    BC6 -- "precondition for" --> BC1
    BC6 -- "installs" --> ARGO
    BC6 -- "installs" --> K8S
    BC6 -- "installs" --> TKN
    BC6 -- "installs" --> GRA

    classDef core fill:#fde,stroke:#a55,stroke-width:2px
    classDef supporting fill:#def,stroke:#55a,stroke-width:1px
    classDef generic fill:#eee,stroke:#888,stroke-width:1px
    classDef external fill:#ffe,stroke:#aa5,stroke-dasharray: 4 2

    class BC1 core
    class BC2,BC3,BC4,BC5,BC7,BC8 supporting
    class BC6 generic
    class GH,OR,K8S,ARGO,TKN,GRA external
```

## Layered architecture

```mermaid
flowchart TB
    subgraph Transport["Transport Layer"]
        CLI[CLI: agent/cli.py]
        HTTP[HTTP: future]
        SLK[Slack: future]
    end

    subgraph App["Application Layer"]
        OAS[OnboardingApplicationService]
        RAS[RollbackApplicationService]
    end

    subgraph Dom["Domain Layer"]
        OS[OnboardingOrchestrationService]
        IES[IntentExtractionService]
        TRS[TemplateRenderingService]
        AGG[(Aggregates & Value Objects)]
        PORTS[Ports / Protocols]
    end

    subgraph Inf["Infrastructure Layer"]
        GHA[GitHub Adapter]
        ORA[OpenRouter Adapter]
        GIT[git CLI Adapter]
        K8A[Kubernetes Adapter]
        FS[Filesystem Stack Repo]
        EM[Event Emitter]
    end

    CLI --> OAS
    HTTP --> OAS
    SLK --> OAS
    CLI --> RAS

    OAS --> OS
    RAS --> OS

    OS --> IES
    OS --> TRS
    OS --> AGG
    OS -.uses ports.-> PORTS

    PORTS -.implemented by.-> GHA
    PORTS -.implemented by.-> ORA
    PORTS -.implemented by.-> GIT
    PORTS -.implemented by.-> K8A
    PORTS -.implemented by.-> FS
    PORTS -.implemented by.-> EM

    classDef transport fill:#fed,stroke:#a85
    classDef app fill:#def,stroke:#58a
    classDef domain fill:#dfe,stroke:#5a8,stroke-width:2px
    classDef infra fill:#fde,stroke:#a58

    class CLI,HTTP,SLK transport
    class OAS,RAS app
    class OS,IES,TRS,AGG,PORTS domain
    class GHA,ORA,GIT,K8A,FS,EM infra
```

## Subdomain classification (Wardley-ish)

```mermaid
quadrantChart
    title Subdomain classification
    x-axis "Genesis / Custom" --> "Commodity / Generic"
    y-axis "Visible to user" --> "Invisible to user"
    quadrant-1 "Generic invisible"
    quadrant-2 "Generic visible"
    quadrant-3 "Custom invisible"
    quadrant-4 "Custom visible (CORE)"
    "Onboarding (BC-1)": [0.15, 0.85]
    "Stack Catalog (BC-2)": [0.30, 0.70]
    "Source Provisioning (BC-3)": [0.40, 0.40]
    "GitOps Config (BC-4)": [0.35, 0.45]
    "Deployment Orch (BC-5)": [0.55, 0.30]
    "Platform Provisioning (BC-6)": [0.85, 0.10]
    "Observability (BC-7)": [0.75, 0.25]
    "Continuous Integration (BC-8)": [0.70, 0.20]
```

The further toward the bottom-right, the more we can buy off the shelf. The further toward the top-left, the more our differentiation lies. The diagram says: *invest engineering hours in BC-1; reuse for BC-6/BC-7/BC-8.*

## Data flow at a glance

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant CLI as CLI (agent/cli.py)
    participant OS as OnboardingOrchestrationService
    participant IES as IntentExtractionService
    participant SRR as SourceRepositoryRepository
    participant GRR as GitOpsRepositoryRepository
    participant ARR as ArgoApplicationRepository
    participant ARGO as ArgoCD (cluster)

    Dev->>CLI: "Deploy NodeJS service inventory-api"
    CLI->>OS: run(OnboardingRequest)
    OS->>IES: extract(request)
    IES-->>OS: ExtractedIntent(appName=inventory-api, stack=nodejs)
    OS->>SRR: create + populate
    SRR-->>OS: SourceRepository(populated)
    OS->>GRR: create + populate
    GRR-->>OS: GitOpsRepository(populated)
    OS->>ARR: add(ArgoApplication)
    ARR-->>OS: ArgoApplication(registered)
    OS-->>CLI: OnboardingRun(succeeded)
    CLI-->>Dev: ✅ inventory-api deployed
    Note right of ARGO: ArgoCD asynchronously syncs the<br/>GitOps repo and rolls out the workload
    ARGO->>ARGO: pull GitOps repo, sync, watch
```
