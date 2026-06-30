import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../../../data/models/message.dart';
import '../../../data/models/rip_response.dart';
import '../../../utils/date_formatter.dart';
import '../../providers/chat_provider.dart';
import '../rich_content/code_block.dart';
import '../response_blocks/impact_block.dart';
import '../response_blocks/file_list_block.dart';
import '../response_blocks/mermaid_block.dart';
import '../response_blocks/table_block.dart';
import '../response_blocks/workflow_tree_block.dart';
import 'typing_indicator.dart';
import 'suggestion_chips.dart';

class RipMessage extends ConsumerWidget {
  final Message message;

  const RipMessage({super.key, required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (message.isLoading) {
      return TypingIndicator(
        label: message.content.isEmpty ? 'RIP is working...' : message.content,
        onStop: () => ref.read(chatProvider.notifier).cancelCurrentRequest(),
      );
    }

    final hasBlocks = message.blocks != null && message.blocks!.isNotEmpty;

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.fromLTRB(14, 7, 50, 7),
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 11),
        decoration: BoxDecoration(
          color: AppColors.surface.withValues(alpha: 0.96),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(8),
            topRight: Radius.circular(24),
            bottomRight: Radius.circular(24),
            bottomLeft: Radius.circular(24),
          ),
          border: Border.all(color: Colors.white.withValues(alpha: 0.075)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.18),
              blurRadius: 26,
              offset: const Offset(0, 14),
            ),
          ],
        ),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.86,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              // Header
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(9),
                      color: AppColors.primary,
                    ),
                    child: const Icon(
                      Icons.bolt_rounded,
                      size: 14,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'RIP',
                    style: AppTextStyles.bodySmMuted.copyWith(
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    DateFormatter.formatTime(message.timestamp),
                    style: TextStyle(
                      color: AppColors.textSecondary.withValues(alpha: 0.62),
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // Content blocks
              if (hasBlocks)
                ...message.blocks!.map((block) => _buildBlockWidget(context, ref, block))
              else
                MarkdownBody(
                  data: message.content,
                  styleSheet: _markdownStyle(),
                ),
              const SizedBox(height: 10),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _AssistantActionButton(
                    icon: Icons.copy_rounded,
                    tooltip: 'Copy',
                    onTap: () {
                      HapticFeedback.selectionClick();
                      Clipboard.setData(ClipboardData(text: message.content));
                    },
                  ),
                  const SizedBox(width: 6),
                  _AssistantActionButton(
                    icon: Icons.refresh_rounded,
                    tooltip: 'Regenerate',
                    onTap: () {
                      HapticFeedback.selectionClick();
                      ref
                          .read(chatProvider.notifier)
                          .regenerateFromAssistant(message.id);
                    },
                  ),
                  const SizedBox(width: 6),
                  _AssistantActionButton(
                    icon: Icons.replay_rounded,
                    tooltip: 'Resend prompt',
                    onTap: () {
                      HapticFeedback.selectionClick();
                      ref
                          .read(chatProvider.notifier)
                          .regenerateFromAssistant(message.id);
                    },
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
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
          title: block.title ?? 'Mermaid Diagram',
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
        height: 1.5,
        color: AppColors.textPrimary.withValues(alpha: 0.94),
      ),
      strong: const TextStyle(
        color: AppColors.textPrimary,
        fontWeight: FontWeight.w800,
      ),
      blockquote: AppTextStyles.bodyMd.copyWith(
        color: AppColors.textSecondary,
        height: 1.45,
      ),
      blockquoteDecoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.055),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.24)),
      ),
      code: AppTextStyles.mono.copyWith(
        color: const Color(0xFFE5E7EB),
        backgroundColor: Colors.white.withValues(alpha: 0.08),
        fontSize: 13,
      ),
      codeblockDecoration: BoxDecoration(
        color: const Color(0xFF0B1020),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      codeblockPadding: const EdgeInsets.all(14),
      listBullet: AppTextStyles.bodyMd.copyWith(
        color: AppColors.textSecondary,
        height: 1.5,
      ),
      tableHead: AppTextStyles.bodyMdBold,
      tableBody: AppTextStyles.bodyMd,
      tableBorder: TableBorder.all(color: Colors.white.withValues(alpha: 0.07)),
    );
  }
}

class _AssistantActionButton extends StatelessWidget {
  const _AssistantActionButton({
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withValues(alpha: 0.055),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Icon(icon, color: AppColors.textSecondary, size: 15),
        ),
      ),
    );
  }
}
