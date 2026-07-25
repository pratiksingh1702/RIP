import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rip_app/core/design/design.dart';
import '../../../data/models/sandbox.dart';
import '../providers/sandbox_provider.dart';
import '../widgets/sandbox/terminal_view.dart';
import '../widgets/sandbox/sandbox_status_bar.dart';
import '../widgets/sandbox/environment_picker.dart';
import '../widgets/sandbox/file_browser.dart';

class SandboxScreen extends ConsumerStatefulWidget {
  final String? projectId;
  const SandboxScreen({super.key, this.projectId});

  @override
  ConsumerState<SandboxScreen> createState() => _SandboxScreenState();
}

class _SandboxScreenState extends ConsumerState<SandboxScreen> {
  bool _showEnvPicker = false;

  @override
  void initState() {
    super.initState();
    final state = ref.read(sandboxProvider);
    if (state.activeSandboxes.isEmpty && state.sandbox == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _autoCreateDefaultSandbox();
      });
    }
  }

  void _autoCreateDefaultSandbox() {
    final projectId = widget.projectId ?? 'default';
    ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: 'python');
  }

  void _createSandbox(SandboxTemplate template) {
    final environment = template.id;
    final projectId = widget.projectId ?? 'default';
    ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: environment);
    setState(() => _showEnvPicker = false);
  }

  void _openEnvSelectorModal() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.75,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        builder: (context, scrollController) => ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: Container(
            color: AppColors.surface,
            child: EnvironmentPicker(
              onSelect: (template) {
                Navigator.pop(context);
                _createSandbox(template);
              },
            ),
          ),
        ),
      ),
    );
  }

  void _openFilesModal() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.85,
        minChildSize: 0.4,
        builder: (context, scrollController) => ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: Container(
            color: AppColors.surface,
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppColors.border,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    const Icon(Icons.folder_copy_rounded, color: AppColors.primary, size: 20),
                    const SizedBox(width: 10),
                    Text(
                      'Workspace Files Inspector',
                      style: AppTextStyles.headlineMd,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: SandboxFileBrowser(
                    files: const [
                      {'name': 'workspace', 'path': '/workspace', 'is_directory': true},
                      {'name': 'main.py', 'path': '/workspace/main.py', 'is_directory': false},
                      {'name': 'requirements.txt', 'path': '/workspace/requirements.txt', 'is_directory': false},
                      {'name': 'logs', 'path': '/workspace/logs', 'is_directory': true},
                    ],
                    onFileTap: (path) {
                      Navigator.pop(context);
                      ref.read(sandboxProvider.notifier).sendCommand('cat $path');
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);
    final activeSessions = state.activeSandboxes;
    final activeSession = state.activeSession;
    final envName = activeSession?.sandbox.environment.toUpperCase() ?? 'PYTHON 3.11';

    final isPickerActive = _showEnvPicker;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: RipTopBar(
        title: 'RIP Sandbox',
        subtitle: isPickerActive ? 'Select Runtime' : '$envName (${activeSessions.length} Active)',
        leadingIcon: const Icon(Icons.terminal_rounded, color: AppColors.primary),
        statusWidget: RipStatusBadge(
          label: activeSessions.isNotEmpty ? 'Running' : 'Offline',
          type: activeSessions.isNotEmpty ? RipStatusType.success : RipStatusType.neutral,
        ),
        actions: [
          if (!isPickerActive && activeSessions.isNotEmpty) ...[
            IconButton(
              icon: const Icon(Icons.add_box_rounded, color: AppColors.primary),
              tooltip: 'Create New Sandbox',
              onPressed: _openEnvSelectorModal,
            ),
            IconButton(
              icon: const Icon(Icons.folder_open_rounded, color: AppColors.textSecondary),
              tooltip: 'Files Inspector',
              onPressed: _openFilesModal,
            ),
          ],
        ],
      ),
      body: isPickerActive
          ? EnvironmentPicker(onSelect: _createSandbox)
          : state.isLoading && activeSessions.isEmpty
              ? Center(
                  child: RipCard(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const RipMascotWidget(
                          pose: RipMascotPose.loading,
                          width: 90,
                          height: 90,
                        ),
                        const SizedBox(height: 20),
                        const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                            valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
                            strokeWidth: 2.5,
                          ),
                        ),
                        const SizedBox(height: 20),
                        Text(
                          'Initializing Container Sandbox...',
                          style: AppTextStyles.headlineMd,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Allocating isolated runtime resources and streaming logs',
                          style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary),
                        ),
                      ],
                    ),
                  ),
                )
              : state.error != null && activeSessions.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: RipCard(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const RipMascotWidget(
                                pose: RipMascotPose.error,
                                width: 90,
                                height: 90,
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'Sandbox Setup Encountered Warning',
                                style: AppTextStyles.headlineMd,
                              ),
                              const SizedBox(height: 12),
                              Container(
                                width: double.infinity,
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: AppColors.codeBg,
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)),
                                ),
                                child: Text(
                                  state.error!,
                                  textAlign: TextAlign.center,
                                  style: AppTextStyles.codeSm.copyWith(color: AppColors.danger),
                                ),
                              ),
                              const SizedBox(height: 24),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  RipButton.primary(
                                    label: 'Auto-Initialize Sandbox',
                                    icon: const Icon(Icons.flash_on_rounded, size: 16),
                                    onPressed: _autoCreateDefaultSandbox,
                                  ),
                                  const SizedBox(width: 12),
                                  RipButton.secondary(
                                    label: 'Choose Env',
                                    icon: const Icon(Icons.tune_rounded, size: 16),
                                    onPressed: _openEnvSelectorModal,
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    )
                  : Column(
                      children: [
                        // Multi-Sandbox Switcher Tabs Bar
                        if (activeSessions.isNotEmpty)
                          _SandboxSessionSwitcherBar(
                            sessions: activeSessions,
                            activeId: state.activeSandboxId,
                            onSelectSession: (id) {
                              ref.read(sandboxProvider.notifier).switchActiveSandbox(id);
                            },
                            onCloseSession: (id) {
                              ref.read(sandboxProvider.notifier).closeSandbox(id);
                            },
                            onAddSession: _openEnvSelectorModal,
                          ),

                        // Sandbox Status Bar
                        if (state.sandbox != null)
                          SandboxStatusBar(
                            onChangeEnvTap: _openEnvSelectorModal,
                            onFilesTap: _openFilesModal,
                          ),

                        const Expanded(child: TerminalView()),
                      ],
                    ),
    );
  }
}

