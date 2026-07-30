import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/utils/date_formatter.dart';
import 'package:rip_app/presentation/providers/auth_provider.dart';
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final themeMode = ref.watch(themeModeProvider);
    final chatSessionsAsync = ref.watch(chatSessionsProvider);
    final activeSessionId = ref.watch(activeChatSessionIdProvider);

    return Drawer(
      width: MediaQuery.sizeOf(context).width * 0.84,
      backgroundColor: bgColor,
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
              // 1. Header: Glassmorphic User Profile Header
              const _DrawerHeaderRow(),
              const SizedBox(height: 12),

              // 2. Compact Actions Row (New Chat, Add Repo, Projects)
              Row(
                children: [
                  Expanded(
                    child: _CompactAction(
                      icon: Icons.add_comment_rounded,
                      label: 'New Chat',
                      isDark: isDark,
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
                      isDark: isDark,
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
                      isDark: isDark,
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
              const SizedBox(height: 14),

              // 3. Scrollable Sidebar Navigation Sections
              Expanded(
                child: ListView(
                  physics: const BouncingScrollPhysics(),
                  padding: EdgeInsets.zero,
                  children: [
                    // Chats Section
                    chatSessionsAsync.when(
                      loading: () => const Padding(
                        padding: EdgeInsets.all(16.0),
                        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
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
                            title: 'CHATS',
                            isDark: isDark,
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(14),
                                child: Text(
                                  'No chats yet. Start a new chat!',
                                  style: AppTextStyles.bodySmMuted.copyWith(
                                    color: isDark ? Colors.white54 : AppColors.textSecondary,
                                  ),
                                ),
                              ),
                            ],
                          );
                        }
                        return _DrawerSection(
                          title: 'CHATS',
                          isDark: isDark,
                          children: [
                            for (int i = 0; i < chatSessions.length; i++) ...[
                              if (i > 0)
                                Divider(
                                  height: 1,
                                  color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06),
                                ),
                              _ChatSessionRow(
                                session: chatSessions[i],
                                isActive: chatSessions[i].id == activeSessionId,
                                isDark: isDark,
                                onTap: () async {
                                  HapticFeedback.selectionClick();
                                  await ref
                                      .read(chatSessionNotifierProvider.notifier)
                                      .selectChatSession(chatSessions[i].id);
                                  if (context.mounted) Navigator.pop(context);
                                },
                                onDelete: () async {
                                  HapticFeedback.mediumImpact();
                                  await ref
                                      .read(chatSessionNotifierProvider.notifier)
                                      .deleteChatSession(chatSessions[i].id);
                                },
                              ),
                            ],
                          ],
                        );
                      },
                    ),
                    const SizedBox(height: 16),

                    // Repository Tools Section (All 10 items preserved)
                    _DrawerSection(
                      title: 'REPOSITORY TOOLS',
                      isDark: isDark,
                      children: [
                        _CompactRow(
                          icon: Icons.smart_toy_rounded,
                          title: 'LLM Config',
                          subtitle: 'Configure AI models',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/llm-settings');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.roundabout_left,
                          title: 'Agent',
                          subtitle: 'Autonomous code editing',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/agent-runs');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.terminal_rounded,
                          title: 'Sandbox',
                          subtitle: 'Terminal and code execution',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/sandbox');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: AppIcons.workflows,
                          title: 'Workflows',
                          subtitle: 'Build and run block flows',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/workflows');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.route_rounded,
                          title: 'Activity',
                          subtitle: 'Sessions and conflicts',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/activity');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.hub_rounded,
                          title: 'Sources',
                          subtitle: 'RIP and external context',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/sources');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.policy_rounded,
                          title: 'Audit',
                          subtitle: 'Role-gated access decisions',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/audit');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.qr_code_rounded,
                          title: 'MCP Export',
                          subtitle: 'Copy agent config for IDEs',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/mcp-export');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.history_rounded,
                          title: 'Clear Query History',
                          subtitle: 'Reset current chat memory',
                          isDark: isDark,
                          onTap: () async {
                            HapticFeedback.mediumImpact();
                            await ref.read(chatProvider.notifier).clearChat();
                            if (context.mounted) Navigator.pop(context);
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.memory_rounded,
                          title: 'Index Context',
                          subtitle: 'Graph-backed workspace memory',
                          isDark: isDark,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Appearance Theme Segmented Switcher
                    _DrawerSection(
                      title: 'APPEARANCE & THEME',
                      isDark: isDark,
                      children: [
                        Padding(
                          padding: const EdgeInsets.all(12),
                          child: Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: _ThemeChipOption(
                                    label: 'System',
                                    isSelected: themeMode == ThemeMode.system,
                                    isDark: isDark,
                                    onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.system),
                                  ),
                                ),
                                Expanded(
                                  child: _ThemeChipOption(
                                    label: 'Light',
                                    isSelected: themeMode == ThemeMode.light,
                                    isDark: isDark,
                                    onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.light),
                                  ),
                                ),
                                Expanded(
                                  child: _ThemeChipOption(
                                    label: 'Dark',
                                    isSelected: themeMode == ThemeMode.dark,
                                    isDark: isDark,
                                    onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.dark),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Profile & Settings Section
                    _DrawerSection(
                      title: 'ACCOUNT & SYSTEM SETTINGS',
                      isDark: isDark,
                      children: [
                        _CompactRow(
                          icon: Icons.person_rounded,
                          title: 'User Profile & Telemetry',
                          subtitle: 'Identity, tokens and graph metrics',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/profile');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: AppIcons.settings,
                          title: 'Server Settings',
                          subtitle: 'Connection endpoint and API key',
                          isDark: isDark,
                          onTap: () {
                            HapticFeedback.selectionClick();
                            Navigator.pop(context);
                            context.push('/setup');
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.logout_rounded,
                          title: 'Sign Out Session',
                          subtitle: 'Logout active user session',
                          isDark: isDark,
                          onTap: () async {
                            HapticFeedback.mediumImpact();
                            Navigator.pop(context);
                            await ref.read(authNotifierProvider.notifier).logout();
                            if (context.mounted) {
                              context.go('/setup');
                            }
                          },
                        ),
                        Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                        _CompactRow(
                          icon: Icons.info_outline_rounded,
                          title: 'About RIP Platform',
                          subtitle: 'v1.4.0 • Repository Intelligence',
                          isDark: isDark,
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
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

/// Header containing User Profile Avatar and Identity details (Matching ProfileScreen design)
class _DrawerHeaderRow extends ConsumerWidget {
  const _DrawerHeaderRow();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final border = Border.all(color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06));

    final userAsync = ref.watch(userProfileFutureProvider);
    final currentUser = ref.watch(currentUserProvider);
    final user = currentUser ?? userAsync.asData?.value;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () {
          HapticFeedback.selectionClick();
          Navigator.pop(context);
          context.push('/profile');
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: cardBgColor,
            borderRadius: BorderRadius.circular(16),
            border: border,
          ),
          child: Row(
            children: [
              Stack(
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5),
                    backgroundImage: user?.avatarUrl != null ? NetworkImage(user!.avatarUrl!) : null,
                    child: user?.avatarUrl == null
                        ? Text(
                            user?.displayName.isNotEmpty == true ? user!.displayName[0].toUpperCase() : 'U',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: textColor),
                          )
                        : null,
                  ),
                  Positioned(
                    right: 0,
                    bottom: 0,
                    child: Container(
                      width: 9,
                      height: 9,
                      decoration: BoxDecoration(
                        color: const Color(0xFF22C55E),
                        shape: BoxShape.circle,
                        border: Border.all(color: cardBgColor, width: 1.5),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      user?.displayName ?? 'pratiksingh1702',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: textColor,
                        letterSpacing: -0.2,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      user?.email ?? 'pratiksingh59165@gmail.com',
                      style: TextStyle(fontSize: 11, color: mutedTextColor),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: isDark ? Colors.white38 : AppColors.textSecondary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompactAction extends StatelessWidget {
  const _CompactAction({
    required this.icon,
    required this.label,
    required this.isDark,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final iconColor = isDark ? Colors.white70 : AppColors.primary;
    final border = Border.all(color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06));

    return Material(
      color: cardBgColor,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: border,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: iconColor, size: 16),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                    color: textColor,
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
  const _DrawerSection({
    required this.title,
    required this.isDark,
    required this.children,
  });

  final String title;
  final bool isDark;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final border = Border.all(color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 6),
          child: Text(
            title.toUpperCase(),
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w800,
              color: isDark ? Colors.white38 : AppColors.textSecondary,
              letterSpacing: 0.8,
            ),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: cardBgColor,
            borderRadius: BorderRadius.circular(16),
            border: border,
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
    required this.isDark,
    required this.onTap,
    required this.onDelete,
  });

  final dynamic session;
  final bool isActive;
  final bool isDark;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final activeBg = isDark ? const Color(0xFF22222E) : AppColors.primaryLight;
    final activeTextColor = isDark ? Colors.white : AppColors.primary;
    final normalTextColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Material(
      color: isActive ? activeBg : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(
                isActive ? Icons.chat_bubble_rounded : Icons.chat_bubble_outline_rounded,
                color: isActive
                    ? (isDark ? Colors.white : AppColors.primary)
                    : (isDark ? Colors.white54 : AppColors.textSecondary),
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
                      style: TextStyle(
                        color: isActive ? activeTextColor : normalTextColor,
                        fontWeight: isActive ? FontWeight.bold : FontWeight.w600,
                        fontSize: 12.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      DateFormatter.formatTime(session.updatedAt),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 10, color: mutedTextColor),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                color: isDark ? Colors.redAccent.shade100 : AppColors.error,
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
    required this.isDark,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool isDark;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final titleColor = isDark ? Colors.white : AppColors.textPrimary;
    final subtitleColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final iconColor = isDark ? Colors.white70 : Colors.black87;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              Icon(icon, color: iconColor, size: 17),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12.5,
                        color: titleColor,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 10.5, color: subtitleColor),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right_rounded,
                size: 16,
                color: isDark ? Colors.white24 : Colors.black26,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ThemeChipOption extends StatelessWidget {
  const _ThemeChipOption({
    required this.label,
    required this.isSelected,
    required this.isDark,
    required this.onTap,
  });

  final String label;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(vertical: 7),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: isSelected
              ? (isDark ? Colors.white24 : Colors.white)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(9),
          boxShadow: isSelected
              ? [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 4)]
              : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11.5,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
            color: isSelected
                ? (isDark ? Colors.white : AppColors.textPrimary)
                : (isDark ? Colors.white54 : AppColors.textSecondary),
          ),
        ),
      ),
    );
  }
}
