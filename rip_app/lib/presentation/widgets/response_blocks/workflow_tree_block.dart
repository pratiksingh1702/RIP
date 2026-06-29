import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../common/section_card.dart';

class WorkflowTreeBlock extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<String> nodes;

  const WorkflowTreeBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.nodes,
  });

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      icon: Icons.alt_route_rounded,
      iconColor: AppColors.iconWorkflow,
      title: title,
      subtitle: subtitle,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: List.generate(nodes.length, (index) {
          final isLast = index == nodes.length - 1;
          return IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Column(
                  children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: isLast ? AppColors.iconWorkflow : AppColors.surfaceVariant,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isLast ? AppColors.iconWorkflow : AppColors.border,
                          width: 2,
                        ),
                      ),
                    ),
                    if (!isLast)
                      Expanded(
                        child: Container(
                          width: 2,
                          color: AppColors.border,
                        ),
                      ),
                  ],
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Text(
                      nodes[index],
                      style: index == 0 || isLast
                          ? AppTextStyles.bodyMdBold
                          : AppTextStyles.bodyMd,
                    ),
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }
}