class _SandboxSessionSwitcherBar extends StatelessWidget {
  final List<SandboxSession> sessions;
  final String? activeId;
  final Function(String) onSelectSession;
  final Function(String) onCloseSession;
  final VoidCallback onAddSession;

  const _SandboxSessionSwitcherBar({
    required this.sessions,
    required this.activeId,
    required this.onSelectSession,
    required this.onCloseSession,
    required this.onAddSession,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        physics: const BouncingScrollPhysics(),
        child: Row(
          children: [
            ...sessions.map((session) {
              final isActive = session.sandbox.id == activeId;
              final envLabel = session.sandbox.environment.toUpperCase();

              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: () => onSelectSession(session.sandbox.id),
                    borderRadius: BorderRadius.circular(9999),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: isActive ? AppColors.primaryLight : AppColors.surface,
                        borderRadius: BorderRadius.circular(9999),
                        border: Border.all(
                          color: isActive ? AppColors.primary : AppColors.border,
                          width: isActive ? 1.5 : 1.0,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const RipStatusDot(type: RipStatusType.success, size: 6),
                          const SizedBox(width: 8),
                          Text(
                            envLabel,
                            style: AppTextStyles.bodyMdBold.copyWith(
                              fontSize: 12,
                              color: isActive ? AppColors.primary : AppColors.textPrimary,
                            ),
                          ),
                          const SizedBox(width: 6),
                          InkWell(
                            onTap: () => onCloseSession(session.sandbox.id),
                            borderRadius: BorderRadius.circular(9999),
                            child: Padding(
                              padding: const EdgeInsets.all(2),
                              child: Icon(
                                Icons.close_rounded,
                                size: 14,
                                color: isActive ? AppColors.primary : AppColors.textSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            }),

            // Add New Sandbox Session Button
            InkWell(
              onTap: onAddSession,
              borderRadius: BorderRadius.circular(9999),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(9999),
                  border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.add_rounded, color: AppColors.primary, size: 14),
                    const SizedBox(width: 4),
                    Text(
                      'New Sandbox',
                      style: AppTextStyles.bodyMdBold.copyWith(
                        fontSize: 12,
                        color: AppColors.primary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}