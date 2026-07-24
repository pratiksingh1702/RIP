import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';

enum RipStatusType { success, warning, danger, info, neutral }

/// 8px Filled Circle Status Dot (color + label rule for accessibility)
class RipStatusDot extends StatelessWidget {
  final RipStatusType type;
  final double size;

  const RipStatusDot({
    super.key,
    required this.type,
    this.size = 8.0,
  });

  Color get _color {
    switch (type) {
      case RipStatusType.success:
        return AppColors.success;
      case RipStatusType.warning:
        return AppColors.warning;
      case RipStatusType.danger:
        return AppColors.danger;
      case RipStatusType.info:
        return AppColors.info;
      case RipStatusType.neutral:
        return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _color,
        shape: BoxShape.circle,
      ),
    );
  }
}

/// Pill Status Badge (Dot + Label) matching base_design.md Section 4
class RipStatusBadge extends StatelessWidget {
  final String label;
  final RipStatusType type;
  final bool showDot;

  const RipStatusBadge({
    super.key,
    required this.label,
    required this.type,
    this.showDot = true,
  });

  const RipStatusBadge.success({
    super.key,
    required this.label,
    this.showDot = true,
  }) : type = RipStatusType.success;

  const RipStatusBadge.warning({
    super.key,
    required this.label,
    this.showDot = true,
  }) : type = RipStatusType.warning;

  const RipStatusBadge.danger({
    super.key,
    required this.label,
    this.showDot = true,
  }) : type = RipStatusType.danger;

  const RipStatusBadge.info({
    super.key,
    required this.label,
    this.showDot = true,
  }) : type = RipStatusType.info;

  Color get _textColor {
    switch (type) {
      case RipStatusType.success:
        return const Color(0xFF15803D);
      case RipStatusType.warning:
        return const Color(0xFFB45309);
      case RipStatusType.danger:
        return const Color(0xFFB91C1C);
      case RipStatusType.info:
        return const Color(0xFF1D4ED8);
      case RipStatusType.neutral:
        return AppColors.textSecondary;
    }
  }

  Color get _backgroundColor {
    switch (type) {
      case RipStatusType.success:
        return const Color(0xFFDCFCE7);
      case RipStatusType.warning:
        return const Color(0xFFFEF3C7);
      case RipStatusType.danger:
        return const Color(0xFFFEE2E2);
      case RipStatusType.info:
        return const Color(0xFFDBEAFE);
      case RipStatusType.neutral:
        return AppColors.surfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(9999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showDot) ...[
            RipStatusDot(type: type, size: 6.0),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: AppTextStyles.labelCaps.copyWith(color: _textColor),
          ),
        ],
      ),
    );
  }
}

// Backward compatibility widget alias supporting status, text, color
class StatusBadge extends StatelessWidget {
  final dynamic status;
  final String? text;
  final Color? color;
  final bool isConnected;

  const StatusBadge({
    super.key,
    this.status,
    this.text,
    this.color,
    this.isConnected = true,
  });

  @override
  Widget build(BuildContext context) {
    if (status != null) {
      final statusStr = status.toString().split('.').last.toLowerCase();
      RipStatusType type = RipStatusType.neutral;
      if (statusStr == 'complete' || statusStr == 'completed' || statusStr == 'success' || statusStr == 'passed') {
        type = RipStatusType.success;
      } else if (statusStr == 'failed' || statusStr == 'error' || statusStr == 'crash') {
        type = RipStatusType.danger;
      } else if (statusStr == 'cloning' || statusStr == 'indexing' || statusStr == 'pending' || statusStr == 'warning') {
        type = RipStatusType.warning;
      } else if (statusStr == 'info') {
        type = RipStatusType.info;
      }
      final label = text ?? (statusStr[0].toUpperCase() + statusStr.substring(1));
      return RipStatusBadge(label: label, type: type);
    }

    final labelText = text ?? 'Status';
    final badgeColor = color ?? AppColors.success;
    return RipStatusBadge(
      label: labelText,
      type: badgeColor == AppColors.success
          ? RipStatusType.success
          : badgeColor == AppColors.warning
              ? RipStatusType.warning
              : badgeColor == AppColors.danger
                  ? RipStatusType.danger
                  : RipStatusType.info,
    );
  }
}
