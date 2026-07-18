import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/pipeline_trace.dart';
import '../providers/gateway_provider.dart';
import '../widgets/chat/pipeline_trace_widgets.dart';

class AgentRunsScreen extends ConsumerStatefulWidget {
  const AgentRunsScreen({super.key});

  @override
  ConsumerState<AgentRunsScreen> createState() => _AgentRunsScreenState();
}

class _AgentRunsScreenState extends ConsumerState<AgentRunsScreen> {
  int _refreshTick = 0;

  Future<Map<String, dynamic>> _runsFuture() {
    _refreshTick;
    return ref.read(ripClientProvider).listAgentRuns();
  }

  void _refresh() {
    if (mounted) setState(() => _refreshTick++);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agent Runs'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _runsFuture(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          final runs = (snapshot.data?['runs'] as List?) ?? [];
          if (runs.isEmpty) return const Center(child: Text('No agent runs yet. Use /agent in chat.'));
          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: runs.length,
              itemBuilder: (_, i) {
                final run = Map<String, dynamic>.from(runs[i] as Map);
                final status = run['status']?.toString() ?? 'running';
                final pending = run['pending_approval'] != null;
                return Card(
                  child: ListTile(
                    leading: Icon(
                      pending
                          ? Icons.verified_user_rounded
                          : status == 'completed'
                              ? Icons.check_circle
                              : Icons.sync,
                      color: pending
                          ? Colors.amber.shade800
                          : status == 'completed'
                              ? Colors.green
                              : Colors.orange,
                    ),
                    title: Text(run['query']?.toString() ?? '', maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Text(pending ? 'Waiting for your approval' : status),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _showRunDetail(context, run['id']?.toString() ?? ''),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  void _showRunDetail(BuildContext context, String runId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _AgentRunDetailSheet(runId: runId, onChanged: _refresh),
    );
  }
}

class _AgentRunDetailSheet extends ConsumerStatefulWidget {
  final String runId;
  final VoidCallback onChanged;

  const _AgentRunDetailSheet({required this.runId, required this.onChanged});

  @override
  ConsumerState<_AgentRunDetailSheet> createState() => _AgentRunDetailSheetState();
}

class _AgentRunDetailSheetState extends ConsumerState<_AgentRunDetailSheet> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Map<String, dynamic>> _load() {
    return ref.read(ripClientProvider).getAgentRun(widget.runId);
  }

  Future<void> _decide(bool approved) async {
    await ref.read(ripClientProvider).approveAgentTool(
          runId: widget.runId,
          approved: approved,
        );
    widget.onChanged();
    if (mounted) {
      setState(() => _future = _load());
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final run = snapshot.data!;
        final trace = _traceFromRun(widget.runId, run);
        final pending = run['pending_approval'] is Map
            ? Map<String, dynamic>.from(run['pending_approval'] as Map)
            : null;
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.85,
          builder: (_, scrollController) => ListView(
            controller: scrollController,
            padding: const EdgeInsets.all(16),
            children: [
              Text('Query: ${run['query']}', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 6),
              Text('Status: ${run['status']} | Tokens: ${run['tokens_total'] ?? 0}'),
              if (pending != null) ...[
                const SizedBox(height: 12),
                _ApprovalCard(pending: pending, onApprove: () => _decide(true), onReject: () => _decide(false)),
              ],
              if (run['summary'] != null) ...[
                const Divider(),
                Text('Summary:', style: Theme.of(context).textTheme.titleSmall),
                Text('${run['summary']}'),
              ],
              const Divider(),
              Text('Live Trace:', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              PipelineStepList(trace: trace),
            ],
          ),
        );
      },
    );
  }
}

class _ApprovalCard extends StatelessWidget {
  final Map<String, dynamic> pending;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalCard({required this.pending, required this.onApprove, required this.onReject});

  @override
  Widget build(BuildContext context) {
    final params = Map<String, dynamic>.from(pending['params'] as Map? ?? const {});
    final target = params['path'] ?? params['command'] ?? '';
    return Card(
      color: Colors.amber.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Approval needed', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 6),
            Text('${pending['tool_name'] ?? pending['tool']}: $target'),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onReject,
                    icon: const Icon(Icons.close_rounded),
                    label: const Text('Reject'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onApprove,
                    icon: const Icon(Icons.check_rounded),
                    label: const Text('Approve'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

PipelineTrace _traceFromRun(String runId, Map<String, dynamic> run) {
  final steps = (run['steps'] as List?) ?? const [];
  final events = <PipelineEvent>[];
  var seq = 1;
  final startedAt = DateTime.now();
  events.add(PipelineEvent(
    sessionId: runId,
    stage: 'started',
    status: 'ok',
    detail: run['query']?.toString() ?? 'Agent run',
    meta: const {},
    seq: seq++,
    timestamp: startedAt,
    source: 'agent',
  ));
  for (final raw in steps) {
    if (raw is! Map) continue;
    final step = Map<String, dynamic>.from(raw);
    final result = Map<String, dynamic>.from(step['tool_result'] as Map? ?? step['result'] as Map? ?? const {});
    final ok = result['ok'] != false;
    final tool = step['tool_name'] ?? step['tool'] ?? 'thinking';
    events.add(PipelineEvent(
      sessionId: runId,
      stage: ok ? 'tool_done' : 'tool_failed',
      status: ok ? 'ok' : 'failed',
      detail: 'Turn ${step['turn']}: $tool',
      meta: {'tool': tool, if (result['error'] != null) 'error': result['error']},
      seq: seq++,
      timestamp: DateTime.tryParse(step['timestamp']?.toString() ?? '') ?? startedAt,
      source: 'agent',
    ));
  }
  if (run['pending_approval'] != null) {
    final pending = Map<String, dynamic>.from(run['pending_approval'] as Map);
    events.add(PipelineEvent(
      sessionId: runId,
      stage: 'approval_needed',
      status: 'ok',
      detail: 'Waiting for approval: ${pending['tool_name'] ?? pending['tool'] ?? 'tool'}',
      meta: pending,
      seq: seq++,
      timestamp: DateTime.tryParse(pending['requested_at']?.toString() ?? '') ?? DateTime.now(),
      source: 'agent',
    ));
  }
  return PipelineTrace(sessionId: runId, events: events);
}
