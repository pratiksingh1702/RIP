import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';

/// Standard Screen Top Bar Header matching base_design.md Section 3 & 4
class RipTopBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final Widget? leadingIcon;
  final bool showBackButton;
  final VoidCallback? onBackTap;
  final List<Widget>? actions;
  final Widget? statusWidget;
  final Widget? avatarWidget;

  const RipTopBar({
    super.key,
    required this.title,
    this.leadingIcon,
    this.showBackButton = false,
    this.onBackTap,
    this.actions,
    this.statusWidget,
    this.avatarWidget,
  });

  @override
  Size get preferredSize => const Size.fromHeight(56.0);

  @override
  Widget build(BuildContext context) {
    return Container(
      height: preferredSize.height,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: const BoxDecoration(
        color: AppColors.background,
        border: Border(bottom: BorderSide(color: AppColors.border, width: 1)),
      ),
      child: Row(
        children: [
          if (showBackButton) ...[
            IconButton(
              icon: const Icon(Icons.arrow_back_rounded, size: 20),
              onPressed: onBackTap ?? () => Navigator.maybePop(context),
              color: AppColors.textPrimary,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            ),
            const SizedBox(width: 8),
          ],
          if (leadingIcon != null) ...[
            IconTheme(
              data: const IconThemeData(color: AppColors.primary, size: 20),
              child: leadingIcon!,
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Text(
              title,
              style: AppTextStyles.headlineLg,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (statusWidget != null) ...[
            statusWidget!,
            const SizedBox(width: 12),
          ],
          if (actions != null) ...[
            ...actions!,
            const SizedBox(width: 12),
          ],
          if (avatarWidget != null) avatarWidget!,
        ],
      ),
    );
  }
}
