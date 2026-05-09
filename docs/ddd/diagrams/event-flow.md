# Event Flow Diagrams

This document supplements [`../07-domain-events.md`](../07-domain-events.md) with end-to-end event flow diagrams for the major scenarios.

## Happy path: a successful onboarding

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant CLI as CLI
    participant OS as OnboardingOrchestrationService
    participant IES as IntentExtractionService
    participant SRR as SourceRepoRepo (BC-3)
    participant GRR as GitOpsRepoRepo (BC-4)
    participant ARR as ArgoAppRepo (BC-5)
    participant ARGO as ArgoCD
    participant K8S as Kubernetes
    participant OBS as Observability (BC-7)

    Dev->>CLI: agent "Deploy NodeJS service inventory-api"
    CLI->>OS: run(OnboardingRequest)

    Note over OS: emit OnboardingRun.Started
    OS->>IES: extract(request)
    IES-->>OS: ExtractedIntent
    Note over OS: emit OnboardingRun.IntentExtracted

    OS->>SRR: create + populate
    SRR->>SRR: GitHub create + git push
    Note over SRR: emit SourceRepository.Created
    Note over SRR: emit SourceRepository.Populated
    SRR-->>OS: SourceRepository(populated)

    OS->>GRR: create + populate
    GRR->>GRR: GitHub create + git push
    Note over GRR: emit GitOpsRepository.Created
    Note over GRR: emit GitOpsRepository.Populated
    GRR-->>OS: GitOpsRepository(populated)

    OS->>ARR: add(ArgoApplication)
    ARR->>K8S: kubectl apply Application CR
    Note over ARR: emit ArgoApplication.Registered
    ARR-->>OS: ArgoApplication

    Note over OS: emit OnboardingRun.Completed
    OS-->>CLI: OnboardingRun(succeeded)
    CLI-->>Dev: ✅ done in 117 s

    Note over ARGO,K8S: --- asynchronously ---
    ARGO->>GRR: poll repo / receive webhook
    Note over ARGO: emit ArgoApplication.SyncStarted
    ARGO->>K8S: apply manifests
    Note over ARGO: emit ArgoApplication.Synced
    K8S->>K8S: pods ready
    Note over K8S: emit Workload.Healthy
    OBS->>OBS: provision dashboard, ServiceMonitor
    Note over OBS: emit ObservabilityProfile.Provisioned
```

## Failure path: GitHub rate limit during repo creation

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant CLI as CLI
    participant OS as OnboardingOrchestrationService
    participant SRR as SourceRepoRepo
    participant GH as GitHub API

    Dev->>CLI: agent "Deploy NodeJS service inventory-api"
    CLI->>OS: run(OnboardingRequest)
    Note over OS: emit OnboardingRun.Started
    Note over OS: emit OnboardingRun.IntentExtracted

    OS->>SRR: create + populate
    SRR->>GH: POST /user/repos
    GH-->>SRR: 403 rate limited
    Note over SRR: ACL translates to RateLimited domain error
    SRR-->>OS: raises RateLimited

    Note over OS: emit OnboardingRun.Failed{step="provision_source_repo", reason="github rate limited, retry after 240s"}
    OS-->>CLI: OnboardingRun(failed)
    CLI-->>Dev: ❌ exit 1 with structured reason
```

## Failure path: LLM unavailable, fallback succeeds

```mermaid
sequenceDiagram
    autonumber
    participant OS as OrchestrationService
    participant IES as IntentExtractionService
    participant ORA as OpenRouter Adapter
    participant OR as OpenRouter API

    OS->>IES: extract(request)
    IES->>ORA: completion(prompt)
    ORA->>OR: POST /chat/completions
    OR-->>ORA: 502 bad gateway
    Note over ORA: ACL translates to LlmUnavailable
    ORA-->>IES: raises LlmUnavailable
    Note over IES: try regex patterns
    IES->>IES: match "called inventory-api"
    IES-->>OS: ExtractedIntent (extraction_path=REGEX)
    Note over OS: emit OnboardingRun.IntentExtracted{extraction_path="regex"}
```

## Rollback flow

```mermaid
sequenceDiagram
    autonumber
    actor Op as Operator
    participant CLI as RollbackCLI (scripts/rollback.sh)
    participant RAS as RollbackApplicationService
    participant GIT as Git CLI
    participant GH as GitHub
    participant ARGO as ArgoCD

    Op->>CLI: rollback inventory-api
    CLI->>RAS: rollback(RollbackCommand)
    RAS->>GIT: clone <gitops-repo>
    RAS->>GIT: revert HEAD
    GIT-->>RAS: new commit sha
    RAS->>GH: push
    Note over RAS: emit GitOpsRepository.RolledBack
    RAS-->>CLI: RollbackResult(succeeded)

    Note over ARGO: --- asynchronously ---
    ARGO->>GH: poll / receive webhook
    Note over ARGO: emit ArgoApplication.SyncStarted
    ARGO->>ARGO: apply previous manifests
    Note over ARGO: emit ArgoApplication.Synced
    Note over ARGO: emit Workload.Healthy (after rollout)
```

## CI-driven image bump

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant SRC as Source Repo
    participant TKN as Tekton Pipeline
    participant REG as Image Registry
    participant GR as GitOps Repo
    participant ARGO as ArgoCD

    Dev->>SRC: git push (new commit on main)
    SRC->>TKN: webhook triggers PipelineRun
    Note over TKN: emit PipelineRun.Started
    TKN->>TKN: clone, test, build
    TKN->>REG: push image
    Note over TKN: emit ImageBuilt
    TKN->>GR: commit deployment.yaml image bump
    Note over TKN: emit PipelineRun.Completed
    Note over GR: emit GitOpsRepository.Promoted
    GR->>ARGO: webhook
    Note over ARGO: emit ArgoApplication.SyncStarted
    ARGO->>ARGO: apply new image manifest
    Note over ARGO: emit ArgoApplication.Synced
    Note over ARGO: emit Workload.Healthy (post-rollout)
```

## Causation graph (per OnboardingRun)

```mermaid
flowchart LR
    A[OnboardingRun.Started] --> B[OnboardingRun.IntentExtracted]
    B --> C[SourceRepository.Created]
    B --> D[GitOpsRepository.Created]
    C --> C2[SourceRepository.Populated]
    D --> D2[GitOpsRepository.Populated]
    D2 --> E[ArgoApplication.Registered]
    E --> F1[ArgoApplication.SyncStarted]
    F1 --> F2[ArgoApplication.Synced]
    F2 --> G[Workload.Healthy]
    G --> H[ObservabilityProfile.Provisioned]
    E --> Z[OnboardingRun.Completed]
    G -. optional gate .-> Z
```

The dotted edge captures the per-profile decision: *demo* completes the run on `ArgoApplication.Registered`; *production* waits for `Workload.Healthy`.
