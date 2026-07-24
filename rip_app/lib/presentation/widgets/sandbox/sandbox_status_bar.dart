import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/sandbox.dart';
import '../providers/sandbox_provider.dart';

class SandboxStatusBar extends ConsumerWidget {
  const SandboxStatusBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(sandboxProvider);
    final status = state.status;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      color: const Color(0xFF16213E),
      child: Row(children: [
        _StatusDot(isRunning: status?.status == 'running'),
        const SizedBox(width: 8),
        Text(
          state.sandbox?.environment ?? 'Sandbox',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500),
        ),
        const Spacer(),
        if (status != null) ...[
          _MetricChip(label: 'CPU', value: '${status.cpuPercent.toStringAsFixed(1)}%'),
          const SizedBox(width: 8),
          _MetricChip(label: 'RAM', value: '${(status.memoryUsedBytes / 1024 / 1024).toStringAsFixed(0)}MB'),
          const SizedBox(width: 8),
          Text(status.status.toUpperCase(), style: TextStyle(color: status.status == 'running' ? Colors.green : Colors.white54, fontSize: 11)),
        ],
      ]),
    );
  }
}

class _StatusDot extends StatelessWidget {
  final bool isRunning;
  const _StatusDot({required this.isRunning});
  @override
  Widget build(BuildContext context) => Container(
    width: 8, height: 8,
    decoration: BoxDecoration(
      color: isRunning ? const Color(0xFF00FF88) : Colors.red,
      shape: BoxShape.circle,
    ),
  );
}

class _MetricChip extends StatelessWidget {
  final String label;
  final String value;
  const _MetricChip({required this.label, required this.value});
  @override
  Widget build(BuildContext context) => Text('$label $value', style: const TextStyle(color: Colors.white38, fontSize: 11));
}
