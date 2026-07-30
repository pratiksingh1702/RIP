import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:rip_app/core/api/rip_websocket_client.dart';
import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import 'package:rip_app/presentation/providers/project_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';

class FirstTimeGithubOnboardingDialog extends ConsumerStatefulWidget {
  const FirstTimeGithubOnboardingDialog({super.key});

  @override
  ConsumerState<FirstTimeGithubOnboardingDialog> createState() =>
      _FirstTimeGithubOnboardingDialogState();
}

class _FirstTimeGithubOnboardingDialogState
    extends ConsumerState<FirstTimeGithubOnboardingDialog> {
  final ScrollController _bgScrollController = ScrollController();
  Timer? _bgScrollTimer;
  RipWebSocketClient? _wsClient;

  List<Map<String, dynamic>> _repos = [];
  bool _isLoadingRepos = true;
  String? _selectedRepoId;
  String? _reposError;

  // Pipeline configuration flags
  bool _buildGraph = true;
  bool _buildVectors = true;
  bool _ingestGitHistory = true;

  bool _isIndexing = false;
  double _indexingProgress = 0.0;
  String _indexingStepText = 'Initializing repository indexing...';
  int _currentStepIndex = 0;
  bool _isFinished = false;

  @override
  void initState() {
    super.initState();
    _fetchGithubRepos();
    _startBgAutoScroll();
  }

  @override
  void dispose() {
    _bgScrollTimer?.cancel();
    _bgScrollController.dispose();
    _wsClient?.dispose();
    super.dispose();
  }

  void _startBgAutoScroll() {
    _bgScrollTimer = Timer.periodic(const Duration(milliseconds: 40), (_) {
      if (_bgScrollController.hasClients) {
        final maxScroll = _bgScrollController.position.maxScrollExtent;
        final currentScroll = _bgScrollController.offset;
        if (currentScroll >= maxScroll) {
          _bgScrollController.jumpTo(0);
        } else {
          _bgScrollController.animateTo(
            currentScroll + 1.2,
            duration: const Duration(milliseconds: 40),
            curve: Curves.linear,
          );
        }
      }
    });
  }

  Future<void> _fetchGithubRepos() async {
    try {
      final client = ref.read(ripClientProvider);
      final repos = await client.getUserGithubRepos();
      if (mounted) {
        setState(() {
          _repos = repos;
          _isLoadingRepos = false;
          if (_repos.isNotEmpty) {
            _selectedRepoId = _repos.first['id']?.toString() ?? _repos.first['full_name'];
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _reposError = e.toString();
          _isLoadingRepos = false;
        });
      }
    }
  }

  Future<void> _startIndexing() async {
    final selected = _repos.firstWhere(
      (r) => r['id'] == _selectedRepoId,
      orElse: () => _repos.isNotEmpty ? _repos[0] : {},
    );
    if (selected.isEmpty) return;

    HapticFeedback.mediumImpact();
    setState(() {
      _isIndexing = true;
      _indexingProgress = 0.15;
      _indexingStepText = 'Cloning ${selected['full_name']}...';
      _currentStepIndex = 1;
    });

    final client = ref.read(ripClientProvider);
    try {
      final repoName = selected['name'] as String;
      final cloneUrl = selected['clone_url'] as String? ??
          'https://github.com/${selected['full_name']}.git';
      final branch = selected['default_branch'] as String? ?? 'main';

      final resp = await client.startGitIndex(
        gitUrl: cloneUrl,
        projectName: repoName,
        folderName: repoName.replaceAll(RegExp(r'[^a-zA-Z0-9._-]'), '_'),
        branch: branch,
      );

      final jobId = resp.jobId;

      // Connect WebSocket push stream for instant progress updates
      try {
        final baseUrl = ref.read(serverUrlProvider);
        _wsClient = RipWebSocketClient(serverUrl: baseUrl);
        _wsClient!.connect(jobId);
        _wsClient!.stream.listen((job) async {
          if (!mounted) return;
          final status = (job['status'] as String? ?? 'pending').toLowerCase();
          final progressMsg = job['progress_message'] as String? ?? '';
          final filesCount = job['files_indexed'] as int? ?? 0;

          if (status == 'cloning') {
            setState(() {
              _indexingProgress = 0.25;
              _currentStepIndex = 1;
              _indexingStepText = progressMsg.isNotEmpty
                  ? progressMsg
                  : 'Cloning $repoName from remote repository...';
            });
          } else if (status == 'indexing') {
            setState(() {
              _indexingProgress = filesCount > 0 ? 0.75 : 0.45;
              _currentStepIndex = filesCount > 0 ? 3 : 2;
              _indexingStepText = progressMsg.isNotEmpty
                  ? progressMsg
                  : 'Indexing Neo4j Knowledge Graph & Qdrant Vector Memory...';
            });
          } else if (status == 'complete') {
            final projectId = job['project_id'] as String? ?? repoName;
            await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(projectId);
            ref.invalidate(projectListProvider);

            setState(() {
              _indexingProgress = 1.0;
              _currentStepIndex = 4;
              _isFinished = true;
              _indexingStepText =
                  'Workspace "$repoName" fully indexed into Neo4j, Qdrant & Git memory!';
            });
            _wsClient?.disconnect();
          } else if (status == 'failed') {
            final errDetail = job['error'] as String? ?? 'Indexing encountered an error';
            setState(() {
              _indexingStepText = 'Indexing error: $errDetail';
            });
            _wsClient?.disconnect();
          }
        });
      } catch (_) {
        // Fallback to polling loop if WebSocket fails
      }

      // Fallback backend polling loop
      Timer.periodic(const Duration(milliseconds: 700), (timer) async {
        if (!mounted || _isFinished) {
          timer.cancel();
          return;
        }

        try {
          final job = await client.getGitJobStatus(jobId);
          final status = (job['status'] as String? ?? 'pending').toLowerCase();
          final progressMsg = job['progress_message'] as String? ?? '';
          final filesCount = job['files_indexed'] as int? ?? 0;

          if (status == 'cloning') {
            setState(() {
              _indexingProgress = 0.25;
              _currentStepIndex = 1;
              _indexingStepText = progressMsg.isNotEmpty
                  ? progressMsg
                  : 'Cloning $repoName from remote repository...';
            });
          } else if (status == 'indexing') {
            setState(() {
              _indexingProgress = filesCount > 0 ? 0.75 : 0.45;
              _currentStepIndex = filesCount > 0 ? 3 : 2;
              _indexingStepText = progressMsg.isNotEmpty
                  ? progressMsg
                  : 'Indexing Neo4j Knowledge Graph & Qdrant Vector Memory...';
            });
          } else if (status == 'complete') {
            timer.cancel();
            final projectId = job['project_id'] as String? ?? repoName;
            await ref.read(activeProjectNotifierProvider.notifier).setActiveProject(projectId);
            ref.invalidate(projectListProvider);

            setState(() {
              _indexingProgress = 1.0;
              _currentStepIndex = 4;
              _isFinished = true;
              _indexingStepText =
                  'Workspace "$repoName" fully indexed into Neo4j, Qdrant & Git memory!';
            });
          } else if (status == 'failed') {
            timer.cancel();
            final errDetail = job['error'] as String? ?? 'Indexing encountered an error';
            setState(() {
              _indexingStepText = 'Indexing error: $errDetail';
            });
          }
        } catch (_) {
          // Continue polling on temporary network lag
        }
      });
    } catch (e) {
      setState(() {
        _indexingStepText = 'Failed to connect to indexing pipeline: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final bodyBgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final borderSide = BorderSide(
      color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
    );

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: EdgeInsets.zero,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // 1. Full Background Blur Backdrop
          Positioned.fill(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 30, sigmaY: 30),
              child: Container(
                color: isDark
                    ? Colors.black.withValues(alpha: 0.65)
                    : Colors.black.withValues(alpha: 0.35),
              ),
            ),
          ),

          // 2. Infinite Stream in Background
          _buildBackgroundInfiniteList(isDark),

          // 3. Main Central Single-Body Glassmorphic Container
          Positioned(
            top: MediaQuery.of(context).size.height * 0.12,
            bottom: MediaQuery.of(context).size.height * 0.14,
            left: 20,
            right: 20,
            child: Center(
              child: Container(
                constraints: const BoxConstraints(maxWidth: 440, maxHeight: 540),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF14141A).withValues(alpha: 0.94)
                      : Colors.white.withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.12)
                        : Colors.black.withValues(alpha: 0.08),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: isDark ? 0.65 : 0.15),
                      blurRadius: 40,
                      offset: const Offset(0, 16),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: Column(
                    children: [
                      // Header Section
                      Container(
                        padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
                        decoration: BoxDecoration(
                          border: Border(bottom: borderSide),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 38,
                              height: 38,
                              decoration: BoxDecoration(
                                color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Icon(
                                Icons.folder_copy_outlined,
                                size: 18,
                                color: isDark ? Colors.white : AppColors.textPrimary,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'GitHub Repository Indexing',
                                    style: TextStyle(
                                      fontSize: 15.5,
                                      fontWeight: FontWeight.bold,
                                      color: textColor,
                                      letterSpacing: -0.3,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Select a repository to index workspace memory',
                                    style: TextStyle(fontSize: 11.5, color: mutedTextColor),
                                  ),
                                ],
                              ),
                            ),
                            IconButton(
                              onPressed: () {
                                HapticFeedback.selectionClick();
                                Navigator.pop(context);
                              },
                              icon: Icon(Icons.close_rounded, size: 20, color: mutedTextColor),
                              tooltip: _isIndexing ? 'Run in background' : 'Close',
                              visualDensity: VisualDensity.compact,
                            ),
                          ],
                        ),
                      ),

                      // Main Content Area
                      Expanded(
                        child: _isIndexing
                            ? _buildIndexingProgressView(
                                isDark, cardBgColor, textColor, mutedTextColor, borderSide)
                            : _buildRepoSelectionView(
                                isDark, cardBgColor, bodyBgColor, textColor, mutedTextColor, borderSide),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // 4. Separate Floating Action Control Chips (Skip & Index Workspace)
          if (!_isIndexing)
            Positioned(
              bottom: MediaQuery.paddingOf(context).bottom + 24,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Floating Skip Button
                  ClipRRect(
                    borderRadius: BorderRadius.circular(18),
                    child: BackdropFilter(
                      filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
                      child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                          },
                          borderRadius: BorderRadius.circular(18),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                            decoration: BoxDecoration(
                              color: isDark
                                  ? Colors.white.withValues(alpha: 0.1)
                                  : Colors.white.withValues(alpha: 0.85),
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(
                                color: isDark
                                    ? Colors.white.withValues(alpha: 0.15)
                                    : Colors.black.withValues(alpha: 0.1),
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.2),
                                  blurRadius: 16,
                                  offset: const Offset(0, 4),
                                ),
                              ],
                            ),
                            child: Text(
                              'Skip for now',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: isDark ? Colors.white70 : AppColors.textPrimary,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),

                  // Floating Index Workspace Button
                  ClipRRect(
                    borderRadius: BorderRadius.circular(18),
                    child: BackdropFilter(
                      filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
                      child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: _selectedRepoId == null ? null : _startIndexing,
                          borderRadius: BorderRadius.circular(18),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: _selectedRepoId == null
                                    ? [Colors.grey.shade700, Colors.grey.shade800]
                                    : (isDark
                                        ? [const Color(0xFF38BDF8), const Color(0xFF2563EB)]
                                        : [const Color(0xFF0EA5E9), const Color(0xFF1D4ED8)]),
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(
                                color: Colors.white.withValues(alpha: 0.2),
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFF0EA5E9).withValues(alpha: 0.4),
                                  blurRadius: 16,
                                  offset: const Offset(0, 4),
                                ),
                              ],
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.bolt_rounded, size: 16, color: Colors.white),
                                SizedBox(width: 6),
                                Text(
                                  'Index Workspace',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBackgroundInfiniteList(bool isDark) {
    return Positioned.fill(
      child: IgnorePointer(
        child: ShaderMask(
          shaderCallback: (rect) {
            return const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Colors.transparent,
                Colors.black,
                Colors.black,
                Colors.transparent,
              ],
              stops: [0.0, 0.15, 0.85, 1.0],
            ).createShader(rect);
          },
          blendMode: BlendMode.dstIn,
          child: ListView.builder(
            controller: _bgScrollController,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: 100,
            itemBuilder: (context, index) {
              final repoName = 'repository_${index % 15}';
              return Container(
                margin: const EdgeInsets.symmetric(horizontal: 32, vertical: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF14141A).withValues(alpha: 0.15)
                      : Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isDark ? Colors.white.withValues(alpha: 0.03) : Colors.black.withValues(alpha: 0.02),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.code_rounded,
                      size: 16,
                      color: isDark ? Colors.white24 : Colors.black26,
                    ),
                    const SizedBox(width: 12),
                    Text(
                      'github.com/workspace/$repoName',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? Colors.white24 : Colors.black38,
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildRepoSelectionView(
    bool isDark,
    Color cardBgColor,
    Color bodyBgColor,
    Color textColor,
    Color mutedTextColor,
    BorderSide borderSide,
  ) {
    return Column(
      children: [
        // Repository List with Top and Bottom Linear Gradient Fades
        Expanded(
          child: _isLoadingRepos
              ? Center(child: CircularProgressIndicator(strokeWidth: 2, color: isDark ? Colors.white54 : Colors.black54))
              : _repos.isEmpty
                  ? Center(
                      child: Text(
                        'No repositories found',
                        style: TextStyle(color: mutedTextColor, fontSize: 12),
                      ),
                    )
                  : ShaderMask(
                      shaderCallback: (rect) {
                        return const LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.transparent,
                            Colors.black,
                            Colors.black,
                            Colors.transparent,
                          ],
                          stops: [0.0, 0.08, 0.92, 1.0],
                        ).createShader(rect);
                      },
                      blendMode: BlendMode.dstIn,
                      child: ListView.builder(
                        physics: const BouncingScrollPhysics(),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        itemCount: _repos.length,
                        itemBuilder: (context, index) {
                          final repo = _repos[index];
                          final isSelected = repo['id'] == _selectedRepoId;
                          return _SingleBodyRepoItem(
                            repo: repo,
                            isSelected: isSelected,
                            isDark: isDark,
                            onTap: () {
                              HapticFeedback.selectionClick();
                              setState(() => _selectedRepoId = repo['id']);
                            },
                          );
                        },
                      ),
                    ),
        ),

        // Pipeline Target Options
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.03) : Colors.black.withValues(alpha: 0.02),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _PipelineToggleOption(
                label: 'AST Call Graph (Neo4j)',
                value: _buildGraph,
                isDark: isDark,
                onChanged: (v) => setState(() => _buildGraph = v ?? true),
              ),
              _PipelineToggleOption(
                label: 'Vector Embeddings (Qdrant)',
                value: _buildVectors,
                isDark: isDark,
                onChanged: (v) => setState(() => _buildVectors = v ?? true),
              ),
              _PipelineToggleOption(
                label: 'Git Commit History Memory',
                value: _ingestGitHistory,
                isDark: isDark,
                onChanged: (v) => setState(() => _ingestGitHistory = v ?? true),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildIndexingProgressView(
    bool isDark,
    Color cardBgColor,
    Color textColor,
    Color mutedTextColor,
    BorderSide borderSide,
  ) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (!_isFinished) ...[
            SizedBox(
              width: 48,
              height: 48,
              child: CircularProgressIndicator(
                value: _indexingProgress,
                strokeWidth: 3,
                color: isDark ? Colors.white : AppColors.textPrimary,
                backgroundColor: isDark ? Colors.white10 : Colors.black12,
              ),
            ),
            const SizedBox(height: 18),
          ] else ...[
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.check_rounded, color: isDark ? Colors.white : AppColors.textPrimary, size: 28),
            ),
            const SizedBox(height: 18),
          ],
          Text(
            _isFinished ? 'Indexing Complete' : 'Indexing Workspace',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: textColor,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _indexingStepText,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: mutedTextColor),
          ),
          const SizedBox(height: 24),

          // Steps Progress
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isDark ? Colors.white.withValues(alpha: 0.04) : Colors.black.withValues(alpha: 0.03),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05),
              ),
            ),
            child: Column(
              children: [
                _ProgressStepRow(
                  number: 1,
                  title: 'Cloning Repository',
                  isCompleted: _currentStepIndex > 1 || _isFinished,
                  isActive: _currentStepIndex == 1 && !_isFinished,
                  isDark: isDark,
                ),
                const SizedBox(height: 6),
                _ProgressStepRow(
                  number: 2,
                  title: 'Building AST Dependency Graph',
                  isCompleted: _currentStepIndex > 2 || _isFinished,
                  isActive: _currentStepIndex == 2 && !_isFinished,
                  isDark: isDark,
                ),
                const SizedBox(height: 6),
                _ProgressStepRow(
                  number: 3,
                  title: 'Indexing Code Vector Memory',
                  isCompleted: _currentStepIndex > 3 || _isFinished,
                  isActive: _currentStepIndex == 3 && !_isFinished,
                  isDark: isDark,
                ),
                const SizedBox(height: 6),
                _ProgressStepRow(
                  number: 4,
                  title: 'Ingesting Commit History',
                  isCompleted: _isFinished,
                  isActive: _currentStepIndex == 4 && !_isFinished,
                  isDark: isDark,
                ),
              ],
            ),
          ),
          const Spacer(),

          if (!_isFinished) ...[
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  HapticFeedback.selectionClick();
                  Navigator.pop(context);
                },
                icon: const Icon(Icons.open_in_new_rounded, size: 14),
                label: const Text(
                  'Run in background & View Status',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: isDark ? Colors.white70 : AppColors.textPrimary,
                  side: BorderSide(
                    color: isDark ? Colors.white24 : Colors.black26,
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ),
          ] else
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: isDark ? Colors.white : AppColors.textPrimary,
                  foregroundColor: isDark ? Colors.black : Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: () {
                  HapticFeedback.selectionClick();
                  Navigator.pop(context);
                  context.go('/chat');
                },
                child: const Text(
                  'Open Chat',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SingleBodyRepoItem extends StatelessWidget {
  const _SingleBodyRepoItem({
    required this.repo,
    required this.isSelected,
    required this.isDark,
    required this.onTap,
  });

  final Map<String, dynamic> repo;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Material(
        color: isSelected
            ? (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06))
            : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              children: [
                Icon(
                  isSelected ? Icons.radio_button_checked_rounded : Icons.radio_button_off_rounded,
                  size: 16,
                  color: isSelected
                      ? (isDark ? Colors.white : AppColors.textPrimary)
                      : mutedTextColor,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              repo['full_name'] ?? repo['name'],
                              style: TextStyle(
                                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                fontSize: 12.5,
                                color: textColor,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Text(
                            repo['language'] ?? 'Code',
                            style: TextStyle(
                              fontSize: 10,
                              color: mutedTextColor,
                            ),
                          ),
                        ],
                      ),
                      if (repo['description'] != null && repo['description'].toString().isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          repo['description'],
                          style: TextStyle(fontSize: 11, color: mutedTextColor),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PipelineToggleOption extends StatelessWidget {
  const _PipelineToggleOption({
    required this.label,
    required this.value,
    required this.isDark,
    required this.onChanged,
  });

  final String label;
  final bool value;
  final bool isDark;
  final ValueChanged<bool?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        children: [
          SizedBox(
            height: 20,
            width: 20,
            child: Checkbox(
              value: value,
              onChanged: onChanged,
              activeColor: isDark ? Colors.white : AppColors.textPrimary,
              checkColor: isDark ? Colors.black : Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
              visualDensity: VisualDensity.compact,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              color: isDark ? Colors.white70 : AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressStepRow extends StatelessWidget {
  const _ProgressStepRow({
    required this.number,
    required this.title,
    required this.isCompleted,
    required this.isActive,
    required this.isDark,
  });

  final int number;
  final String title;
  final bool isCompleted;
  final bool isActive;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          isCompleted
              ? Icons.check_circle_rounded
              : (isActive ? Icons.play_circle_fill_rounded : Icons.radio_button_unchecked_rounded),
          size: 16,
          color: isCompleted || isActive
              ? (isDark ? Colors.white : AppColors.textPrimary)
              : (isDark ? Colors.white30 : Colors.black26),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: isActive || isCompleted ? FontWeight.bold : FontWeight.normal,
              color: isCompleted || isActive
                  ? (isDark ? Colors.white : AppColors.textPrimary)
                  : (isDark ? Colors.white38 : AppColors.textSecondary),
            ),
          ),
        ),
      ],
    );
  }
}
