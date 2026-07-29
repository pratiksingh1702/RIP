import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/design.dart';
import '../../../data/models/message.dart';
import '../../../utils/date_formatter.dart';
import '../../providers/chat_provider.dart';

class UserMessage extends ConsumerWidget {
  final Message message;

  const UserMessage({super.key, required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.fromLTRB(60, 8, 16, 8),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.78,
          ),
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: isDark
                    ? [
                        AppColors.primary,
                        const Color(0xFF4C1D95),
                      ]
                    : [
                        AppColors.primary,
                        const Color(0xFF6D28D9),
                      ],
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.circular(20),
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(4),
              ),
              border: isDark
                  ? Border.all(color: Colors.white.withValues(alpha: 0.15), width: 1)
                  : null,
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: isDark ? 0.35 : 0.25),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  message.content,
                  style: AppTextStyles.bodyMd.copyWith(
                    color: Colors.white,
                    fontSize: 15,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      DateFormatter.formatTime(message.timestamp),
                      style: AppTextStyles.bodySmMuted.copyWith(
                        color: Colors.white.withValues(alpha: 0.7),
                        fontSize: 10,
                      ),
                    ),
                    const SizedBox(width: 10),
                    _UserActionButton(
                      icon: Icons.copy_rounded,
                      tooltip: 'Copy',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        Clipboard.setData(ClipboardData(text: message.content));
                      },
                    ),
                    const SizedBox(width: 6),
                    _UserActionButton(
                      icon: AppIcons.refresh,
                      tooltip: 'Resend',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        ref.read(chatProvider.notifier).resendMessage(message.content);
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _UserActionButton extends StatelessWidget {
  const _UserActionButton({
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
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withValues(alpha: 0.15),
          ),
          child: Icon(icon, color: Colors.white, size: 13),
        ),
      ),
    );
  }
}
