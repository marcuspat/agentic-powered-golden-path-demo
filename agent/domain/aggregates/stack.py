"""Stack aggregate — BC-2 Stack Catalog."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.domain.values import StackName, StackVersion, TemplatePath, TemplateVariableSet


@dataclass(frozen=True)
class SourceTemplate:
    path: TemplatePath


@dataclass(frozen=True)
class GitOpsTemplate:
    path: TemplatePath


@dataclass(frozen=True)
class Stack:
    name: StackName
    version: StackVersion
    declared_variables: TemplateVariableSet
    source_template: SourceTemplate
    gitops_template: GitOpsTemplate

    @classmethod
    def of(
        cls,
        name: str,
        version: str,
        source_template_dir: Path,
        gitops_template_dir: Path,
        declared_variables: set,
    ) -> "Stack":
        return cls(
            name=StackName(name),
            version=StackVersion(version),
            declared_variables=TemplateVariableSet(frozenset(declared_variables)),
            source_template=SourceTemplate(TemplatePath(source_template_dir)),
            gitops_template=GitOpsTemplate(TemplatePath(gitops_template_dir)),
        )
