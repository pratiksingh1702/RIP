import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/models/project.dart';
import '../../providers/project_provider.dart';
import '../common/status_badge.dart';
import '../../../domain/enums/job_status.dart';

class ProjectSwitcher extends StatefulWidget {
  final Function(Project) onProjectSelected;
  final VoidCallback onDismissed;

  const ProjectSwitcher({
    super.key,
    required this.onProjectSelected,
    required this.onDismissed,
  });

  @override
  State<ProjectSwitcher> createState() => _ProjectSwitcherState();
}

class _ProjectSwitcherState extends State<ProjectSwitcher> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _focusNode.requestFocus();
    _controller.addListener(() {
      setState(() {
        _filter = _controller.text.toLowerCase();
      });
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer(
      builder: (context, ref, child) {
        final projectsAsync = ref.watch(projectListProvider);

        return Container(
          height: MediaQuery.of(context).size.height * 0.6,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
            ),
          ),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  autofocus: true,
                  decoration: const InputDecoration(
                    hintText: 'Search projects...',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.search),
                  ),
                ),
              ),
              Expanded(
                child: projectsAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (error, stack) => Center(
                    child: Text('Error loading projects: $error'),
                  ),
                  data: (projects) {
                    final filteredProjects = projects
                        .where((p) =>
                            p.projectName.toLowerCase().contains(_filter) ||
                            (p.gitUrl?.toLowerCase().contains(_filter) ?? false))
                        .toList();
                    return ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: filteredProjects.length,
                      itemBuilder: (context, index) {
                        final project = filteredProjects[index];
                        return ListTile(
                          leading: const Icon(Icons.folder),
                          title: Text(project.projectName),
                          subtitle: project.gitUrl != null
                              ? Text(project.gitUrl!)
                              : null,
                          trailing: const StatusBadge(status: JobStatus.complete),
                          onTap: () {
                            widget.onProjectSelected(project);
                            widget.onDismissed();
                          },
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
