import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/connection_provider.dart';
import '../providers/project_provider.dart';

class WorkspaceDashboard extends ConsumerStatefulWidget {
  const WorkspaceDashboard({super.key});
  @override
  ConsumerState<WorkspaceDashboard> createState() => _WorkspaceDashboardState();
}

class _WorkspaceDashboardState extends ConsumerState<WorkspaceDashboard> {
  @override
  Widget build(BuildContext context) {
    final activeProject = ref.watch(activeProjectProvider);
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => setState(() {}),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Text('Good Morning 👋', style: theme.textTheme.headlineSmall),
            Text('Workspace: ${activeProject.valueOrNull?.projectName ?? "Select a project"}', style: theme.textTheme.bodyMedium),
            const SizedBox(height: 20),
            _GoalsCard(),
            const SizedBox(height: 16),
            _NeedsAttentionCard(),
            const SizedBox(height: 16),
            _KnowledgeReviewCard(),
            const SizedBox(height: 16),
            _RecentActivityCard(),
            const SizedBox(height: 16),
            _QuickAskBar(),
          ]),
        ),
      ),
    );
  }
}

class _GoalsCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('🎯 Active Goals', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      LinearProgressIndicator(value: 0.70, backgroundColor: Colors.grey[200]),
      const SizedBox(height: 4),
      Text('Build Organization Memory — 70% complete', style: Theme.of(context).textTheme.bodySmall),
    ])));
  }
}

class _NeedsAttentionCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(color: Colors.amber.shade50, child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('⚠️ Needs Attention', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      _Item(Icons.warning_amber_rounded, 'Payment module changed 23 times', Colors.red),
      _Item(Icons.info_outline, '3 PRs touching same module', Colors.orange),
      _Item(Icons.lightbulb_outline, 'Search queries slowing — optimize', Colors.amber.shade700),
    ])));
  }
  Widget _Item(IconData icon, String text, Color color) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Row(children: [
      Icon(icon, size: 18, color: color), const SizedBox(width: 8),
      Expanded(child: Text(text, style: TextStyle(fontSize: 13)))
    ]));
  }
}

class _KnowledgeReviewCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('📝 Pending Review', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      ListTile(dense: true, leading: Icon(Icons.auto_awesome, color: Colors.purple.shade300),
        title: Text('"Use SQLite for memory store"', style: TextStyle(fontSize: 13)),
        subtitle: Text('Source: Claude · Confidence: 0.42', style: TextStyle(fontSize: 11)),
        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
          IconButton(icon: Icon(Icons.check, color: Colors.green), onPressed: () {}),
          IconButton(icon: Icon(Icons.close, color: Colors.red), onPressed: () {}),
        ])),
    ])));
  }
}

class _RecentActivityCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('📈 Recent Activity', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      _Activity(Icons.check_circle, 'Agent: Fixed memory search', '2m ago'),
      _Activity(Icons.account_tree, 'Workflow: Deploy Memory Service', '15m ago'),
      _Activity(Icons.chat, 'Claude: Architecture discussion', '1h ago'),
    ])));
  }
  Widget _Activity(IconData icon, String title, String time) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 3), child: Row(children: [
      Icon(icon, size: 16, color: Colors.green), const SizedBox(width: 8),
      Expanded(child: Text(title, style: TextStyle(fontSize: 13))),
      Text(time, style: TextStyle(fontSize: 11, color: Colors.grey)),
    ]));
  }
}

class _QuickAskBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return TextField(
      decoration: InputDecoration(
        hintText: 'Ask anything... "How is Org Memory going?"',
        filled: true, fillColor: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
        suffixIcon: IconButton(icon: const Icon(Icons.send_rounded), onPressed: () {}),
      ),
    );
  }
}
