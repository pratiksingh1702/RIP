import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/rip_client.dart';
import '../../../core/design/app_colors.dart';
import '../../../domain/enums/job_status.dart';
import '../../providers/connection_provider.dart';
import '../../providers/project_provider.dart';
import '../common/status_badge.dart';

class ProjectList extends ConsumerWidget {
  const ProjectList({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final projectsAsync = ref.watch(projectListProvider);
    final activeProjectId = ref.watch(activeProjectIdProvider);

    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.background,
          border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          borderRadius: BorderRadius.circular(22),
        ),
        child: projectsAsync.when(
            loading: () => const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            ),
            error: (error, stack) => Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Error: $error',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 14),
                    _ReloadButton(
                      onPressed: () => ref.invalidate(projectListProvider),
                    ),
                  ],
                ),
              ),
            ),
            data: (projects) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 14, 8),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'Projects',
                          style: TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      _ReloadButton(
                        compact: true,
                        onPressed: () {
                          HapticFeedback.selectionClick();
                          ref.invalidate(projectListProvider);
                        },
                      ),
                    ],
                  ),
                ),
                if (projects.isEmpty)
                  const Expanded(
                    child: Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          'No projects found. Reload after indexing a repo.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    ),
                  ),
                if (projects.isNotEmpty)
                  Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 4, 12, 14),
                    itemCount: projects.length,
                    itemBuilder: (context, index) {
                      final project = projects[index];
                      final isActive = project.projectId == activeProjectId;
                      return _ProjectCard(
                        projectId: project.projectId,
                        name: project.projectName,
                        location: project.locationLabel,
                        owner: project.repositoryOwner,
                        branch: project.branch,
                        filesCount: project.filesCount,
                        entitiesCount: project.entitiesCount,
                        languages: project.languages,
                        isActive: isActive,
                        onTap: () {
                          HapticFeedback.selectionClick();
                          ref
                              .read(activeProjectNotifierProvider.notifier)
                              .setActiveProject(project.projectId);
                          Navigator.of(context).maybePop();
                        },
                        onDelete: () => _confirmDeleteProject(context, ref, project.projectId, project.projectName),
                      );
                    },
                  ),
                ),
              ],
            ),
        ),
      ),
    );
  }

  Future<void> _confirmDeleteProject(
    BuildContext context,
    WidgetRef ref,
    String projectId,
    String projectName,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF14141A),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Delete $projectName?', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: const Text(
          'This will permanently delete this project, including its Neo4j AST graph nodes, Qdrant vector embeddings, database memories, and cloned folder in .remote-repos.',
          style: TextStyle(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: const Text('Delete', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      try {
        final activeId = ref.read(activeProjectIdProvider);
        if (activeId == projectId) {
          await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(null);
        }
        final client = ref.read(ripClientProvider);
        await client.deleteProject(projectId);
        ref.invalidate(projectListProvider);
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Project "$projectName" deleted'),
              backgroundColor: const Color(0xFF22C55E),
            ),
          );
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete project: $e'),
              backgroundColor: const Color(0xFFEF4444),
            ),
          );
        }
      }
    }
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({
    required this.projectId,
    required this.name,
    required this.location,
    required this.filesCount,
    required this.entitiesCount,
    required this.languages,
    required this.isActive,
    required this.onTap,
    required this.onDelete,
    this.owner,
    this.branch,
  });

  final String projectId;
  final String name;
  final String location;
  final String? owner;
  final String? branch;
  final int filesCount;
  final int entitiesCount;
  final List<String> languages;
  final bool isActive;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Material(
        color: isActive
            ? AppColors.primary.withValues(alpha: 0.18)
            : Colors.white.withValues(alpha: 0.055),
        borderRadius: BorderRadius.circular(22),
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOutCubic,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(22),
              border: Border.all(
                color: isActive
                    ? AppColors.primary.withValues(alpha: 0.38)
                    : Colors.white.withValues(alpha: 0.07),
              ),
              boxShadow: isActive
                  ? [
                      BoxShadow(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        blurRadius: 24,
                        offset: const Offset(0, 12),
                      ),
                    ]
                  : null,
            ),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(17),
                    color: isActive
                        ? AppColors.primary
                        : Colors.white.withValues(alpha: 0.08),
                  ),
                  child: const Icon(
                    Icons.folder_open_rounded,
                    color: Colors.white,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _metadataLine,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppColors.textSecondary.withValues(alpha: 0.72),
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        location,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppColors.textSecondary.withValues(alpha: 0.56),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: onDelete,
                  icon: const Icon(Icons.delete_outline_rounded, size: 18, color: Color(0xFFEF4444)),
                  tooltip: 'Delete Project',
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String get _metadataLine {
    final parts = <String>[
      if (owner != null && owner!.trim().isNotEmpty) 'Owner: $owner',
      if (branch != null && branch!.trim().isNotEmpty) 'Branch: $branch',
      '$filesCount files',
      '$entitiesCount entities',
      if (languages.isNotEmpty) languages.take(3).join(', '),
    ];
    return parts.join('  |  ');
  }
}

class _ReloadButton extends StatelessWidget {
  const _ReloadButton({
    required this.onPressed,
    this.compact = false,
  });

  final VoidCallback onPressed;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: 'Reload projects',
      child: IconButton(
        onPressed: onPressed,
        icon: const Icon(Icons.refresh_rounded),
        color: AppColors.textPrimary,
        iconSize: compact ? 19 : 20,
        style: IconButton.styleFrom(
          fixedSize: Size.square(compact ? 36 : 42),
          backgroundColor: Colors.white.withValues(alpha: 0.07),
          shape: const CircleBorder(),
        ),
      ),
    );
  }
}
