import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';

enum RipButtonVariant { primary, secondary, destructive }

/// Unified Pill Button Component matching base_design.md Section 4
class RipButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final RipButtonVariant variant;
  final Widget? icon;
  final bool isLoading;
  final bool isFullWidth;
  final EdgeInsetsGeometry padding;

  const RipButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = RipButtonVariant.primary,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = false,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
  });

  const RipButton.primary({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = false,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
  }) : variant = RipButtonVariant.primary;

  const RipButton.secondary({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = false,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
  }) : variant = RipButtonVariant.secondary;

  const RipButton.destructive({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = false,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
  }) : variant = RipButtonVariant.destructive;

  @override
  Widget build(BuildContext context) {
    Color backgroundColor;
    Color foregroundColor;
    BorderSide borderSide = BorderSide.none;

    switch (variant) {
      case RipButtonVariant.primary:
        backgroundColor = AppColors.primary;
        foregroundColor = Colors.white;
        break;
      case RipButtonVariant.secondary:
        backgroundColor = AppColors.surface;
        foregroundColor = AppColors.textPrimary;
        borderSide = const BorderSide(color: AppColors.border, width: 1);
        break;
      case RipButtonVariant.destructive:
        backgroundColor = AppColors.danger;
        foregroundColor = Colors.white;
        break;
    }

    final childContent = Row(
      mainAxisSize: isFullWidth ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (isLoading) ...[
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(foregroundColor),
            ),
          ),
          const SizedBox(width: 8),
        ] else if (icon != null) ...[
          IconTheme(
            data: IconThemeData(color: foregroundColor, size: 18),
            child: icon!,
          ),
          const SizedBox(width: 8),
        ],
        Text(
          label,
          style: AppTextStyles.bodyMdBold.copyWith(color: foregroundColor),
        ),
      ],
    );

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: isLoading ? null : onPressed,
        borderRadius: BorderRadius.circular(9999), // Pill radius full
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: padding,
          decoration: BoxDecoration(
            color: onPressed == null ? backgroundColor.withValues(alpha: 0.5) : backgroundColor,
            borderRadius: BorderRadius.circular(9999),
            border: Border.fromBorderSide(borderSide),
          ),
          child: childContent,
        ),
      ),
    );
  }
}
