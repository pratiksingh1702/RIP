import 'package:flutter/material.dart';

class MermaidView extends StatelessWidget {
  final String diagram;
  final VoidCallback? onPreview;

  const MermaidView({
    super.key,
    required this.diagram,
    this.onPreview,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.architecture, size: 16),
              const SizedBox(width: 8),
              Text(
                'Architecture Graph',
                style: Theme.of(context).textTheme.labelMedium,
              ),
              const Spacer(),
              if (onPreview != null)
                OutlinedButton.icon(
                  onPressed: onPreview,
                  icon: const Icon(Icons.visibility),
                  label: const Text('Preview'),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              diagram,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
              maxLines: 10,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
