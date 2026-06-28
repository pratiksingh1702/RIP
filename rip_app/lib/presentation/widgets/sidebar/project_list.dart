import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/project.dart';
import '../../providers/project_provider.dart';
import '../common/status_badge.dart';
import '../../../domain/enums/job_status.dart';

class ProjectList extends ConsumerWidget {
  const ProjectList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final projectsAsync = ref.watch(projectListProvider);
    final activeProjectId = ref.watch(activeProjectIdProvider);

    return projectsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, stack) => Center(child: Text('Error: $error')),
      data: (projects) => ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: projects.length,
        itemBuilder: (context, index) {
          final project = projects[index];
          final isActive = project.projectId == activeProjectId;
          return ListTile(
            leading: const Icon(Icons.folder),
            title: Text(project.projectName),
            subtitle: project.gitUrl != null
                ? Text(project.gitUrl!)
                : null,
            trailing: const StatusBadge(status: JobStatus.complete),
            tileColor: isActive
                ? Theme.of(context).colorScheme.primaryContainer
                : null,
            onTap: () {
              ref
                  .read(activeProjectNotifierProvider.notifier)
                  .setActiveProject(project.projectId);
            },
          );
        },
      ),
    );
  }
}
