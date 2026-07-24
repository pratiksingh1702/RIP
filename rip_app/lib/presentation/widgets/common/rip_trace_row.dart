import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import 'status_badge.dart';

/// Trace & Log Step Row Component matching base_design.md Section 4 & B9 Spec
class RipTraceRow extends StatelessWidget {
  final String stepName;
  final String? statusText; // e.g. "done", "passed", "running"
  final String? durationText; // e.g. "0.3s"
  final RipStatusType statusType;
  final int indentLevel;
  final VoidCallback? onTap;

  const RipTraceRow({
    super.key,
    required this.stepName,
    this.statusText,
    this.durationText,
    this.statusType = RipStatusType.success,
    this.indentLevel = 0,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: EdgeInsets.only(
          left: 12.0 + (indentLevel * 16.0),
          right: 12.0,
          top: 6.0,
          bottom: 6.0,
        ),
        child: Row(
          children: [
            RipStatusDot(type: statusType, size: 6.0),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                stepName,
                style: AppTextStyles.codeSm.copyWith(
                  color: AppColors.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (statusText != null) ...[
              const SizedBox(width: 8),
              Text(
                statusText!,
                style: AppTextStyles.codeSm.copyWith(
                  color: statusType == RipStatusType.success
                      ? AppColors.success
                      : statusType == RipStatusType.danger
                          ? AppColors.danger
                          : AppColors.textSecondary,
                ),
              ),
            ],
            if (durationText != null) ...[
              const SizedBox(width: 16),
              Text(
                durationText!,
                style: AppTextStyles.codeSm.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
