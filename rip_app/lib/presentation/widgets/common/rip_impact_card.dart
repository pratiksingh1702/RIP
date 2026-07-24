import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';

enum RipImpactSeverity { high, medium, low }

/// Impact/Finding Card Component matching base_design.md Section 4 & B10 Spec
class RipImpactCard extends StatelessWidget {
  final String title;
  final String description;
  final RipImpactSeverity severity;
  final VoidCallback? onViewDetails;
  final String? codeSnippet;

  const RipImpactCard({
    super.key,
    required this.title,
    required this.description,
    this.severity = RipImpactSeverity.high,
    this.onViewDetails,
    this.codeSnippet,
  });

  Color get _accentColor {
    switch (severity) {
      case RipImpactSeverity.high:
        return AppColors.danger; // Red #EF4444
      case RipImpactSeverity.medium:
        return AppColors.warning; // Amber #F59E0B
      case RipImpactSeverity.low:
        return AppColors.success; // Green #22C55E
    }
  }

  String get _tagText {
    switch (severity) {
      case RipImpactSeverity.high:
        return 'HIGH IMPACT';
      case RipImpactSeverity.medium:
        return 'MEDIUM IMPACT';
      case RipImpactSeverity.low:
        return 'LOW IMPACT';
    }
  }

  IconData get _iconData {
    switch (severity) {
      case RipImpactSeverity.high:
        return Icons.bolt_rounded;
      case RipImpactSeverity.medium:
        return Icons.lightbulb_outline_rounded;
      case RipImpactSeverity.low:
        return Icons.check_circle_outline_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 4px left accent bar in semantic color
            Container(
              width: 4,
              color: _accentColor,
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          _tagText,
                          style: AppTextStyles.labelCaps.copyWith(color: _accentColor),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: _accentColor.withValues(alpha: 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(_iconData, color: _accentColor, size: 18),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      title,
                      style: AppTextStyles.headlineMd,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: AppTextStyles.bodySm,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (codeSnippet != null) ...[
                      const SizedBox(height: 8),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppColors.codeBg,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          codeSnippet!,
                          style: AppTextStyles.codeSm,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                    if (onViewDetails != null) ...[
                      const SizedBox(height: 12),
                      InkWell(
                        onTap: onViewDetails,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              'View details',
                              style: AppTextStyles.bodySm.copyWith(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(width: 4),
                            const Icon(
                              Icons.arrow_forward_rounded,
                              size: 14,
                              color: AppColors.primary,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
