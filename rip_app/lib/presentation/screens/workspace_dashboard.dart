import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';

class WorkspaceDashboard extends ConsumerStatefulWidget {
  const WorkspaceDashboard({super.key});
  @override
  ConsumerState<WorkspaceDashboard> createState() => _WorkspaceDashboardState();
}

class _WorkspaceDashboardState extends ConsumerState<WorkspaceDashboard> {
  Future<Map<String, dynamic>>? _dashboardFuture;

  @override
  void initState() {
    super.initState();
    // Don't call setState inside initState — just assign directly
    _dashboardFuture = _fetchDashboard();
  }

  Future<Map<String, dynamic>>? _fetchDashboard() {
    final projectId = ref.read(activeProjectIdProvider);
    if (projectId == null) return null;
    return ref.read(ripClientProvider).getDashboard(projectId);
  }

  void _refresh() {
    setState(() {
      _dashboardFuture = _fetchDashboard();
    });
    ref.invalidate(projectListProvider);
  }

  @override
  Widget build(BuildContext context) {
    final activeProject = ref.watch(activeProjectProvider);
    final projectId = ref.watch(activeProjectIdProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(activeProject.valueOrNull?.projectName ?? 'Workspace'),
        actions: [
          IconButton(icon: const Icon(Icons.chat_rounded), tooltip: 'Chat', onPressed: () => context.push('/chat')),
          IconButton(icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh', onPressed: _refresh),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: _dashboardFuture == null
            ? _EmptyState(projectId: projectId)
            : FutureBuilder<Map<String, dynamic>>(
                future: _dashboardFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return _EmptyState(projectId: projectId);
                  }

                  final data = snapshot.data ?? {};
                  final suggestions = (data['suggestions'] as List?) ?? [];
                  final recentActivity = (data['recent_activity'] as List?) ?? [];
                  final metrics = data['metrics'] as Map<String, dynamic>? ?? {};

                  return ListView(padding: const EdgeInsets.all(16), children: [
                    if (activeProject.valueOrNull != null) ...[
                      _ProjectHeader(project: activeProject.value!),
                      const SizedBox(height: 16),
                    ],
                    _MetricsRow(metrics: metrics),
                    const SizedBox(height: 16),
                    if (suggestions.isNotEmpty) ...[
                      _SuggestionsList(suggestions: suggestions),
                      const SizedBox(height: 16),
                    ],
                    _RecentActivityList(activities: recentActivity),
                  ]);
                },
              ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final String? projectId;
  const _EmptyState({required this.projectId});
  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(16), children: [
      const SizedBox(height: 40),
      Icon(Icons.dashboard_rounded, size: 48, color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.4)),
      const SizedBox(height: 16),
      Text(projectId == null ? 'No project selected' : 'No data yet', textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      Text(projectId == null ? 'Select a project in chat to see your workspace' : 'Start using the agent to see activity here', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
      const SizedBox(height: 24),
      Center(child: FilledButton.icon(onPressed: () => context.push('/chat'), icon: const Icon(Icons.chat_rounded), label: const Text('Open Chat'))),
    ]);
  }
}

class _ProjectHeader extends StatelessWidget {
  final dynamic project;
  const _ProjectHeader({required this.project});
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(padding: const EdgeInsets.all(16), child: Row(children: [
        Container(width: 48, height: 48, decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: Theme.of(context).colorScheme.primaryContainer), child: const Icon(Icons.folder_rounded, size: 24)),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(project.projectName ?? '', style: Theme.of(context).textTheme.titleMedium),
          Text('${project.filesCount ?? 0} files · ${project.entitiesCount ?? 0} entities', style: Theme.of(context).textTheme.bodySmall),
        ])),
      ])),
    );
  }
}

class _MetricsRow extends StatelessWidget {
  final Map<String, dynamic> metrics;
  const _MetricsRow({required this.metrics});
  @override
  Widget build(BuildContext context) {
    final used = (metrics['tokens_used'] as num?)?.toInt() ?? 0;
    final budgeted = (metrics['tokens_budgeted'] as num?)?.toInt() ?? 0;
    final savings = (metrics['token_savings_pct'] as num?)?.toDouble() ?? 0;
    return Row(children: [
      Expanded(child: _MiniCard(icon: Icons.token_rounded, label: 'Tokens Used', value: '$used')),
      const SizedBox(width: 8),
      Expanded(child: _MiniCard(icon: Icons.savings_rounded, label: 'Saved', value: '${savings.toStringAsFixed(0)}%', color: savings > 0 ? Colors.green : null)),
      const SizedBox(width: 8),
      Expanded(child: _MiniCard(icon: Icons.speed_rounded, label: 'Budget', value: '$budgeted')),
    ]);
  }
}

class _MiniCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? color;
  const _MiniCard({required this.icon, required this.label, required this.value, this.color});
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(padding: const EdgeInsets.all(12), child: Column(children: [
        Icon(icon, size: 20, color: color ?? Theme.of(context).colorScheme.primary),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
        Text(label, style: const TextStyle(fontSize: 10)),
      ])),
    );
  }
}

class _SuggestionsList extends StatelessWidget {
  final List suggestions;
  const _SuggestionsList({required this.suggestions});
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('💡 Suggestions', style: Theme.of(context).textTheme.titleSmall),
      const SizedBox(height: 8),
      ...suggestions.take(3).map((s) {
        final map = Map<String, dynamic>.from(s as Map);
        return Card(
          color: Colors.amber.shade50,
          child: ListTile(dense: true, leading: const Icon(Icons.lightbulb_outline, size: 18, color: Colors.amber), title: Text(map['message']?.toString() ?? '', style: const TextStyle(fontSize: 13))),
        );
      }),
    ]);
  }
}

class _RecentActivityList extends StatelessWidget {
  final List activities;
  const _RecentActivityList({required this.activities});
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('📈 Recent Activity', style: Theme.of(context).textTheme.titleSmall),
      const SizedBox(height: 8),
      if (activities.isEmpty)
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Text('No activity yet. Start using the agent in chat.', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant))))
      else
        ...activities.take(8).map((a) {
          final map = Map<String, dynamic>.from(a as Map);
          return ListTile(
            dense: true,
            leading: Icon(map['status'] == 'completed' ? Icons.check_circle : Icons.sync, size: 18, color: map['status'] == 'completed' ? Colors.green : Colors.orange),
            title: Text(map['summary']?.toString() ?? map['query']?.toString() ?? '', style: const TextStyle(fontSize: 13), maxLines: 2, overflow: TextOverflow.ellipsis),
          );
        }),
    ]);
  }
}