import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../../../data/models/sandbox.dart';
import '../../providers/sandbox_provider.dart';
import '../common/rip_card.dart';

class EnvironmentPicker extends ConsumerWidget {
  final Function(SandboxTemplate) onSelect;

  const EnvironmentPicker({super.key, required this.onSelect});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templates = ref.watch(sandboxProvider).templates;

    if (templates.isEmpty) {
      ref.read(sandboxProvider.notifier).loadTemplates();
    }

    final defaultTemplates = templates.isNotEmpty ? templates : _fallbackTemplates;

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
                ),
                child: const Icon(Icons.developer_board, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Select Environment',
                    style: AppTextStyles.headlineLg,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Isolated runtime sandbox containers for execution',
                    style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 1.15,
              crossAxisSpacing: 14,
              mainAxisSpacing: 14,
            ),
            itemCount: defaultTemplates.length,
            itemBuilder: (context, index) {
              final template = defaultTemplates[index];
              return _TemplateCard(
                template: template,
                onTap: () => onSelect(template),
              );
            },
          ),
        ],
      ),
    );
  }

  static final List<SandboxTemplate> _fallbackTemplates = [
    SandboxTemplate(id: 'python', name: 'Python 3.11', description: 'FastAPI, Pandas, PyTorch & Scripting', color: '#3776AB'),
    SandboxTemplate(id: 'node', name: 'Node.js 20', description: 'TypeScript, Express, Next.js & NPM', color: '#5FA04E'),
    SandboxTemplate(id: 'go', name: 'Go 1.22', description: 'Goroutines, Gin API & Microservices', color: '#00ADD8'),
    SandboxTemplate(id: 'rust', name: 'Rust 2021', description: 'Cargo, Tokio async & High Performance', color: '#DEA584'),
    SandboxTemplate(id: 'flutter', name: 'Flutter & Dart', description: 'Mobile, Web & Desktop App SDK', color: '#02569B'),
    SandboxTemplate(id: 'ubuntu', name: 'Ubuntu Bash', description: 'Full Linux Shell, Git & DevOps', color: '#E95420'),
  ];
}

class _TemplateCard extends StatelessWidget {
  final SandboxTemplate template;
  final VoidCallback onTap;

  const _TemplateCard({required this.template, required this.onTap});

  @override
  Widget build(BuildContext context) {
    Color baseColor;
    try {
      baseColor = Color(int.parse(template.color.replaceFirst('#', '0xFF')));
    } catch (_) {
      baseColor = AppColors.primary;
    }

    return RipCard(
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: baseColor.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(_iconForTemplate(template.id), color: baseColor, size: 22),
              ),
              const Icon(Icons.arrow_forward_ios, color: AppColors.textMuted, size: 12),
            ],
          ),
          const Spacer(),
          Text(
            template.name,
            style: AppTextStyles.bodyMdBold.copyWith(color: AppColors.textPrimary),
          ),
          const SizedBox(height: 4),
          Text(
            template.description,
            style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary, height: 1.2),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  IconData _iconForTemplate(String id) {
    switch (id) {
      case 'python': return Icons.code_rounded;
      case 'node': return Icons.javascript_rounded;
      case 'flutter': return Icons.phone_android_rounded;
      case 'rust': return Icons.build_circle_rounded;
      case 'go': return Icons.terminal_rounded;
      case 'java': return Icons.coffee_rounded;
      case 'fullstack': return Icons.layers_rounded;
      case 'devops': return Icons.cloud_done_rounded;
      case 'datascience': return Icons.analytics_rounded;
      case 'ubuntu': return Icons.computer_rounded;
      default: return Icons.terminal_rounded;
    }
  }
}
