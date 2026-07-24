import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';

/// Reusable List Row Component matching base_design.md Section 4
class RipListRow extends StatefulWidget {
  final Widget? leadingIcon;
  final String title;
  final String? subtitle;
  final String? metaText;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool isSelected;

  const RipListRow({
    super.key,
    required this.title,
    this.leadingIcon,
    this.subtitle,
    this.metaText,
    this.trailing,
    this.onTap,
    this.isSelected = false,
  });

  @override
  State<RipListRow> createState() => _RipListRowState();
}

class _RipListRowState extends State<RipListRow> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final effectiveBg = widget.isSelected
        ? AppColors.primaryLight
        : (_isHovered ? AppColors.primaryLight.withValues(alpha: 0.5) : Colors.transparent);

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.onTap,
          borderRadius: BorderRadius.circular(8),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: effectiveBg,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                if (widget.leadingIcon != null) ...[
                  IconTheme(
                    data: const IconThemeData(color: AppColors.textSecondary, size: 18),
                    child: widget.leadingIcon!,
                  ),
                  const SizedBox(width: 12),
                ],
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        widget.title,
                        style: AppTextStyles.bodyMd.copyWith(
                          fontWeight: widget.isSelected ? FontWeight.w600 : FontWeight.w400,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (widget.subtitle != null) ...[
                        const SizedBox(height: 2),
                        Text(
                          widget.subtitle!,
                          style: AppTextStyles.bodySm,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
                if (widget.metaText != null) ...[
                  const SizedBox(width: 8),
                  Text(
                    widget.metaText!,
                    style: AppTextStyles.bodySm,
                  ),
                ],
                if (widget.trailing != null) ...[
                  const SizedBox(width: 8),
                  widget.trailing!,
                ] else if (widget.onTap != null) ...[
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.chevron_right_rounded,
                    size: 18,
                    color: AppColors.textSecondary,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
