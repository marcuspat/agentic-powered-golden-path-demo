"""OnboardingOrchestrationService — the conductor."""
from __future__ import annotations

import logging

from agent.domain.aggregates.argo_application import ArgoApplication
from agent.domain.aggregates.onboarding_run import OnboardingRun
from agent.domain.errors import DomainError
from agent.domain.events import (
    ArgoApplicationRegistered,
    DomainEvent,
    EventEnvelope,
    GitOpsRepositoryCreated,
    GitOpsRepositoryPopulated,
    OnboardingRunCompleted,
    OnboardingRunFailed,
    OnboardingRunIntentExtracted,
    OnboardingRunStarted,
    SourceRepositoryCreated,
    SourceRepositoryPopulated,
)
from agent.domain.ports import (
    ArgoApplicationPort,
    EventEmitterPort,
    GitOpsRepositoryPort,
    IntentExtractionPort,
    SourceRepositoryPort,
    StackRepositoryPort,
    TemplateRendererPort,
)
from agent.domain.values import (
    AppDescription,
    AppName,
    CommitMessage,
    IngressHost,
    Namespace,
    OnboardingRequest,
    TemplateVariables,
)

logger = logging.getLogger(__name__)


STEP_EXTRACT_INTENT = "extract_intent"
STEP_PROVISION_SOURCE_REPO = "provision_source_repo"
STEP_PROVISION_GITOPS_REPO = "provision_gitops_repo"
STEP_REGISTER_ARGO_APP = "register_argo_application"


COMMIT_MSG_AGENT = CommitMessage("Initial commit from Golden Path Agent")


