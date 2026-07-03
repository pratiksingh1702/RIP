import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/gateway_provider.dart';

class GatewayActivityScreen extends ConsumerWidget {
  const GatewayActivityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final metrics = ref.watch(gatewayMetricsProvider);
    final sessions = ref.watch(gatewaySessionsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Activity')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          metrics.when(
            data: (data) => Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _Metric(label: 'Active', value: '${data['active_sessions'] ?? 0}'),
                _Metric(label: 'Sessions', value: '${data['sessions'] ?? 0}'),
                _Metric(label: 'Tokens in', value: '${data['tokens_retrieved'] ?? 0}'),
                _Metric(label: 'Tokens out', value: '${data['tokens_delivered'] ?? 0}'),
                _Metric(label: 'Conflicts', value: '${data['active_conflicts'] ?? 0}'),
              ],
            ),
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('Activity unavailable: $error'),
          ),
          const SizedBox(height: 18),
          Text('Sessions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          sessions.when(
            data: (items) => Column(
              children: [
                for (final item in items)
                  if (item is Map)
                    ListTile(
                      dense: true,
                      leading: const Icon(Icons.history_rounded),
                      title: Text('${item['task_description'] ?? item['taskDescription'] ?? 'Session'}'),
                      subtitle: Text('${item['intent'] ?? item['classification'] ?? ''}'),
                      trailing: Text('${item['status'] ?? ''}'),
                    ),
              ],
            ),
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('Sessions unavailable: $error'),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;

  const _Metric({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: const Icon(Icons.insights_rounded, size: 16),
      label: Text('$label: $value'),
    );
  }
}
