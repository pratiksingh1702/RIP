import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api/rip_websocket_client.dart';
import '../../../data/models/index_job.dart';
import '../../../domain/enums/job_status.dart';
import '../../providers/connection_provider.dart';
import '../../providers/project_provider.dart';
import '../../providers/settings_provider.dart';
import '../common/status_badge.dart';

class AddRepoSheet extends ConsumerStatefulWidget {
  const AddRepoSheet({super.key});

  @override
  ConsumerState<AddRepoSheet> createState() => _AddRepoSheetState();
}

class _AddRepoSheetState extends ConsumerState<AddRepoSheet> {
  final _gitUrlController = TextEditingController();
  final _projectNameController = TextEditingController();
  final _folderNameController = TextEditingController();
  final _subdirectoryController = TextEditingController(text: 'lib');
  final _branchController = TextEditingController(text: 'main');
  IndexJob? _currentJob;
  RipWebSocketClient? _wsClient;

  @override
  void initState() {
    super.initState();
    _gitUrlController.addListener(_autoFillProjectName);
  }

  @override
  void dispose() {
    _gitUrlController.dispose();
    _projectNameController.dispose();
    _folderNameController.dispose();
    _subdirectoryController.dispose();
    _branchController.dispose();
    _wsClient?.dispose();
    super.dispose();
  }

  void _autoFillProjectName() {
    final url = _gitUrlController.text.trim();
    if (url.isNotEmpty) {
      try {
        final uri = Uri.parse(url);
        final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
        if (segments.isNotEmpty) {
          String name = segments.last;
          if (name.endsWith('.git')) {
            name = name.substring(0, name.length - 4);
          }
          if (_projectNameController.text.isEmpty) {
            _projectNameController.text = name;
          }
          if (_folderNameController.text.isEmpty) {
            _folderNameController.text = _safeFolderName(name);
          }
        }
      } catch (_) {}
    }
  }

  String _safeFolderName(String value) {
    final safe = value.trim().replaceAll(RegExp(r'[^A-Za-z0-9._-]+'), '-');
    return safe.replaceAll(RegExp(r'^[-_.]+|[-_.]+$'), '');
  }

  Future<void> _startIndex() async {
    final gitUrl = _gitUrlController.text.trim();
    final projectName = _projectNameController.text.trim();
    final folderName = _folderNameController.text.trim();
    final subdirectory = _subdirectoryController.text.trim();
    final branch = _branchController.text.trim();

    if (gitUrl.isEmpty || projectName.isEmpty || folderName.isEmpty) return;

    final client = ref.read(ripClientProvider);
    try {
      final job = await client.startGitIndex(
        gitUrl: gitUrl,
        projectName: projectName,
        folderName: folderName,
        subdirectory: subdirectory.isEmpty ? null : subdirectory,
        branch: branch.isEmpty ? 'main' : branch,
      );
      setState(() {
        _currentJob = job;
      });
      // Connect to WebSocket
      _wsClient = RipWebSocketClient(
        serverUrl: ref.read(serverUrlProvider),
        apiKey: ref.read(apiKeyProvider),
      );
      _wsClient!.stream.listen((event) {
        // Update UI from socket event
        if (mounted) {
          setState(() {});
        }
      });
      await _wsClient!.connect(job.jobId);
      // Start polling status as fallback
      await _pollJobStatus(job.jobId);
    } catch (e) {
      if (mounted) {
        setState(() {
          _currentJob = IndexJob(
            jobId: '',
            status: JobStatus.failed,
            progressMessage: 'Error: $e',
            filesIndexed: 0,
            entitiesFound: 0,
            error: e.toString(),
          );
        });
      }
    }
  }

  Future<void> _pollJobStatus(String jobId) async {
    final client = ref.read(ripClientProvider);
    while (mounted &&
        (_currentJob?.status == JobStatus.pending ||
            _currentJob?.status == JobStatus.cloning ||
            _currentJob?.status == JobStatus.indexing)) {
      try {
        final job = await client.getJobStatus(jobId);
        setState(() {
          _currentJob = job;
        });
        if (job.status == JobStatus.complete || job.status == JobStatus.failed) {
          // Refresh projects
          if (mounted) {
            ref.invalidate(projectListProvider);
          }
          break;
        }
      } catch (_) {}
      await Future.delayed(const Duration(seconds: 2));
    }
  }

  void _reset() {
    setState(() {
      _currentJob = null;
      _gitUrlController.clear();
      _projectNameController.clear();
      _folderNameController.clear();
      _subdirectoryController.text = 'lib';
      _branchController.text = 'main';
    });
    _wsClient?.dispose();
    _wsClient = null;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(16),
          topRight: Radius.circular(16),
        ),
      ),
      child: _currentJob != null
          ? _buildStatusScreen()
          : _buildInputScreen(),
    );
  }

  Widget _buildInputScreen() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Add Repository',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _gitUrlController,
          decoration: const InputDecoration(
            labelText: 'Git URL',
            hintText: 'https://github.com/user/repo.git',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _projectNameController,
          decoration: const InputDecoration(
            labelText: 'Project Name',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _folderNameController,
          decoration: const InputDecoration(
            labelText: 'Clone Folder Name',
            hintText: 'my-repository',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _subdirectoryController,
          decoration: const InputDecoration(
            labelText: 'Index Subfolder',
            hintText: 'lib',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _branchController,
          decoration: const InputDecoration(
            labelText: 'Branch',
            hintText: 'main',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _startIndex,
          style: ElevatedButton.styleFrom(
            minimumSize: const Size(double.infinity, 48),
          ),
          child: const Text('Start Indexing'),
        ),
      ],
    );
  }

  Widget _buildStatusScreen() {
    final job = _currentJob!;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              job.status == JobStatus.complete
                  ? 'Indexing Complete'
                  : job.status == JobStatus.failed
                      ? 'Indexing Failed'
                      : 'Indexing...',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: _reset,
            ),
          ],
        ),
        const SizedBox(height: 16),
        StatusBadge(status: job.status),
        const SizedBox(height: 16),
        Text(job.progressMessage),
        if (job.folderName != null || job.clonePath != null || job.indexPath != null) ...[
          const SizedBox(height: 8),
          Text(
            [
              if (job.folderName != null) 'Folder: ${job.folderName}',
              if (job.clonePath != null) 'Path: ${job.clonePath}',
              if (job.indexPath != null) 'Index: ${job.indexPath}',
            ].join(' · '),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Files Indexed',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    '${job.filesIndexed}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ],
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    'Entities Found',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    '${job.entitiesFound}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (job.status == JobStatus.complete || job.status == JobStatus.failed)
          ElevatedButton(
            onPressed: _reset,
            style: ElevatedButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
            ),
            child: Text(job.status == JobStatus.complete ? 'Add Another' : 'Try Again'),
          ),
      ],
    );
  }
}
