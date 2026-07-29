import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/design/design.dart';
import '../../../data/models/message.dart';
import '../../../data/models/project.dart';
import '../../../data/models/rip_response.dart';
import '../../../utils/date_formatter.dart';
import '../../../utils/response_parser.dart';
import '../../providers/chat_provider.dart';
import '../rich_content/code_block.dart';
import '../response_blocks/impact_block.dart';
import '../response_blocks/file_list_block.dart';
import '../response_blocks/mermaid_block.dart';
import '../response_blocks/table_block.dart';
import '../response_blocks/workflow_tree_block.dart';
import 'pipeline_trace_widgets.dart';
import 'supervisor_chat_sheet.dart';
import 'typing_indicator.dart';
import 'suggestion_chips.dart';

class RipMessage extends ConsumerWidget {
  final Message message;
  final Project? project;

  const RipMessage({super.key, required this.message, this.project});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (message.isLoading) {
      if (message.trace != null) {
        return _AssistantShell(
          timestamp: message.timestamp,
          isLoading: true,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              PipelineStepList(trace: message.trace!),
              const SizedBox(height: 12),
              _AssistantActionButton(
                icon: Icons.stop_rounded,
                tooltip: 'Stop',
                onTap: () => ref.read(chatProvider.notifier).cancelCurrentRequest(),
              ),
            ],
          ),
        );
      }
      return TypingIndicator(
        label: message.content.isEmpty ? 'Querying repository graph...' : message.content,
        onStop: () => ref.read(chatProvider.notifier).cancelCurrentRequest(),
      );
    }

    final cleanContent = _cleanMessageContent(message.content);
    final displayBlocks = ResponseParser.parse(cleanContent);
    final hasBlocks = displayBlocks.isNotEmpty;

    return _AssistantShell(
      timestamp: message.timestamp,
      isLoading: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Primary AI Response Content (Main Focus)
          if (hasBlocks)
            ...displayBlocks.map((block) => _buildBlockWidget(context, ref, block))
          else
            MarkdownBody(
              data: cleanContent,
              styleSheet: _markdownStyle(context),
            ),
          if (_workflowRunIds(message.content) != null) ...[
            const SizedBox(height: 12),
            _WorkflowRunOpenButton(ids: _workflowRunIds(message.content)!),
          ],
          
          const SizedBox(height: 14),

          // Faded Muted Grey Metadata & Traces Accordion Panel
          _MetadataAccordion(
            message: message,
            project: project,
          ),

          const SizedBox(height: 10),

          // Secondary Action Buttons
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _AssistantActionButton(
                icon: AppIcons.delete != Icons.delete ? Icons.copy_rounded : AppIcons.add,
                tooltip: 'Copy',
                label: 'Copy',
                onTap: () {
                  HapticFeedback.selectionClick();
                  Clipboard.setData(ClipboardData(text: message.content));
                },
              ),
              const SizedBox(width: 8),
              _AssistantActionButton(
                icon: AppIcons.refresh,
                tooltip: 'Regenerate',
                label: 'Regenerate',
                onTap: () {
                  HapticFeedback.selectionClick();
                  ref.read(chatProvider.notifier).regenerateFromAssistant(message.id);
                },
              ),
              const SizedBox(width: 8),
              _AssistantActionButton(
                icon: Icons.psychology_rounded,
                tooltip: 'Ask Supervisor',
                label: 'Ask Supervisor',
                onTap: () {
                  HapticFeedback.mediumImpact();
                  final runId = _extractRunId(message);
                  SupervisorChatSheet.show(context, runId);
                },
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _extractRunId(Message msg) {
    final runMatch = RegExp(r'run_id:\s*([a-f0-9\-]+)', caseSensitive: false).firstMatch(msg.content);
    if (runMatch != null) return runMatch.group(1)!;
    final uuidMatch = RegExp(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b', caseSensitive: false).firstMatch(msg.content);
    if (uuidMatch != null) return uuidMatch.group(0)!;
    if (msg.metadata != null && msg.metadata!['run_id'] != null) {
      return msg.metadata!['run_id'].toString();
    }
    return msg.id;
  }

  String _cleanMessageContent(String raw) {
    var text = raw;
    text = text.replaceAll(RegExp(r'<rip_escalated source="(.*?)"/>\n?'), '');
    text = text.replaceAll(RegExp(r'^Intent:.*?\n?', multiLine: true), '');
    text = text.replaceAll(RegExp(r'^###\s*(conversational|workspace_memory|source_registry|Conversational Response|Workspace Recent Activity.*)\s*\n?', multiLine: true), '');
    text = text.replaceAll(RegExp(r'^(conversational|workspace_memory|source_registry)\s*\n?', multiLine: true), '');
    text = text.replaceAll(RegExp(r'^\s*[-*•]\s*\[session\]\s*Chat task:.*?\n?', multiLine: true), '');
    text = text.trim();
    if (text.isEmpty && raw.trim().isNotEmpty) {
      return raw.replaceAll(RegExp(r'<rip_escalated source="(.*?)"/>\n?'), '').trim();
    }
    return text;
  }

  Map<String, String>? _workflowRunIds(String content) {
    final workflowMatch = RegExp(r'workflow_id:\s*([^\s]+)').firstMatch(content);
    final runMatch = RegExp(r'run_id:\s*([^\s]+)').firstMatch(content);
    if (workflowMatch == null) return null;
    return {
      'workflow_id': workflowMatch.group(1)!,
      if (runMatch != null) 'run_id': runMatch.group(1)!,
    };
  }

  Widget _buildBlockWidget(BuildContext context, WidgetRef ref, RipResponseBlock block) {
    switch (block.type) {
      case BlockType.text:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: MarkdownBody(
            data: block.textContent ?? '',
            styleSheet: _markdownStyle(context),
          ),
        );
      case BlockType.workflowTree:
        return WorkflowTreeBlock(
          title: block.title ?? 'Workflow Tree',
          subtitle: block.subtitle,
          nodes: block.listContent ?? [],
        );
      case BlockType.mermaid:
        return MermaidBlock(
          title: block.title ?? 'Architecture Graph',
          subtitle: block.subtitle,
          diagramCode: block.textContent ?? '',
        );
      case BlockType.table:
        return TableBlock(
          title: block.title ?? 'Data Table',
          subtitle: block.subtitle,
          headers: block.tableHeaders ?? [],
          rows: block.tableRows ?? [],
        );
      case BlockType.code:
        return CodeBlock(
          code: block.textContent ?? '',
          language: block.language,
        );
      case BlockType.fileList:
        return FileListBlock(
          title: block.title ?? 'Important Files',
          subtitle: block.subtitle,
          files: block.listContent ?? [],
        );
      case BlockType.impact:
        return ImpactBlock(
          title: block.title ?? 'Impact Analysis',
          subtitle: block.subtitle,
          severity: block.severity ?? ImpactSeverity.medium,
        );
      case BlockType.suggestionChips:
        final chips = (block.listContent ?? [])
            .map((text) => SuggestionChip(id: text, text: text))
            .toList();
        return Padding(
          padding: const EdgeInsets.only(top: 8),
          child: SuggestionChips(
            suggestions: chips,
            onSelected: (chip) {
              ref.read(chatProvider.notifier).sendMessage(chip.text);
            },
          ),
        );
    }
  }

  MarkdownStyleSheet _markdownStyle(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final secondaryTextColor = isDark ? Colors.white70 : AppColors.textSecondary;
    final codeBg = isDark ? Colors.white.withValues(alpha: 0.1) : AppColors.primaryLight;
    final codeblockBg = isDark ? const Color(0xFF13132B) : const Color(0xFF0F172A);
    final borderColor = isDark ? Colors.white.withValues(alpha: 0.12) : AppColors.border;

    return MarkdownStyleSheet(
      p: AppTextStyles.bodyMd.copyWith(
        fontSize: 15,
        height: 1.55,
        color: textColor,
      ),
      strong: TextStyle(
        color: textColor,
        fontWeight: FontWeight.w700,
      ),
      blockquote: AppTextStyles.bodyMd.copyWith(
        color: secondaryTextColor,
        height: 1.45,
      ),
      blockquoteDecoration: BoxDecoration(
        color: isDark ? Colors.white.withValues(alpha: 0.05) : AppColors.primaryLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
      ),
      code: AppTextStyles.mono.copyWith(
        color: AppColors.primary,
        backgroundColor: codeBg,
        fontSize: 13,
      ),
      codeblockDecoration: BoxDecoration(
        color: codeblockBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor),
      ),
      codeblockPadding: const EdgeInsets.all(16),
      listBullet: AppTextStyles.bodyMd.copyWith(
        color: secondaryTextColor,
        height: 1.5,
      ),
      tableHead: AppTextStyles.bodyMdBold.copyWith(color: textColor),
      tableBody: AppTextStyles.bodyMd.copyWith(color: textColor),
      tableBorder: TableBorder.all(color: borderColor),
    );
  }
}

