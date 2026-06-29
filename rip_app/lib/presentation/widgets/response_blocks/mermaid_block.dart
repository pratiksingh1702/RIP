import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../common/section_card.dart';

class MermaidBlock extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String diagramCode;

  const MermaidBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.diagramCode,
  });

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      icon: Icons.architecture_rounded,
      iconColor: AppColors.iconMermaid,
      title: title,
      subtitle: subtitle,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Text(
                diagramCode,
                style: AppTextStyles.mono.copyWith(fontSize: 12),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: diagramCode));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Copied Mermaid code!')),
                  );
                },
                icon: const Icon(Icons.copy_rounded, size: 16),
                label: const Text('Copy Code'),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.iconMermaid,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
