import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/utils/date_formatter.dart';
import 'package:rip_app/presentation/providers/chat_provider.dart';
import 'package:rip_app/presentation/providers/project_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';
import 'package:rip_app/presentation/providers/chat_session_provider.dart';
import 'package:rip_app/presentation/widgets/overlays/add_repo_sheet.dart';
import 'package:rip_app/presentation/widgets/sidebar/project_list.dart';

class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final chatSessionsAsync = ref.watch(chatSessionsProvider);
    final activeSessionId = ref.watch(activeChatSessionIdProvider);

    return Drawer(
      width: MediaQuery.sizeOf(context).width * 0.84,
      backgroundColor: AppColors.background,
      elevation: 0,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.only(
          topRight: Radius.circular(24),
          bottomRight: Radius.circular(24),
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
          child: Column(
            children: [
              // 1. Header: Mascot and Greet text in Row
              const _DrawerHeaderRow(),
              const SizedBox(height: 12),

              // 2. Compact Actions Row (New Chat, Add Repo, Projects)
              Row(
                children: [
                  Expanded(
                    child: _CompactAction(
                      icon: Icons.add_comment_rounded,
                      label: 'New Chat',
                      onTap: () async {
                        HapticFeedback.selectionClick();
                        final activeProjectId = ref.read(activeProjectIdProvider);
                        await ref.read(chatSessionNotifierProvider.notifier).createNewChat(
                              projectId: activeProjectId,
                            );
                        if (context.mounted) Navigator.pop(context);
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _CompactAction(
                      icon: AppIcons.add,
                      label: 'Add repo',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        showModalBottomSheet(
                          context: context,
                          isScrollControlled: true,
                          backgroundColor: Colors.transparent,
                          builder: (context) => const AddRepoSheet(),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _CompactAction(
                      icon: Icons.folder_open_rounded,
                      label: 'Projects',
                      onTap: () {
                        HapticFeedback.selectionClick();
                        ref.invalidate(projectListProvider);
                        showDialog(
                          context: context,
                          builder: (context) => const Dialog(
                            backgroundColor: Colors.transparent,
                            insetPadding: EdgeInsets.all(18),
                            child: SizedBox(height: 440, child: ProjectList()),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // 3. Scrollable Sidebar Navigation Sections
              Expanded(
                child: ListView(
                  padding: EdgeInsets.zero,
                  children: [
                    // Chats Section
                    chatSessionsAsync.when(
                      loading: () => const Padding(
                        padding: EdgeInsets.all(16.0),
                        child: Center(child: CircularProgressIndicator()),
                      ),
                      error: (err, stack) => Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Text(
                          'Error loading chats: $err',
                          style: AppTextStyles.bodySmMuted.copyWith(color: AppColors.error),
                        ),
                      ),
                      data: (chatSessions) {
                        if (chatSessions.isEmpty) {
                          return _DrawerSection(
                            title: 'Chats',
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(14),
                                child: Text(
                                  'No chats yet. Start a new chat!',
                                  style: AppTextStyles.bodySmMuted,
                                ),
                              ),

                            ],
                          );

                        }
                        return _DrawerSection(
                          title: 'Chats',
                          children: [
                            for (final session in chatSessions)
                              _ChatSessionRow(
                                session: session,
                                isActive: session.id == activeSessionId,
                                onTap: () async {
                                  HapticFeedback.selectionClick();
                                  await ref
                                      .read(chatSessionNotifierProvider.notifier)
                                      .selectChatSession(session.id);
                                  if (context.mounted) Navigator.pop(context);
                                },
                                onDelete: () async {
                                  HapticFeedback.mediumImpact();
                                  await ref
                                      .read(chatSessionNotifierProvider.notifier)
                                      .deleteChatSession(session.id);
                                },
                              ),
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: 12),

                    // Repository Tools Section (All 10 items preserved)
                    _DrawerSection(
                      title: 'Repository Tools',
                      children: [
                        _CompactRow(
                          icon: Icons.smart_toy_rounded,
                          title: 'LLM Config',
                          subtitle: 'Configure AI models',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/llm-settings');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.roundabout_left,
                          title: 'Agent',
                          subtitle: 'Autonomous code editing',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/agent-runs');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.terminal_rounded,
                          title: 'Sandbox',
                          subtitle: 'Terminal and code execution',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/sandbox');
                          },
                        ),
                        _CompactRow(
                          icon: AppIcons.workflows,
                          title: 'Workflows',
                          subtitle: 'Build and run block flows',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/workflows');
                          },
                        ),

                        _CompactRow(
                          icon: Icons.route_rounded,
                          title: 'Activity',
                          subtitle: 'Sessions and conflicts',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/activity');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.hub_rounded,
                          title: 'Sources',
                          subtitle: 'RIP and external context',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/sources');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.policy_rounded,
                          title: 'Audit',
                          subtitle: 'Role-gated access decisions',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/audit');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.qr_code_rounded,
                          title: 'MCP export',
                          subtitle: 'Copy agent config',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/mcp-export');
                          },
                        ),
                        _CompactRow(
                          icon: Icons.history_rounded,
                          title: 'Clear query history',
                          subtitle: 'Reset current chat',
                          onTap: () async {
                            HapticFeedback.mediumImpact();
                            await ref.read(chatProvider.notifier).clearChat();
                            if (context.mounted) Navigator.pop(context);
                          },
                        ),
                        const _CompactRow(
                          icon: Icons.memory_rounded,
                          title: 'Index context',
                          subtitle: 'Graph-backed workspace memory',
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Theme Section
                    _DrawerSection(
                      title: 'Theme',
                      children: [
                        _ThemeRow(
                          label: 'Light',
                          selected: themeMode == ThemeMode.light,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.light),
                        ),
                        _ThemeRow(
                          label: 'Dark',
                          selected: themeMode == ThemeMode.dark,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.dark),
                        ),
                        _ThemeRow(
                          label: 'System',
                          selected: themeMode == ThemeMode.system,
                          onTap: () => ref
                              .read(settingsNotifierProvider.notifier)
                              .saveThemeMode(ThemeMode.system),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Settings Section
                    _DrawerSection(
                      title: 'Settings',
                      children: [
                        _CompactRow(
                          icon: AppIcons.settings,
                          title: 'Server settings',
                          subtitle: 'Connection and API key',
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/setup');
                          },
                        ),
                        const _CompactRow(
                          icon: Icons.info_outline_rounded,
                          title: 'About RIP',
                          subtitle: 'Repository intelligence',
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Header containing Mascot in a Row with greeting text
class _DrawerHeaderRow extends StatelessWidget {
  const _DrawerHeaderRow();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          const RipMascotWidget(
            pose: RipMascotPose.waving,
            width: 48,
            height: 48,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Welcome to RIP',
                  style: AppTextStyles.bodyMdBold.copyWith(
                    fontSize: 16,
                    color: AppColors.textPrimary,
                  ),
                ),

                const SizedBox(height: 2),
                Text(
                  'Repository Intelligence',
                  style: AppTextStyles.bodySmMuted.copyWith(fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactAction extends StatelessWidget {
  const _CompactAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: AppColors.primary, size: 16),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.bodySm.copyWith(
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DrawerSection extends StatelessWidget {
  const _DrawerSection({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 6),
          child: Text(
            title.toUpperCase(),
            style: AppTextStyles.bodySmMuted.copyWith(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
            ),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(children: children),
        ),
      ],
    );
  }
}

class _ChatSessionRow extends StatelessWidget {
  const _ChatSessionRow({
    required this.session,
    required this.isActive,
    required this.onTap,
    required this.onDelete,
  });

  final dynamic session;
  final bool isActive;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: isActive ? AppColors.primaryLight : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(
                isActive ? Icons.chat_bubble : Icons.chat_bubble_outline_rounded,
                color: isActive ? AppColors.primary : AppColors.textSecondary,
                size: 16,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      session.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySm.copyWith(
                        color: isActive ? AppColors.primary : AppColors.textPrimary,
                        fontWeight: isActive ? FontWeight.w700 : FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      DateFormatter.formatTime(session.updatedAt),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySmMuted.copyWith(fontSize: 10),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                color: AppColors.error,
                onPressed: onDelete,
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompactRow extends StatelessWidget {
  const _CompactRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          child: Row(
            children: [
              Icon(icon, color: AppColors.textSecondary, size: 17),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySm.copyWith(
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySmMuted.copyWith(fontSize: 10),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ThemeRow extends StatelessWidget {
  const _ThemeRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return _CompactRow(
      icon: selected ? Icons.radio_button_checked : Icons.radio_button_off,
      title: label,
      subtitle: selected ? 'Selected' : 'Theme mode',
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
    );
  }
}