class OnboardingOrchestrationService:
    """Drives an OnboardingRun end-to-end via injected ports."""

    def __init__(
        self,
        intent_extraction: IntentExtractionPort,
        stacks: StackRepositoryPort,
        template_renderer: TemplateRendererPort,
        source_repo: SourceRepositoryPort,
        gitops_repo: GitOpsRepositoryPort,
        argo_repo: ArgoApplicationPort,
        events: EventEmitterPort | None = None,
        ingress_suffix: str = "cnoe.localtest.me",
    ) -> None:
        self._intent_extraction = intent_extraction
        self._stacks = stacks
        self._renderer = template_renderer
        self._source_repo = source_repo
        self._gitops_repo = gitops_repo
        self._argo_repo = argo_repo
        self._events = events
        self._ingress_suffix = ingress_suffix

    # ----- public API ----- #

    def run(self, request: OnboardingRequest) -> OnboardingRun:
        run = OnboardingRun.begin(request)
        self._emit(run, OnboardingRunStarted(request_text=request.text))
        try:
            self._do(run, request)
        except DomainError as exc:
            failed_step = _last_failed_step(run) or "unknown"
            run.fail(reason=str(exc), failed_step=failed_step)
            self._emit(
                run,
                OnboardingRunFailed(
                    app_name=run.extracted_app_name.value if run.extracted_app_name else None,
                    failed_step=failed_step,
                    reason=str(exc),
                ),
            )
            logger.error("onboarding.failed step=%s reason=%s", failed_step, exc)
            return run
        run.succeed()
        ingress_url = _ingress_url(run.extracted_app_name, self._ingress_suffix)
        self._emit(
            run,
            OnboardingRunCompleted(
                app_name=run.extracted_app_name.value if run.extracted_app_name else "",
                source_repo_url=run.source_repo_url or "",
                gitops_repo_url=run.gitops_repo_url or "",
                argo_application_name=run.extracted_app_name.value if run.extracted_app_name else "",
                namespace=run.namespace or "",
                ingress_url=ingress_url,
                duration_seconds=run.duration_seconds or 0.0,
            ),
        )
        logger.info(
            "onboarding.completed app=%s duration=%.2fs",
            run.extracted_app_name, run.duration_seconds or 0.0,
        )
        return run

    # ----- inner orchestration ----- #

    def _do(self, run: OnboardingRun, request: OnboardingRequest) -> None:
        # Step 1: extract intent
        run.begin_step(STEP_EXTRACT_INTENT)
        intent = self._intent_extraction.extract(request)
        run.record_intent(intent.app_name, intent.stack)
        run.complete_step(STEP_EXTRACT_INTENT)
        self._emit(
            run,
            OnboardingRunIntentExtracted(
                app_name=intent.app_name.value,
                stack=intent.stack.value,
                extraction_path=intent.extraction_path.value,
            ),
        )

        stack = self._stacks.get(intent.stack)

        # Step 2: source repo
        run.begin_step(STEP_PROVISION_SOURCE_REPO)
        source = self._source_repo.create(intent.app_name, intent.description)
        run.source_repo_url = source.url.value
        self._emit(
            run,
            SourceRepositoryCreated(app_name=intent.app_name.value, url=source.url.value),
        )
        variables = self._build_variables(intent.app_name, intent.description)
        source_files = self._renderer.render(stack.source_template.path.value, variables)
        sha = self._source_repo.populate(source, source_files, COMMIT_MSG_AGENT)
        self._emit(
            run,
            SourceRepositoryPopulated(
                app_name=intent.app_name.value,
                url=source.url.value,
                file_count=len(source_files),
                commit_sha=sha.value,
                commit_message=COMMIT_MSG_AGENT.value,
            ),
        )
        run.complete_step(STEP_PROVISION_SOURCE_REPO)

        # Step 3: gitops repo
        run.begin_step(STEP_PROVISION_GITOPS_REPO)
        gitops = self._gitops_repo.create(intent.app_name, intent.description)
        run.gitops_repo_url = gitops.url.value
        run.namespace = gitops.target_namespace.value
        self._emit(
            run,
            GitOpsRepositoryCreated(app_name=intent.app_name.value, url=gitops.url.value),
        )
        gitops_files = self._renderer.render(stack.gitops_template.path.value, variables)
        gitops_sha = self._gitops_repo.populate(gitops, gitops_files, COMMIT_MSG_AGENT)
        manifest_kinds = list(getattr(gitops, "manifests", []))
        self._emit(
            run,
            GitOpsRepositoryPopulated(
                app_name=intent.app_name.value,
                url=gitops.url.value,
                namespace=gitops.target_namespace.value,
                manifest_kinds=[k.value for k in manifest_kinds],
                file_count=len(gitops_files),
                commit_sha=gitops_sha.value,
            ),
        )
        run.complete_step(STEP_PROVISION_GITOPS_REPO)

        # Step 4: ArgoCD app
        run.begin_step(STEP_REGISTER_ARGO_APP)
        argo = ArgoApplication.for_app(intent.app_name, gitops.url, gitops.target_namespace)
        self._argo_repo.register(argo)
        self._emit(
            run,
            ArgoApplicationRegistered(
                app_name=argo.name.value,
                namespace=argo.destination.namespace.value,
                repo_url=argo.source.repo_url.value,
                sync_policy={
                    "automated": argo.sync_policy.automated,
                    "prune": argo.sync_policy.prune,
                    "selfHeal": argo.sync_policy.self_heal,
                },
            ),
        )
        run.complete_step(STEP_REGISTER_ARGO_APP)

    # ----- helpers ----- #

    def _build_variables(self, app_name: AppName, description: AppDescription) -> TemplateVariables:
        ns = Namespace.from_app(app_name)
        host = IngressHost(f"{app_name.value}.{self._ingress_suffix}")
        return TemplateVariables(
            app_name=app_name,
            description=description,
            namespace=ns,
            host=host,
        )

    def _emit(self, run: OnboardingRun, event: DomainEvent) -> None:
        if self._events is None:
            return
        try:
            envelope = EventEnvelope.wrap(event, correlation_id=run.correlation_id)
            self._events.emit(envelope)
        except Exception:  # pragma: no cover — emitter must never break orchestration
            logger.exception("event.emit_failed name=%s", event.name)


def _last_failed_step(run: OnboardingRun) -> str | None:
    for step in reversed(run.steps):
        if step.status.value == "failed":
            return step.name
        if step.status.value == "in_progress":
            # Treat the in-progress step as the failed one for reporting.
            return step.name
    return None


def _ingress_url(app_name: AppName | None, suffix: str) -> str:
    if app_name is None:
        return ""
    return f"http://{app_name.value}.{suffix}"


