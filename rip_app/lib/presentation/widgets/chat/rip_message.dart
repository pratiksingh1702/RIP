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
import '../../providers/chat_provider.dart';
import '../rich_content/code_block.dart';
import '../response_blocks/impact_block.dart';
import '../response_blocks/file_list_block.dart';
import '../response_blocks/mermaid_block.dart';
import '../response_blocks/table_block.dart';
import '../response_blocks/workflow_tree_block.dart';
import 'pipeline_trace_widgets.dart';
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

    final hasBlocks = message.blocks != null && message.blocks!.isNotEmpty;

    return _AssistantShell(
      timestamp: message.timestamp,
      isLoading: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (message.trace != null && message.trace!.hasEvents) ...[
            PipelineSummaryChip(trace: message.trace!),
            const SizedBox(height: 12),
          ],

          // Content blocks
          if (hasBlocks)
            ...message.blocks!.map((block) => _buildBlockWidget(context, ref, block))
          else
            MarkdownBody(
              data: message.content,
              styleSheet: _markdownStyle(),
            ),
          if (_workflowRunIds(message.content) != null) ...[
            const SizedBox(height: 12),
            _WorkflowRunOpenButton(ids: _workflowRunIds(message.content)!),
          ],
          const SizedBox(height: 14),
          _RepositorySearchFooter(
            project: project,
            timestamp: message.timestamp,
          ),
          const SizedBox(height: 12),
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
            ],
          ),
        ],
      ),
    );
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
            styleSheet: _markdownStyle(),
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

  MarkdownStyleSheet _markdownStyle() {
    return MarkdownStyleSheet(
      p: AppTextStyles.bodyMd.copyWith(
        fontSize: 15,
        height: 1.55,
        color: AppColors.textPrimary,
      ),
      strong: const TextStyle(
        color: AppColors.textPrimary,
        fontWeight: FontWeight.w700,
      ),
      blockquote: AppTextStyles.bodyMd.copyWith(
        color: AppColors.textSecondary,
        height: 1.45,
      ),
      blockquoteDecoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
      ),
      code: AppTextStyles.mono.copyWith(
        color: AppColors.primary,
        backgroundColor: AppColors.primaryLight,
        fontSize: 13,
      ),
      codeblockDecoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      codeblockPadding: const EdgeInsets.all(16),
      listBullet: AppTextStyles.bodyMd.copyWith(
        color: AppColors.textSecondary,
        height: 1.5,
      ),
      tableHead: AppTextStyles.bodyMdBold,
      tableBody: AppTextStyles.bodyMd,
      tableBorder: TableBorder.all(color: AppColors.border),
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
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 12),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.border, width: 1),
          bottom: BorderSide(color: AppColors.border, width: 1),
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
                style: AppTextStyles.bodySmMuted.copyWith(fontSize: 11),
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
    final projectName = project?.projectName ?? 'selected repository';
    final entityCount = project?.entitiesCount ?? 0;
    final scope = entityCount > 0
        ? 'Searched $entityCount entities in $projectName'
        : 'Searched indexed graph in $projectName';

    return Row(
      children: [
        const Icon(Icons.saved_search_rounded, size: 14, color: AppColors.textSecondary),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            '$scope • ${DateFormatter.formatTime(timestamp)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.bodySmMuted.copyWith(fontSize: 11),
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
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.border, width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: AppColors.textSecondary, size: 14),
              if (label != null) ...[
                const SizedBox(width: 6),
                Text(
                  label!,
                  style: AppTextStyles.bodySm.copyWith(
                    fontSize: 12,
                    color: AppColors.textSecondary,
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
