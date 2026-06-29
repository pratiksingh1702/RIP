import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../../../data/models/rip_response.dart';
import '../common/section_card.dart';

class ImpactBlock extends StatelessWidget {
  final String title;
  final String? subtitle;
  final ImpactSeverity severity;

  const ImpactBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.severity,
  });

  @override
  Widget build(BuildContext context) {
    final severityColor = switch (severity) {
      ImpactSeverity.high => AppColors.error,
      ImpactSeverity.medium => AppColors.warning,
      ImpactSeverity.low => AppColors.success,
    };

    final severityText = severity.name.toUpperCase();

    return SectionCard(
      icon: Icons.track_changes_rounded,
      iconColor: AppColors.iconImpact,
      title: title,
      subtitle: subtitle,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: severityColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: severityColor.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            Icon(
              Icons.warning_amber_rounded,
              color: severityColor,
              size: 24,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Risk Severity: $severityText',
                    style: AppTextStyles.bodyMdBold.copyWith(color: severityColor),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Making changes to this module requires careful verification to prevent regression.',
                    style: AppTextStyles.bodySm.copyWith(color: AppColors.textPrimary),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
