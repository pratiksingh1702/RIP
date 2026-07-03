# RIP Documentation

This folder contains user-facing and contributor-facing documentation for RIP, the Repository Intelligence Platform.

The root `README.md` is the project front door. This folder is the reference library.

## Start Here

| Document | Use it for |
| --- | --- |
| [workflow.md](workflow.md) | End-to-end RIP workflow, from repository setup through indexing, search, explain, gateway use, VS Code, Flutter, and MCP. |
| [cli.md](cli.md) | Detailed CLI command reference with examples for indexing, search, trace, impact, explain, projects, API keys, gateway commands, and operations. |
| [setup.md](setup.md) | Local setup, dependencies, environment configuration, and first-run guidance. |
| [api_doc.md](api_doc.md) | HTTP API reference and backend usage notes. |
| [vscode.md](vscode.md) | VS Code extension setup and editor workflows. |
| [gateway_api_flow.md](gateway_api_flow.md) | Context Gateway request flow, project-aware retrieval, API key handling, and gateway command behavior. |

## Architecture And Retrieval

| Document | Use it for |
| --- | --- |
| [REPO_INTELLIGENCE_PLATFORM.md](REPO_INTELLIGENCE_PLATFORM.md) | High-level product and platform architecture. |
| [architecture.md](architecture.md) | System architecture notes and component boundaries. |
| [repository_isolation_and_hybrid_retrieval.md](repository_isolation_and_hybrid_retrieval.md) | Project isolation, graph retrieval, semantic retrieval, and hybrid context assembly. |
| [RIP_INDEXING_UPGRADE.md](RIP_INDEXING_UPGRADE.md) | Indexing pipeline upgrades and implementation notes. |
| [RIP_AGENT_INTEGRATION_THEORY.md](RIP_AGENT_INTEGRATION_THEORY.md) | How agents should consume RIP context and gateway output. |

## Implementation And Product Notes

| Document | Use it for |
| --- | --- |
| [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) | Implementation phases and rollout planning. |
| [RIP_REMOTE_GIT_FLUTTER_PLAN.md](RIP_REMOTE_GIT_FLUTTER_PLAN.md) | Remote Git indexing and Flutter app integration notes. |
| [User_distribution_plan.md](User_distribution_plan.md) | Distribution and user-facing rollout plan. |
| [design.md](design.md) | Product and interface design notes. |
| [adding_a_language.md](adding_a_language.md) | Adding a parser/indexer path for a new language. |
| [adding_an_analysis.md](adding_an_analysis.md) | Adding a new analysis capability to RIP. |
| [api_reference.md](api_reference.md) | Supplemental API reference material. |

## Internal Planning

Maintainer notes and historical planning documents live in [internal/](internal/). They are kept for reference, but they are not the primary user documentation path.

| Document | Use it for |
| --- | --- |
| [internal/TASK.md](internal/TASK.md) | Task checklist and implementation tracking. |
| [internal/REPLAN.md](internal/REPLAN.md) | Replanning notes. |
| [internal/REPLAN_V2_AUDIT.md](internal/REPLAN_V2_AUDIT.md) | Audit notes for replanning work. |
| [internal/plan.md](internal/plan.md) | Historical implementation plan. |
| [internal/issues.md](internal/issues.md) | Collected issue notes. |
| [internal/affected.md](internal/affected.md) | Affected-file notes. |
| [internal/flutter-plan.md](internal/flutter-plan.md) | Flutter-specific planning notes. |
| [internal/local_exc_we.md](internal/local_exc_we.md) | Local execution notes. |

## Web Documentation Site

The production-style single-page documentation site is [../web/doc.html](../web/doc.html). It is linked from [../web/index.html](../web/index.html).

Use the web docs for polished browsing, search, nested navigation, copyable code snippets, and section anchors. Use the Markdown files in this folder when editing source documentation.
