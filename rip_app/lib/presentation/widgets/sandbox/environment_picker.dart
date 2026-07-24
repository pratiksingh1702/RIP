import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/sandbox.dart';
import '../../providers/sandbox_provider.dart';

class EnvironmentPicker extends ConsumerWidget {
  final Function(SandboxTemplate) onSelect;

  const EnvironmentPicker({super.key, required this.onSelect});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final templates = ref.watch(sandboxProvider).templates;

    if (templates.isEmpty) {
      ref.read(sandboxProvider.notifier).loadTemplates();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text('Choose Environment', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        ),
        Expanded(
          child: GridView.builder(
            padding: const EdgeInsets.all(12),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              childAspectRatio: 1.3,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
            ),
            itemCount: templates.length,
            itemBuilder: (context, index) {
              final template = templates[index];
              return _TemplateCard(template: template, onTap: () => onSelect(template));
            },
          ),
        ),
      ],
    );
  }
}

class _TemplateCard extends StatelessWidget {
  final SandboxTemplate template;
  final VoidCallback onTap;

  const _TemplateCard({required this.template, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = Color(int.parse(template.color.replaceFirst('#', '0xFF')));
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          border: Border.all(color: color.withValues(alpha: 0.3)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(_iconForTemplate(template.id), color: color, size: 28),
            const Spacer(),
            Text(template.name, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 4),
            Text(template.description, style: const TextStyle(color: Colors.white54, fontSize: 11), maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }

  IconData _iconForTemplate(String id) {
    switch (id) {
      case 'python': return Icons.code;
      case 'node': return Icons.javascript;
      case 'flutter': return Icons.phone_android;
      case 'rust': return Icons.build;
      case 'go': return Icons.terminal;
      case 'java': return Icons.coffee;
      case 'fullstack': return Icons.layers;
      case 'devops': return Icons.cloud;
      case 'datascience': return Icons.bar_chart;
      default: return Icons.terminal;
    }
  }
}