class _WorkflowRunOpenButton extends StatelessWidget {
  const _WorkflowRunOpenButton({required this.ids});

  final Map<String, String> ids;

  @override
  Widget build(BuildContext context) {
    return RipButton.secondary(
      label: ids['run_id'] == null ? 'Open workflow' : 'Open flow run',
      icon: const Icon(AppIcons.workflows, size: 16),
      onPressed: () {
        HapticFeedback.selectionClick();
        context.push('/workflows', extra: ids);
      },
    );
  }
}

/// Full-width modern Assistant Response container
class _AssistantShell extends StatelessWidget {
  final Widget child;
  final DateTime timestamp;
  final bool isLoading;

  const _AssistantShell({
    required this.child,
    required this.timestamp,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final surfaceColor = isDark
        ? Colors.white.withValues(alpha: 0.04)
        : AppColors.surface;
    final borderColor = isDark
        ? Colors.white.withValues(alpha: 0.08)
        : AppColors.border;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 12),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: surfaceColor,
        border: Border(
          top: BorderSide(color: borderColor, width: 1),
          bottom: BorderSide(color: borderColor, width: 1),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              RipMascotWidget(
                pose: isLoading ? RipMascotPose.thinking : RipMascotPose.happy,
                width: 28,
                height: 28,
              ),
              const SizedBox(width: 10),
              Text(
                'Repository Intelligence',
                style: AppTextStyles.bodyMdBold.copyWith(
                  color: AppColors.primary,
                  fontSize: 14,
                ),
              ),
              const Spacer(),
              Text(
                DateFormatter.formatTime(timestamp),
                style: AppTextStyles.bodySmMuted.copyWith(
                  fontSize: 11,
                  color: isDark ? Colors.white54 : AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _RepositorySearchFooter extends StatelessWidget {
  const _RepositorySearchFooter({
    required this.project,
    required this.timestamp,
  });

  final Project? project;
  final DateTime timestamp;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final projectName = project?.projectName ?? 'selected repository';
    final entityCount = project?.entitiesCount ?? 0;
    final scope = entityCount > 0
        ? 'Searched $entityCount entities in $projectName'
        : 'Searched indexed graph in $projectName';

    return Row(
      children: [
        Icon(
          Icons.saved_search_rounded,
          size: 14,
          color: isDark ? Colors.white54 : AppColors.textSecondary,
        ),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            '$scope • ${DateFormatter.formatTime(timestamp)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.bodySmMuted.copyWith(
              fontSize: 11,
              color: isDark ? Colors.white54 : AppColors.textSecondary,
            ),
          ),
        ),
      ],
    );
  }
}

class _AssistantActionButton extends StatelessWidget {
  const _AssistantActionButton({
    required this.icon,
    required this.tooltip,
    required this.onTap,
    this.label,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: isDark
                ? Colors.white.withValues(alpha: 0.08)
                : AppColors.background,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.12)
                  : AppColors.border,
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                color: isDark ? Colors.white70 : AppColors.textSecondary,
                size: 14,
              ),
              if (label != null) ...[
                const SizedBox(width: 6),
                Text(
                  label!,
                  style: AppTextStyles.bodySm.copyWith(
                    fontSize: 12,
                    color: isDark ? Colors.white70 : AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _OfflineFallbackBanner extends StatelessWidget {
  const _OfflineFallbackBanner();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.amber.withValues(alpha: 0.12)
            : const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark
              ? Colors.amber.withValues(alpha: 0.3)
              : const Color(0xFFFDE68A),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.offline_bolt_rounded,
            size: 16,
            color: Colors.amber,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '⚡ Offline Mode — LLM model was not available for synthesis, showing grounded search results.',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: isDark ? const Color(0xFFFDE68A) : const Color(0xFF92400E),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EscalationBanner extends StatelessWidget {
  const _EscalationBanner({required this.source});

  final String source;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.deepOrange.withValues(alpha: 0.12)
            : const Color(0xFFFFF7ED),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark
              ? Colors.deepOrange.withValues(alpha: 0.3)
              : const Color(0xFFFFEDD5),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.speed_rounded,
            size: 16,
            color: Colors.deepOrange,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Escalated to Deep Tier — Low confidence auto routing triggered escalation. Source: $source',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: isDark ? const Color(0xFFFFEDD5) : const Color(0xFF9A3412),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetadataAccordion extends StatefulWidget {
  final Message message;
  final Project? project;

  const _MetadataAccordion({required this.message, this.project});

  @override
  State<_MetadataAccordion> createState() => _MetadataAccordionState();
}

class _MetadataAccordionState extends State<_MetadataAccordion> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final message = widget.message;
    final trace = message.trace;
    final hasTrace = trace != null && trace.hasEvents;
    final escalationMatch = RegExp(r'<rip_escalated source="(.*?)"/>\n?').firstMatch(message.content);
    final hasEscalation = escalationMatch != null;
    final hasOffline = message.content.contains('[DATA from') ||
        message.content.contains('Offline Mode') ||
        (message.metadata != null && message.metadata!['llm_synthesized'] == false);

    final mutedColor = isDark ? Colors.white38 : AppColors.textSecondary.withValues(alpha: 0.6);

    return Container(
      decoration: BoxDecoration(
        color: isDark ? Colors.white.withValues(alpha: 0.02) : AppColors.background.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.05) : AppColors.border.withValues(alpha: 0.5),
          width: 0.8,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          InkWell(
            onTap: () => setState(() => _isExpanded = !_isExpanded),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
              child: Row(
                children: [
                  Icon(
                    Icons.tune_rounded,
                    size: 13,
                    color: mutedColor,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _buildHeaderLabel(message, hasTrace, hasOffline, hasEscalation),
                      style: AppTextStyles.bodySmMuted.copyWith(
                        fontSize: 11,
                        color: mutedColor,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    _isExpanded ? Icons.keyboard_arrow_up_rounded : Icons.keyboard_arrow_down_rounded,
                    size: 14,
                    color: mutedColor,
                  ),
                ],
              ),
            ),
          ),
          if (_isExpanded) ...[
            Divider(height: 1, color: isDark ? Colors.white.withValues(alpha: 0.05) : AppColors.border),
            Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (hasEscalation) ...[
                    _EscalationBanner(source: escalationMatch.group(1) ?? 'unknown'),
                    const SizedBox(height: 8),
                  ],
                  if (hasOffline) ...[
                    const _OfflineFallbackBanner(),
                    const SizedBox(height: 8),
                  ],
                  if (hasTrace) ...[
                    PipelineStepList(trace: trace),
                    const SizedBox(height: 8),
                  ],
                  _RepositorySearchFooter(
                    project: widget.project,
                    timestamp: message.timestamp,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _buildHeaderLabel(Message message, bool hasTrace, bool hasOffline, bool hasEscalation) {
    List<String> parts = [];
    if (hasEscalation) parts.add("Escalated Deep Tier");
    if (hasOffline) parts.add("Grounded Results");
    if (hasTrace && message.trace!.events.isNotEmpty) {
      parts.add("${message.trace!.events.length} pipeline steps");
    } else {
      parts.add("Execution Details & Traces");
    }
    return parts.join(" • ");
  }
}
