import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/gateway_provider.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import '../providers/gateway_provider.dart';

class AgentRunsScreen extends ConsumerStatefulWidget {
  const AgentRunsScreen({super.key});
  @override
  ConsumerState<AgentRunsScreen> createState() => _AgentRunsScreenState();
}

class _AgentRunsScreenState extends ConsumerState<AgentRunsScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Agent Runs')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: ref.read(ripClientProvider).listAgentRuns(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          final runs = (snapshot.data?['runs'] as List?) ?? [];
          if (runs.isEmpty) return const Center(child: Text('No agent runs yet. Use /agent in chat.'));
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: runs.length,
            itemBuilder: (_, i) {
              final run = runs[i] as Map;
              return Card(
                child: ListTile(
                  leading: Icon(run['status'] == 'completed' ? Icons.check_circle : Icons.sync, color: run['status'] == 'completed' ? Colors.green : Colors.orange),
                  title: Text(run['query']?.toString() ?? '', maxLines: 2, overflow: TextOverflow.ellipsis),
                  subtitle: Text('${run['status']}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _showRunDetail(context, run['id']?.toString() ?? ''),
                ),
              );
            },
          );
        },
      ),
    );
  }

  void _showRunDetail(BuildContext context, String runId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => FutureBuilder<Map<String, dynamic>>(
        future: ref.read(ripClientProvider).getAgentRun(runId),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          final run = snapshot.data!;
          final steps = (run['steps'] as List?) ?? [];
          return DraggableScrollableSheet(
            initialChildSize: 0.8,
            builder: (_, scrollController) => ListView(
              controller: scrollController,
              padding: const EdgeInsets.all(16),
              children: [
                Text('Query: ${run['query']}', style: Theme.of(context).textTheme.titleMedium),
                Text('Status: ${run['status']} | Tokens: ${run['tokens_total']} | Duration: ${run['duration_seconds']?.toStringAsFixed(1)}s'),
                if (run['summary'] != null) ...[const Divider(), Text('Summary:', style: Theme.of(context).textTheme.titleSmall), Text('${run['summary']}')],
                const Divider(), Text('Steps (${steps.length}):', style: Theme.of(context).textTheme.titleSmall),
                ...steps.map((s) => ListTile(
                  dense: true,
                  leading: Icon(s['tool'] != null ? Icons.build : Icons.psychology, size: 18),
                  title: Text('Turn ${s['turn']}: ${s['tool'] ?? 'thinking'}', style: const TextStyle(fontSize: 13)),
                  subtitle: s['result']?['error'] != null ? Text('Error: ${s['result']['error']}', style: const TextStyle(color: Colors.red, fontSize: 11)) : null,
                )),
              ],
            ),
          );
        },
      ),
    );
  }
}
